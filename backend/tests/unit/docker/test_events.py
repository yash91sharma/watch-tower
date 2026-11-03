"""Tests for wt.docker.events with FakeDocker."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from wt.bus import Bus, Message, Topic
from wt.docker.client import ContainerInfo, DockerEvent
from wt.docker.events import follow_events, handle_event
from wt.docker.fake import FakeDocker
from wt.docker.inventory import Inventory

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 1, 1, tzinfo=UTC)
WEB = ContainerInfo("id-1", "web", "nginx:1", {}, "running", "healthy", False, 0)


def event(
    action: str, docker_id: str = "id-1", health: str | None = None
) -> DockerEvent:
    return DockerEvent(action, docker_id, "web", T0, health)


async def test_start_event_updates_the_inventory_and_publishes(
    db_engine: Engine,
) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(WEB)
    subscription = bus.subscribe()

    await handle_event(event("start"), docker, inventory, bus)

    live = inventory.get("web")
    assert live is not None and live.state == "running"
    assert await subscription.get() == Message(Topic.CONTAINER, {"name": "web"})


async def test_health_event_reads_the_new_health(db_engine: Engine) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(WEB)
    await inventory.sync_all(docker)
    docker.add(replace(WEB, health="unhealthy"))

    await handle_event(
        event("health_status", health="unhealthy"), docker, inventory, bus
    )

    live = inventory.get("web")
    assert live is not None and live.health == "unhealthy"


async def test_destroy_removes_the_container_and_publishes(db_engine: Engine) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(WEB)
    await inventory.sync_all(docker)
    subscription = bus.subscribe()

    await handle_event(event("destroy"), docker, inventory, bus)

    assert inventory.get("web") is None
    assert await subscription.get() == Message(Topic.CONTAINER, {"name": "web"})


async def test_destroy_with_an_old_docker_id_keeps_the_new_container(
    db_engine: Engine,
) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(replace(WEB, id="id-new"))
    await inventory.sync_all(docker)
    subscription = bus.subscribe()

    await handle_event(event("destroy", docker_id="id-old"), docker, inventory, bus)

    live = inventory.get("web")
    assert live is not None and live.docker_id == "id-new"
    assert subscription.empty()


async def test_event_for_a_container_that_is_gone_is_skipped(db_engine: Engine) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    subscription = bus.subscribe()

    await handle_event(event("die"), docker, inventory, bus)

    assert subscription.empty()


async def test_event_for_an_excluded_container_publishes_nothing(
    db_engine: Engine,
) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(replace(WEB, labels={"wt.enable": "false"}))
    subscription = bus.subscribe()

    await handle_event(event("start"), docker, inventory, bus)

    assert subscription.empty()


async def test_follow_events_handles_events_until_the_stream_ends(
    db_engine: Engine,
) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(WEB)
    docker.emit(event("start"))
    docker.emit(event("die"))
    docker.end_stream()
    subscription = bus.subscribe()

    await follow_events(docker, inventory, bus)

    assert [(await subscription.get()).data for _ in range(2)] == [{"name": "web"}] * 2


class RecordingListener:
    def __init__(self) -> None:
        self.synced: list[list[ContainerInfo]] = []
        self.events: list[DockerEvent] = []

    def on_sync(self, infos: list[ContainerInfo]) -> None:
        self.synced.append(infos)

    async def on_event(self, event: DockerEvent) -> None:
        self.events.append(event)


async def test_listener_gets_events_but_not_for_excluded_containers(
    db_engine: Engine,
) -> None:
    docker, inventory, bus = FakeDocker(), Inventory(db_engine), Bus()
    docker.add(WEB)
    docker.add(replace(WEB, id="id-2", name="secret", labels={"wt.enable": "false"}))
    listener = RecordingListener()

    await handle_event(event("start"), docker, inventory, bus, listener)
    await handle_event(
        DockerEvent("start", "id-2", "secret", T0, None),
        docker,
        inventory,
        bus,
        listener,
    )
    await handle_event(event("destroy"), docker, inventory, bus, listener)

    assert [(item.action, item.name) for item in listener.events] == [
        ("start", "web"),
        ("destroy", "web"),
    ]
