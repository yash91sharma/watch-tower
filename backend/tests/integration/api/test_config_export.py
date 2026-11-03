"""Tests for GET /api/config/export."""

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlmodel import Session

from wt.clock import FakeClock
from wt.config import Settings, save_settings
from wt.context import AppContext
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container


def add_data(ctx: AppContext) -> None:
    save_settings(ctx.engine, Settings(check_interval_hours=6, ntfy_topic="wt"))
    with Session(ctx.engine) as session:
        session.add(
            Container(
                host_id=LOCAL_HOST_ID,
                name="web",
                docker_id="abc",
                image="nginx",
                tag="1.27",
                release_source="nginx/nginx",
                source_confirmed=True,
            )
        )
        session.add(
            Container(host_id=LOCAL_HOST_ID, name="db", image="postgres", tag="16")
        )
        session.commit()


@pytest.mark.anyio
async def test_export_has_settings_and_container_values(
    app: FastAPI, user_client: httpx.AsyncClient, clock: FakeClock
) -> None:
    add_data(app.state.ctx)

    response = await user_client.get("/api/config/export")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="wt-config-2026-01-01.json"'
    )
    body = response.json()
    assert body["format_version"] == 1
    assert (
        body["settings"]
        == Settings(check_interval_hours=6, ntfy_topic="wt").model_dump()
    )
    assert body["containers"] == [
        {"name": "db", "release_source": None, "source_confirmed": False},
        {"name": "web", "release_source": "nginx/nginx", "source_confirmed": True},
    ]


@pytest.mark.anyio
async def test_export_has_no_secret(
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
    add_data(ctx)

    response = await user_client.get("/api/config/export")

    assert response.status_code == 200
    assert "s3cret" not in response.text
    assert "token" not in response.text
    assert "api_key" not in response.text
