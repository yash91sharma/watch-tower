# aiodocker has no types for its **kwargs. This is the only file that calls aiodocker.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false
"""Docker API client (aiodocker) and its typed data.

WT reads Docker through a read-only socket proxy (DOCKER_HOST). Other modules use the
`DockerApi` interface and the dataclasses here. They never use aiodocker. Tests use
`FakeDocker` (wt.docker.fake), which has the same interface.
"""

import json
import socket
from collections.abc import AsyncGenerator, AsyncIterator, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

import aiodocker  # noqa: TID251  (the only module that uses aiodocker)
import aiohttp
from aiohappyeyeballs import AddrInfoType

from wt.docker.parse import container_name

# The container events that WT uses.
EVENT_ACTIONS = ("start", "die", "health_status", "destroy")


class DockerUnavailableError(Exception):
    """WT cannot talk to Docker (or the socket proxy)."""


class ContainerNotFoundError(Exception):
    pass


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

    async def container_ids(self) -> list[str]:
        """The ids of all containers, also the stopped ones."""
        ...

    async def inspect(self, container_id: str) -> ContainerInfo: ...

    def events(self) -> AsyncIterator[DockerEvent]:
        """Container events. The iteration ends when the stream stops."""
        ...

    def logs(
        self, container_id: str, tail: int | None, since: datetime | None, follow: bool
    ) -> AsyncGenerator[LogLine]:
        """Log lines, with timestamps. tail None: all lines. follow: wait for new lines."""
        ...

    async def close(self) -> None: ...


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
        self._connector: aiohttp.TCPConnector | None = None
        if docker_host and docker_host.startswith(("tcp://", "http://")):
            self._connector = aiohttp.TCPConnector(socket_factory=_keepalive_socket)
        self._docker = aiodocker.Docker(url=docker_host, connector=self._connector)

    async def ping(self) -> None:
        # The proxy allows GET /version. aiodocker has no ping call.
        with _errors():
            await self._docker.version()

    async def container_ids(self) -> list[str]:
        with _errors():
            containers = await self._docker.containers.list(all=True)
        return [container.id for container in containers]

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
            # stop() raises the error of the stream task, if it has one.
            with _errors():
                await self._docker.events.stop()

    async def logs(
        self, container_id: str, tail: int | None, since: datetime | None, follow: bool
    ) -> AsyncGenerator[LogLine]:
        info = await self.inspect(container_id)
        params: dict[str, str | int] = {
            "stdout": "1",
            "stderr": "1",
            "timestamps": "1",
            "follow": "1" if follow else "0",
            "tail": "all" if tail is None else str(tail),
        }
        if since is not None:
            params["since"] = f"{since.timestamp():.6f}"
        decoder = LogDecoder(tty=info.tty)
        # aiodocker drops the stream type of each line, so WT reads the raw response.
        query = self._docker._query(  # pyright: ignore[reportPrivateUsage]
            f"containers/{info.id}/logs", params=params, timeout=None
        )
        with _errors():
            async with query as response:
                try:
                    async for chunk in response.content.iter_any():
                        for line in decoder.feed(chunk):
                            yield line
                finally:
                    # aiodocker does not close the response. A stopped stream cannot go back to the pool.
                    response.close()
        for line in decoder.flush():
            yield line

    async def close(self) -> None:
        await self._docker.close()
        if self._connector is not None:
            await self._connector.close()


def _keepalive_socket(addr_info: AddrInfoType) -> socket.socket:
    """A TCP socket with keepalive probes after 10 s with no data.

    Docker sends nothing on an idle event stream. When the socket proxy restarts, the old
    connection gets no close, so the stream waits for ever. A probe gets a reset (or no
    answer), and the stream fails in about 25 s.
    """
    family, type_, proto, _, _ = addr_info
    sock = socket.socket(family, type_, proto)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    return sock


Stream = Literal["stdout", "stderr"]


@dataclass(frozen=True)
class LogLine:
    # From the Docker timestamp. None if the line has no timestamp.
    time: datetime | None
    stream: Stream
    text: str


def parse_log_line(raw: str, stream: Stream) -> LogLine:
    """Split "<RFC 3339 time with ns> <text>" into time and text."""
    stamp, _, text = raw.partition(" ")
    time = _parse_time(stamp)
    if time is None:
        return LogLine(None, stream, raw)
    return LogLine(time, stream, text)


def _parse_time(stamp: str) -> datetime | None:
    if not stamp.endswith("Z"):
        return None
    seconds, _, fraction = stamp[:-1].partition(".")
    # Python keeps microseconds. Docker gives nanoseconds.
    try:
        time = datetime.fromisoformat(seconds).replace(tzinfo=UTC)
    except ValueError:
        return None
    if fraction.isdigit():
        time = time.replace(microsecond=int(fraction[:6].ljust(6, "0")))
    return time


class LogDecoder:
    """Bytes from GET /containers/{id}/logs to lines.

    With no TTY, Docker sends frames: 1 byte stream (1 stdout, 2 stderr), 3 bytes zero,
    4 bytes length, then the data. aiodocker drops the stream byte, so WT reads the frames
    itself. With a TTY, Docker sends one raw stream: all lines are stdout.
    """

    def __init__(self, tty: bool) -> None:
        self._tty = tty
        self._buffer = b""
        self._partial: dict[Stream, bytes] = {"stdout": b"", "stderr": b""}

    def feed(self, data: bytes) -> list[LogLine]:
        if self._tty:
            return self._lines("stdout", data)
        self._buffer += data
        lines: list[LogLine] = []
        while len(self._buffer) >= _HEADER:
            length = int.from_bytes(self._buffer[4:_HEADER])
            if len(self._buffer) < _HEADER + length:
                break
            stream: Stream = "stderr" if self._buffer[0] == 2 else "stdout"
            payload = self._buffer[_HEADER : _HEADER + length]
            self._buffer = self._buffer[_HEADER + length :]
            lines += self._lines(stream, payload)
        return lines

    def flush(self) -> list[LogLine]:
        """The last lines with no newline."""
        lines: list[LogLine] = []
        for stream, rest in self._partial.items():
            if rest:
                lines.append(_line(rest, stream))
                self._partial[stream] = b""
        return lines

    def _lines(self, stream: Stream, data: bytes) -> list[LogLine]:
        *complete, self._partial[stream] = (self._partial[stream] + data).split(b"\n")
        return [_line(raw, stream) for raw in complete]


_HEADER = 8


def _line(raw: bytes, stream: Stream) -> LogLine:
    return parse_log_line(raw.decode(errors="replace").removesuffix("\r"), stream)
