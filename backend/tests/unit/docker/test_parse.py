"""Tests for wt.docker.parse (pure rules)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wt.docker.parse import (
    ImageRef,
    InvalidImageRefError,
    compose_project,
    container_name,
    group_label,
    is_excluded,
    parse_image,
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


def test_group_label() -> None:
    assert group_label("site") == "site"
    assert group_label(None) == "Other"
