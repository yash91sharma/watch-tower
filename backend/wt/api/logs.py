"""Container logs API: the live log (SSE) and the log download."""

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter
from sqlmodel import Session

from wt import clock
from wt.api.deps import Ctx, get_live
from wt.api.stream import sse_response
from wt.context import AppContext
from wt.docker.client import DockerUnavailableError
from wt.docker.inventory import LiveContainer
from wt.docker.logs import LogLine

# The same tag as the other container routes.
router = APIRouter(prefix="/containers", tags=["containers"])

MAX_TAIL = 10_000


# Docker log line -> JSON.
_LOG_LINE = TypeAdapter(LogLine)


async def _log_lines(
    ctx: AppContext,
    live: LiveContainer,
    tail: int | None,
    since: datetime | None,
    follow: bool,
) -> AsyncGenerator[LogLine]:
    """The log lines of a container. Use it with aclosing: when the client goes, WT closes
    the Docker stream, then the Docker client.
    """
    docker = ctx.docker_factory()
    try:
        async with aclosing(docker.logs(live.docker_id, tail, since, follow)) as lines:
            async for line in lines:
                yield line
    finally:
        await docker.close()


@router.get("/{name}/logs", response_class=StreamingResponse)
async def container_logs(
    name: str,
    ctx: Ctx,
    tail: Annotated[int, Query(ge=0, le=MAX_TAIL)] = 500,
    follow: bool = True,
    since: datetime | None = None,
) -> StreamingResponse:
    """The log as SSE: one event per line, {time, stream, text}.

    When the client goes, WT stops the Docker log stream.
    """
    live = await asyncio.to_thread(_live, ctx, name)

    async def events() -> AsyncGenerator[str]:
        async with aclosing(_log_lines(ctx, live, tail, since, follow)) as lines:
            try:
                async for line in lines:
                    yield f"data: {_LOG_LINE.dump_json(line).decode()}\n\n"
            except DockerUnavailableError as error:
                yield f"event: error\ndata: {json.dumps(str(error))}\n\n"

    return sse_response(events())


@router.get("/{name}/logs.txt", response_class=StreamingResponse)
async def download_logs(name: str, ctx: Ctx) -> StreamingResponse:
    """The full log as a text file, no follow. Line: <time> <stream> <text>."""
    live = await asyncio.to_thread(_live, ctx, name)

    async def text() -> AsyncGenerator[str]:
        async with aclosing(_log_lines(ctx, live, None, None, False)) as lines:
            async for line in lines:
                time = (
                    line.time.isoformat().replace("+00:00", "Z") if line.time else "-"
                )
                yield f"{time} {line.stream} {line.text}\n"

    filename = f"{name}-{clock.now().date().isoformat()}.log"
    return StreamingResponse(
        text(),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _live(ctx: AppContext, name: str) -> LiveContainer:
    with Session(ctx.engine) as session:
        return get_live(session, ctx.inventory, name)[1]
