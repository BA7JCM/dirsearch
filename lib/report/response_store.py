# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from lib.connection.response import BaseResponse


@dataclass(frozen=True)
class ResponseArtifact:
    """Backend-neutral response data passed to response stores."""

    timestamp: str
    url: str
    status: int
    headers: tuple[tuple[str, str], ...]
    content_length: int
    content_type: str
    redirect: str
    elapsed: float
    body: bytes

    @classmethod
    def from_response(cls, response: BaseResponse) -> ResponseArtifact:
        return cls(
            timestamp=response.datetime,
            url=response.url,
            status=response.status,
            headers=tuple(
                (str(name), str(value)) for name, value in response.headers.items()
            ),
            content_length=response.length,
            content_type=response.type,
            redirect=response.redirect,
            elapsed=response.elapsed,
            body=bytes(response.body),
        )


class ResponseStore(ABC):
    """Persistence boundary for matched response artifacts."""

    name = "response"

    def __init__(self, destination: str) -> None:
        self.destination = os.path.abspath(destination)

    @abstractmethod
    def save(self, artifact: ResponseArtifact) -> str:
        raise NotImplementedError

    async def save_async(self, artifact: ResponseArtifact) -> str:
        """Offload synchronous stores; native async stores may override this."""
        return await asyncio.to_thread(self.save, artifact)

    def close(self) -> None:
        pass


def create_response_stores(
    directory: str | None,
    jsonl_file: str | None,
) -> tuple[ResponseStore, ...]:
    """Build configured stores while keeping controller orchestration generic."""
    from lib.report.directory_response_store import DirectoryResponseStore
    from lib.report.jsonl_response_store import JsonlResponseStore

    stores: list[ResponseStore] = []
    try:
        if directory:
            stores.append(DirectoryResponseStore(directory))
        if jsonl_file:
            stores.append(JsonlResponseStore(jsonl_file))
    except Exception:
        for store in stores:
            store.close()
        raise
    return tuple(stores)
