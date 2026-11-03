"""Tests for `wt reset-admin`: reset, then restart WT."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pyotp
import pytest
from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session, select

from wt.api.deps import require_session
from wt.cli import main
from wt.config import Env
from wt.context import AppContext
from wt.db.models import Admin, AuthSession
from wt.main import create_app

PASSWORD = "a long admin password"


@asynccontextmanager
async def running_wt(
    data_dir: Path,
) -> AsyncGenerator[tuple[FastAPI, httpx.AsyncClient]]:
    """Start WT with a protected test route. Stop it at the end."""
    app = create_app(Env(data_dir=data_dir), workers=[])
    router = APIRouter(prefix="/api", dependencies=[Depends(require_session)])
    router.add_api_route("/test/dummy", lambda: {"ok": True})
    app.include_router(router)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://wt"
        ) as client:
            yield app, client


async def set_up_admin(app: FastAPI, client: httpx.AsyncClient) -> str:
    """Set up the admin. Give the session token."""
    ctx: AppContext = app.state.ctx
    token = ctx.setup_token.value
    assert token is not None
    begin = await client.post("/api/auth/setup/begin", json={"token": token})
    code = pyotp.TOTP(begin.json()["totp_secret"]).now()
    await client.post(
        "/api/auth/setup/finish",
        json={"token": token, "password": PASSWORD, "totp_code": code},
    )
    session_token = client.cookies.get("wt_session")
    assert session_token is not None
    return session_token


@pytest.mark.anyio
async def test_reset_then_restart_gives_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    data_dir = tmp_path / "data"
    async with running_wt(data_dir) as (app, client):
        old_session = await set_up_admin(app, client)
        assert (await client.get("/api/test/dummy")).status_code == 200
        for _ in range(5):
            await client.post(
                "/api/auth/login", json={"password": "wrong", "totp_code": "1"}
            )
        ctx: AppContext = app.state.ctx
        assert ctx.login_limit.retry_after() is not None

    monkeypatch.setenv("WT_DATA_DIR", str(data_dir))
    main(["reset-admin"])
    assert (
        "Restart WT (docker restart wt). Then get the setup token from the WT log."
        in (capsys.readouterr().out)
    )

    caplog.clear()
    async with running_wt(data_dir) as (app, client):
        ctx = app.state.ctx
        assert ctx.setup_token.value is not None
        assert ctx.setup_token.value in caplog.text
        assert ctx.login_limit.retry_after() is None
        state = await client.get("/api/auth/state")
        assert state.json() == {"setup_required": True, "logged_in": False}
        client.cookies.set("wt_session", old_session)
        assert (await client.get("/api/test/dummy")).status_code == 401
        with Session(ctx.engine) as session:
            assert session.exec(select(Admin)).first() is None
            assert session.exec(select(AuthSession)).first() is None
