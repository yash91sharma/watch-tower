"""Tests for wt.metrics.store (the rollup of the tiers) and the metric cleanup."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from wt.db import LOCAL_HOST_ID, cleanup
from wt.db.models import Container, ContainerSample, MetricTier, VmSample
from wt.metrics.calc import ContainerValues
from wt.metrics.store import container_average, roll_up, select_samples, vm_average
from wt.metrics.vm import VmValues

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def container_row(engine: Engine) -> int:
    with Session(engine) as session:
        row = Container(host_id=LOCAL_HOST_ID, name="web")
        session.add(row)
        session.commit()
        assert row.id is not None
        return row.id


def sample(
    container_id: int,
    tier: MetricTier,
    time: datetime,
    cpu: float | None,
    mem: int,
) -> ContainerSample:
    return ContainerSample(
        container_id=container_id,
        tier=tier,
        time=time,
        cpu_percent=cpu,
        mem_used=mem,
        mem_limit=1000,
        net_rx_bps=None,
        net_tx_bps=10.0,
        disk_read_bps=None,
        disk_write_bps=None,
    )


def vm(tier: MetricTier, time: datetime, cpu: float | None) -> VmSample:
    return VmSample(
        host_id=LOCAL_HOST_ID,
        tier=tier,
        time=time,
        cpu_percent=cpu,
        mem_used=100,
        mem_total=1000,
        swap_used=0,
        swap_total=10,
        load_1=1.0,
        load_5=1.0,
        load_15=1.0,
        disk_used=5,
        disk_total=10,
        disk_read_bps=None,
        disk_write_bps=None,
        net_rx_bps=None,
        net_tx_bps=None,
    )


def add(engine: Engine, *rows: ContainerSample | VmSample) -> None:
    with Session(engine) as session:
        session.add_all(rows)
        session.commit()


def rows_of(engine: Engine, tier: MetricTier) -> list[ContainerSample]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(ContainerSample)
                .where(ContainerSample.tier == tier)
                .order_by(col(ContainerSample.time))
            )
        )


def test_a_quarter_boundary_saves_the_average_of_its_minutes(db_engine: Engine) -> None:
    web = container_row(db_engine)
    minutes = [T0 + timedelta(minutes=m) for m in range(15)]
    add(
        db_engine,
        *(
            sample(web, MetricTier.MINUTE, t, cpu=2.0 if i % 2 else None, mem=100 * i)
            for i, t in enumerate(minutes)
        ),
        *(vm(MetricTier.MINUTE, t, cpu=10.0) for t in minutes),
        # The next quarter is not part of it.
        sample(web, MetricTier.MINUTE, T0 + timedelta(minutes=15), cpu=50.0, mem=9999),
    )

    roll_up(db_engine, T0 + timedelta(minutes=15))

    [quarter] = rows_of(db_engine, MetricTier.QUARTER)
    assert quarter.time == T0
    # The average skips null, the same as the minute average.
    assert quarter.cpu_percent == pytest.approx(2.0)
    assert quarter.mem_used == 700
    assert quarter.mem_limit == 1000
    assert quarter.net_rx_bps is None
    assert quarter.net_tx_bps == pytest.approx(10.0)
    with Session(db_engine) as session:
        vm_quarter = session.exec(
            select(VmSample).where(VmSample.tier == MetricTier.QUARTER)
        ).one()
    assert vm_quarter.cpu_percent == pytest.approx(10.0)
    assert vm_quarter.disk_total == 10


def test_an_hour_boundary_saves_the_last_quarter_and_then_the_hour(
    db_engine: Engine,
) -> None:
    web = container_row(db_engine)
    add(
        db_engine,
        *(
            sample(
                web,
                MetricTier.QUARTER,
                T0 + timedelta(minutes=15 * q),
                cpu=float(q),
                mem=100,
            )
            for q in range(3)
        ),
        # The minutes of the last quarter (00:45-00:59).
        *(
            sample(
                web, MetricTier.MINUTE, T0 + timedelta(minutes=45 + m), cpu=3.0, mem=100
            )
            for m in range(15)
        ),
    )

    roll_up(db_engine, T0 + timedelta(hours=1))

    assert [row.cpu_percent for row in rows_of(db_engine, MetricTier.QUARTER)] == [
        0.0,
        1.0,
        2.0,
        3.0,
    ]
    [hour] = rows_of(db_engine, MetricTier.HOUR)
    assert hour.time == T0
    assert hour.cpu_percent == pytest.approx(1.5)


def test_a_time_that_is_not_a_boundary_does_nothing(db_engine: Engine) -> None:
    web = container_row(db_engine)
    add(db_engine, sample(web, MetricTier.MINUTE, T0, cpu=1.0, mem=1))

    roll_up(db_engine, T0 + timedelta(minutes=7))

    assert rows_of(db_engine, MetricTier.QUARTER) == []


def test_a_second_rollup_changes_nothing_and_a_missed_quarter_is_done_later(
    db_engine: Engine,
) -> None:
    web = container_row(db_engine)
    add(
        db_engine,
        sample(web, MetricTier.MINUTE, T0 + timedelta(minutes=1), cpu=1.0, mem=1),
        sample(web, MetricTier.MINUTE, T0 + timedelta(minutes=16), cpu=2.0, mem=1),
    )

    # WT was down at 00:15. At 00:30 it rolls up the last hour of quarters.
    roll_up(db_engine, T0 + timedelta(minutes=30))
    roll_up(db_engine, T0 + timedelta(minutes=30))

    assert [
        (row.time, row.cpu_percent) for row in rows_of(db_engine, MetricTier.QUARTER)
    ] == [
        (T0, 1.0),
        (T0 + timedelta(minutes=15), 2.0),
    ]


def test_cleanup_keeps_each_tier_for_its_time(db_engine: Engine, clock: object) -> None:
    web = container_row(db_engine)
    now = T0  # The clock fixture starts at T0.
    kept = [
        (MetricTier.MINUTE, now - timedelta(hours=23)),
        (MetricTier.QUARTER, now - timedelta(days=6)),
        (MetricTier.HOUR, now - timedelta(days=29)),
    ]
    old = [
        (MetricTier.MINUTE, now - timedelta(hours=25)),
        (MetricTier.QUARTER, now - timedelta(days=8)),
        (MetricTier.HOUR, now - timedelta(days=31)),
    ]
    add(
        db_engine,
        *(sample(web, tier, time, cpu=1.0, mem=1) for tier, time in kept + old),
        *(vm(tier, time, cpu=1.0) for tier, time in kept + old),
    )

    cleanup.delete_old_rows(db_engine)

    with Session(db_engine) as session:
        assert {(r.tier, r.time) for r in session.exec(select(ContainerSample))} == set(
            kept
        )
        assert {(r.tier, r.time) for r in session.exec(select(VmSample))} == set(kept)


def test_vm_average_of_samples() -> None:
    rows = [vm(MetricTier.MINUTE, T0, cpu=1.0), vm(MetricTier.MINUTE, T0, cpu=None)]
    rows[1].mem_total, rows[1].mem_used, rows[1].load_5 = 2000, 301, 3.0
    rows[1].disk_read_bps, rows[1].net_tx_bps = 8.0, 4.0
    net = [(row.net_rx_bps, row.net_tx_bps) for row in rows]

    row = vm_average(rows, net, MetricTier.QUARTER, T0)

    assert row.model_dump() == {
        "host_id": LOCAL_HOST_ID,
        "tier": MetricTier.QUARTER,
        "time": T0,
        # The average skips None. Totals take the last value.
        "cpu_percent": 1.0,
        "mem_used": 200,
        "mem_total": 2000,
        "swap_used": 0,
        "swap_total": 10,
        "load_1": 1.0,
        "load_5": 2.0,
        "load_15": 1.0,
        "disk_used": 5,
        "disk_total": 10,
        "disk_read_bps": 8.0,
        "disk_write_bps": None,
        "net_rx_bps": None,
        "net_tx_bps": 4.0,
    }


def test_vm_average_of_poll_values() -> None:
    polls = [
        VmValues(
            cpu_percent=cpu,
            cores=2,
            mem_used=100,
            mem_total=1000,
            swap_used=0,
            swap_total=0,
            load_1=1.0,
            load_5=1.0,
            load_15=1.0,
            uptime_seconds=60.0,
            disk_used=1,
            disk_total=2,
            disk_read_bps=None,
            disk_write_bps=None,
        )
        for cpu in (2.0, 4.0)
    ]

    row = vm_average(polls, [(10.0, None), (20.0, None)], MetricTier.MINUTE, T0)

    assert (row.cpu_percent, row.net_rx_bps, row.net_tx_bps) == (3.0, 15.0, None)


def test_container_average_of_samples_and_of_poll_values() -> None:
    rows = [
        sample(7, MetricTier.MINUTE, T0, cpu, mem)
        for cpu, mem in ((1.0, 10), (None, 20))
    ]
    rows[1].mem_limit = 5000
    polls = [
        ContainerValues(
            cpu_percent=row.cpu_percent,
            cpus=2,
            mem_used=row.mem_used,
            mem_limit=row.mem_limit,
            net_rx_bps=row.net_rx_bps,
            net_tx_bps=row.net_tx_bps,
            disk_read_bps=row.disk_read_bps,
            disk_write_bps=row.disk_write_bps,
        )
        for row in rows
    ]

    from_rows = container_average(7, rows, MetricTier.HOUR, T0)
    from_polls = container_average(7, polls, MetricTier.HOUR, T0)

    assert from_rows == from_polls
    assert from_rows.model_dump() == {
        "container_id": 7,
        "tier": MetricTier.HOUR,
        "time": T0,
        "cpu_percent": 1.0,
        "mem_used": 15,
        "mem_limit": 5000,
        "net_rx_bps": None,
        "net_tx_bps": 10.0,
        "disk_read_bps": None,
        "disk_write_bps": None,
    }


def test_select_samples_gives_the_rows_of_a_tier_in_the_range(
    db_engine: Engine,
) -> None:
    container_id = container_row(db_engine)
    add(
        db_engine,
        sample(container_id, MetricTier.MINUTE, T0 + timedelta(minutes=2), 2.0, 1),
        sample(container_id, MetricTier.MINUTE, T0, 1.0, 1),
        # Not in [T0, T0 + 3 min) or not the tier.
        sample(container_id, MetricTier.MINUTE, T0 + timedelta(minutes=3), 9.0, 1),
        sample(container_id, MetricTier.MINUTE, T0 - timedelta(minutes=1), 9.0, 1),
        sample(container_id, MetricTier.QUARTER, T0, 9.0, 1),
    )

    with Session(db_engine) as session:
        found = session.exec(
            select_samples(
                ContainerSample, MetricTier.MINUTE, T0, T0 + timedelta(minutes=3)
            )
        ).all()

    assert [row.cpu_percent for row in found] == [1.0, 2.0]
