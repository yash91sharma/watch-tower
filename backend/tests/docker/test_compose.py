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
    config = json.loads(result.stdout)
    services = config["services"]

    wt, proxy = services["wt"], services["socket-proxy"]
    for service in (wt, proxy):
        assert service["restart"] == "unless-stopped"
        assert service["read_only"] is True
        assert "no-new-privileges:true" in service["security_opt"]
        assert service["cap_drop"] == ["ALL"]
        assert "ports" not in service
    assert wt["environment"]["DOCKER_HOST"] == "tcp://wt-socket-proxy:2375"
    assert proxy["environment"]["POST"] == "0"

    # Limits: Compose gives bytes and CPUs as numbers.
    assert int(wt["mem_limit"]) == 364 * 1024 * 1024
    assert float(wt["cpus"]) == 1.0
    assert int(proxy["mem_limit"]) == 64 * 1024 * 1024
    assert float(proxy["cpus"]) == 0.25

    # Only WT gets to the internet (wt_egress) and to Traefik. The proxy is internal only.
    assert set(proxy["networks"]) == {"docker"}
    assert set(wt["networks"]) == {"docker", "egress", "traefik_internal"}
    networks = config["networks"]
    assert networks["docker"]["internal"] is True
    assert not networks["egress"].get("internal", False)
    assert networks["traefik_internal"]["external"] is True
