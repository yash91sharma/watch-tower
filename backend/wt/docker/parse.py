"""Parse rules for Docker data (pure functions): name, Compose project, exclude label,
image reference and release source.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

PROJECT_LABEL = "com.docker.compose.project"
ENABLE_LABEL = "wt.enable"
SOURCE_LABEL = "org.opencontainers.image.source"

# "owner/repo" on GitHub. Owners have letters, digits and "-". Repos also "." and "_".
REPO_PATTERN = r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$"
_REPO = re.compile(REPO_PATTERN)
_IMAGE_ID = re.compile(r"^(sha256:)?[0-9a-f]{64}$")
_GITHUB_HOSTS = {"github.com", "www.github.com"}


class InvalidImageRefError(ValueError):
    pass


@dataclass(frozen=True)
class ImageRef:
    # The image name with the registry, for example "ghcr.io/owner/app". Empty for an image id.
    repo: str
    # None if the reference has only a digest.
    tag: str | None
    digest: str | None


def container_name(raw: str) -> str:
    """Docker names start with "/". WT names do not."""
    return raw.lstrip("/")


def compose_project(labels: Mapping[str, str]) -> str | None:
    return labels.get(PROJECT_LABEL) or None


def is_excluded(labels: Mapping[str, str]) -> bool:
    """True if the label wt.enable is "false" (any case)."""
    return labels.get(ENABLE_LABEL, "").strip().lower() == "false"


def parse_image(ref: str) -> ImageRef:
    """Split an image reference into repo, tag and digest. No tag and no digest: "latest"."""
    ref = ref.strip()
    if _IMAGE_ID.match(ref):
        return ImageRef("", None, ref if ref.startswith("sha256:") else f"sha256:{ref}")
    name, _, digest = ref.partition("@")
    # A ":" after the last "/" starts the tag. A ":" before it is a registry port.
    colon = name.rfind(":")
    if colon > name.rfind("/"):
        repo, tag = name[:colon], name[colon + 1 :]
        if not tag:
            raise InvalidImageRefError(f"Empty tag in {ref!r}")
    else:
        repo, tag = name, None
    if not repo or ("@" in ref and not digest):
        raise InvalidImageRefError(f"Not an image reference: {ref!r}")
    if tag is None and not digest:
        tag = "latest"
    return ImageRef(repo, tag, digest or None)


def release_source(value: str | None) -> str | None:
    """Give "owner/repo" from a GitHub URL or from "owner/repo". Else None."""
    value = (value or "").strip()
    if "://" in value:
        try:
            url = urlsplit(value)
            host = url.hostname
        except ValueError:
            return None
        if url.scheme not in ("http", "https") or host not in _GITHUB_HOSTS:
            return None
        parts = [part for part in url.path.split("/") if part]
        if len(parts) < 2:
            return None
        value = f"{parts[0]}/{parts[1]}"
    value = value.removesuffix(".git")
    return value if _REPO.fullmatch(value) else None
