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

    def test_text_crawl_preserves_nested_paths(self):
        text_doc = (
            f"Links: {DUMMY_URL}api/v1/users?next=/dashboard "
            f"{DUMMY_URL}public/scripts/"
        )

        self.assertEqual(
            Crawler.text_crawl(DUMMY_URL, DUMMY_URL, text_doc),
            {"api/v1/users?next=/dashboard", "public/scripts/"},
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
