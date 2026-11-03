"""Tests for POST /api/config/import."""

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session, select

from wt.bus import Topic
from wt.config import Settings, load_settings
from wt.context import AppContext
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, Setting

CONFIG: dict[str, Any] = {
    "format_version": 1,
    "settings": Settings(check_interval_hours=12, ntfy_topic="wt").model_dump(),
    "containers": [
        {"name": "db", "release_source": None, "source_confirmed": True},
        {"name": "web", "release_source": "nginx/nginx", "source_confirmed": True},
    ],
}


def add_container(ctx: AppContext, name: str) -> None:
    with Session(ctx.engine) as session:
        session.add(
            Container(host_id=LOCAL_HOST_ID, name=name, docker_id="id1", image="x")
        )
        session.commit()


def db_state(
    ctx: AppContext,
) -> tuple[list[tuple[str, Any]], list[tuple[str, str | None, bool]]]:
    with Session(ctx.engine) as session:
        settings = [(row.key, row.value) for row in session.exec(select(Setting))]
        containers = [
            (row.name, row.release_source, row.source_confirmed)
            for row in session.exec(select(Container))
        ]
    return sorted(settings), sorted(containers)


async def do_import(
    client: httpx.AsyncClient, body: Any, dry_run: bool
) -> httpx.Response:
    return await client.post(
        f"/api/config/import?dry_run={str(dry_run).lower()}", json=body
    )


@pytest.mark.anyio
async def test_import_of_an_export_into_an_empty_db_gives_the_same_export(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    response = await do_import(user_client, CONFIG, dry_run=False)

    assert response.status_code == 200
    assert response.json() == {
        "dry_run": False,
        "valid": True,
        "settings": 8,
        "containers_added": 2,
        "containers_updated": 0,
        "errors": [],
    }
    export = (await user_client.get("/api/config/export")).json()
    assert export == CONFIG


@pytest.mark.anyio
async def test_import_updates_known_containers_by_name(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    add_container(ctx, "web")

    response = await do_import(user_client, CONFIG, dry_run=False)

    assert response.json()["containers_added"] == 1
    assert response.json()["containers_updated"] == 1
    with Session(ctx.engine) as session:
        web = session.exec(select(Container).where(Container.name == "web")).one()
    assert (web.docker_id, web.release_source, web.source_confirmed) == (
        "id1",
        "nginx/nginx",
        True,
    )


@pytest.mark.anyio
async def test_dry_run_gives_counts_and_changes_nothing(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    add_container(ctx, "web")
    before = db_state(ctx)

    response = await do_import(user_client, CONFIG, dry_run=True)

    assert response.status_code == 200
    assert response.json() == {
        "dry_run": True,
        "valid": True,
        "settings": 8,
        "containers_added": 1,
        "containers_updated": 1,
        "errors": [],
    }
    assert db_state(ctx) == before


BAD_FILES: list[Any] = [
    {**CONFIG, "format_version": 2},
    {**CONFIG, "settings": {**CONFIG["settings"], "check_interval_hours": 0}},
    {
        **CONFIG,
        "containers": [
            {"name": "web", "release_source": "https://x", "source_confirmed": True}
        ],
    },
    {**CONFIG, "containers": [CONFIG["containers"][0], CONFIG["containers"][0]]},
    [1, 2, 3],
]


@pytest.mark.anyio
@pytest.mark.parametrize("bad", BAD_FILES)
async def test_dry_run_of_a_bad_file_gives_errors(
    user_client: httpx.AsyncClient, bad: Any
) -> None:
    response = await do_import(user_client, bad, dry_run=True)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"]
    assert all(set(item) == {"field", "message"} for item in body["errors"])


@pytest.mark.anyio
@pytest.mark.parametrize("bad", BAD_FILES)
async def test_a_bad_file_changes_nothing(
    app: FastAPI, user_client: httpx.AsyncClient, bad: Any
) -> None:
    ctx: AppContext = app.state.ctx
    add_container(ctx, "web")
    before = db_state(ctx)

    response = await do_import(user_client, bad, dry_run=False)

    assert response.status_code == 422
    assert db_state(ctx) == before
    assert load_settings(ctx.engine) == Settings()


@pytest.mark.anyio
async def test_real_import_publishes_settings(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    with ctx.bus.subscribe([Topic.SETTINGS]) as subscription:
        await do_import(user_client, CONFIG, dry_run=True)
        assert subscription.empty()

        await do_import(user_client, CONFIG, dry_run=False)

        message = await asyncio.wait_for(subscription.get(), timeout=1)
    assert message.topic is Topic.SETTINGS
