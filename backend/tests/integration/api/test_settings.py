"""Tests for GET and PUT /api/settings."""

import asyncio
from dataclasses import replace

import httpx
import pytest
import respx
from fastapi import FastAPI
from pydantic import SecretStr

from wt.bus import Topic
from wt.context import AppContext

NEW_VALUES = {
    "check_interval_hours": 6,
    "restart_count": 4,
    "restart_window_minutes": 20,
    "ntfy_url": "https://ntfy.example.com",
    "ntfy_topic": "wt",
    "llm_url": None,
    "llm_model": None,
    "public_url": "https://wt.example.com",
}


@pytest.mark.anyio
async def test_get_gives_defaults_and_secret_state(
    user_client: httpx.AsyncClient,
) -> None:
    response = await user_client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["values"]["check_interval_hours"] == 24
    assert body["secrets"] == {
        "github_token": "not set",
        "ntfy_token": "not set",
        "llm_api_key": "not set",
    }


@pytest.mark.anyio
async def test_no_secret_value_in_a_response(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    env = ctx.env.model_copy(
        update={
            "github_token": SecretStr("s3cret-github"),
            "ntfy_token": SecretStr("s3cret-ntfy"),
            "llm_api_key": SecretStr("s3cret-llm"),
        }
    )
    app.state.ctx = replace(ctx, env=env)

    get = await user_client.get("/api/settings")
    put = await user_client.put("/api/settings", json=NEW_VALUES)

    for response in (get, put):
        assert "s3cret" not in response.text
        assert response.json()["secrets"] == {
            "github_token": "set",
            "ntfy_token": "set",
            "llm_api_key": "set",
        }


@pytest.mark.anyio
async def test_put_saves_the_values(user_client: httpx.AsyncClient) -> None:
    response = await user_client.put("/api/settings", json=NEW_VALUES)

    assert response.status_code == 200
    assert response.json()["values"] == NEW_VALUES
    assert (await user_client.get("/api/settings")).json()["values"] == NEW_VALUES


@pytest.mark.anyio
async def test_a_save_publishes_settings(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    ctx: AppContext = app.state.ctx
    with ctx.bus.subscribe([Topic.SETTINGS]) as subscription:
        await user_client.put("/api/settings", json=NEW_VALUES)

        message = await asyncio.wait_for(subscription.get(), timeout=1)

    assert message.topic is Topic.SETTINGS


@pytest.mark.anyio
async def test_bad_values_give_one_error_per_field(
    user_client: httpx.AsyncClient,
) -> None:
    bad = {**NEW_VALUES, "check_interval_hours": 0, "ntfy_url": "ftp://x"}

    response = await user_client.put("/api/settings", json=bad)

    assert response.status_code == 422
    fields = sorted(item["field"] for item in response.json()["detail"])
    assert fields == ["check_interval_hours", "ntfy_url"]
    assert (await user_client.get("/api/settings")).json()["values"][
        "check_interval_hours"
    ] == 24


NTFY_TEST = "/api/settings/ntfy-test"


@pytest.mark.anyio
async def test_ntfy_test_sends_with_the_form_values_and_the_token(
    app: FastAPI, user_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    ctx: AppContext = app.state.ctx
    env = ctx.env.model_copy(update={"ntfy_token": SecretStr("s3cret-ntfy")})
    app.state.ctx = replace(ctx, env=env)
    with respx.mock:
        route = respx.post("https://ntfy.example.com/wt").mock(
            return_value=httpx.Response(200)
        )

        response = await user_client.post(NTFY_TEST, json=NEW_VALUES)

    assert response.status_code == 204
    request = route.calls.last.request
    assert request.headers["Title"] == "WT test notification"
    assert request.headers["Authorization"] == "Bearer s3cret-ntfy"
    assert request.headers["Click"] == "https://wt.example.com/settings"
    assert "s3cret" not in caplog.text


@pytest.mark.anyio
async def test_ntfy_test_does_not_save_the_values(
    user_client: httpx.AsyncClient,
) -> None:
    with respx.mock:
        respx.post("https://ntfy.example.com/wt").mock(return_value=httpx.Response(200))

        await user_client.post(NTFY_TEST, json=NEW_VALUES)

    assert (await user_client.get("/api/settings")).json()["values"]["ntfy_url"] is None


@pytest.mark.anyio
async def test_ntfy_test_fail_gives_502(user_client: httpx.AsyncClient) -> None:
    with respx.mock:
        respx.post("https://ntfy.example.com/wt").mock(return_value=httpx.Response(403))

        response = await user_client.post(NTFY_TEST, json=NEW_VALUES)

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "ntfy did not accept the message. Check the URL, the topic and the token."
    )


@pytest.mark.anyio
async def test_ntfy_test_with_no_ntfy_settings_gives_400(
    user_client: httpx.AsyncClient,
) -> None:
    values = {**NEW_VALUES, "ntfy_topic": None}

    response = await user_client.post(NTFY_TEST, json=values)

    assert response.status_code == 400
    assert response.json()["detail"] == "Set the ntfy URL and the ntfy topic."


@pytest.mark.anyio
async def test_ntfy_test_bad_values_give_field_errors(
    user_client: httpx.AsyncClient,
) -> None:
    response = await user_client.post(NTFY_TEST, json={**NEW_VALUES, "ntfy_url": "x"})

    assert response.status_code == 422
    assert [item["field"] for item in response.json()["detail"]] == ["ntfy_url"]
