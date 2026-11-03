"""Repo cache: the last GitHub fetch for each repo, in the `repo_cache` table.

WT gets the release list only when the latest tag changes. A failed fetch, or a latest
tag that is not a version, saves the error text. A good fetch clears it. For an error,
WT saves no ETag, so that the next run gets the full answer again (not a 304).
"""

import asyncio
from dataclasses import asdict

from sqlalchemy import Engine
from sqlmodel import Session

from wt import clock
from wt.db.models import RepoCache
from wt.versions.github import (
    Fetched,
    GitHub,
    GitHubError,
    NoRelease,
    NotModified,
    wait_on_rate_limit,
)
from wt.versions.rules import Release, is_version_tag


def cached_releases(cache: RepoCache) -> list[Release]:
    return [Release(**item) for item in cache.releases]


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
    except GitHubError as error:
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
