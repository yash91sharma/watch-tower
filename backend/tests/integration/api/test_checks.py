"""Tests for POST /api/checks and GET /api/checks/status (respx)."""

import asyncio

import httpx
import pytest
import respx
from fastapi import FastAPI

from tests.factories import make_info
from wt.bus import Topic
from wt.context import AppContext

pytestmark = pytest.mark.anyio

SOURCE = "org.opencontainers.image.source"
LATEST = "https://api.github.com/repos/o/web/releases/latest"


async def add_web(ctx: AppContext) -> None:
    labels = {SOURCE: "https://github.com/o/web"}
    await ctx.inventory.update(
        make_info(image="app:1.0", docker_id="id-1", labels=labels)
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


async def test_start_for_one_app_checks_only_its_containers(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    await add_web(ctx)
    project = {"com.docker.compose.project": "shop"}
    await ctx.inventory.update(
        make_info("api", "api:1.0", docker_id="id-2", labels=project)
    )

    with respx.mock:
        web = respx.get(LATEST)
        started = await user_client.post("/api/checks", params={"group": "shop"})
        assert started.status_code == 202
        await wait_until_idle(ctx)

    assert not web.called


async def test_start_for_the_other_group(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    await add_web(ctx)

    with respx.mock:
        web = respx.get(LATEST).mock(
            return_value=httpx.Response(200, json={"tag_name": "1.0"})
        )
        respx.get(LATEST.removesuffix("/latest")).mock(
            return_value=httpx.Response(200, json=[])
        )
        started = await user_client.post("/api/checks", params={"group": "Other"})
        assert started.status_code == 202
        await wait_until_idle(ctx)

    assert web.call_count == 1


async def test_start_for_an_unknown_group_is_404(
    user_client: httpx.AsyncClient,
) -> None:
    response = await user_client.post("/api/checks", params={"group": "nope"})

    assert response.status_code == 404


async def test_start_for_a_group_of_only_excluded_containers_is_404(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    await ctx.inventory.update(make_info("secret", project="hidden", excluded=True))

    response = await user_client.post("/api/checks", params={"group": "hidden"})

    assert response.status_code == 404
