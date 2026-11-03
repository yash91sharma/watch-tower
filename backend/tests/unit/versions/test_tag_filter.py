"""Tests for the tag filter in wt.versions.rules."""

import pytest

from wt.versions.rules import is_version_tag


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
