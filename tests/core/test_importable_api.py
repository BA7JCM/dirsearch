from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from unittest import TestCase

from lib.core.data import options


class APITestHandler(BaseHTTPRequestHandler):
    routes = {
        "/admin.php": (200, b"admin"),
        "/login.php": (200, b"login"),
        "/private.txt": (200, b"private"),
    }

    def do_GET(self):
        status, body = self.routes.get(self.path, (404, b"missing"))
        self.send_response(status)
        self.send_header("content-type", "text/plain")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class LocalHTTPServer:
    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), APITestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class TestImportableAPI(TestCase):
    def test_public_imports_are_available(self):
        from dirsearch import (
            DirsearchFuzzer,
            FuzzerConfig,
            FuzzerResult,
            Wordlist,
            WordlistState,
            WordlistTemplate,
        )

        self.assertIsNotNone(DirsearchFuzzer)
        self.assertIsNotNone(FuzzerConfig)
        self.assertIsNotNone(FuzzerResult)
        self.assertIsNotNone(Wordlist)
        self.assertIsNotNone(WordlistState)
        self.assertIsNotNone(WordlistTemplate)

    def test_python_api_runs_template_wordlist_and_callbacks(self):
        from dirsearch import DirsearchFuzzer, FuzzerConfig, WordlistTemplate

        with LocalHTTPServer() as server:
            template = WordlistTemplate(
                ["%SUBJECT%.%EXT%", "missing.%EXT%"],
                placeholders={"SUBJECT": ["admin", "login"]},
            )
            seen = []
            not_found = []
            config = FuzzerConfig(
                url=server.url,
                wordlist=template,
                extensions=("php",),
            )

            results = DirsearchFuzzer(
                config,
                on_result=seen.append,
                on_not_found=not_found.append,
            ).run()

        self.assertEqual([result.path for result in results], ["admin.php", "login.php"])
        self.assertEqual([result.status for result in seen], [200, 200])
        self.assertEqual([result.path for result in not_found], ["missing.php"])

    def test_two_configs_do_not_leak_state(self):
        from dirsearch import DirsearchFuzzer, FuzzerConfig, WordlistTemplate

        before = dict(options)
        mutable_wordlist = ["admin.php"]
        mutable_headers = {"x-api-test": "first"}
        frozen_config = FuzzerConfig(
            url="http://127.0.0.1",
            wordlist=mutable_wordlist,
            headers=mutable_headers,
        )
        mutable_wordlist.append("private.txt")
        mutable_headers["x-api-test"] = "second"

        with LocalHTTPServer() as server:
            first_template = WordlistTemplate(
                ["%SUBJECT%.%EXT%"],
                placeholders={"SUBJECT": ["admin"]},
            )
            second_template = WordlistTemplate(
                ["%SUBJECT%.%EXT%"],
                placeholders={"SUBJECT": ["private"]},
            )

            first = DirsearchFuzzer(
                FuzzerConfig(
                    url=server.url,
                    wordlist=first_template,
                    extensions=("php",),
                )
            ).run()
            second = DirsearchFuzzer(
                FuzzerConfig(
                    url=server.url,
                    wordlist=second_template,
                    extensions=("txt",),
                )
            ).run()

        self.assertEqual([result.path for result in first], ["admin.php"])
        self.assertEqual([result.path for result in second], ["private.txt"])
        self.assertEqual(list(frozen_config.wordlist), ["admin.php"])
        self.assertEqual(frozen_config.headers["x-api-test"], "first")
        self.assertEqual(options, before)
