from __future__ import annotations

import http.client
import ipaddress
import select
import socket
import socketserver
import ssl
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


IO_TIMEOUT = 3
TUNNEL_TIMEOUT = 5
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class RecordingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    block_on_close = True
    daemon_threads = False

    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self._events = []
        self._events_lock = threading.Lock()

    def record(self, method: str, target: str) -> None:
        with self._events_lock:
            self._events.append((method, target))

    def clear_events(self) -> None:
        with self._events_lock:
            self._events.clear()

    @property
    def events(self) -> list[tuple[str, str]]:
        with self._events_lock:
            return list(self._events)


class TargetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.record("GET", self.path)
        body = f"reached:{self.path}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *args):
        del args


class ForwardProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.record("GET", self.path)
        target = urlsplit(self.path)
        if (
            target.scheme != "http"
            or target.hostname not in LOCAL_HOSTS
            or target.port is None
        ):
            self.send_error(403, "Proxy target is outside the local test stack")
            return

        request_target = urlunsplit(("", "", target.path or "/", target.query, ""))
        upstream = http.client.HTTPConnection(
            target.hostname,
            target.port,
            timeout=IO_TIMEOUT,
        )
        try:
            upstream.request(
                "GET",
                request_target,
                headers={"Host": target.netloc, "Connection": "close"},
            )
            response = upstream.getresponse()
            body = response.read()
        except OSError:
            self.send_error(502, "Local test target is unavailable")
            return
        finally:
            upstream.close()

        self.send_response(response.status)
        self.send_header("Content-Type", response.getheader("Content-Type", "text/plain"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_CONNECT(self):
        self.server.record("CONNECT", self.path)
        host, separator, port = self.path.rpartition(":")
        if not separator or host not in LOCAL_HOSTS:
            self.send_error(403, "Proxy target is outside the local test stack")
            return

        try:
            port_number = int(port)
            upstream = socket.create_connection(
                (host, port_number),
                timeout=IO_TIMEOUT,
            )
        except (OSError, ValueError):
            self.send_error(502, "Local test target is unavailable")
            return

        self.send_response(200, "Connection Established")
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True

        try:
            self._relay(upstream)
        finally:
            upstream.close()

    def _relay(self, upstream: socket.socket) -> None:
        downstream = self.connection
        downstream.settimeout(IO_TIMEOUT)
        upstream.settimeout(IO_TIMEOUT)
        connections = (downstream, upstream)
        deadline = time.monotonic() + TUNNEL_TIMEOUT

        while time.monotonic() < deadline:
            readable, _, _ = select.select(connections, (), (), 0.1)
            if (
                isinstance(downstream, ssl.SSLSocket)
                and downstream.pending()
                and downstream not in readable
            ):
                readable.append(downstream)

            for source in readable:
                try:
                    data = source.recv(65536)
                except (BlockingIOError, ssl.SSLWantReadError):
                    continue
                if not data:
                    return

                destination = upstream if source is downstream else downstream
                try:
                    destination.sendall(data)
                except OSError:
                    return

    def log_message(self, _format, *args):
        del args


class LocalHTTPServer:
    def __init__(
        self,
        handler_class,
        scheme: str,
        certificate: Path | None = None,
        private_key: Path | None = None,
    ) -> None:
        self.scheme = scheme
        self.server = RecordingHTTPServer(("127.0.0.1", 0), handler_class)
        if scheme == "https":
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate, private_key)
            self.server.socket = context.wrap_socket(
                self.server.socket,
                server_side=True,
            )

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name=f"dirsearch-test-{scheme}-server",
        )
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"{self.scheme}://{host}:{port}/"

    @property
    def authority(self) -> str:
        host, port = self.server.server_address
        return f"{host}:{port}"

    @property
    def events(self) -> list[tuple[str, str]]:
        return self.server.events

    def clear_events(self) -> None:
        self.server.clear_events()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=IO_TIMEOUT)
        if self.thread.is_alive():
            raise RuntimeError(f"{self.scheme} test server did not stop")


class ProxyTestStack:
    def __enter__(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        certificate, private_key = _create_test_certificate(
            Path(self._temporary_directory.name)
        )
        self._servers = []
        try:
            self.http_target = self._start(TargetHandler, "http")
            self.https_target = self._start(
                TargetHandler,
                "https",
                certificate,
                private_key,
            )
            self.http_proxy = self._start(ForwardProxyHandler, "http")
            self.https_proxy = self._start(
                ForwardProxyHandler,
                "https",
                certificate,
                private_key,
            )
        except Exception:
            self.close()
            raise
        return self

    def _start(self, handler_class, scheme, certificate=None, private_key=None):
        server = LocalHTTPServer(
            handler_class,
            scheme,
            certificate,
            private_key,
        )
        self._servers.append(server)
        return server

    @property
    def proxies(self) -> tuple[LocalHTTPServer, LocalHTTPServer]:
        return self.http_proxy, self.https_proxy

    @property
    def targets(self) -> tuple[LocalHTTPServer, LocalHTTPServer]:
        return self.http_target, self.https_target

    def close(self) -> None:
        errors = []
        for server in reversed(getattr(self, "_servers", [])):
            try:
                server.close()
            except Exception as error:
                errors.append(error)
        self._servers = []

        temporary_directory = getattr(self, "_temporary_directory", None)
        if temporary_directory is not None:
            temporary_directory.cleanup()
            self._temporary_directory = None

        if errors:
            raise errors[0]

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def _create_test_certificate(directory: Path) -> tuple[Path, Path]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(datetime(2040, 1, 1, tzinfo=timezone.utc))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    certificate_path = directory / "certificate.pem"
    private_key_path = directory / "private-key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return certificate_path, private_key_path
