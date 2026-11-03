"""Tests for GET /api/health."""

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine

from wt.context import AppContext


@pytest.mark.anyio
async def test_health_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_503_when_the_db_does_not_answer(
    app: FastAPI, client: httpx.AsyncClient, tmp_path: Path
) -> None:
    ctx: AppContext = app.state.ctx
    broken = create_engine(f"sqlite:///{tmp_path}/missing/dir/wt.db")
    app.state.ctx = replace(ctx, engine=broken)

    response = await client.get("/api/health")

    assert response.status_code == 503
    broken.dispose()
