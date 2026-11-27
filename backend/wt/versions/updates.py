"""Update rows: one row per container and new version, with the release notes.

The check run plans the rows that need new notes, gets the summary, and saves them. The
API and the update notifications read the current row of a container.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from wt.db.models import Container, RepoCache, Update
from wt.docker.parse import SourceKind, parse_source
from wt.llm.client import LlmResult
from wt.versions.cache import cache_key, cached_releases
from wt.versions.rules import Status, container_status, join_notes, release_range


def current_updates(
    session: Session,
    containers: Iterable[Container],
    caches: Mapping[str, RepoCache],
) -> dict[str, Update]:
    """The current update of each container that has one, by container name. One query.

    The current update is the row for the latest tag, while the status is "update". Older
    rows are not current. `caches` has the repo caches by repo (see status_caches).
    """
    # Container id -> (name, latest tag).
    latest: dict[int, tuple[str, str]] = {}
    for container in containers:
        cache = caches.get(cache_key(container.release_source, container.tag))
        status = container_status(container.tag, container.release_source, cache)
        if cache is not None and container.id is not None and status is Status.UPDATE:
            latest[container.id] = (container.name, cache.latest_tag or "")
    rows = session.exec(select(Update).where(col(Update.container_id).in_(latest)))
    return {
        latest[row.container_id][0]: row
        for row in rows
        if row.to_version == latest[row.container_id][1]
    }


def _update_cache(session: Session, container: Container) -> RepoCache | None:
    """The repo cache of the container, if its status is "update". Else None."""
    cache = session.get(RepoCache, cache_key(container.release_source, container.tag))
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
            # Docker Hub has no release notes: the notes stay empty.
            source = parse_source(row.release_source or "")
            notes = join_notes(releases) if source.kind is SourceKind.GITHUB else ""
            plans.append(UpdatePlan(row.id, row.tag, latest, notes))
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
