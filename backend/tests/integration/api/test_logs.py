"""Tests for GET /api/containers/{name}/logs (SSE) with FakeDocker."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from tests.integration.api.asgi_stream import open_stream
from wt.auth import sessions
from wt.clock import FakeClock
from wt.context import AppContext
from wt.docker.client import ContainerInfo, LogLine, Stream
from wt.docker.fake import FakeDocker

pytestmark = pytest.mark.anyio


def line(second: int, stream: Stream = "stdout") -> LogLine:
    time = datetime(2026, 1, 1, 0, 0, second, tzinfo=UTC)
    return LogLine(time, stream, f"line {second}")


@pytest.fixture
async def fake(app: FastAPI) -> FakeDocker:
    ctx: AppContext = app.state.ctx
    docker = FakeDocker()
    docker.add(ContainerInfo("id-web", "web", "nginx:1", {}, "running", "none", False))
    docker.log_lines["web"] = [line(0), line(1, "stderr"), line(2), line(3)]
    app.state.ctx = replace(ctx, docker_factory=lambda: docker)
    await ctx.inventory.update(docker.containers["id-web"])
    await ctx.inventory.update(
        ContainerInfo(
            "id-x",
            "secret",
            "app:1",
            {"wt.enable": "false"},
            "running",
            "none",
            False,
        )
    )
    return docker


def events(text: str) -> list[dict[str, str]]:
    return [
        json.loads(chunk.removeprefix("data: "))
        for chunk in text.strip().split("\n\n")
        if chunk
    ]


async def test_tail_and_stream_fields(
    fake: FakeDocker, user_client: httpx.AsyncClient
) -> None:
    response = await user_client.get("/api/containers/web/logs?tail=2&follow=false")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events(response.text) == [
        {"time": "2026-01-01T00:00:02Z", "stream": "stdout", "text": "line 2"},
        {"time": "2026-01-01T00:00:03Z", "stream": "stdout", "text": "line 3"},
    ]
    assert fake.closed is True


async def test_default_tail_and_since(
    fake: FakeDocker, user_client: httpx.AsyncClient
) -> None:
    all_lines = events(
        (await user_client.get("/api/containers/web/logs?follow=false")).text
    )
    since = events(
        (
            await user_client.get(
                "/api/containers/web/logs?follow=false&since=2026-01-01T00:00:02Z"
            )
        ).text
    )

    assert [item["text"] for item in all_lines] == [
        "line 0",
        "line 1",
        "line 2",
        "line 3",
    ]
    assert all_lines[1]["stream"] == "stderr"
    assert [item["text"] for item in since] == ["line 2", "line 3"]


@pytest.mark.parametrize("tail", ["-1", "10001", "x"])
async def test_bad_tail_gives_422(
    fake: FakeDocker, user_client: httpx.AsyncClient, tail: str
) -> None:
    response = await user_client.get(f"/api/containers/web/logs?tail={tail}")

    assert response.status_code == 422


@pytest.mark.parametrize("name", ["nope", "secret"])
async def test_unknown_or_excluded_gives_404(
    fake: FakeDocker, user_client: httpx.AsyncClient, name: str
) -> None:
    response = await user_client.get(f"/api/containers/{name}/logs?follow=false")

    assert response.status_code == 404


async def test_disconnect_stops_the_docker_stream(
    app: FastAPI, fake: FakeDocker
) -> None:
    ctx: AppContext = app.state.ctx
    cookie = f"{sessions.COOKIE}={sessions.create_session(ctx.engine)}"

    async with open_stream(app, "/api/containers/web/logs", cookie) as stream:
        assert "line 0" in await stream.next_chunk()
        assert fake.closed is False

    async with asyncio.timeout(2):
        while not fake.closed:
            await asyncio.sleep(0.01)  # noqa: TID251  (real wait for the cleanup)


async def test_download_has_all_lines_and_headers(
    fake: FakeDocker, user_client: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake.log_lines["web"].append(LogLine(None, "stdout", "no time"))

    response = await user_client.get("/api/containers/web/logs.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="web-2026-01-01.log"'
    )
    assert response.text.splitlines() == [
        "2026-01-01T00:00:00Z stdout line 0",
        "2026-01-01T00:00:01Z stderr line 1",
        "2026-01-01T00:00:02Z stdout line 2",
        "2026-01-01T00:00:03Z stdout line 3",
        "- stdout no time",
    ]
    assert fake.closed is True


@pytest.mark.parametrize("name", ["nope", "secret"])
async def test_download_of_unknown_or_excluded_gives_404(
    fake: FakeDocker, user_client: httpx.AsyncClient, name: str
) -> None:
    assert (
        await user_client.get(f"/api/containers/{name}/logs.txt")
    ).status_code == 404


async def test_gone_container_gives_404(
    app: FastAPI, fake: FakeDocker, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    ctx.inventory.remove("web", "id-web")

    response = await user_client.get("/api/containers/web/logs?follow=false")

    assert response.status_code == 404


async def test_docker_error_gives_an_error_event(
    fake: FakeDocker, user_client: httpx.AsyncClient
) -> None:
    fake.fail = True

    response = await user_client.get("/api/containers/web/logs?follow=false")

    assert response.status_code == 200
    assert response.text.startswith("event: error\ndata: ")
    assert "Docker is not there" in response.text
    assert fake.closed is True
