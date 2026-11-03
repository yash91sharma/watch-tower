"""Events worker: keep the inventory up to date from the Docker events stream."""

import logging

from wt.bus import Bus, Topic
from wt.docker.client import ContainerNotFoundError, DockerApi, DockerEvent
from wt.docker.inventory import Inventory

log = logging.getLogger(__name__)


async def handle_event(
    event: DockerEvent, docker: DockerApi, inventory: Inventory, bus: Bus
) -> None:
    """Update the inventory for one event. Publish `container` if a container changed."""
    if event.action == "destroy":
        if inventory.remove(event.name, event.container_id):
            bus.publish(Topic.CONTAINER, {"name": event.name})
        return
    try:
        info = await docker.inspect(event.container_id)
    except ContainerNotFoundError:
        log.debug("Container %s is gone before the inspect", event.name)
        return
    if await inventory.update(info) is not None:
        bus.publish(Topic.CONTAINER, {"name": info.name})


async def follow_events(docker: DockerApi, inventory: Inventory, bus: Bus) -> None:
    """Handle events until the stream stops."""
    async for event in docker.events():
        await handle_event(event, docker, inventory, bus)
