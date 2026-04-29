from __future__ import annotations

from unittest import TestCase

from lib.core.data import options
from lib.core.exceptions import WordlistBackendUnavailableError
from lib.core.wordlist_backend import PythonWordlistBackend, get_wordlist_backend


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
        with self.assertRaises(WordlistBackendUnavailableError):
            get_wordlist_backend("native")
