"""Containers API."""

from typing import Literal, cast, get_args

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from wt.api.deps import Ctx
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, RepoCache, Severity
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
