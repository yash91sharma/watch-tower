"""Containers API."""

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import datetime, timedelta
from typing import Annotated, Literal, cast, get_args

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, TypeAdapter
from sqlmodel import Session, col, select

from wt import clock
from wt.api.deps import Ctx
from wt.api.stream import sse_response
from wt.context import AppContext
from wt.db import find_container
from wt.db.models import Container, Event, EventKind, RepoCache, Severity
from wt.docker.client import DockerUnavailableError, LogLine
from wt.docker.inventory import LiveContainer
from wt.docker.parse import release_source
from wt.versions.check import current_update
from wt.versions.rules import Status, container_status

router = APIRouter(prefix="/containers", tags=["containers"])


class ReleaseSourceIn(BaseModel):
    # A GitHub URL or "owner/repo". None clears the source.
    source: str | None = Field(max_length=500)
    confirmed: bool


class ReleaseSourceOut(BaseModel):
    name: str
    release_source: str | None
    source_confirmed: bool


def get_container(session: Session, name: str) -> Container:
    """The container row by name. 404 if WT does not know it or it is excluded."""
    row = find_container(session, name)
    if row is None or not row.enabled:
        raise HTTPException(404, f"No container {name!r}")
    return row


def get_live(ctx: AppContext, name: str) -> LiveContainer:
    """The live state of a container that is not excluded. 404 if it is not in Docker now."""
    with Session(ctx.engine) as session:
        get_container(session, name)
    live = ctx.inventory.get(name)
    if live is None:
        raise HTTPException(404, f"No container {name!r}")
    return live


@router.put("/{name}/release-source")
def put_release_source(name: str, body: ReleaseSourceIn, ctx: Ctx) -> ReleaseSourceOut:
    """Set, confirm or clear the release source. A cleared source stays clear (confirmed)."""
    source = None
    if body.source is not None:
        source = release_source(body.source)
        if source is None:
            raise RequestValidationError(
                [{"loc": ("body", "source"), "msg": "Give a GitHub URL or owner/repo"}]
            )
    with Session(ctx.engine) as session:
        row = get_container(session, name)
        row.release_source = source
        row.source_confirmed = body.confirmed or source is None
        session.add(row)
        session.commit()
        return ReleaseSourceOut(
            name=row.name,
            release_source=row.release_source,
            source_confirmed=row.source_confirmed,
        )


Health = Literal["healthy", "unhealthy", "starting", "none"]
OTHER_LABEL = "Other"


class ContainerOut(BaseModel):
    name: str
    # Docker state: created, running, paused, restarting, removing, exited or dead.
    state: str
    health: Health
    image: str | None
    tag: str | None
    status: Status
    latest_version: str | None
    # The severity of the current update. None with no update.
    severity: Severity | None
    release_source: str | None
    source_confirmed: bool


# The highest update of a group: "critical" if a container has a critical update, else
# "update" if a container has an update, else "none".
UpdateLevel = Literal["none", "update", "critical"]


class GroupOut(BaseModel):
    # The Compose project. None for the group "Other".
    project: str | None
    label: str
    update: UpdateLevel
    containers: list[ContainerOut]


def update_level(containers: list[ContainerOut]) -> UpdateLevel:
    if any(item.severity is Severity.CRITICAL for item in containers):
        return "critical"
    if any(item.status is Status.UPDATE for item in containers):
        return "update"
    return "none"


def container_out(
    session: Session, row: Container, live: LiveContainer
) -> ContainerOut:
    cache = session.get(RepoCache, row.release_source or "")
    status = container_status(row.tag, row.release_source, cache)
    known = status in (Status.UPDATE, Status.UP_TO_DATE)
    update = current_update(session, row)
    health = live.health if live.health in get_args(Health) else "none"
    return ContainerOut(
        name=row.name,
        state=live.state,
        health=cast(Health, health),
        image=row.image,
        tag=row.tag,
        status=status,
        latest_version=cache.latest_tag if cache and known else None,
        severity=update.severity if update else None,
        release_source=row.release_source,
        source_confirmed=row.source_confirmed,
    )


@router.get("")
def list_containers(ctx: Ctx) -> list[GroupOut]:
    """Containers that exist in Docker now and are not excluded, in Compose groups.

    Groups are sorted by label; "Other" (no project) is last. Containers by name.
    """
    groups: dict[str | None, list[ContainerOut]] = {}
    with Session(ctx.engine) as session:
        for name in ctx.inventory.names():
            live = ctx.inventory.get(name)
            row = find_container(session, name)
            if live is None or row is None or not row.enabled:
                continue
            groups.setdefault(row.compose_project, []).append(
                container_out(session, row, live)
            )
    projects = sorted(project for project in groups if project is not None)
    ordered = [*projects, None] if None in groups else projects
    return [
        GroupOut(
            project=project,
            label=project or OTHER_LABEL,
            update=update_level(groups[project]),
            containers=sorted(groups[project], key=lambda item: item.name),
        )
        for project in ordered
    ]


EVENT_DAYS = 7


class UpdateOut(BaseModel):
    from_version: str
    to_version: str
    severity: Severity
    # Empty with no LLM result.
    summary: str
    # Plain text. The UI must not show it as HTML.
    release_notes: str


class EventOut(BaseModel):
    kind: EventKind
    time: datetime


class ContainerDetail(ContainerOut):
    update: UpdateOut | None
    # The health changes of the last 7 days, newest first.
    events: list[EventOut]


@router.get("/{name}")
def get_container_detail(name: str, ctx: Ctx) -> ContainerDetail:
    """One container with its current update and its events. 404 if it is not in Docker now."""
    with Session(ctx.engine) as session:
        live = get_live(ctx, name)
        row = get_container(session, name)
        update = current_update(session, row)
        since = clock.now() - timedelta(days=EVENT_DAYS)
        events = session.exec(
            select(Event)
            .where(Event.container_id == row.id, col(Event.time) >= since)
            .order_by(col(Event.time).desc())
        )
        return ContainerDetail(
            **container_out(session, row, live).model_dump(),
            update=UpdateOut.model_validate(update, from_attributes=True)
            if update
            else None,
            events=[EventOut(kind=event.kind, time=event.time) for event in events],
        )


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
    live = await asyncio.to_thread(get_live, ctx, name)

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
    live = await asyncio.to_thread(get_live, ctx, name)

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
