"""Repo cache: the last fetch for each release source, in the `repo_cache` table.

GitHub: one row per repo. WT gets the release list only when the latest tag changes. A
failed fetch, or a latest tag that is not a version, saves the error text. A good fetch
clears it. For an error, WT saves no ETag, so that the next run gets the full answer
again (not a 304).

Docker Hub: one row per repo and tag kind (see cache_key). The row keeps the tags of
that kind, with no release notes.
"""

import asyncio
from dataclasses import asdict
from typing import Any, cast

from sqlalchemy import Engine
from sqlalchemy.orm import QueryableAttribute, defer
from sqlmodel import Session, select

from wt import clock
from wt.db.models import RepoCache
from wt.docker.parse import SourceKind, parse_source
from wt.versions.dockerhub import DockerHub
from wt.versions.fetch import FetchError, wait_on_rate_limit
from wt.versions.github import Fetched, GitHub, NoRelease, NotModified
from wt.versions.rules import (
    Release,
    flavor_name,
    is_version_tag,
    latest_version,
    same_flavor,
)


def cache_key(source: str | None, tag: str | None) -> str:
    """The repo cache row of a container. "" with no source.

    GitHub: the source. Docker Hub: the source and the tag kind, for example
    "dockerhub:library/postgres@2-alpine", because each tag kind has its own latest tag.
    """
    if not source:
        return ""
    kind = flavor_name(tag) if tag else None
    if parse_source(source).kind is SourceKind.GITHUB or kind is None:
        return source
    return f"{source}@{kind}"


def cached_releases(cache: RepoCache) -> list[Release]:
    return [Release(**item) for item in cache.releases]


def status_caches(session: Session) -> dict[str, RepoCache]:
    """All repo caches by repo, for the version status. One query.

    The release lists are big and the status does not use them, so they are not loaded.
    Do not read `releases` from these rows after the session closes.
    """
    # SQLModel types the column as a list. It is a mapped attribute at run time.
    releases = cast(QueryableAttribute[Any], RepoCache.releases)
    rows = session.exec(select(RepoCache).options(defer(releases)))
    return {row.repo: row for row in rows}


async def refresh_repo(engine: Engine, github: GitHub, repo: str) -> None:
    """Fetch the latest release of `repo` and update its cache row."""
    cache = await asyncio.to_thread(_load, engine, repo)
    try:
        latest = await wait_on_rate_limit(lambda: github.latest(repo, cache.etag))
        match latest:
            case NotModified():
                cache.error = None
            case NoRelease():
                _set_error(cache, "The repo has no release on GitHub")
            case Fetched(release=release) if not is_version_tag(release.tag):
                _set_error(
                    cache, f"The latest release tag {release.tag!r} is not a version"
                )
            case _:
                tag = latest.release.tag
                if tag != cache.latest_tag or not cache.releases:
                    releases = await wait_on_rate_limit(lambda: github.releases(repo))
                    cache.releases = [asdict(item) for item in releases]
                cache.latest_tag, cache.etag, cache.error = tag, latest.etag, None
    except FetchError as error:
        cache.error = str(error)
    cache.fetched_at = clock.now()
    await asyncio.to_thread(_save, engine, cache)


async def refresh_tags(
    engine: Engine, hub: DockerHub, key: str, repo: str, running: str
) -> None:
    """Fetch the Docker Hub tags of `repo` and update the cache row `key`.

    The row keeps the tags of the same kind as `running`, and the highest one.
    """
    cache = await asyncio.to_thread(_load, engine, key)
    try:
        tags = await wait_on_rate_limit(lambda: hub.tags(repo))
        latest = latest_version(tags, running)
        if latest is None:
            _set_error(
                cache, "Docker Hub has no tag of the same kind as the running tag"
            )
        else:
            kept = [Release(tag, "") for tag in tags if same_flavor(tag, running)]
            cache.releases = [asdict(item) for item in kept]
            cache.latest_tag, cache.error = latest, None
    except FetchError as error:
        cache.error = str(error)
    cache.fetched_at = clock.now()
    await asyncio.to_thread(_save, engine, cache)


def _set_error(cache: RepoCache, text: str) -> None:
    cache.latest_tag, cache.etag, cache.error = None, None, text


def _load(engine: Engine, repo: str) -> RepoCache:
    with Session(engine) as session:
        return session.get(RepoCache, repo) or RepoCache(repo=repo)


def _save(engine: Engine, cache: RepoCache) -> None:
    with Session(engine) as session:
        session.merge(cache)
        session.commit()
