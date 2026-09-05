# -*- coding: utf-8 -*-
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#  Author: Mauro Soria

from __future__ import annotations

import json
import os
import tempfile
from types import SimpleNamespace
from unittest import TestCase

from lib.controller.session import SessionStore
from lib.core.dictionary import Dictionary
from lib.core.exceptions import UnpicklingError


class TestSessionStore(TestCase):
    def _write_json(self, path: str, payload: dict) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def _write_session_dir(self, session_dir: str, url: str) -> None:
        os.makedirs(session_dir, exist_ok=True)
        self._write_json(
            os.path.join(session_dir, SessionStore.FILES["meta"]),
            {"version": SessionStore.SESSION_VERSION},
        )
        self._write_json(
            os.path.join(session_dir, SessionStore.FILES["controller"]),
            {"url": url, "directories": [], "jobs_processed": 1, "errors": 0},
        )
        self._write_json(
            os.path.join(session_dir, SessionStore.FILES["options"]),
            {"urls": ["https://example.com"]},
        )

    def _write_session_file(self, session_file: str, url: str) -> None:
        payload = {
            "version": SessionStore.SESSION_VERSION,
            "controller": {"url": url, "directories": [], "jobs_processed": 2, "errors": 0},
            "dictionary": {"items": [], "index": 0, "extra": [], "extra_index": 0},
            "options": {"urls": ["https://example.com"]},
        }
        self._write_json(session_file, payload)

    def test_list_sessions_recurses_and_includes_root_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "2024-01-01", "session_01")
            self._write_session_dir(nested_dir, "https://nested.example.com")

            root_file = os.path.join(tmpdir, "session_root.json")
            self._write_session_file(root_file, "https://root.example.com")

            sessions = SessionStore({}).list_sessions(tmpdir)

            self.assertEqual(len(sessions), 2)
            self.assertEqual(
                [session["path"] for session in sessions],
                sorted([nested_dir, root_file]),
            )

    def test_request_body_bytes_round_trip_through_json_session(self):
        body = "value=\u00e9&currency=\u20ac\r\n".encode("cp1252")
        session_options = {"data": body, "output_formats": []}
        controller = SimpleNamespace(
            start_time="2026-01-01T00:00:00Z",
            passed_urls=set(),
            directories=[],
            jobs_processed=0,
            errors=0,
            consecutive_errors=0,
            base_path="",
            url="https://example.com/",
            old_session=False,
            dictionary=Dictionary(),
            output_history=[],
        )

        with tempfile.TemporaryDirectory() as session_dir:
            store = SessionStore(session_options)
            store.save(controller, session_dir, "")
            payload = store.load(session_dir)
            restored = store.restore_options(payload["options"])

        self.assertEqual(restored["data"], body)

    def test_bytes_marker_in_headers_remains_a_header_mapping(self):
        marker = SessionStore.SESSION_BYTES_MARKER
        headers = {marker: "header-value"}

        restored = SessionStore({}).restore_options({"headers": headers})

        self.assertEqual(restored["headers"], headers)

    def test_invalid_request_body_encoding_is_rejected(self):
        serialized = {
            "data": {SessionStore.SESSION_BYTES_MARKER: "not base64!"}
        }

        with self.assertRaisesRegex(
            UnpicklingError,
            "Invalid binary session option: data",
        ):
            SessionStore({}).restore_options(serialized)
