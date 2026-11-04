"""Events worker: keep the inventory up to date from the Docker events stream."""

import logging
from typing import Protocol

from wt.bus import Bus, Topic
from wt.docker.client import (
    ContainerInfo,
    ContainerNotFoundError,
    DockerApi,
    DockerEvent,
)
from wt.docker.inventory import Inventory

log = logging.getLogger(__name__)


class DockerListener(Protocol):
    """Gets each sync and each event directly (the health monitor)."""

    def on_sync(self, infos: list[ContainerInfo]) -> None: ...

    async def on_event(self, event: DockerEvent) -> None: ...


async def handle_event(
    event: DockerEvent,
    docker: DockerApi,
    inventory: Inventory,
    bus: Bus,
    listener: DockerListener | None = None,
) -> None:
    """Update the inventory for one event. Publish `container` if a container changed.

    The listener gets the event, but not for excluded containers.
    """
    if event.action == "destroy":
        if inventory.remove(event.name, event.container_id):
            bus.publish(Topic.CONTAINER, {"name": event.name})
    else:
        try:
            info = await docker.inspect(event.container_id)
        except ContainerNotFoundError:
            log.debug("Container %s is gone before the inspect", event.name)
            return
        if await inventory.update(info) is None:
            return
        bus.publish(Topic.CONTAINER, {"name": info.name})
    if listener is not None:
        await listener.on_event(event)


async def follow_events(
    docker: DockerApi,
    inventory: Inventory,
    bus: Bus,
    listener: DockerListener | None = None,
) -> None:
    """Handle events until the stream stops."""
    async for event in docker.events():
        await handle_event(event, docker, inventory, bus, listener)
