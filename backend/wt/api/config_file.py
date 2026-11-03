"""Config export and import: the settings and the per-container admin values. No secrets."""

from typing import Annotated, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, StringConstraints
from sqlmodel import Session, col, select

from wt import clock
from wt.api.deps import Ctx
from wt.config import Settings, load_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container

router = APIRouter(prefix="/config", tags=["config"])

FORMAT_VERSION = 1

# "owner/repo" on GitHub.
Repo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")]


class ContainerConfig(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    release_source: Repo | None
    source_confirmed: bool


class ConfigFile(BaseModel):
    format_version: Literal[1]
    settings: Settings
    containers: list[ContainerConfig]


@router.get("/export")
def export_config(ctx: Ctx, response: Response) -> ConfigFile:
    """The config as a JSON file download."""
    with Session(ctx.engine) as session:
        rows = session.exec(
            select(Container)
            .where(Container.host_id == LOCAL_HOST_ID)
            .order_by(col(Container.name))
        ).all()
    filename = f"wt-config-{clock.now().date().isoformat()}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return ConfigFile(
        format_version=FORMAT_VERSION,
        settings=load_settings(ctx.engine),
        containers=[
            ContainerConfig(
                name=row.name,
                release_source=row.release_source,
                source_confirmed=row.source_confirmed,
            )
            for row in rows
        ],
    )
