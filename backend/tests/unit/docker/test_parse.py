"""Tests for wt.docker.parse (pure rules)."""

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wt.docker.parse import (
    ImageRef,
    InvalidImageRefError,
    Source,
    SourceKind,
    compose_project,
    container_name,
    docker_time,
    dockerhub_source,
    group_label,
    is_excluded,
    parse_image,
    parse_source,
    release_source,
)


@pytest.mark.parametrize(
    ("raw", "name"), [("/web", "web"), ("web", "web"), ("//x", "x")]
)
def test_container_name(raw: str, name: str) -> None:
    assert container_name(raw) == name


def test_compose_project() -> None:
    assert compose_project({"com.docker.compose.project": "site"}) == "site"
    assert compose_project({}) is None
    assert compose_project({"com.docker.compose.project": ""}) is None


@pytest.mark.parametrize(
    ("labels", "excluded"),
    [
        ({"wt.enable": "false"}, True),
        ({"wt.enable": "FALSE"}, True),
        ({"wt.enable": " False "}, True),
        ({"wt.enable": "true"}, False),
        ({"wt.enable": "no"}, False),
        ({}, False),
    ],
)
def test_is_excluded(labels: dict[str, str], excluded: bool) -> None:
    assert is_excluded(labels) is excluded


DIGEST = "sha256:" + "a" * 64


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("nginx", ImageRef("nginx", "latest", None)),
        ("nginx:1.27", ImageRef("nginx", "1.27", None)),
        ("library/nginx:1.27-alpine", ImageRef("library/nginx", "1.27-alpine", None)),
        ("ghcr.io/owner/app:v2.1.0", ImageRef("ghcr.io/owner/app", "v2.1.0", None)),
        ("registry:5000/app", ImageRef("registry:5000/app", "latest", None)),
        ("registry:5000/team/app:3", ImageRef("registry:5000/team/app", "3", None)),
        (f"nginx@{DIGEST}", ImageRef("nginx", None, DIGEST)),
        (f"nginx:1.27@{DIGEST}", ImageRef("nginx", "1.27", DIGEST)),
        (f"registry:5000/app@{DIGEST}", ImageRef("registry:5000/app", None, DIGEST)),
        (DIGEST, ImageRef("", None, DIGEST)),
        ("a" * 64, ImageRef("", None, "sha256:" + "a" * 64)),
    ],
)
def test_parse_image(ref: str, expected: ImageRef) -> None:
    assert parse_image(ref) == expected


@pytest.mark.parametrize("ref", ["", " ", ":1.0", "@sha256:x", "nginx:"])
def test_bad_image_ref(ref: str) -> None:
    with pytest.raises(InvalidImageRefError):
        parse_image(ref)


@pytest.mark.parametrize(
    ("value", "source"),
    [
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo/tree/main/sub", "owner/repo"),
        ("https://www.github.com/owner/repo/", "owner/repo"),
        ("http://github.com/Owner/My.Repo", "Owner/My.Repo"),
        ("owner/repo", "owner/repo"),
        ("owner/repo.git", "owner/repo"),
        (" owner/repo ", "owner/repo"),
        ("https://gitlab.com/owner/repo", None),
        ("https://github.com/owner", None),
        ("https://github.com.evil.com/owner/repo", None),
        ("ftp://github.com/owner/repo", None),
        ("not a url", None),
        ("http://[x/owner/repo", None),
        ("owner/repo/extra", None),
        # Python "$" also matches before a last newline. The config export rejects it.
        ("owner/repo\n.git", None),
        ("", None),
        (None, None),
        # Docker Hub: a hub.docker.com URL or "dockerhub:namespace/repo".
        ("https://hub.docker.com/r/searxng/searxng", "dockerhub:searxng/searxng"),
        ("https://hub.docker.com/r/searxng/searxng/tags", "dockerhub:searxng/searxng"),
        ("https://hub.docker.com/_/nginx", "dockerhub:library/nginx"),
        ("https://hub.docker.com/_/nginx/tags?page=1", "dockerhub:library/nginx"),
        ("https://www.hub.docker.com/r/a1/my_app.x-y", "dockerhub:a1/my_app.x-y"),
        ("dockerhub:searxng/searxng", "dockerhub:searxng/searxng"),
        (" dockerhub:library/nginx ", "dockerhub:library/nginx"),
        ("https://hub.docker.com/r/searxng", None),
        ("https://hub.docker.com/_/", None),
        ("https://hub.docker.com/u/searxng", None),
        ("https://hub.docker.com/r/SearXNG/searxng", None),
        ("https://hub.docker.com/r/wt_test/app", None),
        ("dockerhub:searxng", None),
        ("dockerhub:a/b/c", None),
        ("dockerhub:library\n/nginx", None),
    ],
)
def test_release_source(value: str | None, source: str | None) -> None:
    assert release_source(value) == source


@given(st.text())
def test_any_text_gives_a_result_or_a_typed_error(text: str) -> None:
    assert isinstance(container_name(text), str)
    assert release_source(text) is None or "/" in (release_source(text) or "")
    assert isinstance(is_excluded({"wt.enable": text}), bool)
    try:
        assert isinstance(parse_image(text), ImageRef)
    except InvalidImageRefError:
        pass


@pytest.mark.parametrize(
    ("image", "source"),
    [
        ("searxng/searxng", "dockerhub:searxng/searxng"),
        ("docker.io/searxng/searxng", "dockerhub:searxng/searxng"),
        ("index.docker.io/searxng/searxng", "dockerhub:searxng/searxng"),
        ("nginx", "dockerhub:library/nginx"),
        ("docker.io/library/postgres", "dockerhub:library/postgres"),
        ("ghcr.io/owner/app", None),
        ("lscr.io/linuxserver/sonarr", None),
        ("localhost:5000/app", None),
        ("localhost/app", None),
        ("a/b/c", None),
        # Not a Docker Hub name (an "_" in the namespace). The E2E images use this.
        ("wt_test/e2e-app", None),
        ("", None),
    ],
)
def test_dockerhub_source(image: str, source: str | None) -> None:
    """The Docker Hub source of an image name (no tag), for an image with no label."""
    assert dockerhub_source(image) == source


@pytest.mark.parametrize(
    ("stored", "source", "url"),
    [
        (
            "owner/app",
            Source(SourceKind.GITHUB, "owner/app"),
            "https://github.com/owner/app/releases/tag/v1.0%2Bx",
        ),
        (
            "dockerhub:searxng/searxng",
            Source(SourceKind.DOCKERHUB, "searxng/searxng"),
            "https://hub.docker.com/r/searxng/searxng/tags?name=v1.0%2Bx",
        ),
        (
            "dockerhub:library/nginx",
            Source(SourceKind.DOCKERHUB, "library/nginx"),
            "https://hub.docker.com/_/nginx/tags?name=v1.0%2Bx",
        ),
    ],
)
def test_parse_source_and_release_url(stored: str, source: Source, url: str) -> None:
    assert parse_source(stored) == source
    assert source.release_url("v1.0+x") == url


def test_group_label() -> None:
    assert group_label("site") == "site"
    assert group_label(None) == "Other"


@pytest.mark.parametrize(
    ("stamp", "time"),
    [
        # Docker gives ns. Python keeps µs, so the rest is cut.
        (
            "2026-11-20T01:42:46.871458168Z",
            datetime(2026, 11, 20, 1, 42, 46, 871458, tzinfo=UTC),
        ),
        ("2026-01-01T00:00:01.5Z", datetime(2026, 1, 1, 0, 0, 1, 500000, tzinfo=UTC)),
        ("2026-01-01T00:00:01Z", datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)),
        # A stopped container.
        ("0001-01-01T00:00:00Z", datetime(1, 1, 1, tzinfo=UTC)),
    ],
)
def test_docker_time(stamp: str, time: datetime) -> None:
    assert docker_time(stamp) == time


@pytest.mark.parametrize(
    "stamp", ["", "no time", "2026-01-01T00:00:01", "2026-99-99T00:00:00Z"]
)
def test_docker_time_of_a_bad_value_is_none(stamp: str) -> None:
    assert docker_time(stamp) is None
