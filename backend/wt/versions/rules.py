"""Version rules (pure): tag filter, update rule and release range."""

import re

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
    width = max(len(current), len(newest))
    return _pad(newest, width) > _pad(current, width)


def _pad(parts: tuple[int, ...], width: int) -> tuple[int, ...]:
    return parts + (0,) * (width - len(parts))
