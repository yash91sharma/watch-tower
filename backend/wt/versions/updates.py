"""Update rows: one row per container and new version, with the release notes.

The check run plans the rows that need new notes, gets the summary, and saves them. The
API and the update notifications read the current row of a container.
"""

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db.models import Container, RepoCache, Update
from wt.llm.client import LlmResult
from wt.versions.cache import cached_releases
from wt.versions.rules import Status, container_status, join_notes, release_range


def current_update(session: Session, container: Container) -> Update | None:
    """The current update of a container: the row for the latest tag, while the status is
    "update". Older rows are not current.
    """
    cache = _update_cache(session, container)
    if cache is None or container.id is None:
        return None
    return _update_row(session, container.id, cache.latest_tag or "")


def _update_cache(session: Session, container: Container) -> RepoCache | None:
    """The repo cache of the container, if its status is "update". Else None."""
    cache = session.get(RepoCache, container.release_source or "")
    status = container_status(container.tag, container.release_source, cache)
    return cache if status is Status.UPDATE else None


@dataclass(frozen=True)
class UpdatePlan:
    container_id: int
    from_version: str
    to_version: str
    notes: str


def plan_updates(engine: Engine, rows: list[Container]) -> list[UpdatePlan]:
    """The updates that need new notes: new rows, and rows with a new running version."""
    plans: list[UpdatePlan] = []
    with Session(engine) as session:
        for row in rows:
            cache = _update_cache(session, row)
            if cache is None or row.id is None or row.tag is None:
                continue
            latest = cache.latest_tag or ""
            existing = _update_row(session, row.id, latest)
            if existing is not None and existing.from_version == row.tag:
                continue
            releases = release_range(cached_releases(cache), row.tag, latest)
            plans.append(UpdatePlan(row.id, row.tag, latest, join_notes(releases)))
    return plans


def save_update(engine: Engine, plan: UpdatePlan, summary: LlmResult) -> None:
    """Add the row, or change it. A changed row keeps notified_at (no new message)."""
    with Session(engine) as session:
        row = _update_row(session, plan.container_id, plan.to_version) or Update(
            container_id=plan.container_id,
            from_version=plan.from_version,
            to_version=plan.to_version,
            severity=summary.severity,
            release_notes=plan.notes,
        )
        row.from_version = plan.from_version
        row.release_notes = plan.notes
        row.severity = summary.severity
        row.summary = summary.summary
        session.add(row)
        session.commit()


def _update_row(session: Session, container_id: int, to_version: str) -> Update | None:
    return session.exec(
        select(Update).where(
            Update.container_id == container_id, Update.to_version == to_version
        )
    ).first()
