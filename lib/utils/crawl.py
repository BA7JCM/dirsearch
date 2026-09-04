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

import re
import string

from bs4 import BeautifulSoup

from lib.core.settings import (
    CRAWL_ATTRIBUTES, CRAWL_TAGS,
    MEDIA_EXTENSIONS, ROBOTS_TXT_REGEX,
    URI_REGEX,
)
from lib.parse.url import clean_path, parse_path
from lib.utils.common import merge_path


_ESCAPED_SLASH_REGEX = re.compile(r"\\(?:/|u002f|x2f)", re.IGNORECASE)
_MEDIA_SUFFIXES = tuple(f".{extension}" for extension in MEDIA_EXTENSIONS)
# RFC 3986 URI characters plus brackets used by common array query syntax.
_TEXT_URL_CHARS = frozenset(
    string.ascii_letters + string.digits + "-._~%!$&'()*+,;=:@/?#[]"
)
_TEXT_URL_QUOTES = frozenset("\"'`")


def _filter(paths):
    results = set()

    for path in paths:
        path = clean_path(path, keep_queries=True)
        resource_path = path.split("?", 1)[0]

        if not path or resource_path.lower().endswith(_MEDIA_SUFFIXES):
            continue

        results.add(path)

    return results


def _trim_unquoted_url(path):
    path = path.rstrip(".,")

    for opening, closing in (("(", ")"), ("[", "]")):
        excess = max(0, path.count(closing) - path.count(opening))
        trailing = len(path) - len(path.rstrip(closing))
        trim_count = min(excess, trailing)
        if trim_count:
            path = path[:-trim_count]

    return path


def _extract_scoped_paths(scope, content):
    content = _ESCAPED_SLASH_REGEX.sub("/", content)
    scope_regex = re.compile(re.escape(scope), re.IGNORECASE)

    for match in scope_regex.finditer(content):
        preceding = content[match.start() - 1] if match.start() else ""
        quote = preceding if preceding in _TEXT_URL_QUOTES else None
        path = []

        for char in content[match.end():]:
            if char == quote or char not in _TEXT_URL_CHARS:
                break
            path.append(char)

        path = "".join(path)
        if quote is None:
            path = _trim_unquoted_url(path)

        if path:
            yield path


class Crawler:
    @classmethod
    def crawl(cls, response):
        scope = "/".join(response.url.split("/")[:3]) + "/"

        if "text/html" in response.headers.get("content-type", ""):
            return cls.html_crawl(response.url, scope, response.content)
        elif response.path == "robots.txt":
            return cls.robots_crawl(response.url, scope, response.content)
        else:
            return cls.text_crawl(response.url, scope, response.content)

    @staticmethod
    def text_crawl(url, scope, content):
        return _filter(_extract_scoped_paths(scope, content))

    @staticmethod
    def html_crawl(url, scope, content):
        results = []
        soup = BeautifulSoup(content, 'html.parser')

        for tag in CRAWL_TAGS:
            for found in soup.find_all(tag):
                for attr in CRAWL_ATTRIBUTES:
                    value = found.get(attr)

                    if not value:
                        continue

                    if value.startswith("/"):
                        results.append(value[1:])
                    elif value.startswith(scope):
                        results.append(value[len(scope):])
                    elif not re.search(URI_REGEX, value):
                        new_url = merge_path(url, value)
                        results.append(parse_path(new_url))

        return _filter(results)

    @staticmethod
    def robots_crawl(url, scope, content):
        return _filter(re.findall(ROBOTS_TXT_REGEX, content))
