from unittest import TestCase

from lib.connection.proxy import (
    format_proxy_error,
    is_proxy_connect_rejection,
    proxy_error_status,
)


class TestProxyErrors(TestCase):
    def test_extracts_status_from_connect_failure(self):
        error = RuntimeError("Tunnel connection failed: 429 Too Many Requests")

        self.assertEqual(proxy_error_status(error), 429)
        self.assertEqual(
            format_proxy_error(error),
            "Proxy connection failed with HTTP 429",
        )

    def test_extracts_status_from_nested_bare_status(self):
        cause = RuntimeError("407 Proxy Authentication Required")
        error = RuntimeError("proxy connection failed")
        error.__cause__ = cause

        self.assertEqual(proxy_error_status(error), 407)
        self.assertEqual(format_proxy_error(error), "Proxy authentication required")

    def test_does_not_treat_url_numbers_as_http_status(self):
        error = "error sending request for url (http://127.0.0.1:429/path/500)"

        self.assertIsNone(proxy_error_status(error))
        self.assertEqual(
            format_proxy_error(error),
            "Cannot establish the proxy connection",
        )

    def test_formats_connect_rejection_when_client_discards_status(self):
        error = "client error (Connect): tunnel error: unsuccessful"

        self.assertTrue(is_proxy_connect_rejection(error))
        self.assertEqual(
            format_proxy_error(error),
            "Proxy CONNECT request was rejected",
        )
