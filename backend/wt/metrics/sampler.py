"""The sampler: one poll gets the values of the VM and of the running containers.

In memory: the last counters (for the next delta) and the current values, which the API
shows. Each poll also adds its values to the current minute. At the first poll of a new
minute, WT saves the average of the last minute as `1m` rows and does the rollup that is due
(wt.metrics.store). After each poll WT publishes `metrics {kind: current}`, after each
save `metrics {kind: history}`.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from wt import clock
from wt.bus import Bus, Topic
from wt.db import local_containers
from wt.db.models import MetricTier
from wt.docker.client import (
    ContainerNotFoundError,
    ContainerStats,
    DockerApi,
    DockerUnavailableError,
)
from wt.docker.inventory import Inventory
from wt.metrics.calc import ContainerValues, container_values, total
from wt.metrics.store import Network, container_average, roll_up, vm_average
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
    net: list[Network] = field(default_factory=list[Network])
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

    def vm_network(self) -> Network:
        """The VM network in and out (bytes/s): the sum of the containers."""
        values = self.containers.values()
        return (
            total(v.net_rx_bps for v in values),
            total(v.net_tx_bps for v in values),
        )

    async def poll(self, docker: DockerApi) -> bool:
        """Get all values once. False if Docker is not available (the VM values stay)."""
        now = clock.now()
        start = now.replace(second=0, microsecond=0)
        if self._minute is not None and self._minute.start != start:
            await asyncio.to_thread(_save, self._engine, self._minute, start)
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


def _save(engine: Engine, minute: _Minute, now: datetime) -> None:
    """Save the averages of the minute as `1m` rows, in one transaction. Then save the
    rollup rows that are due at `now` (the start of the new minute).
    """
    with Session(engine) as session:
        if minute.vm:
            session.merge(
                vm_average(minute.vm, minute.net, MetricTier.MINUTE, minute.start)
            )
        rows = {row.name: row for row in local_containers(session)}
        for name, polls in minute.containers.items():
            row = rows.get(name)
            if row is None or row.id is None:
                continue  # The row is gone (for example a config import).
            session.merge(
                container_average(row.id, polls, MetricTier.MINUTE, minute.start)
            )
        session.commit()
    roll_up(engine, now)
