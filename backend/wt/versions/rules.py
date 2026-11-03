"""Version rules (pure): tag filter, update rule and release range."""

import re

# Optional "v", numbers with dots, optional "-suffix" (for example "-alpine", "-r0-ls104").
_VERSION_TAG = re.compile(r"[vV]?(\d+(?:\.\d+)*)(?:-[0-9A-Za-z._-]+)?")


def is_version_tag(tag: str | None) -> bool:
    """True for a version tag. Other tags (latest, stable, main, no tag) get no check."""
    return tag is not None and _VERSION_TAG.fullmatch(tag) is not None
