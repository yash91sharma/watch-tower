"""Tests for wt.db.cleanup."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.clock import FakeClock
from wt.db import LOCAL_HOST_ID, cleanup
from wt.db.models import AuthSession, Container, Event, EventKind


def add_rows(engine: Engine, clock: FakeClock) -> None:
    now = clock.now()
    with Session(engine) as session:
        container = Container(host_id=LOCAL_HOST_ID, name="app")
        session.add(container)
        session.commit()
        assert container.id is not None
        for days in (8, 6):
            session.add(
                Event(
                    container_id=container.id,
                    kind=EventKind.RESTART_LOOP,
                    time=now - timedelta(days=days),
                )
            )
        for name, expires in (
            ("expired", now - timedelta(seconds=1)),
            ("valid", now + timedelta(days=1)),
        ):
            session.add(
                AuthSession(
                    token_hash=name,
                    created=now - timedelta(days=30),
                    expires=expires,
                    last_seen=now,
                )
            )
        session.commit()


def test_old_events_and_expired_sessions_go(
    db_engine: Engine, clock: FakeClock
) -> None:
    add_rows(db_engine, clock)

    cleanup.delete_old_rows(db_engine)

    with Session(db_engine) as session:
        event_ages = [clock.now() - event.time for event in session.exec(select(Event))]
        sessions = [row.token_hash for row in session.exec(select(AuthSession))]
    assert event_ages == [timedelta(days=6)]
    assert sessions == ["valid"]


@pytest.mark.anyio
async def test_worker_runs_at_start_and_each_hour(
    db_engine: Engine, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.now()
    run_times: list[timedelta] = []
    two_runs = asyncio.Event()
    loop = asyncio.get_running_loop()

    # The worker calls this in a thread.
    def fake_delete(engine: Engine) -> None:
        run_times.append(clock.now() - start)
        if len(run_times) == 2:
            loop.call_soon_threadsafe(two_runs.set)

    monkeypatch.setattr(cleanup, "delete_old_rows", fake_delete)

    task = asyncio.create_task(cleanup.run(db_engine))
    await two_runs.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert run_times[:2] == [timedelta(0), timedelta(hours=1)]
