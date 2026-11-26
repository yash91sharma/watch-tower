"""Tests for the tag filter in wt.versions.rules."""

import pytest

from wt.versions.rules import is_version_tag, latest_version, same_flavor


@pytest.mark.parametrize(
    "tag",
    [
        "1",
        "16",
        "1.2",
        "v1.2.3",
        "V2.0",
        "16.4-alpine",
        "3.4.7-r0-ls104",
        "2024.10.1",
        "1.2.3-rc.1",
    ],
)
def test_version_tags(tag: str) -> None:
    assert is_version_tag(tag) is True


@pytest.mark.parametrize(
    "tag",
    [
        None,
        "",
        "latest",
        "stable",
        "main",
        "v",
        "1.",
        ".1",
        "1..2",
        "v1.2.3-",
        "1.2a",
        "sha256:abc",
        "1.2.3+build",
        " 1.2",
        "1.2\n",
    ],
)
def test_tags_that_are_not_versions(tag: str | None) -> None:
    assert is_version_tag(tag) is False


@pytest.mark.parametrize(
    ("tag", "running", "same"),
    [
        ("1.3.0", "1.2.0", True),
        ("2.0.0", "1.2.0", True),
        # The number of parts must match: "1.3" is an other tag line than "1.2.0".
        ("1.3", "1.2.0", False),
        ("17", "16", True),
        ("16.4", "16", False),
        # The suffix must match.
        ("16.5-alpine", "16.4-alpine", True),
        ("16.5", "16.4-alpine", False),
        ("16.5-alpine", "16.4", False),
        ("16.5-bookworm", "16.4-alpine", False),
        # A commit hash suffix matches any commit hash (SearXNG).
        ("2026.11.26-b5605b8f2", "2026.11.20-a7959eeaf", True),
        ("2026.11.26-b5605b8", "2026.11.20-a7959eeaf", True),
        ("2026.11.26-beef", "2026.11.20-a7959eeaf", False),
        ("2026.11.26", "2026.11.20-a7959eeaf", False),
        # The "v" must match.
        ("v1.3", "v1.2", True),
        ("1.3", "v1.2", False),
        ("latest", "1.2", False),
        ("1.2", "latest", False),
    ],
)
def test_same_flavor(tag: str, running: str, same: bool) -> None:
    assert same_flavor(tag, running) is same


def test_latest_version_is_the_highest_tag_of_the_same_flavor() -> None:
    tags = ["latest", "18-alpine", "17.2", "16.5-alpine", "16.4-alpine", "16.6"]

    assert latest_version(tags, "16.4-alpine") == "16.5-alpine"
    assert latest_version(tags, "16.4") == "17.2"
    assert latest_version(tags, "16-alpine") == "18-alpine"
    assert latest_version(tags, "1.0.0") is None


def test_latest_version_of_equal_versions_is_the_first_tag() -> None:
    """Docker Hub sends the newest tag first. Two builds of one day: the newest wins."""
    tags = ["2026.11.20-cd6d28091", "2026.11.20-1ebea4a07", "2026.11.19-a3a114c84"]

    assert latest_version(tags, "2026.11.19-a3a114c84") == "2026.11.20-cd6d28091"
