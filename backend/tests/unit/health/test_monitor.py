"""Tests for wt.health.monitor (clock)."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from wt.bus import Bus, Topic
from wt.clock import FakeClock
from wt.config import Settings, save_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, Event, EventKind
from wt.docker.client import ContainerInfo, DockerEvent
from wt.health.monitor import TICK_SECONDS, HealthMonitor, run_health

pytestmark = pytest.mark.anyio


def add_container(engine: Engine, name: str = "web") -> None:
    with Session(engine) as session:
        session.add(Container(host_id=LOCAL_HOST_ID, name=name))
        session.commit()


def event_rows(engine: Engine) -> list[tuple[str, EventKind]]:
    with Session(engine) as session:
        statement = (
            select(Container.name, Event.kind).join(Container).order_by(col(Event.id))
        )
        return [(name, EventKind(kind)) for name, kind in session.exec(statement)]


async def restart(monitor: HealthMonitor, clock: FakeClock) -> None:
    await monitor.on_event(DockerEvent("die", "id-1", "web", clock.now(), None))
    clock.advance(1)
    await monitor.on_event(DockerEvent("start", "id-1", "web", clock.now(), None))
    clock.advance(10)


async def test_restart_loop_then_quiet_gives_two_event_rows(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_container(db_engine)
    monitor = HealthMonitor(db_engine, Settings())
    for _ in range(3):
        await restart(monitor, clock)

    await monitor.tick()
    clock.advance(timedelta(minutes=10).total_seconds())
    await monitor.tick()

    assert event_rows(db_engine) == [
        ("web", EventKind.RESTART_LOOP),
        ("web", EventKind.RECOVERED_LOOP),
    ]


async def test_health_events_are_saved(db_engine: Engine, clock: FakeClock) -> None:
    add_container(db_engine)
    monitor = HealthMonitor(db_engine, Settings())

    await monitor.on_event(
        DockerEvent("health_status", "id-1", "web", clock.now(), "unhealthy")
    )
    await monitor.on_event(
        DockerEvent("health_status", "id-1", "web", clock.now(), "healthy")
    )

    assert event_rows(db_engine) == [
        ("web", EventKind.BECAME_UNHEALTHY),
        ("web", EventKind.RECOVERED_HEALTH),
    ]


async def test_on_sync_sets_the_baseline_and_skips_excluded(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_container(db_engine)
    add_container(db_engine, "secret")
    monitor = HealthMonitor(db_engine, Settings())

    monitor.on_sync(
        [
            ContainerInfo("id-1", "web", "x", {}, "running", "unhealthy", False),
            ContainerInfo(
                "id-2",
                "secret",
                "x",
                {"wt.enable": "false"},
                "running",
                "unhealthy",
                False,
            ),
        ]
    )
    await monitor.on_event(
        DockerEvent("health_status", "id-1", "web", clock.now(), "healthy")
    )
    await monitor.on_event(
        DockerEvent("health_status", "id-2", "secret", clock.now(), "healthy")
    )

    assert event_rows(db_engine) == [("web", EventKind.RECOVERED_HEALTH)]


async def test_new_settings_change_n(db_engine: Engine, clock: FakeClock) -> None:
    add_container(db_engine)
    monitor = HealthMonitor(db_engine, Settings())

    monitor.settings = Settings(restart_count=2)
    for _ in range(2):
        await restart(monitor, clock)

    assert event_rows(db_engine) == [("web", EventKind.RESTART_LOOP)]


async def test_worker_ticks_every_30_seconds_and_reloads_on_settings(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_container(db_engine)
    bus = Bus()
    monitor = HealthMonitor(db_engine, Settings())
    for _ in range(3):
        await restart(monitor, clock)
    start = clock.now()
    task = asyncio.create_task(run_health(monitor, db_engine, bus))
    try:
        while bus.subscriber_count == 0:
            await asyncio.sleep(0)  # noqa: TID251  (let the worker subscribe)
        save_settings(db_engine, Settings(restart_window_minutes=1))
        bus.publish(Topic.SETTINGS)
        async with asyncio.timeout(5):
            while len(event_rows(db_engine)) < 2:
                await asyncio.sleep(0.01)  # noqa: TID251  (real wait for the worker)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert monitor.settings.restart_window_minutes == 1
    assert (clock.now() - start).total_seconds() % TICK_SECONDS == 0
    assert event_rows(db_engine)[-1] == ("web", EventKind.RECOVERED_LOOP)


async def test_change_for_a_container_with_no_row_is_not_saved(
    db_engine: Engine, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    monitor = HealthMonitor(db_engine, Settings())

    await monitor.on_event(
        DockerEvent("health_status", "id-1", "ghost", clock.now(), "unhealthy")
    )

    assert event_rows(db_engine) == []
    assert "No container row for ghost" in caplog.text


async def test_on_change_gets_each_change_with_the_settings(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_container(db_engine)
    changes: list[tuple[str, EventKind, int]] = []

    async def on_change(name: str, kind: EventKind, settings: Settings) -> None:
        changes.append((name, kind, settings.restart_count))

    monitor = HealthMonitor(db_engine, Settings(), on_change=on_change)

    await monitor.on_event(
        DockerEvent("health_status", "id-1", "web", clock.now(), "unhealthy")
    )
    await monitor.on_event(
        DockerEvent("health_status", "id-1", "web", clock.now(), "unhealthy")
    )

    assert changes == [("web", EventKind.BECAME_UNHEALTHY, 3)]
