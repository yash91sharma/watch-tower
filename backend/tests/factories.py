"""Test data builders. Give only the values that the test is about."""

from collections.abc import Mapping
from datetime import datetime

from wt.docker.client import ContainerInfo, ContainerStats
from wt.docker.parse import ENABLE_LABEL, PROJECT_LABEL, SOURCE_LABEL


def make_info(
    name: str = "web",
    image: str = "nginx:1",
    *,
    docker_id: str | None = None,
    labels: Mapping[str, str] | None = None,
    project: str | None = None,
    source: str | None = None,
    excluded: bool = False,
    state: str = "running",
    health: str = "none",
    tty: bool = False,
) -> ContainerInfo:
    """A container from Docker inspect. The default id is "id-<name>".

    `project`, `source` and `excluded` add the Compose project, release source and
    `wt.enable=false` labels to `labels`.
    """
    all_labels = dict(labels or {})
    if project is not None:
        all_labels[PROJECT_LABEL] = project
    if source is not None:
        all_labels[SOURCE_LABEL] = source
    if excluded:
        all_labels[ENABLE_LABEL] = "false"
    return ContainerInfo(
        docker_id or f"id-{name}", name, image, all_labels, state, health, tty
    )


def make_stats(
    time: datetime,
    *,
    cpu_total: int = 0,
    system_cpu: int = 0,
    mem_usage: int = 1000,
    mem_limit: int = 10_000,
    net_rx: int = 0,
    net_tx: int = 0,
    disk_read: int = 0,
    disk_write: int = 0,
) -> ContainerStats:
    """A Docker stats sample of a container with 2 cores and no inactive file cache."""
    return ContainerStats(
        time=time,
        cpu_total=cpu_total,
        system_cpu=system_cpu,
        online_cpus=2,
        mem_usage=mem_usage,
        mem_inactive_file=0,
        mem_limit=mem_limit,
        net_rx=net_rx,
        net_tx=net_tx,
        disk_read=disk_read,
        disk_write=disk_write,
    )
