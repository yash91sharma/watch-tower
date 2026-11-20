"""The sampler: one poll gets the values of the VM and of the running containers.

In memory: the last counters (for the next delta) and the current values, which the API
shows. Each poll also adds its values to the current minute. At the first poll of a new
minute, WT saves the average of the last minute as `1m` rows. After each poll WT
publishes `metrics {kind: current}`, after each save `metrics {kind: history}`.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import fmean

from sqlalchemy import Engine
from sqlmodel import Session

from wt import clock
from wt.bus import Bus, Topic
from wt.db import LOCAL_HOST_ID, find_container
from wt.db.models import ContainerSample, MetricTier, VmSample
from wt.docker.client import (
    ContainerNotFoundError,
    ContainerStats,
    DockerApi,
    DockerUnavailableError,
)
from wt.docker.inventory import Inventory
from wt.metrics.calc import ContainerValues, container_values
from wt.metrics.vm import VmCounters, VmReadError, VmValues, read_vm, vm_values

log = logging.getLogger(__name__)

# The most Docker stats calls at the same time.
MAX_CALLS = 10


@dataclass
class _Minute:
    """The polls of one minute, before WT saves their average."""

    start: datetime
    vm: list[VmValues] = field(default_factory=list[VmValues])
    # The VM network (sum of the containers) of each poll.
    net: list[tuple[float | None, float | None]] = field(
        default_factory=list[tuple[float | None, float | None]]
    )
    containers: dict[str, list[ContainerValues]] = field(
        default_factory=dict[str, list[ContainerValues]]
    )


class Sampler:
    def __init__(
        self,
        engine: Engine,
        inventory: Inventory,
        bus: Bus,
        data_dir: Path,
        root: Path = Path("/"),
    ) -> None:
        self._engine = engine
        self._inventory = inventory
        self._bus = bus
        self._data_dir = data_dir
        self._root = root
        self._last_vm: VmCounters | None = None
        self._last_stats: dict[str, ContainerStats] = {}
        self._minute: _Minute | None = None
        self._vm_error = ""
        # The current values, by container name. Only running, shown containers.
        self.containers: dict[str, ContainerValues] = {}
        self.vm: VmValues | None = None
        self.sampled_at: datetime | None = None

    def vm_network(self) -> tuple[float | None, float | None]:
        """The VM network in and out (bytes/s): the sum of the containers."""
        rx = [
            v.net_rx_bps for v in self.containers.values() if v.net_rx_bps is not None
        ]
        tx = [
            v.net_tx_bps for v in self.containers.values() if v.net_tx_bps is not None
        ]
        return (sum(rx) if rx else None, sum(tx) if tx else None)

    async def poll(self, docker: DockerApi) -> bool:
        """Get all values once. False if Docker is not available (the VM values stay)."""
        now = clock.now()
        start = now.replace(second=0, microsecond=0)
        if self._minute is not None and self._minute.start != start:
            await asyncio.to_thread(_save, self._engine, self._minute)
            self._bus.publish(Topic.METRICS, {"kind": "history"})
            self._minute = None
        minute = self._minute = self._minute or _Minute(start)

        docker_ok = await self._poll_containers(docker)
        self._poll_vm(now)
        self.sampled_at = now

        if self.vm is not None:
            minute.vm.append(self.vm)
            minute.net.append(self.vm_network())
        for name, values in self.containers.items():
            minute.containers.setdefault(name, []).append(values)
        self._bus.publish(Topic.METRICS, {"kind": "current"})
        return docker_ok

    async def _poll_containers(self, docker: DockerApi) -> bool:
        names = [
            name
            for name in self._inventory.names()
            if (live := self._inventory.get(name)) and live.state == "running"
        ]
        limit = asyncio.Semaphore(MAX_CALLS)
        errors: list[DockerUnavailableError] = []

        async def one(name: str) -> ContainerStats | None:
            async with limit:
                try:
                    return await docker.stats(name)
                except ContainerNotFoundError:
                    return None  # Removed after the list.
                except DockerUnavailableError as error:
                    errors.append(error)
                    return None

        results = await asyncio.gather(*(one(name) for name in names))
        if errors:
            log.warning("Cannot get the container stats: %s", errors[0])
            self.containers, self._last_stats = {}, {}
            return False
        stats = {name: item for name, item in zip(names, results) if item is not None}
        self.containers = {
            name: container_values(self._last_stats.get(name), item)
            for name, item in stats.items()
        }
        # A stopped container has no last counters, so its next start has no delta.
        self._last_stats = stats
        return True

    def _poll_vm(self, now: datetime) -> None:
        try:
            counters = read_vm(self._root, self._data_dir, now)
        except VmReadError as error:
            if str(error) != self._vm_error:
                log.warning("Cannot read the VM values: %s", error)
                self._vm_error = str(error)
            self.vm = self._last_vm = None
            return
        self._vm_error = ""
        self.vm = vm_values(self._last_vm, counters)
        self._last_vm = counters


def _mean(values: list[float | None]) -> float | None:
    """The average of the values that are not None. None if there are none."""
    known = [value for value in values if value is not None]
    return fmean(known) if known else None


def _mean_int(values: list[int]) -> int:
    return round(fmean(values))


def _save(engine: Engine, minute: _Minute) -> None:
    """Save the averages of the minute as `1m` rows, in one transaction."""
    with Session(engine) as session:
        if minute.vm:
            vm = minute.vm
            session.merge(
                VmSample(
                    host_id=LOCAL_HOST_ID,
                    tier=MetricTier.MINUTE,
                    time=minute.start,
                    cpu_percent=_mean([v.cpu_percent for v in vm]),
                    mem_used=_mean_int([v.mem_used for v in vm]),
                    mem_total=vm[-1].mem_total,
                    swap_used=_mean_int([v.swap_used for v in vm]),
                    swap_total=vm[-1].swap_total,
                    load_1=fmean(v.load_1 for v in vm),
                    load_5=fmean(v.load_5 for v in vm),
                    load_15=fmean(v.load_15 for v in vm),
                    disk_used=vm[-1].disk_used,
                    disk_total=vm[-1].disk_total,
                    disk_read_bps=_mean([v.disk_read_bps for v in vm]),
                    disk_write_bps=_mean([v.disk_write_bps for v in vm]),
                    net_rx_bps=_mean([rx for rx, _ in minute.net]),
                    net_tx_bps=_mean([tx for _, tx in minute.net]),
                )
            )
        for name, polls in minute.containers.items():
            row = find_container(session, name)
            if row is None or row.id is None:
                continue  # The row is gone (for example a config import).
            session.merge(
                ContainerSample(
                    container_id=row.id,
                    tier=MetricTier.MINUTE,
                    time=minute.start,
                    cpu_percent=_mean([p.cpu_percent for p in polls]),
                    mem_used=_mean_int([p.mem_used for p in polls]),
                    mem_limit=polls[-1].mem_limit,
                    net_rx_bps=_mean([p.net_rx_bps for p in polls]),
                    net_tx_bps=_mean([p.net_tx_bps for p in polls]),
                    disk_read_bps=_mean([p.disk_read_bps for p in polls]),
                    disk_write_bps=_mean([p.disk_write_bps for p in polls]),
                )
            )
        session.commit()
