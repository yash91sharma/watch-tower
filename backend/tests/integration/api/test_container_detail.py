"""Tests for GET /api/containers/{name}."""

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session, select

from tests.factories import make_info
from wt.clock import FakeClock
from wt.context import AppContext
from wt.db.models import Container, Event, EventKind, RepoCache, Severity, Update

pytestmark = pytest.mark.anyio

SOURCE = "org.opencontainers.image.source"


async def add(ctx: AppContext, name: str, image: str, **labels: str) -> int:
    await ctx.inventory.update(make_info(name, image, labels=labels, health="healthy"))
    with Session(ctx.engine) as session:
        row = session.exec(select(Container).where(Container.name == name)).one()
    assert row.id is not None
    return row.id


@pytest.fixture
async def ctx(app: FastAPI, clock: FakeClock) -> AppContext:
    context: AppContext = app.state.ctx
    web_id = await add(
        context, "web", "nginx:1.26", **{SOURCE: "https://github.com/nginx/nginx"}
    )
    await add(context, "db", "postgres:16")
    await add(context, "secret", "app:1", **{"wt.enable": "false"})
    now = clock.now()
    with Session(context.engine) as session:
        session.add(RepoCache(repo="nginx/nginx", latest_tag="1.27", fetched_at=now))
        session.add(
            Update(
                container_id=web_id,
                from_version="1.26",
                to_version="1.27",
                severity=Severity.NORMAL,
                summary="The update adds HTTP/3.",
                release_notes="## 1.27\n\nHTTP/3",
            )
        )
        for days, kind in (
            (8, EventKind.RESTART_LOOP),
            (2, EventKind.BECAME_UNHEALTHY),
            (1, EventKind.RECOVERED_HEALTH),
        ):
            session.add(
                Event(container_id=web_id, kind=kind, time=now - timedelta(days=days))
            )
        session.commit()
    return context


async def test_container_with_an_update(
    ctx: AppContext, user_client: httpx.AsyncClient, clock: FakeClock
) -> None:
    response = await user_client.get("/api/containers/web")

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["status"], body["latest_version"], body["severity"]) == (
        "web",
        "update",
        "1.27",
        "normal",
    )
    assert body["update"] == {
        "from_version": "1.26",
        "to_version": "1.27",
        "severity": "normal",
        "summary": "The update adds HTTP/3.",
        "release_notes": "## 1.27\n\nHTTP/3",
    }
    assert [event["kind"] for event in body["events"]] == [
        "recovered_health",
        "became_unhealthy",
    ]
    assert body["events"][0]["time"] == (
        clock.now() - timedelta(days=1)
    ).isoformat().replace("+00:00", "Z")


async def test_container_with_no_update(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    body = (await user_client.get("/api/containers/db")).json()

    assert (body["status"], body["update"], body["events"]) == ("no source", None, [])


@pytest.mark.parametrize("name", ["nope", "secret"])
async def test_unknown_or_excluded_gives_404(
    ctx: AppContext, user_client: httpx.AsyncClient, name: str
) -> None:
    assert (await user_client.get(f"/api/containers/{name}")).status_code == 404


async def test_gone_container_gives_404(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    ctx.inventory.remove("db", "id-db")

    assert (await user_client.get("/api/containers/db")).status_code == 404
