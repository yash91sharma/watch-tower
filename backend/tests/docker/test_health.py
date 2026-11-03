"""Docker test: health changes from the real test containers (task 7.5)."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from tests.docker.env import CRASH_FILE, OK_FILE, PROXY_URL, docker, wait_healthy
from wt.bus import Bus, Topic
from wt.clock import FakeClock
from wt.config import Settings
from wt.db.models import Container, Event, EventKind
from wt.docker.client import DockerClient
from wt.docker.connection import DockerState, keep_connected
from wt.docker.inventory import Inventory
from wt.health.monitor import HealthMonitor

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


def rows(engine: Engine) -> list[tuple[str, EventKind, datetime]]:
    with Session(engine) as session:
        statement = (
            select(Container.name, Event.kind, Event.time)
            .join(Container)
            .order_by(col(Event.id))
        )
        return [
            (name, EventKind(kind), time)
            for name, kind, time in session.exec(statement)
        ]


async def wait_for_row(engine: Engine, name: str, kind: EventKind) -> datetime:
    async with asyncio.timeout(30):
        while True:
            for row_name, row_kind, time in rows(engine):
                if (row_name, row_kind) == (name, kind):
                    return time
            await asyncio.sleep(0.2)  # noqa: TID251  (real wait for Docker)


async def test_unhealthy_and_restart_loop_give_the_changes(
    docker_env: dict[str, str], db_engine: Engine, clock: FakeClock
) -> None:
    url = PROXY_URL.replace("http://", "tcp://")
    inventory, bus, state = Inventory(db_engine), Bus(), DockerState()
    monitor = HealthMonitor(
        db_engine, Settings(restart_count=3, restart_window_minutes=1)
    )
    subscription = bus.subscribe([Topic.DOCKER])
    task = asyncio.create_task(
        keep_connected(lambda: DockerClient(url), inventory, bus, state, monitor)
    )
    try:
        while not (await subscription.get()).data["connected"]:
            pass

        await asyncio.to_thread(docker, "exec", "wt_test_unhealthy", "rm", OK_FILE)
        await wait_for_row(db_engine, "wt_test_unhealthy", EventKind.BECAME_UNHEALTHY)
        await asyncio.to_thread(docker, "exec", "wt_test_unhealthy", "touch", OK_FILE)
        await wait_for_row(db_engine, "wt_test_unhealthy", EventKind.RECOVERED_HEALTH)

        await asyncio.to_thread(
            docker, "exec", "wt_test_restart", "sh", "-c", f"echo 3 > {CRASH_FILE}"
        )
        loop_time = await wait_for_row(
            db_engine, "wt_test_restart", EventKind.RESTART_LOOP
        )
        await asyncio.to_thread(wait_healthy, ["wt_test_restart"])
        clock.set(loop_time + timedelta(minutes=1, seconds=10))
        await monitor.tick()
        await wait_for_row(db_engine, "wt_test_restart", EventKind.RECOVERED_LOOP)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.to_thread(docker, "exec", "wt_test_unhealthy", "touch", OK_FILE)
        await asyncio.to_thread(
            docker, "exec", "wt_test_restart", "rm", "-f", CRASH_FILE
        )
        await asyncio.to_thread(wait_healthy, ["wt_test_unhealthy", "wt_test_restart"])

    kinds = [(name, kind) for name, kind, _ in rows(db_engine)]
    assert kinds == [
        ("wt_test_unhealthy", EventKind.BECAME_UNHEALTHY),
        ("wt_test_unhealthy", EventKind.RECOVERED_HEALTH),
        ("wt_test_restart", EventKind.RESTART_LOOP),
        ("wt_test_restart", EventKind.RECOVERED_LOOP),
    ]
