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

import threading


class DNSResolver:
    """Requester-owned hostname overrides used by the --ip option."""

    def __init__(self) -> None:
        self._overrides: dict[tuple[str, int], str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(host: str, port: int) -> tuple[str, int]:
        return host.rstrip(".").casefold(), port

    def add_override(self, host: str, port: int, address: str) -> None:
        with self._lock:
            self._overrides[self._key(host, port)] = address

    def resolve(self, host: str, port: int) -> str:
        with self._lock:
            return self._overrides.get(self._key(host, port), host)
