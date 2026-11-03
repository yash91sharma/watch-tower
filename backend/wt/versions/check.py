"""Check run: fetch the latest release of each repo and save the status counts.

Only one run at a time. WT checks the containers that exist now, are not excluded, and
have a version tag and a release source. Containers with the same repo share one call.
"""

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from wt import clock
from wt.config import Env, load_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, RepoCache, Setting, Update
from wt.docker.inventory import Inventory
from wt.llm.summary import Summary, summarize
from wt.versions.cache import cached_releases, refresh_repo
from wt.versions.github import GitHub
from wt.versions.rules import (
    Status,
    container_status,
    is_version_tag,
    join_notes,
    release_range,
)

# The setting row with the last run time and the status counts.
CHECK_STATUS_KEY = "check_status"


@dataclass(frozen=True)
class CheckStatus:
    last_run: datetime | None
    # Status value -> number of containers.
    counts: dict[str, int]


def load_check_status(engine: Engine) -> CheckStatus:
    with Session(engine) as session:
        row = session.get(Setting, CHECK_STATUS_KEY)
    if row is None:
        return CheckStatus(None, {})
    return CheckStatus(
        datetime.fromisoformat(row.value["last_run"]), dict(row.value["counts"])
    )


class CheckRunner:
    def __init__(self, engine: Engine, env: Env, inventory: Inventory) -> None:
        self._engine = engine
        self._env = env
        self._inventory = inventory
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._lock.locked()

    async def run(self) -> bool:
        """Run a check. False if a run is active (then nothing starts)."""
        if self._lock.locked():
            return False
        async with self._lock:
            rows = await asyncio.to_thread(
                _live_rows, self._engine, self._inventory.names()
            )
            repos = sorted(
                {
                    row.release_source
                    for row in rows
                    if row.release_source and is_version_tag(row.tag)
                }
            )
            github = GitHub(self._env.github_api_url, self._env.github_token)
            try:
                for repo in repos:
                    await refresh_repo(self._engine, github, repo)
            finally:
                await github.close()
            await self._update_rows(rows)
            await asyncio.to_thread(_save_status, self._engine, rows)
        return True

    async def _update_rows(self, rows: list[Container]) -> None:
        """Add or change the update row of each container with an update."""
        settings = await asyncio.to_thread(load_settings, self._engine)
        for plan in await asyncio.to_thread(_plan_updates, self._engine, rows):
            summary = await summarize(plan.notes, settings, self._env.llm_api_key)
            await asyncio.to_thread(_save_update, self._engine, plan, summary)


def current_update(session: Session, container: Container) -> Update | None:
    """The current update of a container: the row for the latest tag, while the status is
    "update". Older rows are not current.
    """
    cache = session.get(RepoCache, container.release_source or "")
    status = container_status(container.tag, container.release_source, cache)
    if status is not Status.UPDATE or cache is None or container.id is None:
        return None
    return _update_row(session, container.id, cache.latest_tag or "")


@dataclass(frozen=True)
class _UpdatePlan:
    container_id: int
    from_version: str
    to_version: str
    notes: str


def _plan_updates(engine: Engine, rows: list[Container]) -> list[_UpdatePlan]:
    """The updates that need new notes: new rows, and rows with a new running version."""
    plans: list[_UpdatePlan] = []
    with Session(engine) as session:
        for row in rows:
            cache = session.get(RepoCache, row.release_source or "")
            status = container_status(row.tag, row.release_source, cache)
            if (
                status is not Status.UPDATE
                or cache is None
                or row.id is None
                or row.tag is None
            ):
                continue
            latest = cache.latest_tag or ""
            existing = _update_row(session, row.id, latest)
            if existing is not None and existing.from_version == row.tag:
                continue
            releases = release_range(cached_releases(cache), row.tag, latest)
            plans.append(_UpdatePlan(row.id, row.tag, latest, join_notes(releases)))
    return plans


def _save_update(engine: Engine, plan: _UpdatePlan, summary: Summary) -> None:
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


def _live_rows(engine: Engine, names: list[str]) -> list[Container]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(Container).where(
                    Container.host_id == LOCAL_HOST_ID,
                    col(Container.enabled),
                    col(Container.name).in_(names),
                )
            )
        )


def _save_status(engine: Engine, rows: list[Container]) -> None:
    with Session(engine) as session:
        caches = {cache.repo: cache for cache in session.exec(select(RepoCache))}
        counts = Counter(
            container_status(
                row.tag, row.release_source, caches.get(row.release_source or "")
            ).value
            for row in rows
        )
        value = {"last_run": clock.now().isoformat(), "counts": dict(counts)}
        session.merge(Setting(key=CHECK_STATUS_KEY, value=value))
        session.commit()
