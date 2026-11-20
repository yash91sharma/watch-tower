"""Metrics API: the current values of the VM, the apps and the containers.

The backend makes all values and labels. The current values come from the sampler (in
memory). The UI fetches them again on each `metrics {kind: current}` message.
"""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session

from wt.api.containers import compose_groups
from wt.api.deps import Ctx
from wt.config import load_settings
from wt.docker.parse import group_label
from wt.metrics.calc import ContainerValues, cores_used
from wt.metrics.labels import (
    bytes_label,
    cpu_label,
    load_label,
    rate_label,
    uptime_label,
    used_of_label,
)
from wt.metrics.sampler import Sampler

router = APIRouter(prefix="/metrics", tags=["metrics"])


class RangeOut(BaseModel):
    # For the `range` query of the history routes.
    key: str
    label: str


# The chart ranges, in the order of the dropdown.
RANGES = [
    RangeOut(key="1h", label="1 hour"),
    RangeOut(key="6h", label="6 hours"),
    RangeOut(key="24h", label="24 hours"),
    RangeOut(key="7d", label="7 days"),
    RangeOut(key="30d", label="30 days"),
]


class VmOut(BaseModel):
    """The current values of the Docker VM. The percents are for bars (0-100)."""

    cpu_percent: float | None
    cpu_label: str
    cores: int
    mem_percent: float
    mem_label: str
    # The memory of the containers that WT shows.
    containers_mem_label: str
    # None if the VM has no swap.
    swap_percent: float | None
    swap_label: str
    disk_percent: float
    disk_label: str
    disk_read_label: str
    disk_write_label: str
    net_rx_label: str
    net_tx_label: str
    load_label: str
    uptime_label: str


class ContainerUsage(BaseModel):
    """The current values of a container. Null values and "-" labels: the container
    does not run, or WT has no value yet.
    """

    name: str
    state: str
    cpu_percent: float | None
    cpu_label: str
    mem_used: int | None
    # % of the memory limit (or of the VM memory if the container has no limit).
    mem_percent: float | None
    mem_label: str
    net_rx_label: str
    net_tx_label: str
    disk_read_label: str
    disk_write_label: str


class GroupUsage(BaseModel):
    """A Compose group with the sums of its containers."""

    project: str | None
    label: str
    cpu_percent: float | None
    cpu_label: str
    mem_used: int | None
    mem_label: str
    containers: list[ContainerUsage]


class CountsOut(BaseModel):
    # Compose projects, plus the containers with no project.
    apps: int
    # The containers that WT shows (not the excluded ones).
    containers: int
    running: int
    apps_label: str
    containers_label: str


class OverviewOut(BaseModel):
    # The time of the last poll. None before the first poll.
    sampled_at: datetime | None
    interval_seconds: int
    vm: VmOut | None
    counts: CountsOut
    groups: list[GroupUsage]
    ranges: list[RangeOut]


def _percent(part: int, total: int) -> float | None:
    return part / total * 100 if total > 0 else None


def _sum(values: list[float | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _vm_out(sampler: Sampler) -> VmOut | None:
    vm = sampler.vm
    if vm is None:
        return None
    rx, tx = sampler.vm_network()
    containers_mem = sum(item.mem_used for item in sampler.containers.values())
    return VmOut(
        cpu_percent=vm.cpu_percent,
        cpu_label=cpu_label(vm.cpu_percent, cores_used(vm.cpu_percent, vm.cores)),
        cores=vm.cores,
        mem_percent=_percent(vm.mem_used, vm.mem_total) or 0.0,
        mem_label=used_of_label(vm.mem_used, vm.mem_total),
        containers_mem_label=bytes_label(containers_mem),
        swap_percent=_percent(vm.swap_used, vm.swap_total),
        swap_label=used_of_label(vm.swap_used, vm.swap_total),
        disk_percent=_percent(vm.disk_used, vm.disk_total) or 0.0,
        disk_label=used_of_label(vm.disk_used, vm.disk_total),
        disk_read_label=rate_label(vm.disk_read_bps),
        disk_write_label=rate_label(vm.disk_write_bps),
        net_rx_label=rate_label(rx),
        net_tx_label=rate_label(tx),
        load_label=load_label(vm.load_1, vm.load_5, vm.load_15),
        uptime_label=uptime_label(vm.uptime_seconds),
    )


def _container_usage(
    name: str, state: str, values: ContainerValues | None
) -> ContainerUsage:
    if values is None:
        return ContainerUsage(
            name=name,
            state=state,
            cpu_percent=None,
            cpu_label=cpu_label(None, None),
            mem_used=None,
            mem_percent=None,
            mem_label=used_of_label(None, 0),
            net_rx_label=rate_label(None),
            net_tx_label=rate_label(None),
            disk_read_label=rate_label(None),
            disk_write_label=rate_label(None),
        )
    cpu = values.cpu_percent
    return ContainerUsage(
        name=name,
        state=state,
        cpu_percent=cpu,
        cpu_label=cpu_label(cpu, cores_used(cpu, values.cpus)),
        mem_used=values.mem_used,
        mem_percent=_percent(values.mem_used, values.mem_limit),
        mem_label=used_of_label(values.mem_used, values.mem_limit),
        net_rx_label=rate_label(values.net_rx_bps),
        net_tx_label=rate_label(values.net_tx_bps),
        disk_read_label=rate_label(values.disk_read_bps),
        disk_write_label=rate_label(values.disk_write_bps),
    )


def _group_usage(
    project: str | None, containers: list[ContainerUsage], cores: int
) -> GroupUsage:
    cpu = _sum([item.cpu_percent for item in containers])
    used = [item.mem_used for item in containers if item.mem_used is not None]
    mem = sum(used) if used else None
    return GroupUsage(
        project=project,
        label=group_label(project),
        cpu_percent=cpu,
        cpu_label=cpu_label(cpu, cores_used(cpu, cores)),
        mem_used=mem,
        mem_label=bytes_label(mem),
        containers=containers,
    )


@router.get("/overview")
def get_overview(ctx: Ctx) -> OverviewOut:
    """The current values, the counts and the groups (in the order of /api/containers)."""
    sampler = ctx.sampler
    with Session(ctx.engine) as session:
        groups = compose_groups(ctx.inventory.live_rows(session))
    # All containers of a VM see the same cores (also when WT cannot read the VM).
    container_cores = (item.cpus for item in sampler.containers.values())
    cores = sampler.vm.cores if sampler.vm else max(container_cores, default=0)
    group_usages: list[GroupUsage] = []
    apps = running = total = 0
    for project, pairs in groups:
        usages = [
            _container_usage(live.name, live.state, sampler.containers.get(live.name))
            for _, live in pairs
        ]
        group_usages.append(_group_usage(project, usages, cores))
        apps += 1 if project is not None else len(pairs)
        total += len(pairs)
        running += sum(1 for _, live in pairs if live.state == "running")
    return OverviewOut(
        sampled_at=sampler.sampled_at,
        interval_seconds=load_settings(ctx.engine).metrics_interval_seconds,
        vm=_vm_out(sampler),
        counts=CountsOut(
            apps=apps,
            containers=total,
            running=running,
            apps_label=f"{apps} app" if apps == 1 else f"{apps} apps",
            containers_label=f"{running} running of {total} containers",
        ),
        groups=group_usages,
        ranges=RANGES,
    )
