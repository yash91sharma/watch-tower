"""Tests for the repo cache in wt.versions.cache (respx, clock)."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy import Engine
from sqlmodel import Session

from wt.clock import FakeClock
from wt.db.models import RepoCache
from wt.versions.cache import cached_releases, refresh_repo
from wt.versions.github import GitHub
from wt.versions.rules import Release

pytestmark = pytest.mark.anyio

API = "http://github.test"
LATEST = f"{API}/repos/owner/app/releases/latest"
RELEASES = f"{API}/repos/owner/app/releases"


def release_json(tag: str) -> dict[str, object]:
    return {
        "tag_name": tag,
        "body": f"Notes {tag}",
        "draft": False,
        "prerelease": False,
    }


def latest(tag: str, etag: str = '"e1"') -> httpx.Response:
    return httpx.Response(200, json=release_json(tag), headers={"ETag": etag})


def release_list(*tags: str) -> httpx.Response:
    return httpx.Response(200, json=[release_json(tag) for tag in tags])


@pytest.fixture
async def github() -> AsyncIterator[GitHub]:
    client = GitHub(API, token=None)
    yield client
    await client.close()


def row(engine: Engine) -> RepoCache:
    with Session(engine) as session:
        cache = session.get(RepoCache, "owner/app")
    assert cache is not None
    return cache


async def test_first_fetch_saves_tag_etag_releases_and_time(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(return_value=latest("v1.1"))
        respx.get(RELEASES).mock(return_value=release_list("v1.1", "v1.0"))

        await refresh_repo(db_engine, github, "owner/app")

    cache = row(db_engine)
    assert (cache.latest_tag, cache.etag, cache.fetched_at, cache.error) == (
        "v1.1",
        '"e1"',
        clock.now(),
        None,
    )
    assert cached_releases(cache) == [
        Release("v1.1", "Notes v1.1"),
        Release("v1.0", "Notes v1.0"),
    ]


async def test_second_run_with_304_makes_no_release_list_call(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        latest_route = respx.get(LATEST).mock(
            side_effect=[latest("v1.1"), httpx.Response(304)]
        )
        list_route = respx.get(RELEASES).mock(return_value=release_list("v1.1"))
        await refresh_repo(db_engine, github, "owner/app")
        clock.advance(3600)

        await refresh_repo(db_engine, github, "owner/app")

    assert list_route.call_count == 1
    assert latest_route.calls.last.request.headers["If-None-Match"] == '"e1"'
    assert row(db_engine).fetched_at == clock.now()


async def test_release_list_only_when_the_latest_tag_changes(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            side_effect=[latest("v1.1"), latest("v1.1", '"e2"'), latest("v1.2", '"e3"')]
        )
        list_route = respx.get(RELEASES).mock(
            side_effect=[release_list("v1.1"), release_list("v1.2", "v1.1")]
        )

        for _ in range(3):
            await refresh_repo(db_engine, github, "owner/app")

    assert list_route.call_count == 2
    assert row(db_engine).latest_tag == "v1.2"
    assert row(db_engine).etag == '"e3"'


async def test_404_saves_an_error(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(return_value=httpx.Response(404))

        await refresh_repo(db_engine, github, "owner/app")

    cache = row(db_engine)
    assert cache.error == "The repo has no release on GitHub"
    assert (cache.latest_tag, cache.etag) == (None, None)


async def test_latest_tag_that_is_not_a_version_saves_an_error(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(return_value=latest("nightly"))

        await refresh_repo(db_engine, github, "owner/app")

    cache = row(db_engine)
    assert cache.error == "The latest release tag 'nightly' is not a version"
    assert cache.etag is None


async def test_failed_fetch_saves_the_error_and_a_good_fetch_clears_it(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            side_effect=[latest("v1.1"), httpx.ReadTimeout("slow"), httpx.Response(304)]
        )
        respx.get(RELEASES).mock(return_value=release_list("v1.1"))
        await refresh_repo(db_engine, github, "owner/app")

        await refresh_repo(db_engine, github, "owner/app")
        assert row(db_engine).error == "GitHub request failed: ReadTimeout"
        assert row(db_engine).latest_tag == "v1.1"

        await refresh_repo(db_engine, github, "owner/app")

    assert row(db_engine).error is None


async def test_failed_release_list_keeps_the_old_tag(
    db_engine: Engine, github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(return_value=latest("v1.1"))
        respx.get(RELEASES).mock(return_value=httpx.Response(500))

        await refresh_repo(db_engine, github, "owner/app")

    cache = row(db_engine)
    assert cache.error == "GitHub answered HTTP 500"
    assert (cache.latest_tag, cache.etag) == (None, None)
