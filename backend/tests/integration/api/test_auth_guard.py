"""Tests for the auth guard: all /api routes need a session, except the public ones."""

import re

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute

from wt.api.deps import require_session
from wt.auth import sessions
from wt.context import AppContext

PUBLIC = re.compile(r"^/api/(health|auth/.*)$")


def add_dummy_route(app: FastAPI) -> None:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_session)])

    @router.get("/test/dummy")
    def dummy() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(router)


@pytest.mark.anyio
async def test_dummy_route_gives_401_with_no_cookie(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    add_dummy_route(app)

    response = await client.get("/api/test/dummy")

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized", "detail": "Log in first"}


@pytest.mark.anyio
async def test_dummy_route_gives_401_with_a_bad_cookie(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    add_dummy_route(app)
    client.cookies.set(sessions.COOKIE, "not-a-session")

    assert (await client.get("/api/test/dummy")).status_code == 401


@pytest.mark.anyio
async def test_dummy_route_works_with_a_session_and_renews_the_cookie(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    add_dummy_route(app)
    ctx: AppContext = app.state.ctx
    client.cookies.set(sessions.COOKIE, sessions.create_session(ctx.engine))

    response = await client.get("/api/test/dummy")

    assert response.status_code == 200
    assert "Max-Age=2592000" in response.headers["set-cookie"]


@pytest.mark.anyio
async def test_old_cookie_gives_401_after_logout(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    add_dummy_route(app)
    ctx: AppContext = app.state.ctx
    token = sessions.create_session(ctx.engine)
    client.cookies.set(sessions.COOKIE, token)
    await client.post("/api/auth/logout")

    client.cookies.set(sessions.COOKIE, token)
    assert (await client.get("/api/test/dummy")).status_code == 401


def protected_routes(app: FastAPI) -> list[tuple[str, str]]:
    """(method, path) for each /api route that is not public. Path params get a value."""
    result: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        if PUBLIC.match(route.path):
            continue
        path = re.sub(r"\{[^}]+\}", "x", route.path)
        result.extend((method, path) for method in sorted(route.methods or ()))
    return result


@pytest.mark.anyio
async def test_each_route_that_is_not_public_gives_401_with_no_cookie(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    for method, path in protected_routes(app):
        response = await client.request(method, path)
        assert response.status_code == 401, f"{method} {path}"


@pytest.mark.anyio
async def test_docs_and_openapi_are_not_served(app: FastAPI) -> None:
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
