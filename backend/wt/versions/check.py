"""Check run: fetch the latest release of each repo and save the status counts.

Only one run at a time. WT checks the containers that exist now, are not excluded, and
have a version tag and a release source. Containers with the same repo share one call.
"""

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt import clock
from wt.bus import Bus, Topic
from wt.config import Env, load_settings
from wt.db.models import Container, RepoCache, Setting
from wt.docker.inventory import Inventory
from wt.llm.summary import summarize
from wt.versions.cache import refresh_repo
from wt.versions.github import GitHub
from wt.versions.rules import (
    container_status,
    is_version_tag,
)
from wt.versions.updates import plan_updates, save_update

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
    # last_run is None after partial runs only (no full run yet).
    last_run = row.value["last_run"]
    return CheckStatus(
        datetime.fromisoformat(last_run) if last_run else None,
        dict(row.value["counts"]),
    )


class CheckRunner:
    def __init__(
        self,
        engine: Engine,
        env: Env,
        inventory: Inventory,
        bus: Bus,
        after_run: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._engine = engine
        self._env = env
        self._inventory = inventory
        self._bus = bus
        # Called after each run (the update notifications, 10.4).
        self._after_run = after_run
        self._lock = asyncio.Lock()
        # The background runs (start). Keep a reference, so that they are not garbage
        # collected.
        self._tasks: set[asyncio.Task[bool]] = set()

    @property
    def running(self) -> bool:
        return self._lock.locked()

    async def run(self, names: Collection[str] | None = None) -> bool:
        """Run a check. False if a run is active (then nothing starts).

        With `names`, check only these containers (one app). This partial run keeps the
        time of the last full run.
        """
        if self._lock.locked():
            return False
        async with self._lock:
            self._bus.publish(Topic.CHECK, {"running": True})
            try:
                await self._run(names)
            finally:
                self._bus.publish(Topic.CHECK, {"running": False})
        return True

    def start(self, names: Collection[str] | None = None) -> None:
        """Start a run in the background ("Check now"). The lifespan stops it (stop)."""
        task = asyncio.create_task(self.run(names))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """Cancel the background runs. Call it at shutdown, before the DB closes."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _run(self, names: Collection[str] | None) -> None:
        live = await asyncio.to_thread(_live_rows, self._engine, self._inventory)
        rows = live if names is None else [row for row in live if row.name in names]
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
        await asyncio.to_thread(_save_status, self._engine, live, names is None)
        if self._after_run is not None:
            await self._after_run()

    async def _update_rows(self, rows: list[Container]) -> None:
        """Add or change the update row of each container with an update."""
        settings = await asyncio.to_thread(load_settings, self._engine)
        for plan in await asyncio.to_thread(plan_updates, self._engine, rows):
            summary = await summarize(plan.notes, settings, self._env.llm_api_key)
            await asyncio.to_thread(save_update, self._engine, plan, summary)


def _live_rows(engine: Engine, inventory: Inventory) -> list[Container]:
    with Session(engine) as session:
        return [row for row, _ in inventory.live_rows(session)]


def _save_status(engine: Engine, rows: list[Container], full: bool) -> None:
    """Save the status counts of all live containers. Only a full run sets the run time."""
    last_run = clock.now() if full else load_check_status(engine).last_run
    with Session(engine) as session:
        caches = {cache.repo: cache for cache in session.exec(select(RepoCache))}
        counts = Counter(
            container_status(
                row.tag, row.release_source, caches.get(row.release_source or "")
            ).value
            for row in rows
        )
        value = {
            "last_run": last_run.isoformat() if last_run else None,
            "counts": dict(counts),
        }
        session.merge(Setting(key=CHECK_STATUS_KEY, value=value))
        session.commit()
