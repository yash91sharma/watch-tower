"""Metrics API: the current values and the history of the VM, the apps and the containers.

The backend makes all values and labels. The current values come from the sampler (in
memory). The UI fetches them again on each `metrics {kind: current}` message, and the
history (sparklines, charts) on each `metrics {kind: history}` message.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlmodel import Session, col, select

from wt import clock
from wt.api.containers import compose_groups
from wt.api.deps import Ctx, get_live
from wt.config import load_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import ContainerSample, MetricTier, VmSample
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


RangeKey = Literal["1h", "6h", "24h", "7d", "30d"]


class RangeOut(BaseModel):
    # For the `range` query of the history routes.
    key: RangeKey
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


# The sparklines show the last hour, one slot per minute.
SPARKLINE_SLOTS = 60


class Sparkline(BaseModel):
    """One value per minute slot, oldest first. Null: no value in that minute."""

    cpu: list[float | None]
    mem: list[int | None]


class SparklinesOut(BaseModel):
    # The start of the first slot. Slot i starts i minutes later.
    start: datetime
    # By group label.
    groups: dict[str, Sparkline]
    # By container name: all shown containers, also the stopped ones.
    containers: dict[str, Sparkline]


def _slot_sum(lines: list[Sparkline]) -> Sparkline:
    """The sum of the lines in each slot. Null if no line has a value in the slot."""
    return Sparkline(
        cpu=[_sum([line.cpu[i] for line in lines]) for i in range(SPARKLINE_SLOTS)],
        mem=[
            None
            if all(line.mem[i] is None for line in lines)
            else sum(line.mem[i] or 0 for line in lines)
            for i in range(SPARKLINE_SLOTS)
        ],
    )


@router.get("/sparklines")
def get_sparklines(ctx: Ctx) -> SparklinesOut:
    """CPU and memory of the last 60 full minutes (the `1m` rows) for each group and
    container. The current minute is not in it: WT saves it at the next minute.
    """
    end = clock.now().replace(second=0, microsecond=0)
    start = end - timedelta(minutes=SPARKLINE_SLOTS)
    with Session(ctx.engine) as session:
        groups = compose_groups(ctx.inventory.live_rows(session))
        names = {row.id: row.name for _, pairs in groups for row, _ in pairs}
        rows = session.exec(
            select(ContainerSample).where(
                ContainerSample.tier == MetricTier.MINUTE,
                col(ContainerSample.time) >= start,
                col(ContainerSample.time) < end,
                col(ContainerSample.container_id).in_(names),
            )
        ).all()
    lines = {
        name: Sparkline(cpu=[None] * SPARKLINE_SLOTS, mem=[None] * SPARKLINE_SLOTS)
        for name in names.values()
    }
    for row in rows:
        slot = int((row.time - start) / timedelta(minutes=1))
        line = lines[names[row.container_id]]
        line.cpu[slot] = row.cpu_percent
        line.mem[slot] = row.mem_used
    return SparklinesOut(
        start=start,
        groups={
            group_label(project): _slot_sum([lines[row.name] for row, _ in pairs])
            for project, pairs in groups
        },
        containers=lines,
    )


# Each range: its length and the tier that it reads (see the tiers in METRIC_MAX_AGE).
RANGE_TIERS: dict[RangeKey, tuple[timedelta, MetricTier]] = {
    "1h": (timedelta(hours=1), MetricTier.MINUTE),
    "6h": (timedelta(hours=6), MetricTier.MINUTE),
    "24h": (timedelta(hours=24), MetricTier.MINUTE),
    "7d": (timedelta(days=7), MetricTier.QUARTER),
    "30d": (timedelta(days=30), MetricTier.HOUR),
}
# The query `?range=`. The name in Python is range_key, because `range` is a built-in.
RangeQuery = Annotated[RangeKey, Query(alias="range")]
TIER_STEPS = {
    MetricTier.MINUTE: timedelta(minutes=1),
    MetricTier.QUARTER: timedelta(minutes=15),
    MetricTier.HOUR: timedelta(hours=1),
}
# The UI formats the axis ticks from the unit.
Unit = Literal["percent", "bytes", "bytes_per_second", "load"]


class SeriesOut(BaseModel):
    key: str
    label: str
    # One value per time slot. Null: no value in the slot.
    values: list[float | None]


class ChartOut(BaseModel):
    key: str
    title: str
    unit: Unit
    # The largest top of the y axis (100 for a percent, the memory total or limit).
    # Null: no limit. The UI scales the axis to the values, up to this max.
    max: float | None
    series: list[SeriesOut]


class HistoryOut(BaseModel):
    range: RangeKey
    step_seconds: int
    # The start of each slot (Unix seconds), oldest first.
    times: list[int]
    charts: list[ChartOut]


class _Slots:
    """The time slots of a range. The current step is not in it (it is not saved yet)."""

    def __init__(self, range_key: RangeKey) -> None:
        length, self.tier = RANGE_TIERS[range_key]
        self.step = TIER_STEPS[self.tier]
        now = clock.now()
        # The start of the current step: the minute, the quarter or the hour. Each step
        # divides a day, so the rest of the time since year 1 gives it.
        end = now - (now - datetime.min.replace(tzinfo=now.tzinfo)) % self.step
        self.start = end - length
        self.end = end
        self.count = int(length / self.step)

    def times(self) -> list[int]:
        return [
            int((self.start + i * self.step).timestamp()) for i in range(self.count)
        ]

    def index(self, time: datetime) -> int:
        return int((time - self.start) / self.step)


def _series[T: (VmSample, ContainerSample)](
    slots: _Slots,
    rows: Sequence[T],
    key: str,
    label: str,
    value: Callable[[T], float | None],
) -> SeriesOut:
    values: list[float | None] = [None] * slots.count
    for row in rows:
        values[slots.index(row.time)] = value(row)
    return SeriesOut(key=key, label=label, values=values)


@router.get("/vm/history")
def get_vm_history(range_key: RangeQuery, ctx: Ctx) -> HistoryOut:
    """The VM charts of a range: CPU, memory, disk I/O, network and load."""
    slots = _Slots(range_key)
    with Session(ctx.engine) as session:
        rows = session.exec(
            select(VmSample)
            .where(
                VmSample.host_id == LOCAL_HOST_ID,
                VmSample.tier == slots.tier,
                col(VmSample.time) >= slots.start,
                col(VmSample.time) < slots.end,
            )
            .order_by(col(VmSample.time))
        ).all()

    def series(
        key: str, label: str, value: Callable[[VmSample], float | None]
    ) -> SeriesOut:
        return _series(slots, rows, key, label, value)

    charts = [
        ChartOut(
            key="cpu",
            title="CPU",
            unit="percent",
            max=100,
            series=[series("cpu", "CPU", lambda r: r.cpu_percent)],
        ),
        ChartOut(
            key="memory",
            title="Memory",
            unit="bytes",
            max=rows[-1].mem_total if rows else None,
            series=[series("used", "Used", lambda r: r.mem_used)],
        ),
        ChartOut(
            key="disk_io",
            title="Disk I/O",
            unit="bytes_per_second",
            max=None,
            series=[
                series("read", "Read", lambda r: r.disk_read_bps),
                series("write", "Write", lambda r: r.disk_write_bps),
            ],
        ),
        ChartOut(
            key="network",
            title="Network",
            unit="bytes_per_second",
            max=None,
            series=[
                series("rx", "In", lambda r: r.net_rx_bps),
                series("tx", "Out", lambda r: r.net_tx_bps),
            ],
        ),
        ChartOut(
            key="load",
            title="Load",
            unit="load",
            max=None,
            series=[
                series("load_1", "1 min", lambda r: r.load_1),
                series("load_5", "5 min", lambda r: r.load_5),
                series("load_15", "15 min", lambda r: r.load_15),
            ],
        ),
    ]
    return HistoryOut(
        range=range_key,
        step_seconds=int(slots.step.total_seconds()),
        times=slots.times(),
        charts=charts,
    )


@router.get("/containers/{name}/history")
def get_container_history(name: str, range_key: RangeQuery, ctx: Ctx) -> HistoryOut:
    """The container charts of a range: CPU, memory, network and disk I/O. 404 if the
    container is not in Docker now. The history stays after a recreate (same name).
    """
    slots = _Slots(range_key)
    with Session(ctx.engine) as session:
        row, _ = get_live(session, ctx.inventory, name)
        rows = session.exec(
            select(ContainerSample)
            .where(
                ContainerSample.container_id == row.id,
                ContainerSample.tier == slots.tier,
                col(ContainerSample.time) >= slots.start,
                col(ContainerSample.time) < slots.end,
            )
            .order_by(col(ContainerSample.time))
        ).all()

    def series(
        key: str, label: str, value: Callable[[ContainerSample], float | None]
    ) -> SeriesOut:
        return _series(slots, rows, key, label, value)

    charts = [
        ChartOut(
            key="cpu",
            title="CPU",
            unit="percent",
            max=100,
            series=[series("cpu", "CPU", lambda r: r.cpu_percent)],
        ),
        ChartOut(
            key="memory",
            title="Memory",
            unit="bytes",
            max=rows[-1].mem_limit if rows else None,
            series=[series("used", "Used", lambda r: r.mem_used)],
        ),
        ChartOut(
            key="network",
            title="Network",
            unit="bytes_per_second",
            max=None,
            series=[
                series("rx", "In", lambda r: r.net_rx_bps),
                series("tx", "Out", lambda r: r.net_tx_bps),
            ],
        ),
        ChartOut(
            key="disk_io",
            title="Disk I/O",
            unit="bytes_per_second",
            max=None,
            series=[
                series("read", "Read", lambda r: r.disk_read_bps),
                series("write", "Write", lambda r: r.disk_write_bps),
            ],
        ),
    ]
    return HistoryOut(
        range=range_key,
        step_seconds=int(slots.step.total_seconds()),
        times=slots.times(),
        charts=charts,
    )
