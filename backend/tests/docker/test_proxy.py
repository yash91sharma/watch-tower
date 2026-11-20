"""The socket proxy is read-only (task 18.2): WT can read Docker, never change it."""

import httpx
import pytest

from tests.docker.env import PROXY_URL, docker

pytestmark = pytest.mark.docker


def test_the_proxy_allows_reads(docker_env: dict[str, str]) -> None:
    assert docker_env
    response = httpx.get(f"{PROXY_URL}/containers/json")

    assert response.status_code == 200


def test_the_proxy_allows_the_container_stats(docker_env: dict[str, str]) -> None:
    # The metrics worker (one-shot stats). CONTAINERS=1 allows all GET /containers/*.
    assert docker_env
    url = f"{PROXY_URL}/containers/wt_test_healthy/stats"
    response = httpx.get(url, params={"stream": "false", "one-shot": "true"})

    assert response.status_code == 200
    assert response.json()["cpu_stats"]["cpu_usage"]["total_usage"] > 0


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/containers/wt_test_healthy/stop"),
        ("POST", "/containers/wt_test_healthy/kill"),
        ("POST", "/containers/create"),
        ("DELETE", "/containers/wt_test_healthy"),
        ("POST", "/images/create"),
    ],
)
def test_the_proxy_blocks_changes(
    docker_env: dict[str, str], method: str, path: str
) -> None:
    assert docker_env
    response = httpx.request(method, f"{PROXY_URL}{path}")

    assert response.status_code == 403
    state = docker("inspect", "-f", "{{.State.Status}}", "wt_test_healthy").strip()
    assert state == "running"
