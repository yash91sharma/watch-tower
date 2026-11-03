"""Login limit: after 5 failures, block setup and login for 15 minutes.

WT has one admin, so the count is for all clients together. The count is in memory:
a restart of WT clears it.
"""

import math
from datetime import datetime, timedelta

from wt import clock

MAX_FAILURES = 5
BLOCK_TIME = timedelta(minutes=15)


class LoginLimit:
    def __init__(self) -> None:
        self._failures = 0
        self._blocked_until: datetime | None = None

    def retry_after(self) -> int | None:
        """Seconds until the block ends (rounded up), or None if not blocked."""
        if self._blocked_until is None:
            return None
        left = (self._blocked_until - clock.now()).total_seconds()
        if left <= 0:
            self.success()
            return None
        return math.ceil(left)

    def failure(self) -> None:
        """Count a failed attempt. The fifth one starts the block."""
        self._failures += 1
        if self._failures >= MAX_FAILURES:
            self._blocked_until = clock.now() + BLOCK_TIME

    def success(self) -> None:
        """Clear the count and the block."""
        self._failures = 0
        self._blocked_until = None
