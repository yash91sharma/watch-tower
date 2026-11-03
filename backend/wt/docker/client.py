# aiodocker has no types for its **kwargs. This is the only file that calls aiodocker.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Docker API client (aiodocker) and its typed data.

WT reads Docker through a read-only socket proxy (DOCKER_HOST). Other modules use the
`DockerApi` interface and the dataclasses here. They never use aiodocker. Tests use
`FakeDocker` (wt.docker.fake), which has the same interface.
"""

import json
from collections.abc import AsyncIterator, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import aiodocker  # noqa: TID251  (the only module that uses aiodocker)
import aiohttp

from wt.docker.parse import container_name

# The container events that WT uses.
EVENT_ACTIONS = ("start", "die", "health_status", "destroy")


class DockerUnavailableError(Exception):
    """WT cannot talk to Docker (or the socket proxy)."""


class ContainerNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ContainerSummary:
    id: str
    name: str


@dataclass(frozen=True)
class ContainerInfo:
    id: str
    # With no leading "/".
    name: str
    # The image reference from the container config, for example "nginx:1.27".
    image: str
    labels: Mapping[str, str]
    # created, running, paused, restarting, removing, exited or dead.
    state: str
    # healthy, unhealthy, starting, or none (no healthcheck).
    health: str
    tty: bool
    restart_count: int


@dataclass(frozen=True)
class DockerEvent:
    # start, die, health_status or destroy.
    action: str
    container_id: str
    name: str
    time: datetime
    # healthy or unhealthy for health_status, else None.
    health: str | None


class DockerApi(Protocol):
    async def ping(self) -> None: ...

    async def list_containers(self) -> list[ContainerSummary]: ...

    async def inspect(self, container_id: str) -> ContainerInfo: ...

    def events(self) -> AsyncIterator[DockerEvent]:
        """Container events. The iteration ends when the stream stops."""
        ...

    async def close(self) -> None: ...


def container_summary(data: Mapping[str, Any]) -> ContainerSummary:
    """From an item of GET /containers/json."""
    names: list[str] = data.get("Names") or [""]
    return ContainerSummary(id=data["Id"], name=container_name(names[0]))


def container_info(data: Mapping[str, Any]) -> ContainerInfo:
    """From GET /containers/{id}/json."""
    config: Mapping[str, Any] = data.get("Config") or {}
    state: Mapping[str, Any] = data.get("State") or {}
    health: Mapping[str, Any] = state.get("Health") or {}
    return ContainerInfo(
        id=data["Id"],
        name=container_name(str(data.get("Name", ""))),
        image=str(config.get("Image", "")),
        labels=dict(config.get("Labels") or {}),
        state=str(state.get("Status", "")),
        health=str(health.get("Status", "none")),
        tty=bool(config.get("Tty", False)),
        restart_count=int(data.get("RestartCount", 0)),
    )


def docker_event(data: Mapping[str, Any]) -> DockerEvent | None:
    """From an item of GET /events. None for events that WT does not use."""
    action, _, detail = str(data.get("Action", "")).partition(": ")
    if data.get("Type") != "container" or action not in EVENT_ACTIONS:
        return None
    actor: Mapping[str, Any] = data.get("Actor") or {}
    attributes: Mapping[str, Any] = actor.get("Attributes") or {}
    return DockerEvent(
        action=action,
        container_id=str(actor.get("ID", "")),
        name=str(attributes.get("name", "")),
        time=datetime.fromtimestamp(int(data.get("timeNano", 0)) / 1e9, UTC),
        health=detail if action == "health_status" else None,
    )


@contextmanager
def _errors() -> Generator[None]:
    """Change aiodocker and network errors to WT errors."""
    try:
        yield
    except aiodocker.DockerError as error:
        if error.status == 404:
            raise ContainerNotFoundError(error.message) from None
        raise DockerUnavailableError(
            f"Docker error {error.status}: {error.message}"
        ) from None
    except (aiohttp.ClientError, OSError, TimeoutError) as error:
        raise DockerUnavailableError(f"Cannot connect to Docker: {error}") from None


class DockerClient:
    """The real client. Make it in the event loop. Close it when done."""

    def __init__(self, docker_host: str | None) -> None:
        self._docker = aiodocker.Docker(url=docker_host)

    async def ping(self) -> None:
        # The proxy allows GET /version. aiodocker has no ping call.
        with _errors():
            await self._docker.version()

    async def list_containers(self) -> list[ContainerSummary]:
        with _errors():
            containers = await self._docker.containers.list(all=True)
        return [container_summary(container._container) for container in containers]  # pyright: ignore[reportPrivateUsage]

    async def inspect(self, container_id: str) -> ContainerInfo:
        with _errors():
            data = await self._docker.containers.container(container_id).show()
        return container_info(data)

    async def events(self) -> AsyncIterator[DockerEvent]:
        filters = json.dumps({"type": ["container"], "event": list(EVENT_ACTIONS)})
        subscriber = self._docker.events.subscribe(filters=filters)
        try:
            while True:
                with _errors():
                    data: Mapping[str, Any] | None = await subscriber.get()
                if data is None:
                    return
                event = docker_event(data)
                if event is not None:
                    yield event
        finally:
            await self._docker.events.stop()

    async def close(self) -> None:
        await self._docker.close()
