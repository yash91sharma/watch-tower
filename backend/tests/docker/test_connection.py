"""Docker test: WT syncs again after a restart of the socket proxy (task 6.6)."""

import asyncio

import pytest
from sqlalchemy import Engine

from tests.docker.env import PROXY, PROXY_URL, docker
from wt.bus import Bus, Topic
from wt.docker.client import DockerClient
from wt.docker.connection import DockerState, keep_connected
from wt.docker.inventory import Inventory

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


async def test_proxy_restart_gives_a_new_sync(
    docker_env: dict[str, str], db_engine: Engine
) -> None:
    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    subscription = bus.subscribe([Topic.DOCKER])
    url = PROXY_URL.replace("http://", "tcp://")
    task = asyncio.create_task(
        keep_connected(lambda: DockerClient(url), inventory, bus, state)
    )
    states: list[bool] = []

    async def wait_for(connected: bool) -> None:
        while True:
            states.append(bool((await subscription.get()).data["connected"]))
            if states[-1] is connected:
                return

    try:
        async with asyncio.timeout(60):
            await wait_for(True)
            await asyncio.to_thread(docker, "restart", PROXY)
            await wait_for(False)
            await wait_for(True)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert state.connected is True
    assert inventory.get("wt_test_healthy") is not None
