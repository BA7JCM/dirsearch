# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import os
import tempfile
from urllib.parse import urlparse

from lib.connection.response import BaseResponse
from lib.core.settings import MAX_RESPONSE_FILENAME_LENGTH
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


class ResponseSaver:
    """Save matched response bodies without serializing scanner workers."""

    def __init__(self, directory: str) -> None:
        self.directory = os.path.abspath(directory)
        os.makedirs(self.directory, exist_ok=True)
        if not os.path.isdir(self.directory):
            raise NotADirectoryError(f"Not a directory: {self.directory}")

        # Fail before a scan starts if the directory cannot create files.
        descriptor, probe_path = tempfile.mkstemp(
            prefix=".dirsearch-write-test-",
            dir=self.directory,
        )
        os.close(descriptor)
        os.unlink(probe_path)

    def save(self, response: BaseResponse) -> str:
        base_name = response_filename(response.url, response.status)
        file_path, descriptor = self._claim_file(base_name)
        completed = False

        try:
            with os.fdopen(descriptor, "wb") as file_handle:
                descriptor = -1
                file_handle.write(response.body)
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
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)

        while True:
            collision_suffix = "" if counter == 0 else f"_{counter}"
            candidate_name = (
                f"{_truncate_filename(base_name, MAX_RESPONSE_FILENAME_LENGTH - len(collision_suffix))}"
                f"{collision_suffix}"
            )
            file_path = os.path.join(self.directory, candidate_name)
            try:
                descriptor = os.open(file_path, flags, 0o600)
            except FileExistsError:
                counter += 1
                continue
            return file_path, descriptor
