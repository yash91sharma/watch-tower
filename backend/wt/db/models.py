"""Tables. Each SQLModel class is the table and its Pydantic model.

Host data links to a `host` row, so that more hosts can come later. The container key
is (host_id, name): Compose makes a new Docker id on each recreate, but the name stays.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Dialect, UniqueConstraint
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

# Names for constraints and indexes. Alembic needs them to change SQLite tables.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator[datetime]):
    """A timezone-aware time, stored in UTC. SQLite has no timezone, so WT adds it."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("The time must have a timezone")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def _time(nullable: bool = False) -> Any:
    """A UTC time column."""
    return Field(sa_column=Column(UTCDateTime(), nullable=nullable))


class Severity(StrEnum):
    CRITICAL = "critical"
    NORMAL = "normal"


class EventKind(StrEnum):
    """A health state change of a container."""

    BECAME_UNHEALTHY = "became_unhealthy"
    RECOVERED_HEALTH = "recovered_health"
    RESTART_LOOP = "restart_loop"
    RECOVERED_LOOP = "recovered_loop"


class Host(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Container(SQLModel, table=True):
    """A container by name. The row stays when the container goes, so that admin values stay."""

    __table_args__ = (UniqueConstraint("host_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    host_id: int = Field(foreign_key="host.id", ondelete="CASCADE")
    name: str
    # Null until Docker sees the container (an import adds rows by name).
    docker_id: str | None = None
    compose_project: str | None = None
    image: str | None = None
    tag: str | None = None
    # False for containers with the label wt.enable=false.
    enabled: bool = True
    # "owner/repo" on GitHub.
    release_source: str | None = None
    # True after the admin confirms, edits or clears the source. Then the label does not change it.
    source_confirmed: bool = False


class RepoCache(SQLModel, table=True):
    """The last GitHub fetch for a repo. Containers with the same repo share it."""

    __tablename__ = "repo_cache"  # pyright: ignore[reportAssignmentType]

    repo: str = Field(primary_key=True)
    etag: str | None = None
    latest_tag: str | None = None
    releases: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    fetched_at: datetime | None = _time(nullable=True)
    error: str | None = None


class Update(SQLModel, table=True):
    """An available update of a container to one version."""

    __table_args__ = (UniqueConstraint("container_id", "to_version"),)

    id: int | None = Field(default=None, primary_key=True)
    container_id: int = Field(
        foreign_key="container.id", ondelete="CASCADE", index=True
    )
    from_version: str
    to_version: str
    severity: Severity
    summary: str = ""
    release_notes: str
    notified_at: datetime | None = _time(nullable=True)


class Event(SQLModel, table=True):
    """A health state change. Kept 7 days."""

    id: int | None = Field(default=None, primary_key=True)
    container_id: int = Field(
        foreign_key="container.id", ondelete="CASCADE", index=True
    )
    kind: EventKind
    time: datetime = _time()


class Setting(SQLModel, table=True):
    """A UI setting."""

    key: str = Field(primary_key=True)
    value: Any = Field(sa_column=Column(JSON, nullable=False))


class Admin(SQLModel, table=True):
    """The one admin. A reset deletes the row."""

    id: int | None = Field(default=None, primary_key=True)
    password_hash: str
    totp_secret: str
    # The last TOTP step that WT accepted. WT rejects it and older steps (replay).
    last_totp_step: int


class AuthSession(SQLModel, table=True):
    """A login session. WT stores only the SHA-256 hash of the token."""

    __tablename__ = "session"  # pyright: ignore[reportAssignmentType]

    token_hash: str = Field(primary_key=True)
    created: datetime = _time()
    expires: datetime = _time()
    last_seen: datetime = _time()


# All tables. Alembic and the tests use it.
metadata = SQLModel.metadata
