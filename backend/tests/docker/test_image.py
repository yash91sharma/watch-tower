"""The WT image (Dockerfile, tasks 15.1 and 16.21): config, CVE scan, run checks."""

import json
import shutil
import subprocess
import time
from collections.abc import Iterator
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


def test_the_image_has_only_the_venv_and_no_pip(image: dict[str, Any]) -> None:
    """WT is a normal package in the venv. No project files, no pip wheel."""
    assert image
    code = (
        "import importlib.util, os, sysconfig, wt;"
        "print(os.listdir('/app'),"
        " wt.__file__.startswith('/app/.venv/'),"
        " importlib.util.find_spec('pip') is None,"
        " os.path.exists(os.path.join(sysconfig.get_path('stdlib'), 'ensurepip')))"
    )
    assert run_python(code) == "['.venv'] True True False"


# Task 16.21: image checks.
TRIVY_IMAGE = "aquasec/trivy:0.58.1"
RUN_NAME = "wt_test_image"


def test_trivy_finds_no_high_or_critical_cve(image: dict[str, Any]) -> None:
    assert image
    docker(
        "run",
        "--rm",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        TRIVY_IMAGE,
        "image",
        "--quiet",
        "--exit-code",
        "1",
        "--severity",
        "HIGH,CRITICAL",
        "--ignore-unfixed",
        IMAGE,
    )


@pytest.fixture(scope="module")
def running(image: dict[str, Any]) -> Iterator[str]:
    """The image as compose.yaml runs it: read-only, /tmp tmpfs, a data volume."""
    assert image
    # No old container is fine.
    subprocess.run([_DOCKER, "rm", "-f", RUN_NAME], capture_output=True, check=False)
    docker(
        "run",
        "-d",
        "--name",
        RUN_NAME,
        "--label",
        "wt.enable=false",
        "--read-only",
        "--tmpfs",
        "/tmp",  # noqa: S108 (a path in the container)
        "--security-opt",
        "no-new-privileges:true",
        "-v",
        "wt_test_image_data:/data",
        # The same health command, checked often, so that the test is fast.
        "--health-interval",
        "2s",
        IMAGE,
    )
    yield RUN_NAME
    docker("stop", RUN_NAME)


def test_the_healthcheck_passes(running: str) -> None:
    status = ""
    for _ in range(60):
        status = docker("inspect", "-f", "{{.State.Health.Status}}", running)
        if status == "healthy":
            break
        time.sleep(1)
    assert status == "healthy"


def test_only_data_and_tmp_are_writable(running: str) -> None:
    code = (
        "import os\n"
        "for d in ['/', '/app', '/app/.venv', '/usr', '/etc', '/data', '/tmp']:\n"
        "    try:\n"
        "        open(os.path.join(d, 'wt-write-test'), 'w').close()\n"
        "        os.remove(os.path.join(d, 'wt-write-test'))\n"
        "        print(d)\n"
        "    except OSError:\n"
        "        pass\n"
    )
    writable = docker("exec", running, "python", "-c", code).split()

    assert writable == ["/data", "/tmp"]  # noqa: S108 (paths in the container)
