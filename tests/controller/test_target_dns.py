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

from unittest import TestCase
from unittest.mock import Mock, call, patch

from lib.controller.controller import Controller
from lib.core.data import options


class TestControllerTargetDNS(TestCase):
    def setUp(self):
        self.original_options = dict(options)
        options.update(
            {
                "request_backend": "python",
                "scheme": None,
                "ip": "192.0.2.10",
            }
        )
        self.controller = object.__new__(Controller)
        self.controller.requester = Mock()

    def tearDown(self):
        options.clear()
        options.update(self.original_options)

    def test_ip_override_uses_detected_default_port(self):
        with patch(
            "lib.controller.controller.detect_scheme",
            side_effect=(ValueError, "https"),
        ) as detect_scheme:
            self.controller.set_target("forced-origin.invalid")

        self.assertEqual(
            detect_scheme.call_args_list,
            [
                call(
                    "forced-origin.invalid",
                    None,
                    connect_host="192.0.2.10",
                ),
                call(
                    "forced-origin.invalid",
                    443,
                    connect_host="192.0.2.10",
                ),
            ],
        )
        self.controller.requester.set_ip.assert_called_once_with(
            "forced-origin.invalid",
            443,
            "192.0.2.10",
        )
        self.controller.requester.set_url.assert_called_once_with(
            "https://forced-origin.invalid/"
        )
