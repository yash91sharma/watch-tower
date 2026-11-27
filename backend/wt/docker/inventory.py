"""Inventory: the containers on the host.

In memory: the live state of each container that exists now and is not excluded.
In the DB: one `container` row per name, kept when the container goes, so that the
admin values stay after a recreate.
"""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session

from wt.db import LOCAL_HOST_ID, find_container, local_containers
from wt.db.models import Container
from wt.docker.client import ContainerInfo, ContainerNotFoundError, DockerApi
from wt.docker.parse import (
    SOURCE_LABEL,
    InvalidImageRefError,
    compose_project,
    dockerhub_source,
    group_label,
    is_excluded,
    parse_image,
    release_source,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveContainer:
    docker_id: str
    name: str
    state: str
    health: str


# The DB row and the live state of a container.
LiveRow = tuple[Container, LiveContainer]


@dataclass(frozen=True)
class LiveGroup:
    """A Compose group of live containers. Project None: the containers with no project."""

    project: str | None
    # Sorted by name.
    members: list[LiveRow]

    @property
    def label(self) -> str:
        return group_label(self.project)


class Inventory:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._live: dict[str, LiveContainer] = {}
        # Set after the first sync_all. Before it, the live state is empty.
        self.synced = asyncio.Event()

    def get(self, name: str) -> LiveContainer | None:
        return self._live.get(name)

    def running_names(self) -> list[str]:
        """The names of the live containers that run now, sorted."""
        return sorted(
            name for name, live in self._live.items() if live.state == "running"
        )

    def live_rows(self, session: Session) -> list[LiveRow]:
        """The DB row and the live state of each container that exists now and is not
        excluded. Sorted by name.
        """
        # One query for all rows: the UI calls this often (for example the overview).
        rows = {row.name: row for row in local_containers(session)}
        pairs: list[LiveRow] = []
        for name, live in sorted(self._live.items()):
            row = rows.get(name)
            if row is not None and row.enabled:
                pairs.append((row, live))
        return pairs

    def live_groups(self, session: Session) -> list[LiveGroup]:
        """The live rows in Compose groups: sorted by project, "Other" (no project) last.
        The UI shows the groups in this order.
        """
        groups: dict[str | None, list[LiveRow]] = {}
        for row, live in self.live_rows(session):
            groups.setdefault(row.compose_project, []).append((row, live))
        projects = sorted(project for project in groups if project is not None)
        ordered = [*projects, None] if None in groups else projects
        return [LiveGroup(project, groups[project]) for project in ordered]

    async def sync_all(self, docker: DockerApi) -> list[ContainerInfo]:
        """List and inspect all containers. Save them in one transaction, then replace
        the live state at once, so that a reader never sees a part of it. Give the infos.
        """
        infos: list[ContainerInfo] = []
        for container_id in await docker.container_ids():
            try:
                infos.append(await docker.inspect(container_id))
            except ContainerNotFoundError:
                continue  # Removed after the list.
        await asyncio.to_thread(_save, self._engine, infos)
        self._live = {
            info.name: _live(info) for info in infos if not is_excluded(info.labels)
        }
        self.synced.set()
        return infos

    async def update(self, info: ContainerInfo) -> LiveContainer | None:
        """Save the container and its live state. None for an excluded container."""
        await asyncio.to_thread(_save, self._engine, [info])
        if is_excluded(info.labels):
            self._live.pop(info.name, None)
            return None
        live = self._live[info.name] = _live(info)
        return live

    def remove(self, name: str, docker_id: str) -> bool:
        """Remove the live state, only if `docker_id` is the current one for the name.

        After a recreate, the destroy event of the old container comes after the
        start of the new one. Then the new container must stay.
        """
        live = self._live.get(name)
        if live is None or live.docker_id != docker_id:
            return False
        del self._live[name]
        return True


def _live(info: ContainerInfo) -> LiveContainer:
    return LiveContainer(info.id, info.name, info.state, info.health)


def _save(engine: Engine, infos: list[ContainerInfo]) -> None:
    """Add or change the rows of the containers, in one transaction."""
    with Session(engine) as session:
        for info in infos:
            _upsert(session, info)
        session.commit()


def _upsert(session: Session, info: ContainerInfo) -> None:
    try:
        image = parse_image(info.image)
        repo, tag = image.repo or None, image.tag
    except InvalidImageRefError:
        log.warning(
            "Container %s has an image reference that WT cannot read", info.name
        )
        repo, tag = None, None
    row = find_container(session, info.name) or Container(
        host_id=LOCAL_HOST_ID, name=info.name
    )
    row.docker_id = info.id
    row.compose_project = compose_project(info.labels)
    row.image, row.tag = repo, tag
    row.enabled = not is_excluded(info.labels)
    if not row.source_confirmed:
        # The label first. Else the Docker Hub repo of the image, if it is on Docker Hub.
        row.release_source = release_source(info.labels.get(SOURCE_LABEL)) or (
            dockerhub_source(repo) if repo else None
        )
    session.add(row)
