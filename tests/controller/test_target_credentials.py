from unittest import TestCase
from unittest.mock import Mock, patch

from lib.controller.controller import Controller
from lib.core.data import options


class TestControllerTargetCredentials(TestCase):
    def setUp(self):
        self.original_options = dict(options)
        options.update(
            {
                "request_backend": "python",
                "scheme": None,
                "ip": None,
            }
        )
        self.controller = object.__new__(Controller)
        self.controller.requester = Mock()

    def tearDown(self):
        options.clear()
        options.update(self.original_options)

    def test_embedded_basic_credentials_are_parsed_and_decoded(self):
        cases = (
            ("http://user:pass@example.test/", "user:pass"),
            (
                "http://user%40name:p%40ss%3Aword@example.test/",
                "user@name:p@ss:word",
            ),
            ("http://user:p@ss@example.test/", "user:p@ss"),
            ("http://user@example.test/", "user"),
            ("http://:pass@example.test/", ":pass"),
        )

        for target, credential in cases:
            with self.subTest(target=target):
                self.controller.requester.reset_mock()

                self.controller.set_target(target)

                self.controller.requester.set_auth.assert_called_once_with(
                    "basic", credential
                )
                self.controller.requester.set_url.assert_called_once_with(
                    "http://example.test/"
                )

    def test_target_path_and_query_survive_credential_removal(self):
        self.controller.set_target(
            "https://user:pass@example.test/private?debug=true"
        )

        self.assertEqual(self.controller.base_path, "private/")
        self.controller.requester.set_url.assert_called_once_with(
            "https://example.test/"
        )
        self.controller.requester.set_query.assert_called_once_with("debug=true")

    def test_scheme_less_target_supports_embedded_credentials(self):
        with patch(
            "lib.controller.controller.detect_scheme",
            side_effect=(ValueError, "https"),
        ):
            self.controller.set_target("user:p%40ss@example.test")

        self.controller.requester.set_auth.assert_called_once_with(
            "basic", "user:p@ss"
        )
        self.controller.requester.set_url.assert_called_once_with(
            "https://example.test/"
        )

    def test_target_without_credentials_does_not_override_authentication(self):
        self.controller.set_target("https://example.test/")

        self.controller.requester.set_auth.assert_not_called()
        self.controller.requester.set_url.assert_called_once_with(
            "https://example.test/"
        )
