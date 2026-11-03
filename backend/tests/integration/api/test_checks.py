"""Tests for POST /api/checks and GET /api/checks/status (respx)."""

import asyncio

import httpx
import pytest
import respx
from fastapi import FastAPI

from wt.bus import Topic
from wt.context import AppContext
from wt.docker.client import ContainerInfo

pytestmark = pytest.mark.anyio

SOURCE = "org.opencontainers.image.source"
LATEST = "https://api.github.com/repos/o/web/releases/latest"


async def add_web(ctx: AppContext) -> None:
    labels = {SOURCE: "https://github.com/o/web"}
    await ctx.inventory.update(
        ContainerInfo("id-1", "web", "app:1.0", labels, "running", "none", False, 0)
    )


async def wait_until_idle(ctx: AppContext) -> None:
    async with asyncio.timeout(5):
        while ctx.checker.running:
            await asyncio.sleep(0.01)  # noqa: TID251  (real wait for the background run)


async def test_status_before_the_first_run(user_client: httpx.AsyncClient) -> None:
    response = await user_client.get("/api/checks/status")

    assert response.json() == {"running": False, "last_run": None, "counts": {}}


async def test_start_409_during_a_run_and_status_after(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    await add_web(ctx)
    gate = asyncio.Event()

    async def slow(request: httpx.Request) -> httpx.Response:
        await gate.wait()
        return httpx.Response(200, json={"tag_name": "1.0"})

    with ctx.bus.subscribe([Topic.CHECK]) as subscription, respx.mock:
        respx.get(LATEST).mock(side_effect=slow)
        respx.get(LATEST.removesuffix("/latest")).mock(
            return_value=httpx.Response(200, json=[])
        )

        started = await user_client.post("/api/checks")
        assert started.status_code == 202
        while not ctx.checker.running:
            await asyncio.sleep(0)  # noqa: TID251  (let the run start)

        assert (await user_client.post("/api/checks")).status_code == 409
        assert (await user_client.get("/api/checks/status")).json()["running"] is True

        gate.set()
        await wait_until_idle(ctx)
        messages = [(await subscription.get()).data for _ in range(2)]

    status = (await user_client.get("/api/checks/status")).json()
    assert status["running"] is False
    assert status["last_run"] is not None
    assert status["counts"] == {"up to date": 1}
    assert messages == [{"running": True}, {"running": False}]
