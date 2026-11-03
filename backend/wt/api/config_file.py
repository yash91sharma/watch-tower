"""Config export and import: the settings and the per-container admin values. No secrets."""

from typing import Annotated, Literal, Self

from fastapi import APIRouter, Body, Response
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    JsonValue,
    StringConstraints,
    ValidationError,
    model_validator,
)
from sqlmodel import Session, col, select

from wt import clock
from wt.api.deps import Ctx
from wt.api.errors import FieldError, field_errors
from wt.bus import Topic
from wt.config import Settings, load_settings, write_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container
from wt.docker.parse import REPO_PATTERN

router = APIRouter(prefix="/config", tags=["config"])

FORMAT_VERSION = 1

# "owner/repo" on GitHub.
Repo = Annotated[str, StringConstraints(pattern=REPO_PATTERN)]


class ContainerConfig(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    release_source: Repo | None
    source_confirmed: bool


class ConfigFile(BaseModel):
    format_version: Literal[1]
    settings: Settings
    containers: list[ContainerConfig]

    @model_validator(mode="after")
    def _unique_names(self) -> Self:
        names = [item.name for item in self.containers]
        if len(names) != len(set(names)):
            raise ValueError("Each container name must be in the file only once")
        return self


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


class ImportResult(BaseModel):
    dry_run: bool
    valid: bool
    # The number of settings in the file.
    settings: int
    containers_added: int
    containers_updated: int
    errors: list[FieldError]


@router.post("/import")
def import_config(
    ctx: Ctx, body: Annotated[JsonValue, Body()], dry_run: bool = True
) -> ImportResult:
    """Check the file, then save the settings and the container values in one transaction.

    A dry run gives the counts and the errors and saves nothing. A real import of a
    bad file gives 422. Containers that WT does not know yet get a new row.
    """
    try:
        config = ConfigFile.model_validate(body)
    except ValidationError as error:
        if not dry_run:
            raise RequestValidationError(error.errors()) from None
        return ImportResult(
            dry_run=True,
            valid=False,
            settings=0,
            containers_added=0,
            containers_updated=0,
            errors=field_errors(error.errors()),
        )

    with Session(ctx.engine) as session:
        known = {
            row.name: row
            for row in session.exec(
                select(Container).where(Container.host_id == LOCAL_HOST_ID)
            )
        }
        added = [item for item in config.containers if item.name not in known]
        result = ImportResult(
            dry_run=dry_run,
            valid=True,
            settings=len(Settings.model_fields),
            containers_added=len(added),
            containers_updated=len(config.containers) - len(added),
            errors=[],
        )
        if dry_run:
            return result
        write_settings(session, config.settings)
        for item in config.containers:
            row = known.get(item.name) or Container(
                host_id=LOCAL_HOST_ID, name=item.name
            )
            row.release_source = item.release_source
            row.source_confirmed = item.source_confirmed
            session.add(row)
        session.commit()
    ctx.bus.publish(Topic.SETTINGS)
    return result
