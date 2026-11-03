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
from wt.config import Env
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, RepoCache, Setting
from wt.docker.inventory import Inventory
from wt.versions.cache import refresh_repo
from wt.versions.github import GitHub
from wt.versions.rules import container_status, is_version_tag

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
            await asyncio.to_thread(_save_status, self._engine, rows)
        return True


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
