from __future__ import annotations

from unittest import TestCase

from lib.core.data import options
from lib.core.exceptions import WordlistBackendUnavailableError
from lib.core.wordlist_backend import (
    NativeWordlistBackend,
    PythonWordlistBackend,
    get_wordlist_backend,
)


class TestWordlistBackend(TestCase):
    def setUp(self):
        self._original_options = dict(options)
        options["wordlist_backend"] = "auto"

    def tearDown(self):
        options.clear()
        options.update(self._original_options)

    def test_auto_selects_python_backend(self):
        self.assertIsInstance(get_wordlist_backend(), PythonWordlistBackend)

    def test_python_selects_python_backend(self):
        self.assertIsInstance(get_wordlist_backend("python"), PythonWordlistBackend)

    def test_native_reports_unavailable(self):
        try:
            backend = get_wordlist_backend("native")
        except WordlistBackendUnavailableError:
            return

        self.assertIsInstance(backend, NativeWordlistBackend)

    def test_native_matches_python_when_available(self):
        try:
            native = get_wordlist_backend("native")
        except WordlistBackendUnavailableError:
            return

        files = ["tests/static/wordlist.txt"]
        original = dict(options)
        options.update(
            {
                "extensions": ("php", "json"),
                "exclude_extensions": (),
                "force_extensions": True,
                "overwrite_extensions": False,
                "prefixes": (),
                "suffixes": (),
                "lowercase": False,
                "uppercase": False,
                "capitalization": False,
                "wordlist_max_size": 500000,
            }
        )
        try:
            python = get_wordlist_backend("python")
            self.assertEqual(
                native.generate(files),
                python.generate(files),
            )
        finally:
            options.clear()
            options.update(original)
