"""The deploy file compose.yaml (task 15.3): `docker compose config` accepts it."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.docker

REPO = Path(__file__).parents[3]
_DOCKER = shutil.which("docker") or "docker"


def test_compose_config_passes_and_has_the_deploy_rules(tmp_path: Path) -> None:
    # A copy in an empty dir: no .env file, as at a first deploy.
    shutil.copy(REPO / "compose.yaml", tmp_path / "compose.yaml")
    result = subprocess.run(
        [_DOCKER, "compose", "config", "--format", "json"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(result.stdout)["services"]

    wt, proxy = services["wt"], services["socket-proxy"]
    assert wt["restart"] == proxy["restart"] == "unless-stopped"
    assert wt["read_only"] is True
    assert wt["environment"]["DOCKER_HOST"] == "tcp://socket-proxy:2375"
    assert "no-new-privileges:true" in wt["security_opt"]
    assert proxy["environment"]["POST"] == "0"
    assert "ports" not in proxy
