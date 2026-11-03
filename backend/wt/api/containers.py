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
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from wt import clock
from wt.api.deps import Ctx
from wt.context import AppContext
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, Event, EventKind, RepoCache, Severity
from wt.docker.client import DockerUnavailableError
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
    row = session.exec(
        select(Container).where(
            Container.host_id == LOCAL_HOST_ID, Container.name == name
        )
    ).first()
    if row is None or not row.enabled:
        raise HTTPException(404, f"No container {name!r}")
    return row


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


class GroupOut(BaseModel):
    # The Compose project. None for the group "Other".
    project: str | None
    label: str
    containers: list[ContainerOut]


def container_out(
    session: Session, row: Container, live: LiveContainer
) -> ContainerOut:
    cache = session.get(RepoCache, row.release_source or "")
    status = container_status(row.tag, row.release_source, cache)
    known = status in (Status.UPDATE, Status.UP_TO_DATE) and cache is not None
    update = current_update(session, row)
    health = live.health if live.health in get_args(Health) else "none"
    return ContainerOut(
        name=row.name,
        state=live.state,
        health=cast(Health, health),
        image=row.image,
        tag=row.tag,
        status=status,
        latest_version=cache.latest_tag if known and cache else None,
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
            row = session.exec(
                select(Container).where(
                    Container.host_id == LOCAL_HOST_ID, Container.name == name
                )
            ).first()
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
    live = ctx.inventory.get(name)
    with Session(ctx.engine) as session:
        row = get_container(session, name)
        if live is None or row.id is None:
            raise HTTPException(404, f"No container {name!r}")
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


class LogLineOut(BaseModel):
    time: datetime | None
    stream: Literal["stdout", "stderr"]
    text: str


def _live_container(ctx: AppContext, name: str) -> LiveContainer:
    """The live state of a container that is not excluded. 404 if it is not in Docker now."""
    with Session(ctx.engine) as session:
        get_container(session, name)
    live = ctx.inventory.get(name)
    if live is None:
        raise HTTPException(404, f"No container {name!r}")
    return live


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
    live = await asyncio.to_thread(_live_container, ctx, name)
    docker = ctx.docker_factory()

    async def events() -> AsyncGenerator[str]:
        try:
            # aclosing: when the client goes, close the Docker stream before the client.
            async with aclosing(
                docker.logs(live.docker_id, tail, since, follow)
            ) as lines:
                async for line in lines:
                    item = LogLineOut(
                        time=line.time, stream=line.stream, text=line.text
                    )
                    yield f"data: {item.model_dump_json()}\n\n"
        except DockerUnavailableError as error:
            yield f"event: error\ndata: {json.dumps(str(error))}\n\n"
        finally:
            await docker.close()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{name}/logs.txt", response_class=StreamingResponse)
async def download_logs(name: str, ctx: Ctx) -> StreamingResponse:
    """The full log as a text file, no follow. Line: <time> <stream> <text>."""
    live = await asyncio.to_thread(_live_container, ctx, name)
    docker = ctx.docker_factory()

    async def text() -> AsyncGenerator[str]:
        try:
            async with aclosing(
                docker.logs(live.docker_id, None, None, False)
            ) as lines:
                async for line in lines:
                    time = (
                        line.time.isoformat().replace("+00:00", "Z")
                        if line.time
                        else "-"
                    )
                    yield f"{time} {line.stream} {line.text}\n"
        finally:
            await docker.close()

    filename = f"{name}-{clock.now().date().isoformat()}.log"
    return StreamingResponse(
        text(),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
