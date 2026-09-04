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

import gc
import weakref
from unittest import TestCase

from lib.core.settings import DUMMY_URL
from lib.utils.crawl import Crawler


class WeakText(str):
    pass


class TestCrawl(TestCase):
    def assert_body_is_released(self, parser, body):
        clear_cache = getattr(parser, "cache_clear", None)
        if clear_cache:
            clear_cache()

        content = WeakText(body)
        reference = weakref.ref(content)
        try:
            parser(DUMMY_URL, DUMMY_URL, content)
            del content
            gc.collect()
            self.assertIsNone(reference())
        finally:
            if clear_cache:
                clear_cache()

    def test_text_crawl(self):
        html_doc = f'Link: {DUMMY_URL}foobar'
        self.assertEqual(Crawler.text_crawl(DUMMY_URL, DUMMY_URL, html_doc), {"foobar"})

    def test_text_crawl_preserves_url_components(self):
        paths = (
            "api/v1/users?next=/dashboard",
            "public/scripts/",
            "catalog;view=full/items:latest@v2?filter[status]=active",
            "reports/Ben's_(final)/view?format=csv",
            "search/%E2%9C%93?q=one%20two&next=/account?tab=keys",
            "?page=2&next=/dashboard",
        )

        for path in paths:
            with self.subTest(path=path):
                text_doc = f'const endpoint = "{DUMMY_URL}{path}";'

                self.assertEqual(
                    Crawler.text_crawl(DUMMY_URL, DUMMY_URL, text_doc),
                    {path},
                )

    def test_text_crawl_handles_serialized_url_forms(self):
        cases = (
            (
                'JSON escaped solidus',
                r'const endpoint = "https:\/\/example.com\/api\/v1\/users";',
                "api/v1/users",
            ),
            (
                'JavaScript Unicode escape',
                r'const endpoint = "https:\u002F\u002Fexample.com\u002Fgraphql\u002Fv2";',
                "graphql/v2",
            ),
            (
                'JavaScript hexadecimal escape',
                r'const endpoint = "https:\x2f\x2fexample.com\x2fassets\x2fapp.js";',
                "assets/app.js",
            ),
            (
                "case-insensitive origin",
                'const endpoint = "HTTPS://EXAMPLE.COM/Admin/Users";',
                "Admin/Users",
            ),
        )

        for name, text_doc, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    Crawler.text_crawl(DUMMY_URL, DUMMY_URL, text_doc),
                    {expected},
                )

    def test_text_crawl_respects_context_delimiters(self):
        text_doc = (
            f'quoted = "{DUMMY_URL}api/search?q=one,two"; '
            f"fetch('{DUMMY_URL}api/health'); "
            f"angle = <{DUMMY_URL}docs/start>; "
            f"See ({DUMMY_URL}docs/(draft)). "
            f"Then visit {DUMMY_URL}account/profile, and continue."
        )

        self.assertEqual(
            Crawler.text_crawl(DUMMY_URL, DUMMY_URL, text_doc),
            {
                "account/profile",
                "api/health",
                "api/search?q=one,two",
                "docs/(draft)",
                "docs/start",
            },
        )

    def test_text_crawl_keeps_scope_and_fragment_boundaries(self):
        text_doc = (
            f"{DUMMY_URL}api/health#readiness "
            f"{DUMMY_URL}api/health#liveness "
            f"{DUMMY_URL}#overview "
            "http://example.com/wrong-scheme "
            "https://example.com.evil.test/lookalike "
            "https://other.example/api/external"
        )

        self.assertEqual(
            Crawler.text_crawl(DUMMY_URL, DUMMY_URL, text_doc),
            {"api/health"},
        )

    def test_text_crawl_filters_media_paths_not_route_suffixes(self):
        text_doc = (
            f'route = "{DUMMY_URL}api/generatepdf"; '
            f'image = "{DUMMY_URL}assets/LOGO.PNG?v=2#hero";'
        )

        self.assertEqual(
            Crawler.text_crawl(DUMMY_URL, DUMMY_URL, text_doc),
            {"api/generatepdf"},
        )

    def test_html_crawl(self):
        html_doc = f'<a href="{DUMMY_URL}foo">link</a><script src="/bar.js"><img src="/bar.png">'
        self.assertEqual(Crawler.html_crawl(DUMMY_URL, DUMMY_URL, html_doc), {"foo", "bar.js"})

    def test_html_crawl_handles_rtl_override(self):
        html_doc = '<a href="/admin/\u202eexe.txt/">link</a>'

        self.assertEqual(
            Crawler.html_crawl(DUMMY_URL, DUMMY_URL, html_doc),
            {"admin/\u202eexe.txt/"},
        )

    def test_html_crawl_handles_large_zwj_emoji_sequence(self):
        family = "👨‍👩‍👧‍👦" * 500
        html_doc = f'<a href="/admin/{family}/ok">link</a>'

        self.assertEqual(
            Crawler.html_crawl(DUMMY_URL, DUMMY_URL, html_doc),
            {f"admin/{family}/ok"},
        )

    def test_robots_crawl(self):
        robots_txt = """
User-agent: Googlebot
Disallow: /path1

User-agent: *
        Allow: /path2"""
        self.assertEqual(Crawler.robots_crawl(DUMMY_URL, DUMMY_URL, robots_txt), {"path1", "path2"})

    def test_text_crawl_releases_response_body(self):
        self.assert_body_is_released(
            Crawler.text_crawl,
            f"Link: {DUMMY_URL}text-retention-check",
        )

    def test_html_crawl_releases_response_body(self):
        self.assert_body_is_released(
            Crawler.html_crawl,
            '<a href="/html-retention-check">link</a>',
        )

    def test_robots_crawl_releases_response_body(self):
        self.assert_body_is_released(
            Crawler.robots_crawl,
            "Allow: /robots-retention-check",
        )
