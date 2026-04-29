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

from __future__ import annotations

import itertools
import re
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests

from lib.core.settings import DEFAULT_HEADERS, EXTENSION_TAG
from lib.core.structures import OrderedSet
from lib.utils.common import safequote


__all__ = [
    "DirsearchFuzzer",
    "FuzzerConfig",
    "FuzzerResult",
    "Wordlist",
    "WordlistState",
    "WordlistTemplate",
]


@dataclass(frozen=True)
class FuzzerResult:
    url: str
    path: str
    status: int
    length: int
    content_type: str
    redirect: str = ""
    elapsed: float = 0.0
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


@dataclass(frozen=True)
class WordlistState:
    items: tuple[str, ...]
    index: int = 0


@dataclass(frozen=True)
class Wordlist:
    items: tuple[str, ...]

    def __init__(self, items: Iterable[str]) -> None:
        object.__setattr__(self, "items", tuple(self._dedupe(items)))

    @classmethod
    def from_file(cls, path: str) -> Wordlist:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return cls(line.strip() for line in handle)

    @classmethod
    def from_template(
        cls,
        template: WordlistTemplate,
        *,
        extensions: Iterable[str] = (),
        placeholders: Mapping[str, Iterable[str] | str] | None = None,
    ) -> Wordlist:
        return cls(template.render(extensions=extensions, placeholders=placeholders))

    @staticmethod
    def _dedupe(items: Iterable[str]) -> Iterator[str]:
        seen = OrderedSet()
        for item in items:
            path = item.strip().lstrip("/")
            if not path or path.startswith("#") or path in seen:
                continue
            seen.add(path)
            yield path

    def __iter__(self) -> Iterator[str]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def state(self, index: int = 0) -> WordlistState:
        return WordlistState(items=self.items, index=index)


@dataclass(frozen=True)
class WordlistTemplate:
    lines: tuple[str, ...]
    placeholders: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __init__(
        self,
        lines: Iterable[str],
        placeholders: Mapping[str, Iterable[str] | str] | None = None,
    ) -> None:
        object.__setattr__(self, "lines", tuple(lines))
        object.__setattr__(
            self,
            "placeholders",
            self._normalize_placeholders(placeholders or {}),
        )

    @staticmethod
    def _normalize_placeholders(
        placeholders: Mapping[str, Iterable[str] | str]
    ) -> dict[str, tuple[str, ...]]:
        normalized: dict[str, tuple[str, ...]] = {}
        for key, values in placeholders.items():
            token = key if key.startswith("%") and key.endswith("%") else f"%{key}%"
            if isinstance(values, str):
                normalized[token.upper()] = (values,)
            else:
                normalized[token.upper()] = tuple(str(value) for value in values)
        return normalized

    def render(
        self,
        *,
        extensions: Iterable[str] = (),
        placeholders: Mapping[str, Iterable[str] | str] | None = None,
    ) -> Iterator[str]:
        values = dict(self.placeholders)
        values.update(self._normalize_placeholders(placeholders or {}))
        values[EXTENSION_TAG.upper()] = tuple(extensions)

        token_re = re.compile(r"%[A-Z0-9_:-]+%", re.IGNORECASE)
        for line in self.lines:
            tokens = []
            for token in token_re.findall(line):
                normalized = token.upper()
                if normalized in values and normalized not in tokens:
                    tokens.append(normalized)

            if not tokens:
                yield line
                continue

            expansions = [values[token] for token in tokens]
            if any(not expansion for expansion in expansions):
                continue

            for combo in itertools.product(*expansions):
                rendered = line
                for token, value in zip(tokens, combo):
                    rendered = re.sub(
                        re.escape(token),
                        value,
                        rendered,
                        flags=re.IGNORECASE,
                    )
                yield rendered


@dataclass(frozen=True)
class FuzzerConfig:
    url: str
    wordlist: Wordlist | WordlistTemplate | Iterable[str]
    extensions: tuple[str, ...] = ()
    headers: Mapping[str, str] = field(default_factory=dict)
    http_method: str = "GET"
    data: bytes | str | None = None
    timeout: float = 10.0
    follow_redirects: bool = False
    include_status_codes: frozenset[int] = field(default_factory=frozenset)
    exclude_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({404})
    )
    verify_tls: bool = False
    user_agent: str | None = None

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("FuzzerConfig.url is required")
        if not isinstance(self.wordlist, (Wordlist, WordlistTemplate)):
            object.__setattr__(self, "wordlist", Wordlist(self.wordlist))
        object.__setattr__(self, "headers", dict(self.headers))
        object.__setattr__(self, "extensions", tuple(self.extensions))
        object.__setattr__(
            self, "include_status_codes", frozenset(self.include_status_codes)
        )
        object.__setattr__(
            self, "exclude_status_codes", frozenset(self.exclude_status_codes)
        )


class DirsearchFuzzer:
    def __init__(
        self,
        config: FuzzerConfig,
        *,
        on_result: Callable[[FuzzerResult], Any] | None = None,
        on_not_found: Callable[[FuzzerResult], Any] | None = None,
        on_error: Callable[[Exception], Any] | None = None,
    ) -> None:
        self.config = config
        self.on_result = on_result
        self.on_not_found = on_not_found
        self.on_error = on_error

    def run(self) -> list[FuzzerResult]:
        results: list[FuzzerResult] = []
        session = requests.Session()
        try:
            session.verify = self.config.verify_tls
            headers = {**DEFAULT_HEADERS, **dict(self.config.headers)}
            if self.config.user_agent:
                headers["user-agent"] = self.config.user_agent

            for path in self._wordlist():
                try:
                    result = self._request(session, headers, path)
                except requests.RequestException as error:
                    if self.on_error:
                        self.on_error(error)
                    continue

                if self._is_match(result):
                    results.append(result)
                    if self.on_result:
                        self.on_result(result)
                elif self.on_not_found:
                    self.on_not_found(result)
        finally:
            session.close()
        return results

    def _wordlist(self) -> Wordlist:
        source = self.config.wordlist
        if isinstance(source, Wordlist):
            return source
        if isinstance(source, WordlistTemplate):
            return Wordlist.from_template(source, extensions=self.config.extensions)
        return Wordlist(source)

    def _request(
        self,
        session: requests.Session,
        headers: Mapping[str, str],
        path: str,
    ) -> FuzzerResult:
        url = self._join_url(self.config.url, path)
        start = time.perf_counter()
        response = session.request(
            self.config.http_method,
            url,
            headers=headers,
            data=self.config.data,
            timeout=self.config.timeout,
            allow_redirects=self.config.follow_redirects,
        )
        body = response.content
        return FuzzerResult(
            url=url,
            path=path,
            status=response.status_code,
            length=int(response.headers.get("content-length") or len(body)),
            content_type=response.headers.get("content-type", "").split(";")[0],
            redirect=response.headers.get("location", ""),
            elapsed=time.perf_counter() - start,
            headers=dict(response.headers),
            body=body,
        )

    def _is_match(self, result: FuzzerResult) -> bool:
        if result.status in self.config.exclude_status_codes:
            return False
        if (
            self.config.include_status_codes
            and result.status not in self.config.include_status_codes
        ):
            return False
        return True

    @staticmethod
    def _join_url(base_url: str, path: str) -> str:
        if not base_url.endswith("/"):
            base_url += "/"
        return urljoin(base_url, safequote(path))
