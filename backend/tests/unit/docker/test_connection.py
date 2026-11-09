"""Tests for wt.docker.connection (clock, FakeDocker)."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import Engine

from tests.factories import make_info
from tests.fake_docker import FakeDocker
from wt.bus import Bus, Subscription, Topic
from wt.clock import FakeClock
from wt.docker.client import ContainerInfo, DockerEvent
from wt.docker.connection import DockerState, keep_connected
from wt.docker.inventory import Inventory

pytestmark = pytest.mark.anyio

WEB = make_info(docker_id="id-1", health="healthy")


async def next_docker_state(subscription: Subscription) -> bool:
    message = await asyncio.wait_for(subscription.get(), timeout=1)
    return bool(message.data["connected"])


async def test_connects_after_two_failures_with_backoff(
    db_engine: Engine, clock: FakeClock
) -> None:
    fake = FakeDocker()
    fake.add(WEB)
    attempts = 0

    def make_client() -> FakeDocker:
        nonlocal attempts
        attempts += 1
        fake.fail = attempts <= 2
        return fake

    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    subscription = bus.subscribe([Topic.DOCKER])
    start = clock.now()
    task = asyncio.create_task(keep_connected(make_client, inventory, bus, state))
    try:
        states = [await next_docker_state(subscription) for _ in range(4)]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert states == [False, False, False, True]
    assert clock.now() - start == timedelta(seconds=1 + 2)
    assert state.connected is True
    assert inventory.get("web") is not None


async def test_stream_end_gives_disconnected_then_a_new_sync(
    db_engine: Engine, clock: FakeClock
) -> None:
    fake = FakeDocker()
    fake.add(WEB)
    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    subscription = bus.subscribe([Topic.DOCKER])
    task = asyncio.create_task(keep_connected(lambda: fake, inventory, bus, state))
    try:
        assert await next_docker_state(subscription) is False
        assert await next_docker_state(subscription) is True

        fake.remove("id-1")
        fake.end_stream()

        assert await next_docker_state(subscription) is False
        assert await next_docker_state(subscription) is True
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert inventory.get("web") is None


async def test_backoff_stops_at_60_seconds(db_engine: Engine, clock: FakeClock) -> None:
    fake = FakeDocker()
    fake.fail = True
    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    subscription = bus.subscribe([Topic.DOCKER])
    start = clock.now()
    task = asyncio.create_task(keep_connected(lambda: fake, inventory, bus, state))
    try:
        for _ in range(10):
            await next_docker_state(subscription)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    # 1 + 2 + 4 + 8 + 16 + 32 + 60 + 60 + 60 seconds before the 10th message.
    assert clock.now() - start == timedelta(seconds=243)
    assert state.connected is False


async def test_listener_gets_the_infos_after_each_sync(
    db_engine: Engine, clock: FakeClock
) -> None:
    fake = FakeDocker()
    fake.add(WEB)
    synced: list[list[str]] = []

    class Listener:
        def on_sync(self, infos: list[ContainerInfo]) -> None:
            synced.append([info.name for info in infos])

        async def on_event(self, event: DockerEvent) -> None:
            return None

    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    subscription = bus.subscribe([Topic.DOCKER])
    task = asyncio.create_task(
        keep_connected(lambda: fake, inventory, bus, state, Listener())
    )
    try:
        while not await next_docker_state(subscription):
            pass
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert synced == [["web"]]


async def test_each_connect_is_logged(
    db_engine: Engine, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    # The log shows "not available" at a failure, so it must also show the connect after it.
    fake = FakeDocker()
    attempts = 0

    def make_client() -> FakeDocker:
        nonlocal attempts
        attempts += 1
        fake.fail = attempts == 1
        return fake

    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    subscription = bus.subscribe([Topic.DOCKER])
    caplog.set_level("INFO", logger="wt.docker.connection")
    task = asyncio.create_task(keep_connected(make_client, inventory, bus, state))
    try:
        while not await next_docker_state(subscription):
            pass
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    messages = [(r.levelname, r.getMessage()) for r in caplog.records]
    assert messages[0][0] == "WARNING"
    assert messages[1] == ("INFO", "Connected to Docker")
