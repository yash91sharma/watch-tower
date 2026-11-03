"""Tests for GET /api/stream (SSE)."""

import asyncio
import json

import pytest
from fastapi import FastAPI

from tests.integration.api.asgi_stream import open_stream
from wt.auth import sessions
from wt.bus import Topic
from wt.clock import FakeClock
from wt.context import AppContext

pytestmark = pytest.mark.anyio


def session_cookie(ctx: AppContext) -> str:
    return f"{sessions.COOKIE}={sessions.create_session(ctx.engine)}"


def parse(chunk: str) -> tuple[str, object]:
    lines = dict(line.split(": ", 1) for line in chunk.strip().splitlines())
    return lines["event"], json.loads(lines["data"])


async def test_first_event_is_the_docker_state(app: FastAPI) -> None:
    ctx: AppContext = app.state.ctx
    ctx.docker_state.connected = True

    async with open_stream(app, "/api/stream", session_cookie(ctx)) as stream:
        assert stream.status == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["cache-control"] == "no-cache"
        assert stream.headers["x-accel-buffering"] == "no"
        assert parse(await stream.next_chunk()) == ("docker", {"connected": True})


async def test_bus_events_arrive(app: FastAPI) -> None:
    ctx: AppContext = app.state.ctx
    async with open_stream(app, "/api/stream", session_cookie(ctx)) as stream:
        await stream.next_chunk()

        ctx.bus.publish(Topic.CONTAINER, {"name": "web"})
        ctx.bus.publish(Topic.SETTINGS)
        ctx.bus.publish(Topic.CHECK, {"running": True})

        assert parse(await stream.next_chunk()) == ("container", {"name": "web"})
        assert parse(await stream.next_chunk()) == ("check", {"running": True})


async def test_keep_alive_comment(app: FastAPI, clock: FakeClock) -> None:
    ctx: AppContext = app.state.ctx
    async with open_stream(app, "/api/stream", session_cookie(ctx)) as stream:
        await stream.next_chunk()

        assert await stream.next_chunk() == ": keep-alive\n\n"


async def test_disconnect_removes_the_subscriber(app: FastAPI) -> None:
    ctx: AppContext = app.state.ctx
    async with open_stream(app, "/api/stream", session_cookie(ctx)) as stream:
        await stream.next_chunk()
        assert ctx.bus.subscriber_count == 1  # No workers run in this test app.

    assert await wait_for_count(ctx, 0)


async def wait_for_count(ctx: AppContext, count: int) -> bool:
    async with asyncio.timeout(2):
        while ctx.bus.subscriber_count != count:
            await asyncio.sleep(0.01)  # noqa: TID251  (real wait for the cleanup)
    return True


async def test_no_session_gives_401(app: FastAPI) -> None:
    async with open_stream(app, "/api/stream") as stream:
        assert stream.status == 401
