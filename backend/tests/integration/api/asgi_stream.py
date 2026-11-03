"""Test helper: open a streaming GET on an ASGI app, read chunks, then disconnect.

httpx's ASGITransport waits for the full response, so it cannot read an endless stream.
"""

import asyncio
from collections.abc import AsyncGenerator, MutableMapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI


@dataclass
class Stream:
    status: int = 0
    headers: dict[str, str] = field(default_factory=dict[str, str])
    _chunks: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue[bytes])

    async def next_chunk(self, timeout: float = 2) -> str:
        return (await asyncio.wait_for(self._chunks.get(), timeout)).decode()


@asynccontextmanager
async def open_stream(
    app: FastAPI, path: str, cookie: str = ""
) -> AsyncGenerator[Stream]:
    stream = Stream()
    started = asyncio.Event()
    disconnect = asyncio.Event()
    scope = {
        "type": "http",
        # As Uvicorn: with spec 2.3, Starlette stops a stream when receive() gives a disconnect.
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"host", b"wt"), (b"cookie", cookie.encode())],
        "client": ("127.0.0.1", 1234),
        "server": ("wt", 443),
    }
    sent_request = False

    async def receive() -> dict[str, Any]:
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        if message["type"] == "http.response.start":
            stream.status = message["status"]
            stream.headers = {
                key.decode(): value.decode() for key, value in message["headers"]
            }
            started.set()
        elif message["type"] == "http.response.body" and message.get("body"):
            stream._chunks.put_nowait(message["body"])  # pyright: ignore[reportPrivateUsage]

    task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(started.wait(), 2)
        yield stream
    finally:
        disconnect.set()
        await asyncio.wait_for(task, 5)
