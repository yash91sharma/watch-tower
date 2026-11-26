"""Parse rules for Docker data (pure functions): name, time, Compose project, exclude
label, image reference and release source.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import quote, urlsplit

PROJECT_LABEL = "com.docker.compose.project"
ENABLE_LABEL = "wt.enable"
SOURCE_LABEL = "org.opencontainers.image.source"
# The group of the containers with no Compose project.
OTHER_GROUP = "Other"

# "owner/repo" on GitHub. Owners have letters, digits and "-". Repos also "." and "_".
_GITHUB_REPO = r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+"
# "namespace/repo" on Docker Hub: lower case. Namespaces have letters and digits only.
_HUB_REPO = r"[a-z0-9]+/[a-z0-9]+(?:[._-][a-z0-9]+)*"
# A stored release source: "owner/repo" (GitHub) or "dockerhub:namespace/repo".
DOCKERHUB_PREFIX = "dockerhub:"
SOURCE_PATTERN = rf"^(?:{_GITHUB_REPO}|{DOCKERHUB_PREFIX}{_HUB_REPO})$"
_REPO = re.compile(_GITHUB_REPO)
_HUB = re.compile(_HUB_REPO)
_IMAGE_ID = re.compile(r"^(sha256:)?[0-9a-f]{64}$")
_GITHUB_HOSTS = {"github.com", "www.github.com"}
_HUB_HOSTS = {"hub.docker.com", "www.hub.docker.com"}
# Image name prefixes of Docker Hub. An image with no registry is on Docker Hub too.
_HUB_REGISTRIES = ("docker.io/", "index.docker.io/", "registry-1.docker.io/")


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


def docker_time(stamp: str) -> datetime | None:
    """A Docker time in UTC, for example "2026-11-20T01:42:46.871458168Z". None if it
    is not a Docker time. Docker gives ns. Python keeps µs, so the rest is cut.
    """
    if not stamp.endswith("Z"):
        return None
    seconds, _, fraction = stamp[:-1].partition(".")
    try:
        time = datetime.fromisoformat(seconds).replace(tzinfo=UTC)
    except ValueError:
        return None
    if fraction.isdigit():
        time = time.replace(microsecond=int(fraction[:6].ljust(6, "0")))
    return time


def compose_project(labels: Mapping[str, str]) -> str | None:
    return labels.get(PROJECT_LABEL) or None


def group_label(project: str | None) -> str:
    """The group of a container in the list: its Compose project, or "Other"."""
    return project or OTHER_GROUP


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
    """Give the stored release source from a URL or a short form. Else None.

    GitHub: a github.com URL or "owner/repo" gives "owner/repo". Docker Hub: a
    hub.docker.com URL or "dockerhub:namespace/repo" gives "dockerhub:namespace/repo".
    """
    value = (value or "").strip()
    if "://" in value:
        return _source_from_url(value)
    if value.startswith(DOCKERHUB_PREFIX):
        return value if _HUB.fullmatch(value.removeprefix(DOCKERHUB_PREFIX)) else None
    value = value.removesuffix(".git")
    return value if _REPO.fullmatch(value) else None


def _source_from_url(value: str) -> str | None:
    try:
        url = urlsplit(value)
        host = url.hostname
    except ValueError:
        return None
    parts = [part for part in url.path.split("/") if part]
    if url.scheme not in ("http", "https"):
        return None
    if host in _GITHUB_HOSTS and len(parts) >= 2:
        repo = f"{parts[0]}/{parts[1]}".removesuffix(".git")
        return repo if _REPO.fullmatch(repo) else None
    if host in _HUB_HOSTS and len(parts) >= 2 and parts[0] in ("r", "_"):
        # "/_/nginx" is an official image: "library/nginx".
        repo = f"library/{parts[1]}" if parts[0] == "_" else "/".join(parts[1:3])
        return f"{DOCKERHUB_PREFIX}{repo}" if _HUB.fullmatch(repo) else None
    return None


def dockerhub_source(image: str) -> str | None:
    """The Docker Hub source of an image name (no tag), for example "nginx" gives
    "dockerhub:library/nginx". None for an image on an other registry.
    """
    for registry in _HUB_REGISTRIES:
        image = image.removeprefix(registry)
    parts = image.split("/")
    if parts[0] == "localhost":
        return None
    if len(parts) == 1:
        parts = ["library", *parts]
    repo = "/".join(parts)
    # A registry host with "." or ":" ("ghcr.io", "localhost:5000") does not match _HUB.
    return f"{DOCKERHUB_PREFIX}{repo}" if _HUB.fullmatch(repo) else None


class SourceKind(StrEnum):
    GITHUB = "github"
    DOCKERHUB = "dockerhub"


@dataclass(frozen=True)
class Source:
    """A stored release source, split into its kind and its repo name."""

    kind: SourceKind
    # "owner/repo" (GitHub) or "namespace/repo" (Docker Hub).
    name: str

    def release_url(self, tag: str) -> str:
        """The web page of the version `tag`."""
        if self.kind is SourceKind.GITHUB:
            return f"https://github.com/{self.name}/releases/tag/{quote(tag, safe='')}"
        namespace, _, repo = self.name.partition("/")
        page = f"_/{repo}" if namespace == "library" else f"r/{self.name}"
        return f"https://hub.docker.com/{page}/tags?name={quote(tag, safe='')}"


def parse_source(stored: str) -> Source:
    """Split a stored release source (a value that release_source gave)."""
    if stored.startswith(DOCKERHUB_PREFIX):
        return Source(SourceKind.DOCKERHUB, stored.removeprefix(DOCKERHUB_PREFIX))
    return Source(SourceKind.GITHUB, stored)
