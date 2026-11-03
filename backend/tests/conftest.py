"""Shared pytest fixtures."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from wt import clock as wt_clock
from wt.clock import Clock, FakeClock
from wt.db.engine import create_db_engine
from wt.db.migrate import upgrade


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests (`@pytest.mark.anyio`) on asyncio only."""
    return "asyncio"


@pytest.fixture
def clock() -> Iterator[FakeClock]:
    """Replace the clock with a fake clock at 2026-01-01 00:00 UTC."""
    fake = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    wt_clock.use(fake)
    yield fake
    wt_clock.use(Clock())


@pytest.fixture
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    """An engine for a new DB in a temp dir, upgraded to the newest revision."""
    engine = create_db_engine(tmp_path)
    upgrade(engine)
    yield engine
    engine.dispose()
