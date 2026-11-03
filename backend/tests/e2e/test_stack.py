"""The E2E stack (e2e/compose.test.yaml, task 16.4): it starts and WT is healthy."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

STACK = Path(__file__).parents[3] / "e2e" / "compose.test.yaml"
_DOCKER = shutil.which("docker") or "docker"


def docker(*args: str) -> str:
    return subprocess.run(
        [_DOCKER, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_the_stack_starts_and_wt_is_healthy() -> None:
    docker("compose", "-f", str(STACK), "up", "-d", "--build", "--wait")

    health = docker("inspect", "-f", "{{.State.Health.Status}}", "wt_test_e2e_wt")
    # The browser path: HTTPS through Traefik (self-signed certificate).
    body = docker(
        "exec",
        "wt_test_e2e_traefik",
        "wget",
        "-q",
        "--no-check-certificate",
        "-O-",
        "https://wt.test/api/health",
    )

    assert health == "healthy"
    assert json.loads(body) == {"status": "ok"}
