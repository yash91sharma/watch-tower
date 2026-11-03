"""Tests for POST /api/auth/logout."""

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session, select

from wt.auth import sessions
from wt.context import AppContext
from wt.db.models import AuthSession


@pytest.mark.anyio
async def test_logout_deletes_the_session_and_the_cookie(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    token = sessions.create_session(ctx.engine)
    client.cookies.set(sessions.COOKIE, token)

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert 'wt_session="";' in response.headers["set-cookie"]
    with Session(ctx.engine) as session:
        assert session.exec(select(AuthSession)).first() is None

    client.cookies.set(sessions.COOKIE, token)
    state = await client.get("/api/auth/state")
    assert state.json()["logged_in"] is False


@pytest.mark.anyio
async def test_logout_with_no_cookie_is_ok(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
