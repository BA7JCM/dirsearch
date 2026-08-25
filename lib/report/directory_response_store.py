# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import os
import tempfile
from urllib.parse import urlparse

from lib.core.settings import MAX_RESPONSE_FILENAME_LENGTH
from lib.report.response_store import ResponseArtifact, ResponseStore
from lib.utils.common import get_valid_filename


def _truncate_filename(value: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    return value.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")


def response_filename(
    url: str,
    status: int,
    max_length: int = MAX_RESPONSE_FILENAME_LENGTH,
) -> str:
    """Build a portable filename without exposing the raw query string."""
    parsed = urlparse(url)
    host = parsed.hostname or "response"
    if parsed.port is not None:
        host = f"{host}_{parsed.port}"

    name = get_valid_filename(f"{host}{parsed.path}")
    if parsed.query:
        query_hash = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:12]
        name = f"{name}_query-{query_hash}"

    name = name.strip(" ._") or "response"
    suffix = f"_{status}"
    return f"{_truncate_filename(name, max_length - len(suffix))}{suffix}"


def _exclusive_open(file_path: str) -> int:
    if os.name == "nt":
        return _exclusive_open_windows(file_path)

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(file_path, flags, 0o600)


def _exclusive_open_windows(file_path: str) -> int:
    """Create a Windows file without following an existing reparse point."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    generic_write = 0x40000000
    create_new = 1
    file_attribute_normal = 0x00000080
    file_flag_open_reparse_point = 0x00200000
    invalid_handle = ctypes.c_void_p(-1).value
    absolute_path = os.path.abspath(file_path)
    if not absolute_path.startswith("\\\\?\\"):
        if absolute_path.startswith("\\\\"):
            absolute_path = "\\\\?\\UNC\\" + absolute_path[2:]
        else:
            absolute_path = "\\\\?\\" + absolute_path

    handle = create_file(
        absolute_path,
        generic_write,
        0,
        None,
        create_new,
        file_attribute_normal | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle:
        error_code = ctypes.get_last_error()
        if error_code in (80, 183):
            raise FileExistsError(error_code, "File already exists", file_path)
        raise OSError(error_code, ctypes.FormatError(error_code), file_path)

    try:
        return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    except Exception:
        close_handle(handle)
        raise


class DirectoryResponseStore(ResponseStore):
    """Save one raw response body per exclusively created file."""

    name = "directory"

    def __init__(self, directory: str) -> None:
        super().__init__(directory)
        os.makedirs(self.destination, exist_ok=True)
        if not os.path.isdir(self.destination):
            raise NotADirectoryError(f"Not a directory: {self.destination}")

        descriptor, probe_path = tempfile.mkstemp(
            prefix=".dirsearch-write-test-",
            dir=self.destination,
        )
        os.close(descriptor)
        os.unlink(probe_path)

    def save(self, artifact: ResponseArtifact) -> str:
        base_name = response_filename(artifact.url, artifact.status)
        file_path, descriptor = self._claim_file(base_name)
        completed = False

        try:
            with os.fdopen(descriptor, "wb") as file_handle:
                descriptor = -1
                file_handle.write(artifact.body)
            completed = True
            return file_path
        finally:
            if descriptor != -1:
                os.close(descriptor)
            if not completed:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def _claim_file(self, base_name: str) -> tuple[str, int]:
        counter = 0

        while True:
            collision_suffix = "" if counter == 0 else f"_{counter}"
            candidate_name = (
                f"{_truncate_filename(base_name, MAX_RESPONSE_FILENAME_LENGTH - len(collision_suffix))}"
                f"{collision_suffix}"
            )
            file_path = os.path.join(self.destination, candidate_name)
            try:
                descriptor = _exclusive_open(file_path)
            except FileExistsError:
                counter += 1
                continue
            return file_path, descriptor
