import asyncio
import warnings
from unittest import TestCase, skipUnless

from urllib3.exceptions import InsecureRequestWarning

from lib.connection.native import NativeHTTPBackend
from lib.connection.requester import AsyncRequester, Requester
from lib.core.data import options
from tests.connection.proxy_server import ProxyTestStack


try:
    import dirsearch_native
except ImportError:
    dirsearch_native = None


class TestProxyIntegration(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack_context = ProxyTestStack()
        cls.stack = cls.stack_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.stack_context.__exit__(None, None, None)

    def setUp(self):
        self.original_options = dict(options)
        options.update(
            {
                "proxies": [],
                "headers": {},
                "data": None,
                "cert_file": None,
                "key_file": None,
                "network_interface": None,
                "random_agents": False,
                "auth": None,
                "auth_type": None,
                "max_retries": 0,
                "max_rate": 0,
                "thread_count": 2,
                "follow_redirects": False,
                "http_method": "GET",
                "timeout": 3,
                "proxy_auth": None,
            }
        )

    def tearDown(self):
        options.clear()
        options.update(self.original_options)

    def test_sync_engine_uses_http_and_https_proxies_for_both_targets(self):
        for proxy, target in self._cases():
            with self.subTest(proxy=proxy.scheme, target=target.scheme):
                path = f"sync-{proxy.scheme}-proxy-{target.scheme}-target"
                self._prepare_case(proxy, target)
                options["proxies"] = [proxy.url]
                requester = Requester()
                requester.set_url(target.url)
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", InsecureRequestWarning)
                        response = requester.request(path)
                finally:
                    requester.session.close()

                self._assert_case(proxy, target, path, response)

    def test_async_engine_uses_http_and_https_proxies_for_both_targets(self):
        asyncio.run(self._test_async_engine())

    async def _test_async_engine(self):
        for proxy, target in self._cases():
            with self.subTest(proxy=proxy.scheme, target=target.scheme):
                path = f"async-{proxy.scheme}-proxy-{target.scheme}-target"
                self._prepare_case(proxy, target)
                options["proxies"] = [proxy.url]
                requester = AsyncRequester()
                requester.set_url(target.url)
                try:
                    response = await requester.request(path)
                finally:
                    await requester.session.aclose()

                self._assert_case(proxy, target, path, response)

    @skipUnless(
        dirsearch_native is not None
        and hasattr(dirsearch_native, "NativeHttpEngine"),
        "native extension is not installed",
    )
    def test_native_engine_uses_http_and_https_proxies_for_both_targets(self):
        for proxy, target in self._cases():
            with self.subTest(proxy=proxy.scheme, target=target.scheme):
                path = f"native-{proxy.scheme}-proxy-{target.scheme}-target"
                self._prepare_case(proxy, target)
                options["proxies"] = [proxy.url]
                backend = NativeHTTPBackend()
                rows = list(backend.scan(target.url, [path]))

                self.assertEqual(len(rows), 1)
                _, response, error = rows[0]
                self.assertIsNone(error)
                self._assert_case(proxy, target, path, response)

    def _cases(self):
        for proxy in self.stack.proxies:
            for target in self.stack.targets:
                yield proxy, target

    @staticmethod
    def _prepare_case(proxy, target):
        proxy.clear_events()
        target.clear_events()

    def _assert_case(self, proxy, target, path, response):
        self.assertIsNotNone(response)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, f"reached:/{path}".encode())
        self.assertEqual(target.events, [("GET", f"/{path}")])

        if target.scheme == "http":
            expected_proxy_event = ("GET", target.url + path)
        else:
            expected_proxy_event = ("CONNECT", target.authority)
        self.assertEqual(proxy.events, [expected_proxy_event])
