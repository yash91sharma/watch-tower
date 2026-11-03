"""Docker test: the log SSE route with the real test containers (task 12.1)."""

import json
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

from tests.docker.env import PROXY_URL
from tests.integration.api.asgi_stream import open_stream
from wt import clock
from wt.auth import sessions
from wt.context import AppContext
from wt.docker.client import DockerClient

pytestmark = [pytest.mark.docker, pytest.mark.anyio]

URL = PROXY_URL.replace("http://", "tcp://")


@pytest.fixture
async def ctx(app: FastAPI, docker_env: dict[str, str]) -> AppContext:
    context: AppContext = app.state.ctx
    app.state.ctx = context = replace(context, docker_factory=lambda: DockerClient(URL))
    client = DockerClient(URL)
    try:
        await context.inventory.sync_all(client)
    finally:
        await client.close()
    return context


def lines(text: str) -> list[dict[str, str]]:
    return [
        json.loads(chunk.removeprefix("data: "))
        for chunk in text.strip().split("\n\n")
        if chunk
    ]


async def test_tail_with_stdout_and_stderr(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    response = await user_client.get(
        "/api/containers/wt_test_json/logs?tail=10&follow=false"
    )

    items = lines(response.text)
    assert len(items) == 10
    assert {item["stream"] for item in items} == {"stdout", "stderr"}


async def test_since(ctx: AppContext, user_client: httpx.AsyncClient) -> None:
    since = (clock.now() - timedelta(seconds=3)).isoformat().replace("+00:00", "Z")

    response = await user_client.get(
        "/api/containers/wt_test_healthy/logs",
        params={"since": since, "follow": "false", "tail": "100"},
    )

    items = lines(response.text)
    assert items
    assert all(item["time"] >= since for item in items)


async def test_follow_gets_new_lines_and_disconnect_ends_it(
    app: FastAPI, ctx: AppContext
) -> None:
    cookie = f"{sessions.COOKIE}={sessions.create_session(ctx.engine)}"
    start = clock.now().isoformat().replace("+00:00", "Z")

    async with open_stream(
        app, "/api/containers/wt_test_healthy/logs?tail=0", cookie
    ) as stream:
        first = json.loads((await stream.next_chunk(timeout=5)).removeprefix("data: "))

    assert first["time"] >= start
