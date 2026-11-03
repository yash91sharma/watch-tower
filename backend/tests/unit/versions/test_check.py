"""Tests for the check run in wt.versions.check (respx, clock)."""

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import Engine
from sqlmodel import Session

from wt.clock import FakeClock
from wt.config import Env
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, Setting
from wt.docker.client import ContainerInfo
from wt.docker.inventory import Inventory
from wt.versions.check import CheckRunner, load_check_status

pytestmark = pytest.mark.anyio

API = "http://github.test"
SOURCE = "org.opencontainers.image.source"


def latest(tag: str) -> httpx.Response:
    return httpx.Response(
        200, json={"tag_name": tag, "body": f"Notes {tag}"}, headers={"ETag": '"e"'}
    )


async def add(
    inventory: Inventory, name: str, image: str, source: str | None, **labels: str
) -> None:
    all_labels = {SOURCE: f"https://github.com/{source}"} if source else {}
    all_labels.update(labels)
    await inventory.update(
        ContainerInfo(
            f"id-{name}", name, image, all_labels, "running", "none", False, 0
        )
    )


@pytest.fixture
async def runner(db_engine: Engine) -> CheckRunner:
    inventory = Inventory(db_engine)
    await add(inventory, "web1", "nginx:1.26", "nginx/nginx")
    await add(inventory, "web2", "nginx:1.27", "nginx/nginx")
    await add(inventory, "db", "postgres:16", "docker-library/postgres")
    await add(inventory, "nosrc", "app:1.0", None)
    await add(inventory, "rolling", "app:latest", "o/app")
    await add(inventory, "hidden", "app:1.0", "o/hidden", **{"wt.enable": "false"})
    return CheckRunner(
        db_engine, Env(data_dir=Path("."), github_api_url=API), inventory
    )


async def test_one_call_per_repo_and_saved_counts(
    runner: CheckRunner, db_engine: Engine, clock: FakeClock
) -> None:
    with respx.mock:
        nginx = respx.get(f"{API}/repos/nginx/nginx/releases/latest").mock(
            return_value=latest("1.27")
        )
        respx.get(f"{API}/repos/nginx/nginx/releases").mock(
            return_value=httpx.Response(200, json=[])
        )
        postgres = respx.get(
            f"{API}/repos/docker-library/postgres/releases/latest"
        ).mock(return_value=httpx.Response(500))

        assert await runner.run() is True

    assert nginx.call_count == 1
    assert postgres.call_count == 1
    status = load_check_status(db_engine)
    assert status.last_run == clock.now()
    assert status.counts == {
        "update": 1,
        "up to date": 1,
        "error": 1,
        "no source": 1,
        "no check": 1,
    }


async def test_a_second_run_during_a_run_does_not_start(
    runner: CheckRunner, db_engine: Engine, clock: FakeClock
) -> None:
    gate = asyncio.Event()

    async def slow(request: httpx.Request) -> httpx.Response:
        await gate.wait()
        return httpx.Response(404)

    with respx.mock:
        respx.get(url__regex=rf"{API}/repos/.*/releases/latest").mock(side_effect=slow)
        first = asyncio.create_task(runner.run())
        while not runner.running:
            await asyncio.sleep(0)  # noqa: TID251  (let the first run start)

        assert await runner.run() is False

        gate.set()
        assert await first is True
    assert runner.running is False


async def test_no_run_yet_gives_an_empty_status(db_engine: Engine) -> None:
    status = load_check_status(db_engine)

    assert (status.last_run, status.counts) == (None, {})


async def test_status_survives_a_new_runner(
    runner: CheckRunner, db_engine: Engine, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(url__regex=rf"{API}/repos/.*/releases/latest").mock(
            return_value=httpx.Response(404)
        )
        await runner.run()

    with Session(db_engine) as session:
        row = session.get(Setting, "check_status")
    assert row is not None
    value: dict[str, Any] = row.value
    assert value["last_run"] == clock.now().isoformat()


async def test_a_gone_container_is_not_checked(
    db_engine: Engine, clock: FakeClock
) -> None:
    with Session(db_engine) as session:
        session.add(
            Container(
                host_id=LOCAL_HOST_ID, name="gone", tag="1.0", release_source="o/gone"
            )
        )
        session.commit()
    runner = CheckRunner(
        db_engine, Env(data_dir=Path("."), github_api_url=API), Inventory(db_engine)
    )

    with respx.mock:
        route = respx.get(f"{API}/repos/o/gone/releases/latest")
        await runner.run()

    assert not route.called
