"""Shared pytest fixtures."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import Engine

from wt import clock as wt_clock
from wt.clock import Clock, FakeClock
from wt.config import Env
from wt.db import open_db
from wt.main import create_app


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
    """An engine for a new DB in a temp dir, opened as at WT start (all tables, local host)."""
    engine = open_db(tmp_path)
    yield engine
    engine.dispose()


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    """The app with a new DB and no workers. The lifespan runs."""
    app = create_app(Env(data_dir=tmp_path / "data"), workers=[])
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTPS client for the app (the session cookie is Secure)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://wt") as http:
        yield http
