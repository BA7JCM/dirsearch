# -*- coding: utf-8 -*-

import asyncio
import base64
import json
import os
import queue
import tempfile
import threading
from unittest import IsolatedAsyncioTestCase, TestCase, skipUnless
from unittest.mock import patch

from lib.connection.response import NativeResponse
from lib.controller.controller import Controller
from lib.report.directory_response_store import (
    DirectoryResponseStore,
    response_filename,
)
from lib.report.jsonl_response_store import (
    JSONL_RESPONSE_SCHEMA,
    JsonlResponseStore,
)
from lib.report.response_store import (
    ResponseArtifact,
    ResponseStore,
    create_response_stores,
)


def make_response(
    url: str = "https://example.com/admin",
    body: bytes = b"response body",
) -> NativeResponse:
    return NativeResponse(
        url,
        200,
        [
            ("Content-Type", "application/octet-stream"),
            ("X-Response-Id", "test-response"),
        ],
        body,
        elapsed=0.125,
    )


def make_artifact(
    url: str = "https://example.com/admin",
    body: bytes = b"response body",
) -> ResponseArtifact:
    return ResponseArtifact.from_response(make_response(url, body))


def read_jsonl(file_path: str) -> list[dict]:
    with open(file_path, encoding="utf-8") as file_handle:
        return [json.loads(line) for line in file_handle]


class TestResponseArtifact(TestCase):
    def test_copies_backend_neutral_response_data(self):
        artifact = make_artifact(body=b"\x00binary\xffbody")

        self.assertEqual(artifact.url, "https://example.com/admin")
        self.assertEqual(artifact.status, 200)
        self.assertEqual(artifact.content_length, len(artifact.body))
        self.assertEqual(artifact.content_type, "application/octet-stream")
        self.assertEqual(artifact.elapsed, 0.125)
        self.assertEqual(dict(artifact.headers)["x-response-id"], "test-response")


class TestResponseFilename(TestCase):
    def test_filename_is_portable_and_bounded(self):
        filename = response_filename(
            f"https://example.com:8443/{'a' * 500}",
            200,
        )

        self.assertLessEqual(len(filename), 200)
        self.assertTrue(filename.startswith("example.com_8443_"))
        self.assertTrue(filename.endswith("_200"))
        self.assertNotIn("/", filename)

        unicode_filename = response_filename(
            f"https://example.com/{'测试' * 200}",
            200,
        )
        self.assertLessEqual(len(unicode_filename.encode("utf-8")), 200)

    def test_query_values_are_replaced_by_a_stable_hash(self):
        url = "https://example.com/admin?token=super-secret&user=mauro"

        first = response_filename(url, 200)
        second = response_filename(url, 200)

        self.assertEqual(first, second)
        self.assertIn("_query-", first)
        self.assertNotIn("super-secret", first)
        self.assertNotIn("mauro", first)


class TestDirectoryResponseStore(TestCase):
    def test_saves_exact_bytes_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DirectoryResponseStore(directory)
            artifact = make_artifact(body=b"\x00binary\xffbody")

            first = store.save(artifact)
            second = store.save(artifact)

            self.assertNotEqual(first, second)
            self.assertTrue(second.endswith("_1"))
            self.assertLessEqual(len(os.path.basename(second).encode("utf-8")), 200)
            with open(first, "rb") as file_handle:
                self.assertEqual(file_handle.read(), artifact.body)
            with open(second, "rb") as file_handle:
                self.assertEqual(file_handle.read(), artifact.body)

    def test_existing_regular_file_is_rejected_as_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses")
            with open(file_path, "wb") as file_handle:
                file_handle.write(b"existing")

            with self.assertRaises((FileExistsError, NotADirectoryError)):
                DirectoryResponseStore(file_path)

    def test_preflight_write_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "lib.report.directory_response_store.tempfile.mkstemp",
                side_effect=PermissionError("read-only"),
            ):
                with self.assertRaisesRegex(PermissionError, "read-only"):
                    DirectoryResponseStore(directory)

    @skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_dangling_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DirectoryResponseStore(directory)
            artifact = make_artifact()
            base_path = os.path.join(
                directory,
                response_filename(artifact.url, artifact.status),
            )
            outside_path = os.path.join(directory, "outside-response")
            try:
                os.symlink(outside_path, base_path)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            saved_path = store.save(artifact)

            self.assertTrue(os.path.islink(base_path))
            self.assertFalse(os.path.exists(outside_path))
            self.assertEqual(saved_path, f"{base_path}_1")

    def test_concurrent_saves_allocate_unique_files(self):
        worker_count = 16
        with tempfile.TemporaryDirectory() as directory:
            store = DirectoryResponseStore(directory)
            artifact = make_artifact(body=b"same body")
            barrier = threading.Barrier(worker_count + 1)
            results = queue.Queue()

            def save() -> None:
                barrier.wait()
                try:
                    results.put((store.save(artifact), None))
                except Exception as error:
                    results.put((None, error))

            threads = [threading.Thread(target=save) for _ in range(worker_count)]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            saved = [results.get_nowait() for _ in range(worker_count)]
            self.assertTrue(all(error is None for _, error in saved))
            paths = [path for path, _ in saved]
            self.assertEqual(len(set(paths)), worker_count)
            self.assertEqual(len(os.listdir(directory)), worker_count)
            for path in paths:
                with open(path, "rb") as file_handle:
                    self.assertEqual(file_handle.read(), artifact.body)

    def test_failed_write_removes_the_partial_file(self):
        class FailingFile:
            def __init__(self, file_handle):
                self.file_handle = file_handle

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.file_handle.close()

            def write(self, body):
                self.file_handle.write(body[:2])
                raise OSError("disk full")

        with tempfile.TemporaryDirectory() as directory:
            store = DirectoryResponseStore(directory)
            real_fdopen = os.fdopen

            with patch(
                "lib.report.directory_response_store.os.fdopen",
                side_effect=lambda descriptor, mode: FailingFile(
                    real_fdopen(descriptor, mode)
                ),
            ):
                with self.assertRaisesRegex(OSError, "disk full"):
                    store.save(make_artifact())

            self.assertEqual(os.listdir(directory), [])


class TestJsonlResponseStore(TestCase):
    def test_writes_one_versioned_binary_safe_record(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses.jsonl")
            store = JsonlResponseStore(file_path)
            artifact = make_artifact(body=b"\x00binary\xffbody")

            result = store.save(artifact)
            store.close()

            self.assertEqual(result, os.path.abspath(file_path))
            records = read_jsonl(file_path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["schema"], JSONL_RESPONSE_SCHEMA)
            self.assertEqual(records[0]["bodyEncoding"], "base64")
            self.assertEqual(records[0]["capturedBodyLength"], len(artifact.body))
            self.assertEqual(records[0]["url"], artifact.url)
            self.assertEqual(records[0]["status"], artifact.status)
            self.assertEqual(
                base64.b64decode(records[0]["body"]),
                artifact.body,
            )

    def test_appends_after_existing_record_without_final_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses.jsonl")
            first = JsonlResponseStore(file_path)
            first.save(make_artifact(url="https://example.com/first"))
            first.close()
            with open(file_path, "rb+") as file_handle:
                file_handle.seek(-1, os.SEEK_END)
                file_handle.truncate()

            second = JsonlResponseStore(file_path)
            second.save(make_artifact(url="https://example.com/second"))
            second.close()

            self.assertEqual(
                [record["url"] for record in read_jsonl(file_path)],
                ["https://example.com/first", "https://example.com/second"],
            )

    def test_rejects_incompatible_existing_jsonl_without_modifying_it(self):
        for content in (
            b"not json\n",
            b'{"schema":"another.schema"}\n',
            b'{"schema":"dirsearch.response.v1"}\n\n',
        ):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                file_path = os.path.join(directory, "responses.jsonl")
                with open(file_path, "wb") as file_handle:
                    file_handle.write(content)

                with self.assertRaises(ValueError):
                    JsonlResponseStore(file_path)

                with open(file_path, "rb") as file_handle:
                    self.assertEqual(file_handle.read(), content)

    def test_existing_directory_is_rejected_as_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(IsADirectoryError):
                JsonlResponseStore(directory)

    @skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symbolic_link_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses.jsonl")
            outside_path = os.path.join(directory, "outside.jsonl")
            try:
                os.symlink(outside_path, file_path)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            with self.assertRaises(OSError):
                JsonlResponseStore(file_path)

            self.assertTrue(os.path.islink(file_path))
            self.assertFalse(os.path.exists(outside_path))

    def test_concurrent_saves_produce_complete_independent_lines(self):
        worker_count = 16
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses.jsonl")
            store = JsonlResponseStore(file_path)
            artifacts = [
                make_artifact(
                    url=f"https://example.com/{index}",
                    body=bytes([index]) * 65536,
                )
                for index in range(worker_count)
            ]
            barrier = threading.Barrier(worker_count + 1)
            errors = queue.Queue()

            def save(artifact: ResponseArtifact) -> None:
                barrier.wait()
                try:
                    store.save(artifact)
                except Exception as error:
                    errors.put(error)

            threads = [
                threading.Thread(target=save, args=(artifact,))
                for artifact in artifacts
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5)
            store.close()

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertTrue(errors.empty())
            records = read_jsonl(file_path)
            self.assertEqual(len(records), worker_count)
            self.assertEqual(
                {record["url"] for record in records},
                {artifact.url for artifact in artifacts},
            )
            bodies = {
                record["url"]: base64.b64decode(record["body"])
                for record in records
            }
            self.assertEqual(
                bodies,
                {artifact.url: artifact.body for artifact in artifacts},
            )

    def test_failed_write_rolls_back_partial_record(self):
        class FailingFile:
            def __init__(self, file_handle):
                self.file_handle = file_handle

            def fileno(self):
                return self.file_handle.fileno()

            def write(self, data):
                self.file_handle.write(data[:5])
                raise OSError("disk full")

            def flush(self):
                self.file_handle.flush()

            def close(self):
                self.file_handle.close()

        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses.jsonl")
            store = JsonlResponseStore(file_path)
            store._file = FailingFile(store._file)

            with self.assertRaisesRegex(OSError, "disk full"):
                store.save(make_artifact())
            store.close()

            self.assertEqual(os.path.getsize(file_path), 0)

    def test_close_is_idempotent_and_prevents_late_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonlResponseStore(os.path.join(directory, "responses.jsonl"))
            store.close()
            store.close()

            with self.assertRaisesRegex(OSError, "closed"):
                store.save(make_artifact())


class TestResponseStoreFactory(TestCase):
    def test_builds_both_configured_store_types(self):
        with tempfile.TemporaryDirectory() as directory:
            stores = create_response_stores(
                os.path.join(directory, "responses"),
                os.path.join(directory, "responses.jsonl"),
            )
            try:
                self.assertEqual(
                    [type(store) for store in stores],
                    [DirectoryResponseStore, JsonlResponseStore],
                )
            finally:
                for store in stores:
                    store.close()

    def test_controller_writes_to_both_configured_stores(self):
        with tempfile.TemporaryDirectory() as directory:
            response_directory = os.path.join(directory, "responses")
            jsonl_file = os.path.join(directory, "responses.jsonl")
            controller = object.__new__(Controller)
            controller.response_stores = create_response_stores(
                response_directory,
                jsonl_file,
            )

            controller.save_response(make_response(body=b"\x00both stores"))
            controller._close_response_stores()

            raw_files = os.listdir(response_directory)
            self.assertEqual(len(raw_files), 1)
            with open(os.path.join(response_directory, raw_files[0]), "rb") as handle:
                self.assertEqual(handle.read(), b"\x00both stores")
            records = read_jsonl(jsonl_file)
            self.assertEqual(len(records), 1)
            self.assertEqual(base64.b64decode(records[0]["body"]), b"\x00both stores")


class TestControllerResponseStores(TestCase):
    def test_initialization_closes_store_when_setup_fails(self):
        class RecordingCloseStore(ResponseStore):
            def __init__(self):
                super().__init__("memory")
                self.closed = False

            def save(self, artifact):
                return self.destination

            def close(self):
                self.closed = True

        store = RecordingCloseStore()

        def failing_setup(controller):
            controller.response_stores = (store,)
            raise RuntimeError("setup failed")

        with patch.dict("lib.controller.controller.options", {"session_file": None}):
            with patch.object(Controller, "setup", failing_setup):
                with self.assertRaisesRegex(RuntimeError, "setup failed"):
                    Controller()

        self.assertTrue(store.closed)

    def test_failure_in_one_store_does_not_skip_the_next_store(self):
        class FailingStore(ResponseStore):
            name = "failing"

            def save(self, artifact):
                raise OSError("disk full")

        class RecordingStore(ResponseStore):
            name = "recording"

            def __init__(self):
                super().__init__("memory")
                self.artifacts = []

            def save(self, artifact):
                self.artifacts.append(artifact)
                return self.destination

        failing = FailingStore("failure")
        recording = RecordingStore()
        controller = object.__new__(Controller)
        controller.response_stores = (failing, recording)

        with patch("lib.controller.controller.logger.exception"), patch(
            "lib.controller.controller.interface.error"
        ) as report_error:
            controller.save_response(make_response())

        report_error.assert_called_once()
        self.assertEqual(len(recording.artifacts), 1)

    def test_close_failure_does_not_skip_remaining_stores(self):
        class FailingCloseStore(ResponseStore):
            name = "failing"

            def save(self, artifact):
                return self.destination

            def close(self):
                raise OSError("close failed")

        class RecordingCloseStore(ResponseStore):
            def __init__(self):
                super().__init__("memory")
                self.closed = False

            def save(self, artifact):
                return self.destination

            def close(self):
                self.closed = True

        recording = RecordingCloseStore()
        controller = object.__new__(Controller)
        controller.response_stores = (FailingCloseStore("failure"), recording)

        with patch("lib.controller.controller.logger.exception"), patch(
            "lib.controller.controller.interface.error"
        ) as report_error:
            controller._close_response_stores()

        report_error.assert_called_once()
        self.assertTrue(recording.closed)


class TestAsyncResponseStores(IsolatedAsyncioTestCase):
    async def test_controller_offloads_and_awaits_store(self):
        started = threading.Event()
        release = threading.Event()

        class BlockingStore(ResponseStore):
            def save(self, artifact):
                started.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("test did not release store")
                return self.destination

        controller = object.__new__(Controller)
        controller.response_stores = (BlockingStore("memory"),)
        task = asyncio.create_task(controller.save_response_async(make_response()))

        self.assertTrue(await asyncio.to_thread(started.wait, 2))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        release.set()
        await asyncio.wait_for(task, timeout=2)
