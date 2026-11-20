"""Tests for GET /api/metrics/sparklines."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session

from tests.factories import make_info
from wt.clock import FakeClock
from wt.context import AppContext
from wt.db import find_container
from wt.db.models import ContainerSample, MetricTier

pytestmark = pytest.mark.anyio

# The clock fixture starts here. The test sets the time to 01:00:30, so the 60 slots
# are the minutes 00:00 to 00:59.
T0 = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def ctx(app: FastAPI, clock: FakeClock) -> AppContext:
    context: AppContext = app.state.ctx
    for item in [
        make_info("web", project="site"),
        make_info("api", project="site", state="exited"),
        make_info("tool"),
        make_info("secret", project="site", excluded=True),
    ]:
        await context.inventory.update(item)
    clock.set(T0 + timedelta(hours=1, seconds=30))
    return context


def add(
    ctx: AppContext,
    name: str,
    minute: int,
    cpu: float | None,
    mem: int,
    tier: MetricTier = MetricTier.MINUTE,
) -> None:
    with Session(ctx.engine) as session:
        row = find_container(session, name)
        assert row is not None and row.id is not None
        session.add(
            ContainerSample(
                container_id=row.id,
                tier=tier,
                time=T0 + timedelta(minutes=minute),
                cpu_percent=cpu,
                mem_used=mem,
                mem_limit=1000,
                net_rx_bps=None,
                net_tx_bps=None,
                disk_read_bps=None,
                disk_write_bps=None,
            )
        )
        session.commit()


async def get(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/metrics/sparklines")
    assert response.status_code == 200
    return response.json()


async def test_60_minute_slots_with_null_for_a_gap(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    add(ctx, "web", 0, cpu=1.0, mem=100)
    add(ctx, "web", 59, cpu=3.0, mem=300)
    # Not in the window: before the first slot, the current minute, another tier.
    add(ctx, "web", -1, cpu=9.0, mem=900)
    add(ctx, "web", 60, cpu=9.0, mem=900)
    add(ctx, "web", 30, cpu=9.0, mem=900, tier=MetricTier.QUARTER)

    body = await get(user_client)

    assert body["start"] == "2026-01-01T00:00:00Z"
    web = body["containers"]["web"]
    assert len(web["cpu"]) == len(web["mem"]) == 60
    assert web["cpu"][0] == 1.0
    assert web["cpu"][59] == 3.0
    assert web["cpu"][1:59] == [None] * 58
    assert web["mem"][0] == 100
    assert web["mem"][30] is None


async def test_all_shown_containers_and_no_group_lines(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    body = await get(user_client)

    # The UI shows no group sparklines, so the API sends none.
    assert set(body) == {"start", "containers"}
    # All shown containers, also a stopped one. Not the excluded one.
    assert set(body["containers"]) == {"web", "api", "tool"}
    assert body["containers"]["tool"]["cpu"] == [None] * 60
