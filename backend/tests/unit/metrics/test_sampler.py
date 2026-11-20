"""Tests for wt.metrics.sampler (poll the VM and the containers, save each minute)."""

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from tests.factories import make_info, make_stats
from tests.fake_docker import FakeDocker
from tests.unit.metrics.conftest import write_cpu
from wt.bus import Bus, Topic
from wt.clock import FakeClock
from wt.db import find_container
from wt.db.models import ContainerSample, MetricTier, VmSample
from wt.docker.inventory import Inventory
from wt.metrics.sampler import Sampler

pytestmark = pytest.mark.anyio

# Each poll moves the counters this much: the container uses 1% of all cores and gets
# 1000 bytes/s. The VM is 25% busy.
SYSTEM_STEP = 10_000_000_000


@pytest.fixture
async def docker(db_engine: Engine) -> FakeDocker:
    fake = FakeDocker()
    fake.add(make_info("web", project="site"))
    fake.add(make_info("db", project="site"))
    fake.add(make_info("off", excluded=True))
    return fake


async def make_sampler(
    db_engine: Engine, docker: FakeDocker, vm_root: Path, tmp_path: Path
) -> tuple[Sampler, Inventory, Bus]:
    inventory = Inventory(db_engine)
    await inventory.sync_all(docker)
    bus = Bus()
    return Sampler(db_engine, inventory, bus, tmp_path, vm_root), inventory, bus


def set_counters(
    docker: FakeDocker, clock: FakeClock, vm_root: Path, step: int
) -> None:
    """The counters of all containers and of the VM after `step` polls."""
    for name in ("web", "db"):
        docker.stats_values[name] = make_stats(
            clock.now(),
            cpu_total=step * SYSTEM_STEP // 100,
            system_cpu=step * SYSTEM_STEP,
            mem_usage=1000 + step * 100,
            net_rx=step * 10_000,
        )
    write_cpu(vm_root, busy=step * 100, idle=step * 300)


async def test_the_first_poll_has_no_cpu_and_the_second_has(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, bus = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(10)

    set_counters(docker, clock, vm_root, 1)
    with bus.subscribe([Topic.METRICS]) as subscription:
        assert await sampler.poll(docker)
        assert (await subscription.get()).data == {"kind": "current"}

    assert set(sampler.containers) == {"web", "db"}
    assert sampler.containers["web"].cpu_percent is None
    assert sampler.vm is not None
    assert sampler.vm.cpu_percent is None

    clock.advance(10)
    set_counters(docker, clock, vm_root, 2)
    await sampler.poll(docker)

    web = sampler.containers["web"]
    assert web.cpu_percent == pytest.approx(1.0)
    assert web.net_rx_bps == pytest.approx(1000.0)
    assert sampler.vm is not None
    assert sampler.vm.cpu_percent == pytest.approx(25.0)
    # The VM network is the sum of the containers.
    assert sampler.vm_network() == (pytest.approx(2000.0), pytest.approx(0.0))


async def test_a_new_minute_saves_the_averages_of_the_last_minute(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, bus = await make_sampler(db_engine, docker, vm_root, tmp_path)
    for step in range(1, 4):  # 00:00:15, 00:00:30, 00:00:45
        clock.advance(15)
        set_counters(docker, clock, vm_root, step)
        await sampler.poll(docker)
    with Session(db_engine) as session:
        assert session.exec(select(ContainerSample)).all() == []

    clock.advance(15)  # 00:01:00
    set_counters(docker, clock, vm_root, 4)
    with bus.subscribe([Topic.METRICS]) as subscription:
        await sampler.poll(docker)
        kinds = [(await subscription.get()).data["kind"] for _ in range(2)]

    assert kinds == ["history", "current"]
    with Session(db_engine) as session:
        web = find_container(session, "web")
        assert web is not None
        rows = session.exec(select(ContainerSample)).all()
        assert len(rows) == 2
        row = session.get(
            ContainerSample, (web.id, MetricTier.MINUTE, clock.now().replace(minute=0))
        )
        assert row is not None
        # The average of the 3 polls of the minute. The first poll has no CPU and no rates.
        assert row.cpu_percent == pytest.approx(1.0)
        assert row.mem_used == 1200
        assert row.mem_limit == 10_000
        assert row.net_rx_bps == pytest.approx(666.666, rel=1e-3)
        vm = session.exec(select(VmSample)).one()
        assert vm.tier is MetricTier.MINUTE
        assert vm.cpu_percent == pytest.approx(25.0)
        assert vm.net_rx_bps == pytest.approx(2 * 666.666, rel=1e-3)
        assert vm.mem_used == 2000000 * 1024


async def test_a_minute_with_no_value_saves_null(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(30)
    set_counters(docker, clock, vm_root, 1)
    await sampler.poll(docker)

    clock.advance(30)
    set_counters(docker, clock, vm_root, 2)
    await sampler.poll(docker)

    with Session(db_engine) as session:
        rows = session.exec(select(ContainerSample)).all()
        assert [row.cpu_percent for row in rows] == [None, None]
        assert [row.mem_used for row in rows] == [1100, 1100]


async def test_a_stopped_container_is_not_polled(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, inventory, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(10)
    set_counters(docker, clock, vm_root, 1)
    await sampler.poll(docker)

    await inventory.update(make_info("db", project="site", state="exited"))
    del docker.stats_values["db"]
    clock.advance(10)
    set_counters(docker, clock, vm_root, 2)
    await sampler.poll(docker)

    assert set(sampler.containers) == {"web"}


async def test_a_container_removed_after_the_list_is_skipped(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(10)
    set_counters(docker, clock, vm_root, 1)
    docker.remove("id-db")

    assert await sampler.poll(docker)

    assert set(sampler.containers) == {"web"}


async def test_when_docker_is_down_the_poll_keeps_the_vm_values(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(10)
    set_counters(docker, clock, vm_root, 1)
    docker.fail = True

    assert not await sampler.poll(docker)

    assert sampler.containers == {}
    assert sampler.vm is not None
    assert sampler.vm_network() == (None, None)


async def test_when_the_vm_files_cannot_be_read_the_containers_still_work(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sampler, _, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    (vm_root / "proc" / "meminfo").unlink()
    for _ in range(2):
        clock.advance(10)
        set_counters(docker, clock, vm_root, 1)
        await sampler.poll(docker)
    clock.advance(60)
    await sampler.poll(docker)

    assert sampler.vm is None
    assert set(sampler.containers) == {"web", "db"}
    # One warning, not one per poll.
    assert [r.message for r in caplog.records].count(
        f"Cannot read the VM values: Cannot read {vm_root / 'proc' / 'meminfo'}: No such file or directory"
    ) == 1
    with Session(db_engine) as session:
        assert session.exec(select(VmSample)).all() == []
        assert len(session.exec(select(ContainerSample)).all()) == 2


async def test_a_container_with_no_row_is_not_saved(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(30)
    set_counters(docker, clock, vm_root, 1)
    await sampler.poll(docker)
    with Session(db_engine) as session:
        row = find_container(session, "db")
        session.delete(row)
        session.commit()

    clock.advance(30)
    await sampler.poll(docker)

    with Session(db_engine) as session:
        assert len(session.exec(select(ContainerSample)).all()) == 1


async def test_the_save_at_a_quarter_boundary_also_saves_the_quarter(
    db_engine: Engine,
    docker: FakeDocker,
    vm_root: Path,
    tmp_path: Path,
    clock: FakeClock,
) -> None:
    sampler, _, _ = await make_sampler(db_engine, docker, vm_root, tmp_path)
    clock.advance(14 * 60 + 30)  # 00:14:30
    set_counters(docker, clock, vm_root, 1)
    await sampler.poll(docker)

    clock.advance(30)  # 00:15:00
    await sampler.poll(docker)

    with Session(db_engine) as session:
        tiers = [
            row.tier for row in session.exec(select(VmSample).order_by(VmSample.tier))
        ]
    assert sorted(tiers) == sorted([MetricTier.MINUTE, MetricTier.QUARTER])
