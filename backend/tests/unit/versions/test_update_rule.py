"""Tests for the update rule in wt.versions.rules."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wt.versions.rules import is_update, version_parts


@pytest.mark.parametrize(
    ("tag", "parts"),
    [
        ("1", (1,)),
        ("v1.2.3", (1, 2, 3)),
        ("16.4-alpine", (16, 4)),
        ("3.4.7-r0-ls104", (3, 4, 7)),
    ],
)
def test_version_parts(tag: str, parts: tuple[int, ...]) -> None:
    assert version_parts(tag) == parts


@pytest.mark.parametrize("tag", ["latest", "", "1.2a"])
def test_version_parts_of_a_tag_that_is_not_a_version(tag: str) -> None:
    with pytest.raises(ValueError, match="version"):
        version_parts(tag)


@pytest.mark.parametrize(
    ("running", "latest", "update"),
    [
        # Short form: the running tag is a prefix of the latest.
        ("16", "16.4.1", False),
        ("16.4", "16.4.1", False),
        ("16", "17.0.1", True),
        ("16.3", "16.4.1", True),
        # Same version, other forms.
        ("1.2.0", "1.2", False),
        ("1.2", "1.2.0", False),
        ("v1.2.3", "1.2.3", False),
        ("1.2.3-alpine", "v1.2.3", False),
        # Newer and older.
        ("1.2.3", "1.2.4", True),
        ("1.2.3", "1.10.0", True),
        ("1.9", "1.10", True),
        ("2.0.0", "1.9.9", False),
        ("1.2.4", "1.2.3", False),
        ("2.0", "1.9.9.9", False),
    ],
)
def test_update_rule(running: str, latest: str, update: bool) -> None:
    assert is_update(running, latest) is update


def version_tag(prefix: str, numbers: list[int], suffix: str) -> str:
    return prefix + ".".join(map(str, numbers)) + suffix


versions = st.builds(
    version_tag,
    st.sampled_from(["", "v"]),
    st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=5),
    st.sampled_from(["", "-alpine", "-rc.1", "-r0-ls104"]),
)


@given(versions, versions)
def test_no_crash_and_same_result(running: str, latest: str) -> None:
    assert is_update(running, latest) == is_update(running, latest)


@given(versions)
def test_equal_versions_give_no_update(version: str) -> None:
    assert is_update(version, version) is False


@given(versions, versions)
def test_never_an_update_both_ways(first: str, second: str) -> None:
    assert not (is_update(first, second) and is_update(second, first))
