"""Version rules (pure): tag filter, update rule and release range."""

import re
from dataclasses import dataclass
from enum import StrEnum

from wt.db.models import RepoCache

# Optional "v", numbers with dots, optional "-suffix" (for example "-alpine", "-r0-ls104").
_VERSION_TAG = re.compile(r"([vV]?)(\d+(?:\.\d+)*)(?:-([0-9A-Za-z._-]+))?")
# A git commit hash suffix, for example "-b5605b8f2" (SearXNG builds).
_COMMIT = re.compile(r"[0-9a-f]{7,40}")


def is_version_tag(tag: str | None) -> bool:
    """True for a version tag. Other tags (latest, stable, main, no tag) get no check."""
    return tag is not None and _VERSION_TAG.fullmatch(tag) is not None


def version_parts(tag: str) -> tuple[int, ...]:
    """The number parts. A leading v and a -suffix are removed. "v1.2.3-alpine" -> (1, 2, 3)."""
    match = _VERSION_TAG.fullmatch(tag)
    if match is None:
        raise ValueError(f"{tag!r} is not a version tag")
    return tuple(int(part) for part in match.group(2).split("."))


def same_flavor(tag: str, running: str) -> bool:
    """True if `tag` and `running` are version tags of the same kind.

    The same kind has the same "v", the same number of parts and the same suffix. So
    "16.4-alpine" matches "16.5-alpine", not "16.5" or "17". A commit hash suffix matches
    any commit hash. WT uses it for Docker Hub, where one repo has many tag kinds.
    """
    flavor = _flavor(tag)
    return flavor is not None and flavor == _flavor(running)


def _flavor(tag: str) -> tuple[str, int, str] | None:
    """("v" or "", number of parts, suffix). None if `tag` is not a version tag."""
    match = _VERSION_TAG.fullmatch(tag)
    if match is None:
        return None
    prefix, numbers, suffix = match.group(1), match.group(2), match.group(3) or ""
    if _COMMIT.fullmatch(suffix):
        suffix = "<commit>"
    return prefix, numbers.count(".") + 1, suffix


def latest_version(tags: list[str], running: str) -> str | None:
    """The highest tag of the same kind as `running`. None if there is none.

    For equal versions, the first tag wins (Docker Hub sends the newest first).
    """
    kept = [tag for tag in tags if same_flavor(tag, running)]
    return max(kept, key=_key) if kept else None


def is_update(running: str, latest: str) -> bool:
    """True if `latest` is higher than `running`.

    A running tag that is a short form of the latest is no update ("16" and "16.4" match
    "16.4.1"). Else missing parts are 0 ("1.2" = "1.2.0").
    """
    current, newest = version_parts(running), version_parts(latest)
    if len(current) < len(newest) and newest[: len(current)] == current:
        return False
    return _key(latest) > _key(running)


def _key(tag: str) -> tuple[int, ...]:
    """The version parts to compare. Trailing zeros are removed, so "1.2" = "1.2.0"."""
    parts = version_parts(tag)
    while parts and parts[-1] == 0:
        parts = parts[:-1]
    return parts


@dataclass(frozen=True)
class Release:
    """A GitHub release."""

    tag: str
    notes: str
    draft: bool = False
    prerelease: bool = False


def release_range(releases: list[Release], running: str, latest: str) -> list[Release]:
    """The releases after the running version, up to the latest. Newest first.

    Drafts, pre-releases and tags that are not versions are dropped.
    """
    low, high = _key(running), _key(latest)
    kept = [
        release
        for release in releases
        if not release.draft
        and not release.prerelease
        and is_version_tag(release.tag)
        and low < _key(release.tag) <= high
    ]
    return sorted(kept, key=lambda release: _key(release.tag), reverse=True)


def join_notes(releases: list[Release]) -> str:
    """The notes of all releases, with one heading per version.

    Many release notes start with a heading of their version. WT removes it, so that the
    version does not show two times.
    """
    sections = [
        f"## {release.tag}\n\n{_without_tag_heading(release)}".strip()
        for release in releases
    ]
    return "\n\n".join(sections)


def _without_tag_heading(release: Release) -> str:
    notes = release.notes.strip()
    first, _, rest = notes.partition("\n")
    if first.lstrip("#").strip() == release.tag and first.startswith("#"):
        return rest.strip()
    return notes


class Status(StrEnum):
    NO_CHECK = "no check"
    NO_SOURCE = "no source"
    NOT_CHECKED = "not checked"
    UP_TO_DATE = "up to date"
    UPDATE = "update"
    ERROR = "error"


def container_status(
    tag: str | None, release_source: str | None, cache: RepoCache | None
) -> Status:
    """The version status of a container. Computed on read, so it stays after a restart."""
    if not is_version_tag(tag):
        return Status.NO_CHECK
    if not release_source:
        return Status.NO_SOURCE
    if cache is None or cache.fetched_at is None:
        return Status.NOT_CHECKED
    if cache.error:
        return Status.ERROR
    if tag is None or cache.latest_tag is None:
        return Status.NOT_CHECKED
    return Status.UPDATE if is_update(tag, cache.latest_tag) else Status.UP_TO_DATE
