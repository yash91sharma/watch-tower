"""Tests for PUT /api/containers/{name}/release-source."""

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session, select

from wt.context import AppContext
from wt.db.models import Container
from wt.docker.client import ContainerInfo

pytestmark = pytest.mark.anyio

LABEL = {"org.opencontainers.image.source": "https://github.com/label/source"}


def web(labels: dict[str, str] = LABEL) -> ContainerInfo:
    return ContainerInfo("id-1", "web", "app:1.0", labels, "running", "none", False, 0)


def saved(ctx: AppContext) -> tuple[str | None, bool]:
    with Session(ctx.engine) as session:
        row = session.exec(select(Container).where(Container.name == "web")).one()
    return row.release_source, row.source_confirmed


async def put(
    client: httpx.AsyncClient, body: object, name: str = "web"
) -> httpx.Response:
    return await client.put(f"/api/containers/{name}/release-source", json=body)


@pytest.fixture
async def ctx(app: FastAPI) -> AppContext:
    context: AppContext = app.state.ctx
    await context.inventory.update(web())
    return context


async def test_set_without_confirm(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    response = await put(
        user_client,
        {"source": "https://github.com/admin/choice.git", "confirmed": False},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "web",
        "release_source": "admin/choice",
        "source_confirmed": False,
    }
    assert saved(ctx) == ("admin/choice", False)


async def test_confirm_keeps_the_value_after_a_new_inspect(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    await put(user_client, {"source": "label/source", "confirmed": True})

    await ctx.inventory.update(
        web({"org.opencontainers.image.source": "https://github.com/new/label"})
    )

    assert saved(ctx) == ("label/source", True)


async def test_clear_stays_clear_after_a_new_inspect(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    response = await put(user_client, {"source": None, "confirmed": False})

    await ctx.inventory.update(web())

    assert response.json()["source_confirmed"] is True
    assert saved(ctx) == (None, True)


@pytest.mark.parametrize("source", ["https://gitlab.com/a/b", "not a repo", "a/b/c"])
async def test_bad_value_gives_422(
    ctx: AppContext, user_client: httpx.AsyncClient, source: str
) -> None:
    response = await put(user_client, {"source": source, "confirmed": True})

    assert response.status_code == 422
    assert [item["field"] for item in response.json()["detail"]] == ["source"]
    assert saved(ctx) == ("label/source", False)


async def test_unknown_name_gives_404(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    response = await put(user_client, {"source": "a/b", "confirmed": True}, name="nope")

    assert response.status_code == 404


async def test_excluded_container_gives_404(
    ctx: AppContext, user_client: httpx.AsyncClient
) -> None:
    await ctx.inventory.update(
        ContainerInfo(
            "id-2",
            "secret",
            "app:1.0",
            {"wt.enable": "false"},
            "running",
            "none",
            False,
            0,
        )
    )

    response = await put(
        user_client, {"source": "a/b", "confirmed": True}, name="secret"
    )

    assert response.status_code == 404
