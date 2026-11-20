"""The routes that the UI calls often make a fixed number of DB queries.

The number must not grow with the number of containers (no query per container).
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import event
from sqlmodel import Session

from tests.factories import make_info
from wt.clock import FakeClock
from wt.context import AppContext
from wt.db import find_container
from wt.db.models import RepoCache, Severity, Update
from wt.notify.updates import pending_updates

pytestmark = pytest.mark.anyio

ROUTES = [
    "/api/containers",
    "/api/metrics/overview",
    "/api/metrics/sparklines",
    "/api/checks/status",
]


@contextmanager
def count_queries(ctx: AppContext) -> Generator[list[int]]:
    """Count the SQL statements on the engine. The count is in the list."""
    count = [0]

    def on_execute(*_: Any) -> None:
        count[0] += 1

    event.listen(ctx.engine, "before_cursor_execute", on_execute)
    try:
        yield count
    finally:
        event.remove(ctx.engine, "before_cursor_execute", on_execute)


async def add_containers(
    ctx: AppContext, clock: FakeClock, first: int, last: int
) -> None:
    """Containers with an update: each has a repo, a repo cache and an update row."""
    for i in range(first, last):
        await ctx.inventory.update(
            make_info(f"c{i}", "app:1.0", project=f"p{i % 2}", source=f"o/r{i}")
        )
    with Session(ctx.engine) as session:
        for i in range(first, last):
            row = find_container(session, f"c{i}")
            assert row is not None and row.id is not None
            session.add(
                RepoCache(
                    repo=f"o/r{i}",
                    latest_tag="2.0",
                    fetched_at=clock.now(),
                    releases=[{"tag": "2.0", "notes": "n", "draft": False}],
                )
            )
            session.add(
                Update(
                    container_id=row.id,
                    from_version="1.0",
                    to_version="2.0",
                    severity=Severity.NORMAL,
                    release_notes="notes",
                )
            )
        session.commit()


async def queries(client: httpx.AsyncClient, ctx: AppContext, path: str) -> int:
    """The queries of one request. A first request before it does the one-time work."""
    await client.get(path)
    with count_queries(ctx) as count:
        response = await client.get(path)
    assert response.status_code == 200, response.text
    return count[0]


@pytest.mark.parametrize("path", ROUTES)
async def test_the_query_count_does_not_grow_with_the_containers(
    app: FastAPI, user_client: httpx.AsyncClient, clock: FakeClock, path: str
) -> None:
    ctx: AppContext = app.state.ctx
    await add_containers(ctx, clock, 0, 2)
    few = await queries(user_client, ctx, path)

    await add_containers(ctx, clock, 2, 8)
    many = await queries(user_client, ctx, path)

    assert many == few


async def test_the_container_list_still_shows_each_update(
    app: FastAPI, user_client: httpx.AsyncClient, clock: FakeClock
) -> None:
    ctx: AppContext = app.state.ctx
    await add_containers(ctx, clock, 0, 3)

    body: list[dict[str, Any]] = (await user_client.get("/api/containers")).json()

    containers = [item for group in body for item in group["containers"]]
    assert [(c["name"], c["status"], c["severity"]) for c in containers] == [
        ("c0", "update", "normal"),
        ("c2", "update", "normal"),
        ("c1", "update", "normal"),
    ]


async def test_the_pending_update_notifications_use_a_fixed_number_of_queries(
    app: FastAPI, clock: FakeClock
) -> None:
    ctx: AppContext = app.state.ctx
    await add_containers(ctx, clock, 0, 2)
    with count_queries(ctx) as few:
        assert len(pending_updates(ctx.engine)) == 2

    await add_containers(ctx, clock, 2, 8)
    with count_queries(ctx) as many:
        assert len(pending_updates(ctx.engine)) == 8

    assert many[0] == few[0]
