# -*- coding: utf-8 -*-

import asyncio
import os
import queue
import tempfile
import threading
from unittest import IsolatedAsyncioTestCase, TestCase, skipUnless
from unittest.mock import patch

from lib.connection.response import NativeResponse
from lib.controller.controller import Controller
from lib.report.response_saver import ResponseSaver, response_filename


def make_response(
    url: str = "https://example.com/admin",
    body: bytes = b"response body",
) -> NativeResponse:
    return NativeResponse(url, 200, [("Content-Type", "application/octet-stream")], body)


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


class TestResponseSaver(TestCase):
    def test_saves_exact_bytes_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            saver = ResponseSaver(directory)
            response = make_response(body=b"\x00binary\xffbody")

            first = saver.save(response)
            second = saver.save(response)

            self.assertNotEqual(first, second)
            self.assertTrue(second.endswith("_1"))
            self.assertLessEqual(len(os.path.basename(second).encode("utf-8")), 200)
            with open(first, "rb") as file_handle:
                self.assertEqual(file_handle.read(), response.body)
            with open(second, "rb") as file_handle:
                self.assertEqual(file_handle.read(), response.body)

    def test_existing_regular_file_is_rejected_as_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "responses")
            with open(file_path, "wb") as file_handle:
                file_handle.write(b"existing")

            with self.assertRaises((FileExistsError, NotADirectoryError)):
                ResponseSaver(file_path)

    def test_preflight_write_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "lib.report.response_saver.tempfile.mkstemp",
                side_effect=PermissionError("read-only"),
            ):
                with self.assertRaisesRegex(PermissionError, "read-only"):
                    ResponseSaver(directory)

    @skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_dangling_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            saver = ResponseSaver(directory)
            response = make_response()
            base_path = os.path.join(
                directory,
                response_filename(response.url, response.status),
            )
            outside_path = os.path.join(directory, "outside-response")
            try:
                os.symlink(outside_path, base_path)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            saved_path = saver.save(response)

            self.assertTrue(os.path.islink(base_path))
            self.assertFalse(os.path.exists(outside_path))
            self.assertEqual(saved_path, f"{base_path}_1")

    def test_concurrent_saves_allocate_unique_files_without_a_global_lock(self):
        worker_count = 16
        with tempfile.TemporaryDirectory() as directory:
            saver = ResponseSaver(directory)
            response = make_response(body=b"same body")
            barrier = threading.Barrier(worker_count + 1)
            results = queue.Queue()

            def save() -> None:
                barrier.wait()
                try:
                    results.put((saver.save(response), None))
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
                    self.assertEqual(file_handle.read(), response.body)

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
            saver = ResponseSaver(directory)
            real_fdopen = os.fdopen

            with patch(
                "lib.report.response_saver.os.fdopen",
                side_effect=lambda descriptor, mode: FailingFile(
                    real_fdopen(descriptor, mode)
                ),
            ):
                with self.assertRaisesRegex(OSError, "disk full"):
                    saver.save(make_response())

            self.assertEqual(os.listdir(directory), [])

    def test_controller_reports_save_failure_without_deadlocking(self):
        class FailingSaver:
            def save(self, response):
                raise OSError("disk full")

        controller = object.__new__(Controller)
        controller.response_saver = FailingSaver()

        with patch("lib.controller.controller.logger.exception"), patch(
            "lib.controller.controller.interface.error"
        ) as report_error:
            controller.save_response(make_response())

        report_error.assert_called_once()


class TestAsyncResponseSaver(IsolatedAsyncioTestCase):
    async def test_controller_offloads_and_awaits_save(self):
        started = threading.Event()
        release = threading.Event()

        class BlockingSaver:
            def save(self, response):
                started.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("test did not release saver")

        controller = object.__new__(Controller)
        controller.response_saver = BlockingSaver()
        task = asyncio.create_task(controller.save_response_async(make_response()))

        self.assertTrue(await asyncio.to_thread(started.wait, 2))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        release.set()
        await asyncio.wait_for(task, timeout=2)
