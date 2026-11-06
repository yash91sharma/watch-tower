"""The app and the workers.

One process runs the API and the workers (Uvicorn with 1 worker), because the workers
keep state in memory. The lifespan opens the DB, starts the workers at start and stops
them at shutdown.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from wt import api
from wt.api import errors, static
from wt.api.headers import SecurityHeadersMiddleware
from wt.auth.setup_token import SetupToken
from wt.bus import Bus
from wt.config import Env, load_settings
from wt.context import AppContext, Worker
from wt.db import cleanup, open_db
from wt.docker.client import DockerClient
from wt.docker.connection import keep_connected
from wt.docker.inventory import Inventory
from wt.health.monitor import HealthMonitor, run_health
from wt.notify.health import notify_health
from wt.notify.updates import notify_updates
from wt.versions.check import CheckRunner
from wt.versions.scheduler import run_scheduler

log = logging.getLogger(__name__)


async def cleanup_worker(ctx: AppContext) -> None:
    await cleanup.run(ctx.engine)


async def docker_worker(ctx: AppContext) -> None:
    await keep_connected(
        ctx.docker_factory,
        ctx.inventory,
        ctx.bus,
        ctx.docker_state,
        ctx.health,
    )


async def health_worker(ctx: AppContext) -> None:
    await run_health(ctx.health, ctx.engine, ctx.bus)


async def scheduler_worker(ctx: AppContext) -> None:
    # A check before the first Docker sync finds no containers and still counts as a run.
    await ctx.inventory.synced.wait()
    await run_scheduler(ctx.checker, ctx.engine)


# The workers that WT starts.
WORKERS: list[Worker] = [cleanup_worker, docker_worker, health_worker, scheduler_worker]


def create_app(
    env: Env,
    workers: Sequence[Worker] = WORKERS,
    static_dir: Path = static.STATIC_DIR,
) -> FastAPI:
    """Make the app. Tests give their own env, workers and static dir."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        engine = open_db(env.data_dir)
        inventory = Inventory(engine)
        bus = Bus()
        ctx = AppContext(
            env=env,
            engine=engine,
            bus=bus,
            setup_token=SetupToken.at_start(engine),
            inventory=inventory,
            health=HealthMonitor(
                engine,
                load_settings(engine),
                on_change=lambda name, kind, settings: notify_health(
                    name, kind, settings, env.ntfy_token
                ),
            ),
            docker_factory=lambda: DockerClient(env.docker_host),
            checker=CheckRunner(
                engine,
                env,
                inventory,
                bus,
                after_run=lambda: notify_updates(engine, env),
            ),
        )
        app.state.ctx = ctx
        tasks = [asyncio.create_task(_run_worker(worker, ctx)) for worker in workers]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            engine.dispose()

    # No docs and no schema URL: they have no auth, and Swagger UI loads scripts from a CDN.
    # `wt openapi` writes the schema.
    app = FastAPI(
        title="Watch Tower",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(api.router)
    errors.install(app)
    static.install(app, static_dir)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


async def _run_worker(worker: Worker, ctx: AppContext) -> None:
    """Run a worker. If it stops with an error, log the error. The other workers continue."""
    try:
        await worker(ctx)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Worker %s stopped with an error", worker.__name__)
