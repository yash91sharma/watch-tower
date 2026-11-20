"""The metric rows: the averages of a step, and the rollup of the tiers.

`vm_average` and `container_average` make the row of one step from the polls of a minute
(the sampler) or from the rows of a shorter tier (the rollup). The average skips null
values. Totals and limits take the last value.

The sampler calls `roll_up` after it saves a minute. At each 15-min boundary, WT saves
the average of the minutes of each quarter of the last hour. At each hour, it also saves
the average of the quarters of each hour of the last 6 hours. Thus a short stop of WT
loses no step, and a second rollup of a step gives the same row (merge on the key).
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from statistics import fmean

from sqlalchemy import Engine
from sqlmodel import Session, col, select
from sqlmodel.sql.expression import SelectOfScalar

from wt.db import LOCAL_HOST_ID
from wt.db.models import ContainerSample, MetricTier, VmSample
from wt.metrics.calc import ContainerValues, mean, mean_int
from wt.metrics.vm import VmValues

QUARTER = timedelta(minutes=15)
HOUR = timedelta(hours=1)
# The steps that each rollup does again (see the module doc).
QUARTERS_BACK = 4
HOURS_BACK = 6

# The network in and out (bytes/s) of the VM at one poll or in one step.
Network = tuple[float | None, float | None]


def vm_average[T: (VmValues, VmSample)](
    rows: Sequence[T], net: Sequence[Network], tier: MetricTier, time: datetime
) -> VmSample:
    """The VM row of one step. `net` has the network of each row (the VM poll values
    have no network: the sampler adds up the containers).
    """
    return VmSample(
        host_id=LOCAL_HOST_ID,
        tier=tier,
        time=time,
        cpu_percent=mean([r.cpu_percent for r in rows]),
        mem_used=mean_int([r.mem_used for r in rows]),
        mem_total=rows[-1].mem_total,
        swap_used=mean_int([r.swap_used for r in rows]),
        swap_total=rows[-1].swap_total,
        load_1=fmean(r.load_1 for r in rows),
        load_5=fmean(r.load_5 for r in rows),
        load_15=fmean(r.load_15 for r in rows),
        disk_used=rows[-1].disk_used,
        disk_total=rows[-1].disk_total,
        disk_read_bps=mean([r.disk_read_bps for r in rows]),
        disk_write_bps=mean([r.disk_write_bps for r in rows]),
        net_rx_bps=mean([rx for rx, _ in net]),
        net_tx_bps=mean([tx for _, tx in net]),
    )


def container_average[T: (ContainerValues, ContainerSample)](
    container_id: int, rows: Sequence[T], tier: MetricTier, time: datetime
) -> ContainerSample:
    """The container row of one step."""
    return ContainerSample(
        container_id=container_id,
        tier=tier,
        time=time,
        cpu_percent=mean([r.cpu_percent for r in rows]),
        mem_used=mean_int([r.mem_used for r in rows]),
        mem_limit=rows[-1].mem_limit,
        net_rx_bps=mean([r.net_rx_bps for r in rows]),
        net_tx_bps=mean([r.net_tx_bps for r in rows]),
        disk_read_bps=mean([r.disk_read_bps for r in rows]),
        disk_write_bps=mean([r.disk_write_bps for r in rows]),
    )


def select_samples[T: (ContainerSample, VmSample)](
    table: type[T], tier: MetricTier, start: datetime, end: datetime
) -> SelectOfScalar[T]:
    """The rows of a tier in [start, end), oldest first."""
    return (
        select(table)
        .where(col(table.tier) == tier, col(table.time) >= start, col(table.time) < end)
        .order_by(col(table.time))
    )


def roll_up(engine: Engine, now: datetime) -> None:
    """Save the rollup rows that are due at `now` (the start of the new minute)."""
    if now.minute % 15:
        return
    with Session(engine) as session:
        for back in range(QUARTERS_BACK, 0, -1):
            start = now - back * QUARTER
            _roll(
                session, MetricTier.MINUTE, MetricTier.QUARTER, start, start + QUARTER
            )
        if now.minute == 0:
            for back in range(HOURS_BACK, 0, -1):
                start = now - back * HOUR
                _roll(session, MetricTier.QUARTER, MetricTier.HOUR, start, start + HOUR)
        session.commit()


def _roll(
    session: Session,
    source: MetricTier,
    target: MetricTier,
    start: datetime,
    end: datetime,
) -> None:
    """Save the average of the `source` rows in [start, end) as one `target` row per
    container and one for the VM.
    """
    # Flush the rows of the shorter tier first (the hour reads the last quarter).
    session.flush()
    per_container: dict[int, list[ContainerSample]] = {}
    for row in session.exec(select_samples(ContainerSample, source, start, end)):
        per_container.setdefault(row.container_id, []).append(row)
    for container_id, rows in per_container.items():
        session.merge(container_average(container_id, rows, target, start))
    vm = list(session.exec(select_samples(VmSample, source, start, end)))
    if vm:
        net = [(row.net_rx_bps, row.net_tx_bps) for row in vm]
        session.merge(vm_average(vm, net, target, start))
