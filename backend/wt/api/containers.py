"""Containers API: the list, the detail and the release source."""

from datetime import datetime
from typing import Literal, cast, get_args
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from wt import clock
from wt.api.deps import Ctx, get_container, get_live
from wt.db.models import EVENT_MAX_AGE, Container, Event, EventKind, RepoCache, Severity
from wt.docker.inventory import LiveContainer
from wt.docker.parse import group_label, release_source
from wt.versions.rules import Status, container_status
from wt.versions.updates import current_update

router = APIRouter(prefix="/containers", tags=["containers"])


class ReleaseSourceIn(BaseModel):
    # A GitHub URL or "owner/repo". None clears the source.
    source: str | None = Field(max_length=500)
    confirmed: bool


class ReleaseSourceOut(BaseModel):
    name: str
    release_source: str | None
    source_confirmed: bool


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


class ContainerOut(BaseModel):
    name: str
    # Docker state: created, running, paused, restarting, removing, exited or dead.
    state: str
    health: Health
    image: str | None
    tag: str | None
    status: Status
    latest_version: str | None
    # The GitHub release page of the latest version. None with no latest version.
    latest_url: str | None
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
    latest = cache.latest_tag if cache and known else None
    return ContainerOut(
        name=row.name,
        state=live.state,
        health=cast(Health, health),
        image=row.image,
        tag=row.tag,
        status=status,
        latest_version=latest,
        latest_url=(
            f"https://github.com/{row.release_source}/releases/tag/{quote(latest)}"
            if latest
            else None
        ),
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
        for row, live in ctx.inventory.live_rows(session):
            groups.setdefault(row.compose_project, []).append(
                container_out(session, row, live)
            )
    projects = sorted(project for project in groups if project is not None)
    ordered = [*projects, None] if None in groups else projects
    return [
        GroupOut(
            project=project,
            label=group_label(project),
            update=update_level(groups[project]),
            containers=sorted(groups[project], key=lambda item: item.name),
        )
        for project in ordered
    ]


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
        row, live = get_live(session, ctx.inventory, name)
        update = current_update(session, row)
        since = clock.now() - EVENT_MAX_AGE
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
