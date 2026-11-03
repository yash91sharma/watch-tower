"""Tests for wt.clock and the `clock` fixture."""

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wt import clock
from wt.clock import FakeClock

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_real_now_is_utc_and_aware() -> None:
    value = clock.now()

    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


@pytest.mark.anyio
async def test_real_sleep_returns() -> None:
    await clock.sleep(0)


def test_fixture_sets_the_time(clock: FakeClock) -> None:
    assert clock.now() == START

    clock.set(datetime(2030, 5, 6, 7, 8, tzinfo=UTC))

    assert clock.now() == datetime(2030, 5, 6, 7, 8, tzinfo=UTC)


def test_fixture_moves_the_time(clock: FakeClock) -> None:
    clock.advance(90)

    assert clock.now() == START + timedelta(seconds=90)


@pytest.mark.anyio
async def test_fake_sleep_moves_the_time_with_no_wait(clock: FakeClock) -> None:
    await clock.sleep(3600)

    assert clock.now() == START + timedelta(hours=1)


def test_set_rejects_a_naive_time(clock: FakeClock) -> None:
    with pytest.raises(ValueError, match="timezone"):
        clock.set(datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "code",
    [
        "from datetime import datetime\nx = datetime.now()\n",
        "import datetime\nx = datetime.datetime.utcnow()\n",
        "import time\nx = time.time()\n",
        "import asyncio\n\n\nasync def f() -> None:\n    await asyncio.sleep(1)\n",
    ],
)
def test_ruff_bans_time_calls_outside_clock(code: str) -> None:
    ruff = Path(sys.executable).with_name("ruff")

    result = subprocess.run(
        [ruff, "check", "--stdin-filename", "wt/other.py", "-"],
        input=code,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "TID251" in result.stdout
