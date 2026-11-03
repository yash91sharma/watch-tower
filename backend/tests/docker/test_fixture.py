"""Tests for the Docker test fixture (task 6.1)."""

import httpx
import pytest

from tests.docker.env import CONTAINERS, PROXY, PROXY_URL, docker, start_test_env

pytestmark = pytest.mark.docker


def test_all_containers_start_healthy(docker_env: dict[str, str]) -> None:
    assert sorted(docker_env) == sorted(spec.name for spec in CONTAINERS)
    for spec in CONTAINERS:
        assert (
            docker("inspect", "-f", "{{.State.Health.Status}}", spec.name) == "healthy"
        )


def test_a_second_run_reuses_the_containers(docker_env: dict[str, str]) -> None:
    assert start_test_env() == docker_env


def test_this_container_reaches_the_socket_proxy_by_name(
    docker_env: dict[str, str],
) -> None:
    ping = httpx.get(f"{PROXY_URL}/_ping", timeout=5)
    containers = httpx.get(f"{PROXY_URL}/containers/json", timeout=5)

    assert ping.text == "OK"
    assert PROXY in containers.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/containers/create"),
        ("GET", "/images/json"),
        ("POST", "/containers/x/stop"),
    ],
)
def test_the_socket_proxy_is_read_only(
    docker_env: dict[str, str], method: str, path: str
) -> None:
    response = httpx.request(method, f"{PROXY_URL}{path}", timeout=5)

    assert response.status_code == 403
