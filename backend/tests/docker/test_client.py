"""Docker test: the client through the socket proxy (task 6.2)."""

import pytest

from tests.docker.env import PROXY_URL, VERSIONED_SOURCE
from wt.docker.client import DockerClient

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


async def test_ping_list_and_inspect_through_the_proxy(
    docker_env: dict[str, str],
) -> None:
    client = DockerClient(PROXY_URL.replace("http://", "tcp://"))
    try:
        await client.ping()
        names = {summary.name for summary in await client.list_containers()}
        healthy = await client.inspect("wt_test_healthy")
        versioned = await client.inspect(docker_env["wt_test_versioned"])
    finally:
        await client.close()

    assert {"wt_test_healthy", "wt_test_excluded", "wt_test_socket_proxy"} <= names
    assert healthy.health == "healthy"
    assert healthy.labels["com.docker.compose.project"] == "wt_test"
    assert versioned.labels["org.opencontainers.image.source"] == VERSIONED_SOURCE
    assert versioned.image == "wt_test/versioned:1.0.0"
