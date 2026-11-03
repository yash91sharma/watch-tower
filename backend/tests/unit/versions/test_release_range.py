"""Tests for the release range in wt.versions.rules."""

from hypothesis import given
from hypothesis import strategies as st

from wt.versions.rules import Release, join_notes, release_range, version_parts

RELEASES = [
    Release("v1.4.0-beta.1", "beta", prerelease=True),
    Release("v1.3.1", "Fix B"),
    Release("v1.3.0", "Feature A"),
    Release("v1.2.9", "Old"),
    Release("v1.3.5", "Draft notes", draft=True),
    Release("nightly", "Nightly build"),
    Release("v1.2.10", "Fix C"),
    Release("v1.4.0", "Newer than latest"),
]


def tags(releases: list[Release]) -> list[str]:
    return [release.tag for release in releases]


def test_range_above_running_up_to_latest_newest_first() -> None:
    result = release_range(RELEASES, running="1.2.9", latest="v1.3.1")

    assert tags(result) == ["v1.3.1", "v1.3.0", "v1.2.10"]


def test_range_with_running_suffix_and_short_latest() -> None:
    result = release_range(RELEASES, running="1.3.0-alpine", latest="1.3.1")

    assert tags(result) == ["v1.3.1"]


def test_empty_range_when_running_is_latest() -> None:
    assert release_range(RELEASES, running="1.3.1", latest="1.3.1") == []


def test_join_notes_has_one_heading_per_version() -> None:
    notes = join_notes([Release("v1.3.1", "Fix B\n"), Release("v1.3.0", "  Feature A")])

    assert notes == "## v1.3.1\n\nFix B\n\n## v1.3.0\n\nFeature A"


def test_join_notes_of_a_release_with_no_notes() -> None:
    assert join_notes([Release("v2.0", "")]) == "## v2.0"


def tag_text(parts: list[int]) -> str:
    return "v" + ".".join(map(str, parts))


part_lists = st.lists(st.integers(min_value=0, max_value=50), min_size=1, max_size=4)


@st.composite
def release_lists(draw: st.DrawFn) -> tuple[list[Release], str, str]:
    """Releases with a valid latest version above the running version."""
    running = draw(part_lists)
    latest = [*running, draw(st.integers(min_value=1, max_value=50))]
    others = draw(
        st.lists(
            st.builds(
                Release,
                st.one_of(
                    part_lists.map(tag_text),
                    st.sampled_from(["latest", "nightly", "x"]),
                ),
                st.text(max_size=20),
                st.booleans(),
                st.booleans(),
            ),
            max_size=15,
        )
    )
    releases = [*others, Release(tag_text(latest), "the latest")]
    shuffled = draw(st.permutations(releases))
    return list(shuffled), tag_text(running), tag_text(latest)


@given(release_lists())
def test_result_is_a_sorted_subset_that_contains_the_latest(
    data: tuple[list[Release], str, str],
) -> None:
    releases, running, latest = data

    result = release_range(releases, running, latest)

    assert all(release in releases for release in result)
    assert latest in tags(result)
    keys = [version_parts(release.tag) for release in result]
    padded = [key + (0,) * (6 - len(key)) for key in keys]
    assert padded == sorted(padded, reverse=True)
    assert all(not release.draft and not release.prerelease for release in result)
