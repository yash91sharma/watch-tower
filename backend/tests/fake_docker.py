"""FakeDocker: the DockerApi interface in memory, for tests with no Docker."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import datetime

from wt.docker.client import (
    ContainerInfo,
    ContainerNotFoundError,
    DockerEvent,
    DockerUnavailableError,
)
from wt.docker.logs import LogLine


class FakeDocker:
    def __init__(self) -> None:
        self.containers: dict[str, ContainerInfo] = {}
        # True: each call fails as if Docker is not there.
        self.fail = False
        self.closed = False
        self._events: asyncio.Queue[DockerEvent | None] = asyncio.Queue()
        # Container name -> its log lines.
        self.log_lines: dict[str, list[LogLine]] = {}

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

    async def container_ids(self) -> list[str]:
        self._check()
        return list(self.containers)

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

    async def logs(
        self, container_id: str, tail: int | None, since: datetime | None, follow: bool
    ) -> AsyncGenerator[LogLine]:
        self._check()
        info = self.containers.get(container_id)
        lines = self.log_lines.get(info.name if info else container_id, [])
        if since is not None:
            lines = [line for line in lines if line.time is None or line.time >= since]
        if tail is not None:
            lines = lines[-tail:] if tail else []
        for line in lines:
            yield line
        if follow:
            # No new lines come. Wait until the reader stops.
            await asyncio.Event().wait()

    async def close(self) -> None:
        self.closed = True
