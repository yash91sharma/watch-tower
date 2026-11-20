"""Tests for GET /api/metrics/vm/history and /api/metrics/containers/{name}/history."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session

from tests.factories import make_info
from wt.clock import FakeClock
from wt.context import AppContext
from wt.db import LOCAL_HOST_ID, find_container
from wt.db.models import ContainerSample, MetricTier, VmSample

pytestmark = pytest.mark.anyio

# The time of the tests: 2026-01-31 12:07:30 UTC.
NOW = datetime(2026, 1, 31, 12, 7, 30, tzinfo=UTC)


@pytest.fixture
async def ctx(app: FastAPI, clock: FakeClock) -> AppContext:
    context: AppContext = app.state.ctx
    await context.inventory.update(make_info("web", project="site"))
    clock.set(NOW)
    return context


def vm_row(tier: MetricTier, time: datetime, cpu: float | None) -> VmSample:
    return VmSample(
        host_id=LOCAL_HOST_ID,
        tier=tier,
        time=time,
        cpu_percent=cpu,
        mem_used=100,
        mem_total=1000,
        swap_used=0,
        swap_total=0,
        load_1=1.0,
        load_5=2.0,
        load_15=3.0,
        disk_used=1,
        disk_total=2,
        disk_read_bps=10.0,
        disk_write_bps=None,
        net_rx_bps=5.0,
        net_tx_bps=6.0,
    )


def container_row(
    ctx: AppContext, tier: MetricTier, time: datetime, limit: int
) -> ContainerSample:
    with Session(ctx.engine) as session:
        row = find_container(session, "web")
        assert row is not None and row.id is not None
        container_id = row.id
    return ContainerSample(
        container_id=container_id,
        tier=tier,
        time=time,
        cpu_percent=2.0,
        mem_used=300,
        mem_limit=limit,
        net_rx_bps=1.0,
        net_tx_bps=None,
        disk_read_bps=None,
        disk_write_bps=4.0,
    )


def add(ctx: AppContext, *rows: VmSample | ContainerSample) -> None:
    with Session(ctx.engine) as session:
        session.add_all(rows)
        session.commit()


async def get(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def chart(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in body["charts"] if item["key"] == key)


async def test_vm_history_of_1h_has_60_minute_slots(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    end = NOW.replace(second=0)  # 12:07
    add(
        ctx,
        vm_row(MetricTier.MINUTE, end - timedelta(minutes=60), cpu=1.0),
        vm_row(MetricTier.MINUTE, end - timedelta(minutes=1), cpu=None),
        # Not in the window: too old, the current minute, another tier.
        vm_row(MetricTier.MINUTE, end - timedelta(minutes=61), cpu=9.0),
        vm_row(MetricTier.MINUTE, end, cpu=9.0),
        vm_row(MetricTier.QUARTER, end - timedelta(minutes=30), cpu=9.0),
    )

    body = await get(user_client, "/api/metrics/vm/history?range=1h")

    assert body["range"] == "1h"
    assert body["step_seconds"] == 60
    assert len(body["times"]) == 60
    assert body["times"][0] == int((end - timedelta(minutes=60)).timestamp())
    assert body["times"][1] - body["times"][0] == 60
    assert [c["key"] for c in body["charts"]] == [
        "cpu",
        "memory",
        "disk_io",
        "network",
        "load",
    ]
    cpu = chart(body, "cpu")
    assert cpu["title"] == "CPU"
    assert cpu["unit"] == "percent"
    assert cpu["max"] == 100
    [series] = cpu["series"]
    assert series["label"] == "CPU"
    assert series["values"][0] == 1.0
    assert series["values"][1:] == [None] * 59
    memory = chart(body, "memory")
    assert memory["unit"] == "bytes"
    assert memory["max"] == 1000
    assert [s["label"] for s in chart(body, "disk_io")["series"]] == ["Read", "Write"]
    assert [s["label"] for s in chart(body, "network")["series"]] == ["In", "Out"]
    load = chart(body, "load")
    assert [s["label"] for s in load["series"]] == ["1 min", "5 min", "15 min"]
    assert [s["values"][0] for s in load["series"]] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    ("range_key", "tier", "step", "slots", "end"),
    [
        ("6h", MetricTier.MINUTE, 60, 360, datetime(2026, 1, 31, 12, 7, tzinfo=UTC)),
        ("24h", MetricTier.MINUTE, 60, 1440, datetime(2026, 1, 31, 12, 7, tzinfo=UTC)),
        ("7d", MetricTier.QUARTER, 900, 672, datetime(2026, 1, 31, 12, 0, tzinfo=UTC)),
        ("30d", MetricTier.HOUR, 3600, 720, datetime(2026, 1, 31, 12, 0, tzinfo=UTC)),
    ],
)
async def test_each_range_reads_its_tier(
    user_client: httpx.AsyncClient,
    ctx: AppContext,
    range_key: str,
    tier: MetricTier,
    step: int,
    slots: int,
    end: datetime,
) -> None:
    add(ctx, vm_row(tier, end - timedelta(seconds=step), cpu=7.0))

    body = await get(user_client, f"/api/metrics/vm/history?range={range_key}")

    assert body["step_seconds"] == step
    assert len(body["times"]) == slots
    assert body["times"][-1] == int(end.timestamp()) - step
    assert chart(body, "cpu")["series"][0]["values"][-1] == 7.0


async def test_vm_history_with_no_rows_has_no_memory_max(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    body = await get(user_client, "/api/metrics/vm/history?range=1h")

    assert chart(body, "memory")["max"] is None
    assert body["empty_label"] == "No values in this range."


@pytest.mark.parametrize(
    ("range_key", "label"),
    [
        (
            "7d",
            (
                "No values in this range. It shows 15-minute averages: "
                "WT makes one after each full 15 minutes."
            ),
        ),
        (
            "30d",
            (
                "No values in this range. It shows 1-hour averages: "
                "WT makes one after each full hour."
            ),
        ),
    ],
)
async def test_an_empty_long_range_says_when_its_values_come(
    user_client: httpx.AsyncClient, ctx: AppContext, range_key: str, label: str
) -> None:
    # 1-minute values do not show in the 7 d and 30 d ranges.
    add(ctx, vm_row(MetricTier.MINUTE, NOW.replace(second=0) - timedelta(minutes=1), 5))

    vm = await get(user_client, f"/api/metrics/vm/history?range={range_key}")
    web = await get(
        user_client, f"/api/metrics/containers/web/history?range={range_key}"
    )

    assert vm["empty_label"] == label
    assert web["empty_label"] == label


async def test_a_bad_range_is_a_validation_error(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    response = await user_client.get("/api/metrics/vm/history?range=2h")

    assert response.status_code == 422


async def test_container_history(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    end = NOW.replace(second=0)
    add(
        ctx,
        container_row(ctx, MetricTier.MINUTE, end - timedelta(minutes=2), limit=1000),
        container_row(ctx, MetricTier.MINUTE, end - timedelta(minutes=1), limit=2000),
    )

    body = await get(user_client, "/api/metrics/containers/web/history?range=1h")

    assert [c["key"] for c in body["charts"]] == ["cpu", "memory", "network", "disk_io"]
    assert chart(body, "cpu")["series"][0]["values"][-2:] == [2.0, 2.0]
    # The memory max is the last limit.
    assert chart(body, "memory")["max"] == 2000
    assert chart(body, "memory")["series"][0]["values"][-1] == 300
    assert chart(body, "network")["series"][1]["values"][-1] is None
    assert chart(body, "disk_io")["series"][1]["values"][-1] == 4.0
    assert body["empty_label"] is None


async def test_the_container_history_stays_after_a_recreate(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    end = NOW.replace(second=0)
    add(ctx, container_row(ctx, MetricTier.MINUTE, end - timedelta(minutes=1), limit=1))
    # Compose makes a new container with a new id and the same name.
    await ctx.inventory.update(make_info("web", project="site", docker_id="new-id"))

    body = await get(user_client, "/api/metrics/containers/web/history?range=1h")

    assert chart(body, "cpu")["series"][0]["values"][-1] == 2.0


async def test_an_unknown_container_is_404(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    response = await user_client.get("/api/metrics/containers/nope/history?range=1h")

    assert response.status_code == 404
