"""Tests for GET /api/containers."""

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session, select

from tests.factories import make_info
from wt.clock import FakeClock
from wt.context import AppContext
from wt.db.models import Container, RepoCache, Severity, Update
from wt.docker.client import ContainerInfo

pytestmark = pytest.mark.anyio

SOURCE = "org.opencontainers.image.source"


def info(
    name: str,
    image: str,
    project: str | None = None,
    health: str = "none",
    **labels: str,
) -> ContainerInfo:
    return make_info(name, image, labels=labels, project=project, health=health)


@pytest.fixture
async def ctx(app: FastAPI, clock: FakeClock) -> AppContext:
    context: AppContext = app.state.ctx
    for item in [
        info(
            "web",
            "nginx:1.26",
            "site",
            "healthy",
            **{SOURCE: "https://github.com/nginx/nginx"},
        ),
        info(
            "api", "app:2.0", "site", "starting", **{SOURCE: "https://github.com/o/app"}
        ),
        info("db", "postgres:16", "data", "unhealthy"),
        info("tool", "busybox:latest"),
        info("secret", "app:1.0", "site", **{"wt.enable": "false"}),
    ]:
        await context.inventory.update(item)
    with Session(context.engine) as session:
        session.add(
            RepoCache(repo="nginx/nginx", latest_tag="1.27", fetched_at=clock.now())
        )
        session.add(RepoCache(repo="o/app", error="HTTP 500", fetched_at=clock.now()))
        web = session.exec(select(Container).where(Container.name == "web")).one()
        assert web.id is not None
        session.add(
            Update(
                container_id=web.id,
                from_version="1.26",
                to_version="1.27",
                severity=Severity.CRITICAL,
                release_notes="notes",
            )
        )
        session.commit()
    return context


async def get_groups(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/api/containers")
    assert response.status_code == 200
    return response.json()


async def test_groups_sorted_with_other_last(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    groups = await get_groups(user_client)

    assert [(group["project"], group["label"]) for group in groups] == [
        ("data", "data"),
        ("site", "site"),
        (None, "Other"),
    ]
    assert [item["name"] for item in groups[1]["containers"]] == ["api", "web"]


async def test_excluded_container_is_absent(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    names = [
        item["name"]
        for group in await get_groups(user_client)
        for item in group["containers"]
    ]

    assert "secret" not in names


async def test_fields_per_status(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    items = {
        item["name"]: item
        for group in await get_groups(user_client)
        for item in group["containers"]
    }

    assert items["web"] == {
        "name": "web",
        "state": "running",
        "health": "healthy",
        "health_label": "healthy",
        "image": "nginx",
        "tag": "1.26",
        "status": "update",
        "status_label": "update available",
        "latest_version": "1.27",
        "latest_url": "https://github.com/nginx/nginx/releases/tag/1.27",
        "severity": "critical",
        "release_source": "nginx/nginx",
        "source_confirmed": False,
    }
    assert (
        items["api"]["status"],
        items["api"]["latest_version"],
        items["api"]["health"],
    ) == (
        "error",
        None,
        "starting",
    )
    assert (items["db"]["status"], items["db"]["severity"], items["db"]["health"]) == (
        "no source",
        None,
        "unhealthy",
    )
    assert (items["tool"]["status"], items["tool"]["health"]) == ("no check", "none")
    assert (items["tool"]["status_label"], items["tool"]["health_label"]) == (
        "no check",
        "no healthcheck",
    )


async def test_gone_container_is_absent(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    ctx.inventory.remove("db", "id-db")

    names = [
        item["name"]
        for group in await get_groups(user_client)
        for item in group["containers"]
    ]

    assert "db" not in names


async def test_live_container_with_no_db_row_is_absent(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    with Session(ctx.engine) as session:
        tool = session.exec(select(Container).where(Container.name == "tool")).one()
        session.delete(tool)
        session.commit()

    names = [
        item["name"]
        for group in await get_groups(user_client)
        for item in group["containers"]
    ]
    assert "tool" not in names
    assert "web" in names


async def test_group_update_level(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    levels = {
        group["label"]: group["update"] for group in await get_groups(user_client)
    }

    assert levels == {"data": "none", "site": "critical", "Other": "none"}

    with Session(ctx.engine) as session:
        update = session.exec(select(Update)).one()
        update.severity = Severity.NORMAL
        session.add(update)
        session.commit()
    levels = {
        group["label"]: group["update"] for group in await get_groups(user_client)
    }

    assert levels["site"] == "update"


async def test_no_latest_url_without_a_latest_version(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    items = {
        item["name"]: item
        for group in await get_groups(user_client)
        for item in group["containers"]
    }

    assert items["api"]["latest_url"] is None
    assert items["tool"]["latest_url"] is None


async def test_an_unknown_docker_health_shows_as_none(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    await ctx.inventory.update(info("odd", "busybox:latest", health="weird"))

    groups = await get_groups(user_client)

    items = {item["name"]: item for group in groups for item in group["containers"]}
    assert items["odd"]["health"] == "none"
