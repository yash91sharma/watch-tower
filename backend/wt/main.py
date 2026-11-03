"""The app and the workers.

One process runs the API and the workers (Uvicorn with 1 worker), because the workers
keep state in memory. The lifespan opens the DB, starts the workers at start and stops
them at shutdown.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from wt import api
from wt.api import errors
from wt.api.headers import SecurityHeadersMiddleware
from wt.bus import Bus
from wt.config import Env
from wt.context import AppContext, Worker
from wt.db import cleanup, open_db

log = logging.getLogger(__name__)


async def cleanup_worker(ctx: AppContext) -> None:
    await cleanup.run(ctx.engine)


# The workers that WT starts.
WORKERS: list[Worker] = [cleanup_worker]


def create_app(env: Env, workers: Sequence[Worker] = WORKERS) -> FastAPI:
    """Make the app. Tests give their own env and workers."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        engine = open_db(env.data_dir)
        ctx = AppContext(env=env, engine=engine, bus=Bus())
        app.state.ctx = ctx
        tasks = [asyncio.create_task(_run_worker(worker, ctx)) for worker in workers]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            engine.dispose()

    app = FastAPI(title="Watch Tower", lifespan=lifespan)
    app.include_router(api.router)
    errors.install(app)
    # Use X-Forwarded-For and X-Forwarded-Proto only from the trusted proxies.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=env.trusted_proxies)
    return app


async def _run_worker(worker: Worker, ctx: AppContext) -> None:
    """Run a worker. If it stops with an error, log the error. The other workers continue."""
    try:
        await worker(ctx)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Worker %s stopped with an error", worker.__name__)
