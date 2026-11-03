"""Docker connection worker: connect, sync all, follow events, and connect again.

When the stream stops or Docker does not answer, WT publishes `docker` disconnected and
waits with backoff (1 s, doubles, max 60 s). After each connect it lists all containers
again, because events can be lost while the connection is down.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from wt import clock
from wt.bus import Bus, Topic
from wt.docker.client import DockerApi, DockerUnavailableError
from wt.docker.events import follow_events
from wt.docker.inventory import Inventory

log = logging.getLogger(__name__)

FIRST_DELAY = 1.0
MAX_DELAY = 60.0


@dataclass
class DockerState:
    """The current connection state. A new SSE client gets it first."""

    connected: bool = False


async def keep_connected(
    make_client: Callable[[], DockerApi],
    inventory: Inventory,
    bus: Bus,
    state: DockerState,
) -> None:
    """Run until WT stops it (task cancel)."""
    _set(state, bus, connected=False)
    delay = FIRST_DELAY
    while True:
        client = make_client()
        try:
            await client.ping()
            await inventory.sync_all(client)
            _set(state, bus, connected=True)
            delay = FIRST_DELAY
            await follow_events(client, inventory, bus)
            log.warning("The Docker event stream stopped")
        except DockerUnavailableError as error:
            log.warning("Docker is not available: %s", error)
        finally:
            await client.close()
        _set(state, bus, connected=False)
        await clock.sleep(delay)
        delay = min(delay * 2, MAX_DELAY)


def _set(state: DockerState, bus: Bus, connected: bool) -> None:
    state.connected = connected
    bus.publish(Topic.DOCKER, {"connected": connected})
