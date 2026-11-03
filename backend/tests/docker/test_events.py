"""Docker test: the events stream through the socket proxy (task 6.5)."""

import asyncio

import pytest
from sqlalchemy import Engine

from tests.docker.env import PROXY_URL, docker, wait_healthy
from wt.bus import Bus, Topic
from wt.docker.client import DockerClient
from wt.docker.events import follow_events
from wt.docker.inventory import Inventory

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


async def test_restart_of_a_container_gives_events(
    docker_env: dict[str, str], db_engine: Engine
) -> None:
    client = DockerClient(PROXY_URL.replace("http://", "tcp://"))
    inventory, bus = Inventory(db_engine), Bus()
    subscription = bus.subscribe([Topic.CONTAINER])
    task = asyncio.create_task(follow_events(client, inventory, bus))
    try:
        await asyncio.sleep(0.5)  # noqa: TID251  (let the stream connect)
        await asyncio.to_thread(docker, "restart", "-t", "1", "wt_test_healthy")
        names: set[str] = set()
        async with asyncio.timeout(20):
            while "wt_test_healthy" not in names:
                names.add((await subscription.get()).data["name"])
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.close()
        await asyncio.to_thread(wait_healthy, ["wt_test_healthy"])

    live = inventory.get("wt_test_healthy")
    assert live is not None and live.state == "running"
