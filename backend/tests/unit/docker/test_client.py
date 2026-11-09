"""Tests for wt.docker.client (parse of the Docker API data) and FakeDocker."""

import asyncio
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fake_docker import FakeDocker
from wt.docker import client
from wt.docker.client import (
    ContainerInfo,
    ContainerNotFoundError,
    DockerEvent,
    DockerUnavailableError,
    container_info,
    docker_event,
)

INSPECT = {
    "Id": "abc123",
    "Name": "/web",
    "State": {"Status": "running", "Health": {"Status": "healthy"}},
    "Config": {
        "Image": "nginx:1.27",
        "Tty": False,
        "Labels": {"com.docker.compose.project": "site"},
    },
}


def test_container_info_from_inspect() -> None:
    assert container_info(INSPECT) == ContainerInfo(
        id="abc123",
        name="web",
        image="nginx:1.27",
        labels={"com.docker.compose.project": "site"},
        state="running",
        health="healthy",
        tty=False,
    )


def test_container_with_no_healthcheck_and_no_labels() -> None:
    data = {
        **INSPECT,
        "State": {"Status": "exited"},
        "Config": {"Image": "x", "Labels": None},
    }

    info = container_info(data)

    assert (info.state, info.health, info.labels, info.tty) == (
        "exited",
        "none",
        {},
        False,
    )


@pytest.mark.parametrize(
    ("action", "expected_action", "health"),
    [
        ("start", "start", None),
        ("die", "die", None),
        ("destroy", "destroy", None),
        ("health_status: unhealthy", "health_status", "unhealthy"),
        ("health_status: healthy", "health_status", "healthy"),
    ],
)
def test_docker_event(action: str, expected_action: str, health: str | None) -> None:
    data = {
        "Type": "container",
        "Action": action,
        "Actor": {"ID": "abc", "Attributes": {"name": "web", "image": "nginx"}},
        "timeNano": 1767225600_500000000,
    }

    assert docker_event(data) == DockerEvent(
        action=expected_action,
        container_id="abc",
        name="web",
        time=datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=UTC),
        health=health,
    )


@pytest.mark.parametrize(
    "data",
    [
        {"Type": "image", "Action": "pull", "Actor": {"ID": "x"}, "timeNano": 1},
        {
            "Type": "container",
            "Action": "exec_start: sh",
            "Actor": {"ID": "x"},
            "timeNano": 1,
        },
    ],
)
def test_other_events_are_skipped(data: dict[str, object]) -> None:
    assert docker_event(data) is None


@pytest.mark.anyio
async def test_fake_docker_has_the_same_calls() -> None:
    fake = FakeDocker()
    info = container_info(INSPECT)
    fake.add(info)

    await fake.ping()
    assert await fake.container_ids() == ["abc123"]
    assert await fake.inspect("abc123") == info
    assert await fake.inspect("web") == info
    with pytest.raises(ContainerNotFoundError):
        await fake.inspect("nope")


@pytest.mark.anyio
async def test_fake_docker_events_end_when_the_stream_ends() -> None:
    fake = FakeDocker()
    event = DockerEvent("start", "abc", "web", datetime(2026, 1, 1, tzinfo=UTC), None)

    fake.emit(event)
    fake.end_stream()

    received = [item async for item in fake.events()]
    assert received == [event]


@pytest.mark.anyio
async def test_fake_docker_can_fail(clock: object) -> None:
    fake = FakeDocker()
    fake.fail = True

    with pytest.raises(Exception, match="Docker"):
        await fake.ping()
    with pytest.raises(Exception, match="Docker"):
        await asyncio.wait_for(anext(fake.events()), 1)


def test_ruff_bans_aiodocker_outside_wt_docker() -> None:
    ruff = Path(sys.executable).with_name("ruff")

    result = subprocess.run(
        [ruff, "check", "--stdin-filename", "wt/other.py", "-"],
        input="import aiodocker\n\nx = aiodocker\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert "TID251" in result.stdout


@pytest.mark.parametrize(
    ("error", "expected", "text"),
    [
        (
            client.aiodocker.DockerError(404, "No such container: web"),
            ContainerNotFoundError,
            "No such container: web",
        ),
        (
            client.aiodocker.DockerError(403, "Forbidden"),
            DockerUnavailableError,
            "Docker error 403: Forbidden",
        ),
        (
            client.aiohttp.ClientConnectionError("refused"),
            DockerUnavailableError,
            "Cannot connect to Docker: refused",
        ),
        (OSError("no route"), DockerUnavailableError, "Cannot connect"),
        (TimeoutError(), DockerUnavailableError, "Cannot connect"),
    ],
)
def test_docker_errors_become_wt_errors(
    error: Exception, expected: type[Exception], text: str
) -> None:
    errors = client._errors  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(expected, match=text), errors():
        raise error


def test_other_errors_pass_through() -> None:
    errors = client._errors  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ValueError, match="bug"), errors():
        raise ValueError("bug")


def test_keepalive_socket_options() -> None:
    addr_info = (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 2375))
    sock = client._keepalive_socket(addr_info)  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
    try:
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
        assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) == 10
        assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL) == 5
        assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT) == 3
    finally:
        sock.close()
