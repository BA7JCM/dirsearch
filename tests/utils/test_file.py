# -*- coding: utf-8 -*-

import os
import tempfile
from unittest import TestCase, skipUnless
from unittest.mock import patch

from lib.utils.file import FileUtils


class TestFileUtils(TestCase):
    def test_create_writable_dir_creates_and_validates_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = FileUtils.build_path(directory, "responses")

            FileUtils.create_writable_dir(destination)

            self.assertTrue(FileUtils.is_dir(destination))
            self.assertEqual(os.listdir(destination), [])

    def test_create_writable_dir_rejects_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = FileUtils.build_path(directory, "responses")
            with open(destination, "wb"):
                pass

            with self.assertRaises((FileExistsError, NotADirectoryError)):
                FileUtils.create_writable_dir(destination)

    def test_create_writable_dir_propagates_probe_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "lib.utils.file.tempfile.mkstemp",
                side_effect=PermissionError("read-only"),
            ):
                with self.assertRaisesRegex(PermissionError, "read-only"):
                    FileUtils.create_writable_dir(directory)

    def test_open_exclusive_never_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            file_name = FileUtils.build_path(directory, "response")
            descriptor = FileUtils.open_exclusive(file_name)
            with os.fdopen(descriptor, "wb") as file_handle:
                file_handle.write(b"original")

            with self.assertRaises(FileExistsError):
                FileUtils.open_exclusive(file_name)

            self.assertEqual(FileUtils.read_bytes(file_name), b"original")

    def test_open_binary_append_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            file_name = FileUtils.build_path(directory, "responses.jsonl")
            for body in (b"first", b"second"):
                descriptor = FileUtils.open_binary_append(file_name)
                with os.fdopen(descriptor, "ab", buffering=0) as file_handle:
                    file_handle.write(body)

            self.assertEqual(FileUtils.read_bytes(file_name), b"firstsecond")

    @skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_open_binary_append_does_not_follow_symbolic_link(self):
        with tempfile.TemporaryDirectory() as directory:
            file_name = FileUtils.build_path(directory, "responses.jsonl")
            outside = FileUtils.build_path(directory, "outside.jsonl")
            try:
                os.symlink(outside, file_name)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symbolic links are unavailable: {error}")

            with self.assertRaises(OSError):
                FileUtils.open_binary_append(file_name)

            self.assertFalse(FileUtils.exists(outside))
