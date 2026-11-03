"""The only source of the current time.

All code gets the time from `now()` and waits with `sleep()`. Ruff (TID251) bans the
stdlib time calls in all other modules. Tests replace the clock with a `FakeClock`
(pytest fixture `clock`), so that they can set and move the time.
"""

import asyncio
from datetime import UTC, datetime, timedelta


class Clock:
    """The real clock."""

    def now(self) -> datetime:
        """Give the current time in UTC (timezone-aware)."""
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        """Wait for `seconds`."""
        await asyncio.sleep(seconds)


class FakeClock(Clock):
    """A clock for tests. The time moves only when a test or `sleep` moves it."""

    def __init__(self, start: datetime) -> None:
        self._now: datetime
        self.set(start)

    def now(self) -> datetime:
        return self._now

    def set(self, when: datetime) -> None:
        """Set the time. `when` must be timezone-aware."""
        if when.tzinfo is None:
            raise ValueError("The time must have a timezone")
        self._now = when.astimezone(UTC)

    def advance(self, seconds: float) -> None:
        """Move the time forward by `seconds`."""
        self._now += timedelta(seconds=seconds)

    async def sleep(self, seconds: float) -> None:
        """Move the time forward by `seconds`, with no real wait. Let other tasks run."""
        self.advance(seconds)
        await asyncio.sleep(0)


_clock: Clock = Clock()


def use(new_clock: Clock) -> None:
    """Replace the clock. Only tests call this."""
    global _clock
    _clock = new_clock


def now() -> datetime:
    """Give the current time in UTC (timezone-aware)."""
    return _clock.now()


async def sleep(seconds: float) -> None:
    """Wait for `seconds`. In tests, move the fake time with no real wait."""
    await _clock.sleep(seconds)
