"""Tests for wt.main: app, lifespan, workers and proxy headers."""

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request
from sqlmodel import Session

from wt import clock, main
from wt.bus import Topic
from wt.config import Env
from wt.context import AppContext, Worker
from wt.db.models import Host
from wt.docker.client import ContainerInfo
from wt.docker.fake import FakeDocker
from wt.main import create_app


def make_env(tmp_path: Path, trusted_proxies: list[str] | None = None) -> Env:
    return Env(data_dir=tmp_path, trusted_proxies=trusted_proxies or [])


@pytest.mark.anyio
async def test_lifespan_starts_and_stops_workers(tmp_path: Path) -> None:
    started: list[str] = []
    stopped: list[str] = []

    def make_worker(name: str) -> Worker:
        async def worker(ctx: AppContext) -> None:
            started.append(name)
            try:
                await asyncio.Event().wait()
            finally:
                stopped.append(name)

        return worker

    app = create_app(make_env(tmp_path), workers=[make_worker("a"), make_worker("b")])
    tasks_before = asyncio.all_tasks()

    async with app.router.lifespan_context(app):
        await clock.sleep(0)  # Let the workers start.
        assert sorted(started) == ["a", "b"]

    assert sorted(stopped) == ["a", "b"]
    assert asyncio.all_tasks() == tasks_before


@pytest.mark.anyio
async def test_a_crashed_worker_is_logged_and_others_run(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    other_running = asyncio.Event()

    async def crash(ctx: AppContext) -> None:
        raise RuntimeError("boom")

    async def other(ctx: AppContext) -> None:
        other_running.set()
        await asyncio.Event().wait()

    app = create_app(make_env(tmp_path), workers=[crash, other])

    async with app.router.lifespan_context(app):
        await other_running.wait()
        await clock.sleep(0)  # Let the crash finish.

    assert "Worker crash stopped with an error" in caplog.text
    assert "boom" in caplog.text


@pytest.mark.anyio
async def test_lifespan_opens_the_db(tmp_path: Path) -> None:
    app = create_app(make_env(tmp_path), workers=[])

    async with app.router.lifespan_context(app):
        ctx: AppContext = app.state.ctx
        assert ctx.bus.subscriber_count == 0
        assert ctx.setup_token.value is not None
        with Session(ctx.engine) as session:
            assert session.get(Host, 1) is not None

    assert (tmp_path / "wt.db").exists()


def add_client_route(app: FastAPI) -> None:
    """Test-only route: gives the client IP and the scheme that WT sees."""

    async def client(request: Request) -> dict[str, str | None]:
        host = request.client.host if request.client else None
        return {"host": host, "scheme": request.url.scheme}

    app.add_api_route("/test/client", client)


async def get_client(app: FastAPI, client_ip: str, headers: dict[str, str]) -> object:
    transport = httpx.ASGITransport(app=app, client=(client_ip, 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://wt") as http:
        response = await http.get("/test/client", headers=headers)
    return response.json()


FORWARDED = {"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"}


@pytest.mark.anyio
async def test_forwarded_headers_from_a_trusted_proxy(tmp_path: Path) -> None:
    app = create_app(make_env(tmp_path, ["172.18.0.2"]), workers=[])
    add_client_route(app)

    result = await get_client(app, "172.18.0.2", FORWARDED)

    assert result == {"host": "203.0.113.7", "scheme": "https"}


@pytest.mark.anyio
async def test_forwarded_headers_from_a_trusted_network(tmp_path: Path) -> None:
    app = create_app(make_env(tmp_path, ["172.18.0.0/16"]), workers=[])
    add_client_route(app)

    result = await get_client(app, "172.18.5.9", FORWARDED)

    assert result == {"host": "203.0.113.7", "scheme": "https"}


@pytest.mark.anyio
async def test_forwarded_headers_from_another_ip_are_ignored(tmp_path: Path) -> None:
    app = create_app(make_env(tmp_path, ["172.18.0.2"]), workers=[])
    add_client_route(app)

    result = await get_client(app, "10.0.0.9", FORWARDED)

    assert result == {"host": "10.0.0.9", "scheme": "http"}


@pytest.mark.anyio
async def test_no_trusted_proxies_ignores_forwarded_headers(tmp_path: Path) -> None:
    app = create_app(make_env(tmp_path), workers=[])
    add_client_route(app)

    result = await get_client(app, "127.0.0.1", FORWARDED)

    assert result == {"host": "127.0.0.1", "scheme": "http"}


@pytest.mark.anyio
async def test_docker_worker_connects_and_fills_the_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker()
    fake.add(ContainerInfo("id-1", "web", "nginx:1", {}, "running", "healthy", False))

    def make_client(docker_host: str | None) -> FakeDocker:
        return fake

    monkeypatch.setattr(main, "DockerClient", make_client)
    app = create_app(make_env(tmp_path), workers=[main.docker_worker])

    async with app.router.lifespan_context(app):
        ctx: AppContext = app.state.ctx
        with ctx.bus.subscribe([Topic.DOCKER]) as subscription:
            while ctx.docker_state.connected is False:
                await subscription.get()
        assert ctx.inventory.get("web") is not None


@pytest.mark.anyio
async def test_scheduler_worker_starts_after_the_first_docker_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before the first sync the inventory is empty: a check then checks no container.
    started = asyncio.Event()

    async def run_scheduler(runner: object, engine: object) -> None:
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "run_scheduler", run_scheduler)
    app = create_app(make_env(tmp_path), workers=[main.scheduler_worker])

    async with app.router.lifespan_context(app):
        ctx: AppContext = app.state.ctx
        for _ in range(5):
            await clock.sleep(0)
        assert not started.is_set()

        await ctx.inventory.sync_all(FakeDocker())
        await asyncio.wait_for(started.wait(), timeout=5)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("worker", "target"),
    [
        (main.cleanup_worker, "wt.db.cleanup.run"),
        (main.health_worker, "wt.main.run_health"),
    ],
)
async def test_worker_calls_its_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker: Worker,
    target: str,
) -> None:
    called = asyncio.Event()

    async def loop(*args: object) -> None:
        called.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(target, loop)
    app = create_app(make_env(tmp_path), workers=[worker])

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(called.wait(), timeout=5)
