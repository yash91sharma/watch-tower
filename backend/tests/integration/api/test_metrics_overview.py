"""Tests for GET /api/metrics/overview."""

from dataclasses import replace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from tests.factories import make_info
from wt.context import AppContext
from wt.metrics.calc import ContainerValues
from wt.metrics.vm import VmValues

pytestmark = pytest.mark.anyio

GIB = 1024**3


def values(cpu: float | None, mem: int, rx: float | None = 100.0) -> ContainerValues:
    return ContainerValues(
        cpu_percent=cpu,
        cpus=10,
        mem_used=mem,
        mem_limit=8 * GIB,
        net_rx_bps=rx,
        net_tx_bps=None,
        disk_read_bps=0.0,
        disk_write_bps=None,
    )


VM = VmValues(
    cpu_percent=25.0,
    cores=10,
    mem_used=2 * GIB,
    mem_total=8 * GIB,
    swap_used=0,
    swap_total=GIB,
    load_1=0.5,
    load_5=0.4,
    load_15=0.3,
    uptime_seconds=3700.0,
    disk_used=50 * GIB,
    disk_total=100 * GIB,
    disk_read_bps=1024.0,
    disk_write_bps=None,
)


@pytest.fixture
async def ctx(app: FastAPI) -> AppContext:
    context: AppContext = app.state.ctx
    for item in [
        make_info("web", project="site"),
        make_info("api", project="site"),
        make_info("db", project="data", state="exited"),
        make_info("tool"),
        make_info("cron"),
        make_info("secret", project="site", excluded=True),
    ]:
        await context.inventory.update(item)
    return context


async def get(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/metrics/overview")
    assert response.status_code == 200
    return response.json()


async def test_before_the_first_poll_there_are_no_values(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    body = await get(user_client)

    # Only the values that the UI shows.
    assert set(body) == {"vm", "counts", "groups", "ranges"}
    assert body["vm"] is None
    web = body["groups"][1]["containers"][1]
    assert web["name"] == "web"
    assert web["cpu_label"] == "-"


async def test_counts_and_groups_in_the_order_of_the_container_list(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    body = await get(user_client)

    # 2 projects, and 2 containers with no project: 4 apps. The excluded one is not counted.
    assert body["counts"] == {
        "apps_label": "4 apps",
        "containers_label": "4 running of 5 containers",
    }
    assert [g["label"] for g in body["groups"]] == ["data", "site", "Other"]
    assert [c["name"] for c in body["groups"][2]["containers"]] == ["cron", "tool"]
    assert [r["key"] for r in body["ranges"]] == ["1h", "6h", "24h", "7d", "30d"]
    assert body["ranges"][0]["label"] == "1 hour"


async def test_current_values_with_labels_and_group_sums(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    ctx.sampler.containers = {
        "web": values(cpu=9.09, mem=GIB),
        "api": values(cpu=None, mem=GIB // 2, rx=None),
        "tool": values(cpu=0.5, mem=1024),
    }
    ctx.sampler.vm = VM

    body = await get(user_client)

    site = body["groups"][1]
    assert site["cpu_label"] == "9.1% (0.91 core)"
    assert site["mem_label"] == "1.5 GiB"
    web = site["containers"][1]
    assert web == {
        "name": "web",
        "state": "running",
        "cpu_label": "9.1% (0.91 core)",
        "mem_label": "1.0 / 8.0 GiB",
        "mem_used_label": "1.0 GiB",
        "net_rx_label": "100 B/s",
        "net_tx_label": "-",
        "disk_read_label": "0 B/s",
        "disk_write_label": "-",
    }
    # A stopped container has no values.
    db = body["groups"][0]
    assert db["cpu_label"] == "-"
    assert db["mem_label"] == "-"
    assert db["containers"][0]["mem_label"] == "-"
    assert db["containers"][0]["mem_used_label"] == "-"


async def test_the_vm_values(user_client: httpx.AsyncClient, ctx: AppContext) -> None:
    ctx.sampler.containers = {
        "web": values(cpu=1.0, mem=GIB),
        "tool": values(cpu=1.0, mem=GIB),
    }
    ctx.sampler.vm = VM

    vm = (await get(user_client))["vm"]

    assert vm == {
        "cpu_percent": 25.0,
        "cpu_label": "25% (2.5 cores)",
        "mem_percent": 25.0,
        "mem_label": "2.0 / 8.0 GiB",
        "containers_mem_label": "2.0 GiB",
        "swap_percent": 0.0,
        "swap_label": "0 B / 1.0 GiB",
        "disk_percent": 50.0,
        "disk_label": "50.0 / 100.0 GiB",
        "disk_read_label": "1.0 KiB/s",
        "disk_write_label": "-",
        "net_rx_label": "200 B/s",
        "net_tx_label": "-",
        "load_label": "0.50 / 0.40 / 0.30",
        "uptime_label": "1 h 1 min",
    }


async def test_a_vm_with_no_swap(
    user_client: httpx.AsyncClient, ctx: AppContext
) -> None:
    ctx.sampler.vm = replace(VM, swap_total=0, cpu_percent=None)

    vm = (await get(user_client))["vm"]

    assert vm["swap_percent"] is None
    assert vm["swap_label"] == "0 / 0 B"
    assert vm["cpu_label"] == "-"


async def test_one_app_and_no_vm_values(
    user_client: httpx.AsyncClient, app: FastAPI
) -> None:
    context: AppContext = app.state.ctx
    await context.inventory.update(make_info("web", project="site"))
    # WT cannot read the VM: the cores come from the container.
    context.sampler.containers = {"web": values(cpu=20.0, mem=GIB)}

    body = await get(user_client)

    assert body["counts"]["apps_label"] == "1 app"
    assert body["vm"] is None
    assert body["groups"][0]["cpu_label"] == "20% (2.0 cores)"


async def test_the_route_needs_a_session(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/metrics/overview")

    assert response.status_code == 401
