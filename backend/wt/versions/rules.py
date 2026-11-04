"""Version rules (pure): tag filter, update rule and release range."""

import re
from dataclasses import dataclass
from enum import StrEnum

from wt.db.models import RepoCache

# Optional "v", numbers with dots, optional "-suffix" (for example "-alpine", "-r0-ls104").
_VERSION_TAG = re.compile(r"[vV]?(\d+(?:\.\d+)*)(?:-[0-9A-Za-z._-]+)?")


def is_version_tag(tag: str | None) -> bool:
    """True for a version tag. Other tags (latest, stable, main, no tag) get no check."""
    return tag is not None and _VERSION_TAG.fullmatch(tag) is not None


def version_parts(tag: str) -> tuple[int, ...]:
    """The number parts. A leading v and a -suffix are removed. "v1.2.3-alpine" -> (1, 2, 3)."""
    match = _VERSION_TAG.fullmatch(tag)
    if match is None:
        raise ValueError(f"{tag!r} is not a version tag")
    return tuple(int(part) for part in match.group(1).split("."))


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
    """The notes of all releases, with one heading per version."""
    sections = [
        f"## {release.tag}\n\n{release.notes.strip()}".strip() for release in releases
    ]
    return "\n\n".join(sections)


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
