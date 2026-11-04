"""Inventory: the containers on the host.

In memory: the live state of each container that exists now and is not excluded.
In the DB: one `container` row per name, kept when the container goes, so that the
admin values stay after a recreate.
"""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db import LOCAL_HOST_ID
from wt.db.models import Container
from wt.docker.client import ContainerInfo, ContainerNotFoundError, DockerApi
from wt.docker.parse import (
    SOURCE_LABEL,
    InvalidImageRefError,
    compose_project,
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


class Inventory:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._live: dict[str, LiveContainer] = {}
        # Set after the first sync_all. Before it, the live state is empty.
        self.synced = asyncio.Event()

    def get(self, name: str) -> LiveContainer | None:
        return self._live.get(name)

    def names(self) -> list[str]:
        return sorted(self._live)

    async def sync_all(self, docker: DockerApi) -> list[ContainerInfo]:
        """List and inspect all containers. Replace the live state. Give the infos."""
        infos: list[ContainerInfo] = []
        for summary in await docker.list_containers():
            try:
                infos.append(await docker.inspect(summary.id))
            except ContainerNotFoundError:
                continue  # Removed after the list.
        self._live = {}
        for info in infos:
            await self.update(info)
        self.synced.set()
        return infos

    async def update(self, info: ContainerInfo) -> LiveContainer | None:
        """Save the container and its live state. None for an excluded container."""
        await asyncio.to_thread(_upsert, self._engine, info)
        if is_excluded(info.labels):
            self._live.pop(info.name, None)
            return None
        live = LiveContainer(info.id, info.name, info.state, info.health)
        self._live[info.name] = live
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


def _upsert(engine: Engine, info: ContainerInfo) -> None:
    try:
        image = parse_image(info.image)
        repo, tag = image.repo or None, image.tag
    except InvalidImageRefError:
        log.warning(
            "Container %s has an image reference that WT cannot read", info.name
        )
        repo, tag = None, None
    with Session(engine) as session:
        row = session.exec(
            select(Container).where(
                Container.host_id == LOCAL_HOST_ID, Container.name == info.name
            )
        ).first() or Container(host_id=LOCAL_HOST_ID, name=info.name)
        row.docker_id = info.id
        row.compose_project = compose_project(info.labels)
        row.image, row.tag = repo, tag
        row.enabled = not is_excluded(info.labels)
        if not row.source_confirmed:
            row.release_source = release_source(info.labels.get(SOURCE_LABEL))
        session.add(row)
        session.commit()
