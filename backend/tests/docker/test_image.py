"""The WT image (Dockerfile, task 15.1): it builds and has the expected config."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.docker

REPO = Path(__file__).parents[3]
IMAGE = "wt_test/wt:local"
_DOCKER = shutil.which("docker") or "docker"


def docker(*args: str) -> str:
    return subprocess.run(
        [_DOCKER, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(scope="module")
def image() -> dict[str, Any]:
    """Build the image and give its config (docker image inspect)."""
    docker(
        "build",
        "--quiet",
        "--build-arg",
        "VERSION=1.2.3",
        "--build-arg",
        "REVISION=abc123",
        "-t",
        IMAGE,
        str(REPO),
    )
    return json.loads(docker("image", "inspect", IMAGE))[0]["Config"]


def run_python(code: str) -> str:
    return docker("run", "--rm", "--entrypoint", "python", IMAGE, "-c", code)


def test_the_image_config(image: dict[str, Any]) -> None:
    assert image["User"] not in ("", "root", "0")
    assert image["Entrypoint"] == ["wt"]
    assert image["Cmd"] == ["serve"]
    assert "8000/tcp" in image["ExposedPorts"]
    assert "/api/health" in " ".join(image["Healthcheck"]["Test"])
    assert image["Labels"]["org.opencontainers.image.version"] == "1.2.3"
    assert image["Labels"]["org.opencontainers.image.revision"] == "abc123"
    assert image["Labels"]["org.opencontainers.image.source"].startswith(
        "https://github.com/"
    )


def test_the_image_has_the_frontend_the_bytecode_and_a_data_dir(
    image: dict[str, Any],
) -> None:
    assert image["Env"]
    code = (
        "import os, wt.api.static as s, wt.main as m;"
        "print((s.STATIC_DIR / 'index.html').is_file(),"
        " m.__cached__ is not None and os.path.exists(m.__cached__),"
        " os.stat('/data').st_uid == os.getuid())"
    )
    assert run_python(code) == "True True True"
    assert "serve" in docker("run", "--rm", IMAGE, "--help")
