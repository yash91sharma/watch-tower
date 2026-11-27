"""Tests for the repo cache in wt.versions.cache (respx, clock)."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy import Engine, inspect
from sqlmodel import Session

from wt.clock import FakeClock
from wt.db.models import RepoCache
from wt.versions.cache import (
    cache_key,
    cached_releases,
    refresh_repo,
    refresh_tags,
    status_caches,
)
from wt.versions.dockerhub import DockerHub
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


def test_status_caches_gives_each_repo_without_the_release_list(
    db_engine: Engine, clock: FakeClock
) -> None:
    notes = [{"tag": "1.0", "notes": "n", "draft": False, "prerelease": False}]
    with Session(db_engine) as session:
        session.add(RepoCache(repo="o/a", latest_tag="1.0", releases=notes))
        session.add(RepoCache(repo="o/b", error="HTTP 500", fetched_at=clock.now()))
        session.commit()

    with Session(db_engine) as session:
        caches = status_caches(session)

        assert {repo: (c.latest_tag, c.error) for repo, c in caches.items()} == {
            "o/a": ("1.0", None),
            "o/b": (None, "HTTP 500"),
        }
        # Not loaded. A read in the session still loads it.
        state = inspect(caches["o/a"])
        assert state is not None
        assert "releases" not in state.dict
        assert caches["o/a"].releases == notes


HUB = "http://hub.test"
HUB_TAGS = f"{HUB}/v2/namespaces/searxng/repositories/searxng/tags"
HUB_KEY = "dockerhub:searxng/searxng@3-<commit>"


@pytest.fixture
async def hub() -> AsyncIterator[DockerHub]:
    client = DockerHub(HUB)
    yield client
    await client.close()


def hub_row(engine: Engine) -> RepoCache:
    with Session(engine) as session:
        cache = session.get(RepoCache, HUB_KEY)
    assert cache is not None
    return cache


def tag_page(*tags: str) -> httpx.Response:
    return httpx.Response(200, json={"results": [{"name": tag} for tag in tags]})


@pytest.mark.parametrize(
    ("source", "tag", "key"),
    [
        ("owner/app", "v1.2", "owner/app"),
        ("dockerhub:searxng/searxng", "2026.11.20-a7959eeaf", HUB_KEY),
        (
            "dockerhub:library/postgres",
            "16.4-alpine",
            "dockerhub:library/postgres@2-alpine",
        ),
        ("dockerhub:library/postgres", "v16", "dockerhub:library/postgres@v1"),
        ("dockerhub:library/postgres", "latest", "dockerhub:library/postgres"),
        (None, "1.0", ""),
    ],
)
def test_cache_key(source: str | None, tag: str | None, key: str) -> None:
    """Docker Hub: one cache row per tag kind, because each kind has its own latest."""
    assert cache_key(source, tag) == key


async def test_docker_hub_fetch_saves_the_latest_tag_of_the_same_kind(
    db_engine: Engine, hub: DockerHub, clock: FakeClock
) -> None:
    tags = ("latest", "2026.11.26-b5605b8f2", "2026.11.23-a7163d091")
    with respx.mock:
        respx.get(HUB_TAGS).mock(return_value=tag_page(*tags))

        await refresh_tags(
            db_engine, hub, HUB_KEY, "searxng/searxng", "2026.11.20-a7959eeaf"
        )

    cache = hub_row(db_engine)
    assert (cache.latest_tag, cache.error, cache.fetched_at) == (
        "2026.11.26-b5605b8f2",
        None,
        clock.now(),
    )
    assert cached_releases(cache) == [
        Release("2026.11.26-b5605b8f2", ""),
        Release("2026.11.23-a7163d091", ""),
    ]


async def test_docker_hub_with_no_tag_of_the_same_kind_is_an_error(
    db_engine: Engine, hub: DockerHub
) -> None:
    with respx.mock:
        respx.get(HUB_TAGS).mock(return_value=tag_page("latest", "1.0"))

        await refresh_tags(
            db_engine, hub, HUB_KEY, "searxng/searxng", "2026.11.20-a7959eeaf"
        )

    cache = hub_row(db_engine)
    assert cache.latest_tag is None
    assert cache.error == "Docker Hub has no tag of the same kind as the running tag"


async def test_docker_hub_error_is_saved(db_engine: Engine, hub: DockerHub) -> None:
    with respx.mock:
        respx.get(HUB_TAGS).mock(return_value=httpx.Response(404))

        await refresh_tags(
            db_engine, hub, HUB_KEY, "searxng/searxng", "2026.11.20-a7959eeaf"
        )

    assert hub_row(db_engine).error == "The image is not on Docker Hub"
