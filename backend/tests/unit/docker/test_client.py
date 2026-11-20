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
    ContainerStats,
    DockerEvent,
    DockerUnavailableError,
    EventAction,
    container_info,
    container_stats,
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


# GET /containers/{id}/stats?stream=false&one-shot=true from Docker 29 (cgroup v2), shortened.
STATS = {
    "read": "2026-11-20T01:42:46.871458168Z",
    "cpu_stats": {
        "cpu_usage": {"total_usage": 2674526453000},
        "system_cpu_usage": 7255789130000000,
        "online_cpus": 11,
    },
    "memory_stats": {
        "usage": 847872,
        "stats": {"inactive_file": 4096, "anon": 262144},
        "limit": 8321568768,
    },
    "networks": {
        "eth0": {"rx_bytes": 1082, "tx_bytes": 126},
        "eth1": {"rx_bytes": 18, "tx_bytes": 4},
    },
    "blkio_stats": {
        "io_service_bytes_recursive": [
            {"major": 254, "minor": 0, "op": "read", "value": 4096},
            {"major": 254, "minor": 0, "op": "write", "value": 512},
            {"major": 254, "minor": 16, "op": "read", "value": 100},
        ]
    },
    "precpu_stats": {"cpu_usage": {"total_usage": 0}},
}


def test_container_stats_from_docker() -> None:
    assert container_stats(STATS) == ContainerStats(
        time=datetime(2026, 11, 20, 1, 42, 46, 871458, tzinfo=UTC),
        cpu_total=2674526453000,
        system_cpu=7255789130000000,
        online_cpus=11,
        mem_usage=847872,
        mem_inactive_file=4096,
        mem_limit=8321568768,
        net_rx=1100,
        net_tx=130,
        disk_read=4196,
        disk_write=512,
    )


def test_container_stats_with_no_network_and_no_disk_values() -> None:
    # A container with network_mode none has no networks. cgroup v2 can give null lists.
    data = {**STATS, "blkio_stats": {"io_service_bytes_recursive": None}}
    del data["networks"]

    stats = container_stats(data)

    assert (stats.net_rx, stats.net_tx, stats.disk_read, stats.disk_write) == (
        0,
        0,
        0,
        0,
    )


def test_container_stats_from_cgroup_v1() -> None:
    # cgroup v1: "total_inactive_file" and the ops "Read" and "Write".
    data = {
        **STATS,
        "memory_stats": {
            "usage": 900,
            "stats": {"total_inactive_file": 100},
            "limit": 1000,
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"op": "Read", "value": 7},
                {"op": "Write", "value": 3},
                {"op": "Total", "value": 10},
            ]
        },
    }

    stats = container_stats(data)

    assert stats.mem_inactive_file == 100
    assert (stats.disk_read, stats.disk_write) == (7, 3)


def test_container_stats_with_a_bad_time_is_an_error() -> None:
    with pytest.raises(ValueError, match="Docker time"):
        container_stats({"read": "bad"})


def test_container_stats_of_a_stopped_container() -> None:
    # Docker gives zero values and no system_cpu_usage for a stopped container.
    data = {
        "read": "0001-01-01T00:00:00Z",
        "cpu_stats": {"cpu_usage": {"total_usage": 0}},
        "memory_stats": {},
    }

    stats = container_stats(data)

    assert stats.system_cpu == 0
    assert stats.online_cpus == 0
    assert (stats.mem_usage, stats.mem_limit) == (0, 0)


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
def test_docker_event(
    action: str, expected_action: EventAction, health: str | None
) -> None:
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
async def test_fake_docker_gives_the_stats_that_the_test_sets() -> None:
    fake = FakeDocker()
    info = container_info(INSPECT)
    fake.add(info)
    stats = container_stats(STATS)
    fake.stats_values["web"] = stats

    assert await fake.stats("abc123") == stats
    assert await fake.stats("web") == stats
    with pytest.raises(ContainerNotFoundError):
        await fake.stats("nope")


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
    with pytest.raises(Exception, match="Docker"):
        await fake.stats("web")


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
