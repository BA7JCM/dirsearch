from unittest import TestCase
from unittest.mock import patch

from lib.core.options import parse_options


class TestOptions(TestCase):
    def test_response_size_options_accept_raw_bytes_and_units(self):
        args = [
            "dirsearch.py",
            "--wordlist-status",
            "-e",
            "php",
            "--exclude-sizes",
            "512,1KB,2MB",
            "--min-response-size",
            "1KB",
            "--max-response-size",
            "2MB",
        ]

        with patch("sys.argv", args):
            parsed = parse_options()

        self.assertEqual(parsed["exclude_sizes"], {512, 1024, 2 * 1024 * 1024})
        self.assertEqual(parsed["minimum_response_size"], 1024)
        self.assertEqual(parsed["maximum_response_size"], 2 * 1024 * 1024)

    def test_response_size_options_accept_bytes_suffix(self):
        args = [
            "dirsearch.py",
            "--wordlist-status",
            "-e",
            "php",
            "--exclude-sizes",
            "1024B",
            "--min-response-size",
            "512B",
            "--max-response-size",
            "2048B",
        ]

        with patch("sys.argv", args):
            parsed = parse_options()

        self.assertEqual(parsed["exclude_sizes"], {1024})
        self.assertEqual(parsed["minimum_response_size"], 512)
        self.assertEqual(parsed["maximum_response_size"], 2048)
