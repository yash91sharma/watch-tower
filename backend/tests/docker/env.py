"""Docker test environment (task 6.1): test containers on the host Docker.

The Docker daemon is on the host, not in wt_dev. So the images have all their files (no
bind mounts), and this container joins the network `wt_test_net` to reach them by name.
All names start with `wt_test_`. The containers stay after the tests. The next run reuses
them, and makes a container again only if its image or its spec changed.
Run the Docker tests with: uv run pytest -m docker -n0
"""

import hashlib
import json
import shutil
import socket
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

NETWORK = "wt_test_net"
PROXY = "wt_test_socket_proxy"
PROXY_URL = f"http://{PROXY}:2375"
PROXY_IMAGE = "lscr.io/linuxserver/socket-proxy:3.4.7-r0-ls104"
APP_DIR = Path(__file__).parents[3] / "e2e" / "fakes" / "containers" / "app"
APP_IMAGE = "wt_test/app"
VERSIONED_IMAGE = "wt_test/versioned:1.0.0"
VERSIONED_SOURCE = "https://github.com/wt-test/versioned"
PROJECT = "wt_test"
SPEC_LABEL = "wt.test.spec"
# Files in the test app container (see e2e/fakes/containers/app/app.sh).
OK_FILE = "/tmp/ok"  # noqa: S108
CRASH_FILE = "/tmp/crash"  # noqa: S108

_DOCKER = shutil.which("docker") or "docker"


@dataclass(frozen=True)
class TestContainer:
    name: str
    image: str = f"{APP_IMAGE}:1.0.0"
    env: dict[str, str] = field(default_factory=dict[str, str])
    labels: dict[str, str] = field(
        default_factory=lambda: {"com.docker.compose.project": PROJECT}
    )
    tty: bool = False
    restart: str = "no"


CONTAINERS = [
    TestContainer("wt_test_healthy"),
    TestContainer("wt_test_unhealthy"),
    TestContainer("wt_test_restart", restart="on-failure"),
    TestContainer("wt_test_json", env={"MODE": "json"}),
    # No Compose project: WT shows it in the group "Other".
    TestContainer("wt_test_tty", tty=True, labels={}),
    TestContainer("wt_test_latest", image=f"{APP_IMAGE}:latest"),
    TestContainer(
        "wt_test_excluded",
        labels={"com.docker.compose.project": PROJECT, "wt.enable": "false"},
    ),
    TestContainer("wt_test_versioned", image=VERSIONED_IMAGE),
]


def docker(*args: str) -> str:
    """Run a docker command. Give its output."""
    result = subprocess.run(
        [_DOCKER, *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _exists(kind: str, name: str) -> bool:
    result = subprocess.run(
        [_DOCKER, kind, "inspect", name], capture_output=True, check=False
    )
    return result.returncode == 0


def build_images() -> None:
    docker(
        "build",
        "-q",
        "-t",
        f"{APP_IMAGE}:1.0.0",
        "-t",
        f"{APP_IMAGE}:latest",
        str(APP_DIR),
    )
    docker(
        "build",
        "-q",
        "--label",
        f"org.opencontainers.image.source={VERSIONED_SOURCE}",
        "-t",
        VERSIONED_IMAGE,
        str(APP_DIR),
    )


def join_network() -> None:
    """Make the network and connect this container (wt_dev or the CI container) to it."""
    if not _exists("network", NETWORK):
        docker("network", "create", NETWORK)
    me = socket.gethostname()
    networks = json.loads(
        docker("inspect", "-f", "{{json .NetworkSettings.Networks}}", me)
    )
    if NETWORK not in networks:
        docker("network", "connect", NETWORK, me)


def _run(name: str, image: str, spec_hash: str, args: list[str]) -> str:
    """Start the container. Reuse it if it has the same image and spec."""
    if _exists("container", name):
        current_image = docker("inspect", "-f", "{{.Image}}", name)
        current_spec = docker(
            "inspect", "-f", f'{{{{index .Config.Labels "{SPEC_LABEL}"}}}}', name
        )
        wanted_image = docker("image", "inspect", "-f", "{{.Id}}", image)
        if current_image == wanted_image and current_spec == spec_hash:
            docker("start", name)
            return docker("inspect", "-f", "{{.Id}}", name)
        docker("rm", "-f", name)
    return docker(
        "run",
        "-d",
        "--name",
        name,
        "--network",
        NETWORK,
        "--log-opt",
        "max-size=1m",
        "--label",
        f"{SPEC_LABEL}={spec_hash}",
        *args,
        image,
    )


def start_proxy() -> str:
    """The read-only socket proxy, as in compose.yaml."""
    env = {"CONTAINERS": "1", "EVENTS": "1", "ALLOW_LOGS": "1", "POST": "0"}
    args = ["--read-only", "--tmpfs", "/run", "--label", "wt.enable=false"]
    args += ["-v", "/var/run/docker.sock:/var/run/docker.sock:ro"]
    for key, value in env.items():
        args += ["-e", f"{key}={value}"]
    if not _exists("image", PROXY_IMAGE):
        docker("pull", "-q", PROXY_IMAGE)
    return _run(PROXY, PROXY_IMAGE, _hash(env), args)


def start_container(spec: TestContainer) -> str:
    args = ["--restart", spec.restart]
    if spec.tty:
        args.append("-t")
    for key, value in spec.env.items():
        args += ["-e", f"{key}={value}"]
    for key, value in spec.labels.items():
        args += ["--label", f"{key}={value}"]
    return _run(spec.name, spec.image, _hash(asdict(spec)), args)


def wait_healthy(names: list[str], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    for name in names:
        while docker("inspect", "-f", "{{.State.Health.Status}}", name) != "healthy":
            if time.monotonic() > deadline:
                raise TimeoutError(f"{name} is not healthy")
            time.sleep(0.5)


def start_test_env() -> dict[str, str]:
    """Start the proxy and all test containers. Give name -> container id."""
    build_images()
    join_network()
    start_proxy()
    ids = {spec.name: start_container(spec) for spec in CONTAINERS}
    wait_healthy(list(ids))
    return ids


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]
