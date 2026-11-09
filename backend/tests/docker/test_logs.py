"""Docker test: the log reader through the socket proxy (task 6.7)."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest

from tests.docker.env import PROXY_URL
from wt import clock
from wt.docker.client import DockerClient
from wt.docker.logs import LogLine

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


@pytest.fixture
async def client(docker_env: dict[str, str]) -> AsyncIterator[DockerClient]:
    client = DockerClient(PROXY_URL.replace("http://", "tcp://"))
    yield client
    await client.close()


async def read(
    client: DockerClient,
    name: str,
    tail: int | None,
    since: datetime | None,
    follow: bool,
) -> list[LogLine]:
    return [
        line async for line in client.logs(name, tail=tail, since=since, follow=follow)
    ]


async def test_tail_gives_the_last_lines(client: DockerClient) -> None:
    lines = await read(client, "wt_test_json", tail=6, since=None, follow=False)

    assert len(lines) == 6
    assert all(line.time is not None for line in lines)


async def test_stdout_and_stderr_lines(client: DockerClient) -> None:
    lines = await read(client, "wt_test_json", tail=20, since=None, follow=False)

    streams = {line.stream for line in lines}
    assert streams == {"stdout", "stderr"}
    assert all(line.text.startswith("{") for line in lines if line.stream == "stdout")
    assert all(
        line.text.startswith("error line") for line in lines if line.stream == "stderr"
    )


async def test_since_gives_only_new_lines(client: DockerClient) -> None:
    since = clock.now() - timedelta(seconds=3)

    lines = await read(client, "wt_test_healthy", tail=None, since=since, follow=False)

    assert lines
    assert all(line.time is not None and line.time >= since for line in lines)


async def test_follow_gives_new_lines(client: DockerClient) -> None:
    start = clock.now()
    new: list[LogLine] = []
    async with asyncio.timeout(10):
        async for line in client.logs(
            "wt_test_healthy", tail=0, since=None, follow=True
        ):
            new.append(line)
            if len(new) == 2:
                break

    assert all(
        line.time is not None and line.time >= start - timedelta(seconds=1)
        for line in new
    )


async def test_tty_container_lines_are_stdout(client: DockerClient) -> None:
    lines = await read(client, "wt_test_tty", tail=5, since=None, follow=False)

    assert len(lines) == 5
    assert {line.stream for line in lines} == {"stdout"}
    assert all(
        line.text.startswith("tick ") and "\r" not in line.text for line in lines
    )
