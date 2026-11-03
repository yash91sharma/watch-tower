"""Tests for POST /api/auth/login (clock)."""

import httpx
import pyotp
import pytest
from fastapi import FastAPI
from sqlmodel import Session

from wt.auth import totp
from wt.auth.password import hash_password
from wt.clock import FakeClock
from wt.context import AppContext
from wt.db.models import ADMIN_ID, Admin

PASSWORD = "a long admin password"
SECRET = totp.new_secret()
FAILURE = {
    "error": "Unauthorized",
    "detail": "The password or the TOTP code is not correct",
}


@pytest.fixture
def admin(app: FastAPI) -> None:
    ctx: AppContext = app.state.ctx
    with Session(ctx.engine) as session:
        session.add(
            Admin(
                id=ADMIN_ID,
                password_hash=hash_password(PASSWORD),
                totp_secret=SECRET,
                last_totp_step=0,
            )
        )
        session.commit()


def code_now(clock: FakeClock) -> str:
    return pyotp.TOTP(SECRET).at(clock.now())


def wrong_code(clock: FakeClock) -> str:
    return "000000" if code_now(clock) != "000000" else "111111"


async def login(client: httpx.AsyncClient, password: str, code: str) -> httpx.Response:
    return await client.post(
        "/api/auth/login", json={"password": password, "totp_code": code}
    )


@pytest.mark.anyio
@pytest.mark.usefixtures("admin")
async def test_good_login_sets_the_cookie(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    response = await login(client, PASSWORD, code_now(clock))

    assert response.status_code == 200
    assert response.json() == {"setup_required": False, "logged_in": True}
    assert response.headers["set-cookie"].startswith("wt_session=")
    state = await client.get("/api/auth/state")
    assert state.json()["logged_in"] is True


@pytest.mark.anyio
@pytest.mark.usefixtures("admin")
async def test_wrong_password_fails(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    response = await login(client, "a wrong password", code_now(clock))

    assert response.status_code == 401
    assert response.json() == FAILURE
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
@pytest.mark.usefixtures("admin")
async def test_wrong_code_fails_with_the_same_message(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    response = await login(client, PASSWORD, wrong_code(clock))

    assert response.status_code == 401
    assert response.json() == FAILURE


@pytest.mark.anyio
@pytest.mark.usefixtures("admin")
async def test_a_code_works_only_once(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    code = code_now(clock)

    assert (await login(client, PASSWORD, code)).status_code == 200
    assert (await login(client, PASSWORD, code)).status_code == 401


@pytest.mark.anyio
@pytest.mark.usefixtures("admin")
async def test_6th_attempt_gets_429_and_login_works_after_15_minutes(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    for _ in range(5):
        assert (
            await login(client, "a wrong password", code_now(clock))
        ).status_code == 401

    blocked = await login(client, PASSWORD, code_now(clock))
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "900"

    clock.advance(15 * 60)
    assert (await login(client, PASSWORD, code_now(clock))).status_code == 200


@pytest.mark.anyio
async def test_login_before_setup_gives_409(
    client: httpx.AsyncClient, clock: FakeClock
) -> None:
    response = await login(client, PASSWORD, code_now(clock))

    assert response.status_code == 409


@pytest.mark.anyio
async def test_the_setup_code_fails_at_login(
    app: FastAPI, client: httpx.AsyncClient, clock: FakeClock
) -> None:
    ctx: AppContext = app.state.ctx
    token = ctx.setup_token.value
    assert token is not None
    secret = (await client.post("/api/auth/setup/begin", json={"token": token})).json()[
        "totp_secret"
    ]
    code = pyotp.TOTP(secret).at(clock.now())
    finish = await client.post(
        "/api/auth/setup/finish",
        json={"token": token, "password": PASSWORD, "totp_code": code},
    )
    assert finish.status_code == 200

    assert (await login(client, PASSWORD, code)).status_code == 401
