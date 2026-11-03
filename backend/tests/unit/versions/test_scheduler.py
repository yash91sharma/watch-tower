"""Tests for the check scheduler in wt.versions.scheduler (clock)."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from wt.clock import FakeClock
from wt.config import Settings, save_settings
from wt.db.models import Setting
from wt.versions.check import CHECK_STATUS_KEY
from wt.versions.scheduler import run_scheduler

pytestmark = pytest.mark.anyio


def save_last_run(engine: Engine, time: datetime) -> None:
    with Session(engine) as session:
        session.merge(
            Setting(
                key=CHECK_STATUS_KEY, value={"last_run": time.isoformat(), "counts": {}}
            )
        )
        session.commit()


class FakeRunner:
    """Records the run times and saves the last run, as the real runner does."""

    def __init__(self, engine: Engine, clock: FakeClock, runs: int) -> None:
        self.engine, self.clock, self.runs = engine, clock, runs
        self.times: list[datetime] = []
        self.done = asyncio.Event()
        self.on_run: list[Settings] = []

    async def run(self) -> bool:
        self.times.append(self.clock.now())
        save_last_run(self.engine, self.clock.now())
        if self.on_run:
            save_settings(self.engine, self.on_run.pop(0))
        if len(self.times) == self.runs:
            self.done.set()
        return True


async def times_of(runner: FakeRunner, engine: Engine) -> list[timedelta]:
    start = runner.clock.now()
    task = asyncio.create_task(run_scheduler(runner, engine))
    try:
        await asyncio.wait_for(runner.done.wait(), timeout=10)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    return [time - start for time in runner.times]


async def test_runs_at_start_when_there_is_no_last_run(
    db_engine: Engine, clock: FakeClock
) -> None:
    runner = FakeRunner(db_engine, clock, runs=1)

    assert await times_of(runner, db_engine) == [timedelta(0)]


async def test_runs_at_the_interval(db_engine: Engine, clock: FakeClock) -> None:
    runner = FakeRunner(db_engine, clock, runs=3)

    assert await times_of(runner, db_engine) == [
        timedelta(hours=hours) for hours in (0, 24, 48)
    ]


async def test_no_run_at_start_when_not_due(
    db_engine: Engine, clock: FakeClock
) -> None:
    save_last_run(db_engine, clock.now() - timedelta(hours=1))
    runner = FakeRunner(db_engine, clock, runs=1)

    assert await times_of(runner, db_engine) == [timedelta(hours=23)]


async def test_a_new_interval_takes_effect(db_engine: Engine, clock: FakeClock) -> None:
    runner = FakeRunner(db_engine, clock, runs=2)
    runner.on_run.append(Settings(check_interval_hours=6))

    assert await times_of(runner, db_engine) == [timedelta(0), timedelta(hours=6)]
