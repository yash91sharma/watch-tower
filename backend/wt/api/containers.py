"""Containers API."""

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from wt.api.deps import Ctx
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container
from wt.docker.parse import release_source

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
