"""Tests for the setup API: /api/auth/state and /api/auth/setup/*."""

import httpx
import pyotp
import pytest
from fastapi import FastAPI
from sqlmodel import Session, select

from wt.context import AppContext
from wt.db.models import Admin

PASSWORD = "a long admin password"


def ctx_of(app: FastAPI) -> AppContext:
    return app.state.ctx


def token_of(app: FastAPI) -> str:
    value = ctx_of(app).setup_token.value
    assert value is not None
    return value


async def begin(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.post("/api/auth/setup/begin", json={"token": token})


async def finish(
    client: httpx.AsyncClient, token: str, code: str, password: str = PASSWORD
) -> httpx.Response:
    return await client.post(
        "/api/auth/setup/finish",
        json={"token": token, "password": password, "totp_code": code},
    )


async def full_setup(app: FastAPI, client: httpx.AsyncClient) -> httpx.Response:
    token = token_of(app)
    secret = (await begin(client, token)).json()["totp_secret"]
    return await finish(client, token, pyotp.TOTP(secret).now())


@pytest.mark.anyio
async def test_state_before_setup(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/state")

    assert response.json() == {"setup_required": True, "logged_in": False}


@pytest.mark.anyio
async def test_begin_gives_secret_uri_and_qr_code(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    response = await begin(client, token_of(app))

    assert response.status_code == 200
    body = response.json()
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert f"secret={body['totp_secret']}" in body["otpauth_uri"]
    assert body["qr_svg"].startswith("<svg")


@pytest.mark.anyio
async def test_full_flow(app: FastAPI, client: httpx.AsyncClient) -> None:
    response = await full_setup(app, client)

    assert response.status_code == 200
    assert response.json() == {"setup_required": False, "logged_in": True}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("wt_session=")
    assert "HttpOnly" in cookie
    assert ctx_of(app).setup_token.value is None

    state = await client.get("/api/auth/state")
    assert state.json() == {"setup_required": False, "logged_in": True}


@pytest.mark.anyio
async def test_setup_saves_the_admin_with_the_matched_step(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    token = token_of(app)
    secret = (await begin(client, token)).json()["totp_secret"]
    totp = pyotp.TOTP(secret)
    await finish(client, token, totp.now())

    with Session(ctx_of(app).engine) as session:
        admin = session.exec(select(Admin)).one()
    assert admin.totp_secret == secret
    assert admin.password_hash.startswith("$argon2id$")
    assert PASSWORD not in admin.password_hash
    assert totp.at(admin.last_totp_step * 30) == totp.now()


@pytest.mark.anyio
async def test_wrong_token_gives_403(client: httpx.AsyncClient) -> None:
    assert (await begin(client, "wrong")).status_code == 403
    assert (await finish(client, "wrong", "123456")).status_code == 403


@pytest.mark.anyio
async def test_wrong_code_fails(app: FastAPI, client: httpx.AsyncClient) -> None:
    token = token_of(app)
    secret = (await begin(client, token)).json()["totp_secret"]
    wrong = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"

    response = await finish(client, token, wrong)

    assert response.status_code == 400
    assert ctx_of(app).setup_token.value == token


@pytest.mark.anyio
async def test_finish_before_begin_fails(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    response = await finish(client, token_of(app), "123456")

    assert response.status_code == 400


@pytest.mark.anyio
async def test_short_password_gives_a_field_error(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    token = token_of(app)
    secret = (await begin(client, token)).json()["totp_secret"]

    response = await finish(client, token, pyotp.TOTP(secret).now(), password="short")

    assert response.status_code == 422
    assert [item["field"] for item in response.json()["detail"]] == ["password"]


@pytest.mark.anyio
async def test_second_setup_gives_409(app: FastAPI, client: httpx.AsyncClient) -> None:
    token = token_of(app)
    await full_setup(app, client)

    assert (await begin(client, token)).status_code == 409
    assert (await finish(client, token, "123456")).status_code == 409


@pytest.mark.anyio
async def test_blocked_after_5_failures_gives_429(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    for _ in range(5):
        assert (await begin(client, "wrong")).status_code == 403

    response = await begin(client, token_of(app))

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) == 900
