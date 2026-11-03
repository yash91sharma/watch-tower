"""Tests for the container status in wt.versions.rules."""

from datetime import UTC, datetime

import pytest

from wt.db.models import RepoCache
from wt.versions.rules import Status, container_status

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def cache(latest_tag: str | None = "v1.2", error: str | None = None) -> RepoCache:
    return RepoCache(repo="o/r", latest_tag=latest_tag, error=error, fetched_at=T0)


@pytest.mark.parametrize(
    ("tag", "source", "repo_cache", "status"),
    [
        ("latest", "o/r", cache(), Status.NO_CHECK),
        (None, "o/r", cache(), Status.NO_CHECK),
        ("1.2", None, cache(), Status.NO_SOURCE),
        ("1.2", "o/r", None, Status.NOT_CHECKED),
        ("1.2", "o/r", RepoCache(repo="o/r"), Status.NOT_CHECKED),
        ("1.2", "o/r", cache(latest_tag=None), Status.NOT_CHECKED),
        ("1.2", "o/r", cache(latest_tag=None, error="HTTP 500"), Status.ERROR),
        ("1.2", "o/r", cache(error="rate limit"), Status.ERROR),
        ("1.2", "o/r", cache("v1.2"), Status.UP_TO_DATE),
        ("1.2.0", "o/r", cache("v1.2"), Status.UP_TO_DATE),
        ("1.1", "o/r", cache("v1.2"), Status.UPDATE),
        ("1", "o/r", cache("v1.2"), Status.UP_TO_DATE),
    ],
)
def test_status(
    tag: str | None, source: str | None, repo_cache: RepoCache | None, status: Status
) -> None:
    assert container_status(tag, source, repo_cache) is status


def test_status_values() -> None:
    assert [status.value for status in Status] == [
        "no check",
        "no source",
        "not checked",
        "up to date",
        "update",
        "error",
    ]
