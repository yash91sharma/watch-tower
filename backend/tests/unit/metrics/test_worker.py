"""Tests for wt.metrics.worker (the poll loop of the sampler)."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import Engine

from tests.fake_docker import FakeDocker
from wt import clock
from wt.bus import Bus, Topic
from wt.clock import FakeClock
from wt.config import Settings, save_settings
from wt.docker.client import DockerApi
from wt.metrics.worker import run_metrics

pytestmark = pytest.mark.anyio


class Polls:
    """A poll function that records the time and the client of each poll."""

    def __init__(self, results: list[bool] | None = None) -> None:
        self.times: list[datetime] = []
        self.clients: list[DockerApi] = []
        self._results = results or []
        self._waiters: dict[int, asyncio.Event] = {}

    async def __call__(self, docker: DockerApi) -> bool:
        self.times.append(clock.now())
        self.clients.append(docker)
        for count, event in self._waiters.items():
            if len(self.times) >= count:
                event.set()
        return self._results.pop(0) if self._results else True

    async def wait_for(self, count: int) -> None:
        event = self._waiters.setdefault(count, asyncio.Event())
        if len(self.times) >= count:
            event.set()
        await asyncio.wait_for(event.wait(), timeout=5)

    def gaps(self) -> list[float]:
        return [(b - a).total_seconds() for a, b in zip(self.times, self.times[1:])]


class Clients:
    """Makes FakeDocker clients and keeps them."""

    def __init__(self) -> None:
        self.made: list[FakeDocker] = []

    def __call__(self) -> FakeDocker:
        self.made.append(FakeDocker())
        return self.made[-1]


async def test_the_worker_polls_at_the_interval_of_the_settings(
    db_engine: Engine, clock: FakeClock
) -> None:
    polls, bus = Polls(), Bus()
    save_settings(db_engine, Settings(metrics_interval_seconds=15))
    task = asyncio.create_task(run_metrics(polls, Clients(), db_engine, bus))
    await polls.wait_for(3)
    task.cancel()

    assert polls.gaps()[:2] == [15.0, 15.0]


async def test_a_settings_change_changes_the_interval(
    db_engine: Engine, clock: FakeClock
) -> None:
    polls, bus = Polls(), Bus()
    task = asyncio.create_task(run_metrics(polls, Clients(), db_engine, bus))
    await polls.wait_for(2)

    save_settings(db_engine, Settings(metrics_interval_seconds=60))
    bus.publish(Topic.SETTINGS)
    # The fake clock does not wait, so some polls can come before the settings reload.
    async with asyncio.timeout(5):
        while polls.gaps()[-1] != 60.0:
            await polls.wait_for(len(polls.times) + 1)
    task.cancel()

    assert polls.gaps()[0] == 10.0


async def test_a_failed_poll_makes_a_new_client(
    db_engine: Engine, clock: FakeClock
) -> None:
    polls, clients = Polls(results=[False]), Clients()
    task = asyncio.create_task(run_metrics(polls, clients, db_engine, Bus()))
    await polls.wait_for(2)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert polls.clients[0] is clients.made[0]
    assert polls.clients[1] is clients.made[1]
    assert clients.made[0].closed


async def test_a_cancel_closes_the_client(db_engine: Engine, clock: FakeClock) -> None:
    polls, clients = Polls(), Clients()
    task = asyncio.create_task(run_metrics(polls, clients, db_engine, Bus()))
    await polls.wait_for(1)

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert [client.closed for client in clients.made] == [True]
