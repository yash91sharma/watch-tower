"""FakeDocker: the DockerApi interface in memory, for tests with no Docker."""

import asyncio
from collections.abc import AsyncIterator

from wt.docker.client import (
    ContainerInfo,
    ContainerNotFoundError,
    ContainerSummary,
    DockerEvent,
    DockerUnavailableError,
)


class FakeDocker:
    def __init__(self) -> None:
        self.containers: dict[str, ContainerInfo] = {}
        # True: each call fails as if Docker is not there.
        self.fail = False
        self._events: asyncio.Queue[DockerEvent | None] = asyncio.Queue()

    # Test controls.

    def add(self, info: ContainerInfo) -> None:
        self.containers[info.id] = info

    def remove(self, container_id: str) -> None:
        self.containers.pop(container_id, None)

    def emit(self, event: DockerEvent) -> None:
        self._events.put_nowait(event)

    def end_stream(self) -> None:
        self._events.put_nowait(None)

    # DockerApi.

    def _check(self) -> None:
        if self.fail:
            raise DockerUnavailableError("Docker is not there (fake)")

    async def ping(self) -> None:
        self._check()

    async def list_containers(self) -> list[ContainerSummary]:
        self._check()
        return [
            ContainerSummary(info.id, info.name) for info in self.containers.values()
        ]

    async def inspect(self, container_id: str) -> ContainerInfo:
        self._check()
        for info in self.containers.values():
            if container_id in (info.id, info.name):
                return info
        raise ContainerNotFoundError(container_id)

    async def events(self) -> AsyncIterator[DockerEvent]:
        self._check()
        while (event := await self._events.get()) is not None:
            yield event

    async def close(self) -> None:
        return None
