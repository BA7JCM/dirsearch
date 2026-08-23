import os
import signal
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import TestCase, skipUnless

try:
    import dirsearch_native
except ImportError:
    dirsearch_native = None


class NativeScanInterrupted(Exception):
    pass


class StalledHTTPServer:
    def __init__(self):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.release = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @property
    def url(self):
        host, port = self.listener.getsockname()
        return f"http://{host}:{port}/"

    def _serve(self):
        try:
            connection, _ = self.listener.accept()
            with connection:
                self.release.wait(timeout=5)
        except OSError:
            pass

    def close(self):
        self.release.set()
        self.listener.close()
        self.thread.join(timeout=1)


class KeepAliveHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *args):
        return None


class CountingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), KeepAliveHandler)
        self.connection_count = 0
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def get_request(self):
        request = super().get_request()
        self.connection_count += 1
        return request

    @property
    def url(self):
        host, port = self.server_address
        return f"http://{host}:{port}/"

    def close(self):
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=1)


@skipUnless(
    dirsearch_native is not None
    and hasattr(dirsearch_native, "NativeHttpEngine"),
    "native extension is not installed",
)
class TestNativeHttpEngine(TestCase):
    def test_reuses_http_connection_across_scans(self):
        server = CountingHTTPServer()
        engine = dirsearch_native.NativeHttpEngine()

        try:
            first = engine.scan(server.url, ["first"])
            second = engine.scan(server.url, ["second"])
        finally:
            server.close()

        self.assertEqual([first[0].status, second[0].status], [200, 200])
        self.assertEqual(server.connection_count, 1)

    def test_compatibility_function_reuses_http_connection(self):
        server = CountingHTTPServer()

        try:
            first = dirsearch_native.scan_http(server.url, ["first"])
            second = dirsearch_native.scan_http(server.url, ["second"])
        finally:
            server.close()

        self.assertEqual([first[0].status, second[0].status], [200, 200])
        self.assertEqual(server.connection_count, 1)

    def test_explicit_cancellation_interrupts_active_scan(self):
        server = StalledHTTPServer()
        engine = dirsearch_native.NativeHttpEngine(timeout_secs=5)
        cancel_timer = threading.Timer(0.1, engine.cancel)

        try:
            cancel_timer.start()
            started = time.monotonic()
            results = engine.scan(server.url, ["slow"])
            elapsed = time.monotonic() - started
        finally:
            cancel_timer.join(timeout=1)
            server.close()

        self.assertEqual(results, [])
        self.assertLess(elapsed, 2)

    def test_python_signal_interrupts_active_scan(self):
        server = StalledHTTPServer()
        engine = dirsearch_native.NativeHttpEngine(timeout_secs=5)
        previous_handler = signal.getsignal(signal.SIGINT)
        signal_timer = threading.Timer(
            0.1, lambda: os.kill(os.getpid(), signal.SIGINT)
        )

        def interrupt_scan(_signum, _frame):
            raise NativeScanInterrupted("stop native scan")

        try:
            signal.signal(signal.SIGINT, interrupt_scan)
            signal_timer.start()
            started = time.monotonic()
            with self.assertRaisesRegex(NativeScanInterrupted, "stop native scan"):
                engine.scan(server.url, ["slow"])
            elapsed = time.monotonic() - started
        finally:
            signal_timer.join(timeout=1)
            signal.signal(signal.SIGINT, previous_handler)
            server.close()

        self.assertLess(elapsed, 2)
