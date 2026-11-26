"""Shared parts of the release source clients (GitHub, Docker Hub): errors and rate limits."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from importlib.metadata import version

from wt import clock

TIMEOUT_SECONDS = 30
# A run waits for the rate limit this many times, then fails.
MAX_RATE_LIMIT_WAITS = 3
# The version of the installed WT package (pyproject.toml).
USER_AGENT = f"watch-tower/{version('wt')}"

log = logging.getLogger(__name__)


class FetchError(Exception):
    """The fetch failed. WT saves the text in repo_cache.error."""


class RateLimitedError(FetchError):
    """Rate limit: wait until `reset_at`, then try again."""

    def __init__(self, service: str, reset_at: datetime) -> None:
        super().__init__(f"{service} rate limit until {reset_at.isoformat()}")
        self.service = service
        self.reset_at = reset_at


async def wait_on_rate_limit[T](call: Callable[[], Awaitable[T]]) -> T:
    """Run `call`. On a rate limit, wait until the reset (through clock) and run it again."""
    service = "The source"
    for _ in range(MAX_RATE_LIMIT_WAITS):
        try:
            return await call()
        except RateLimitedError as error:
            service = error.service
            seconds = max((error.reset_at - clock.now()).total_seconds(), 0) + 1
            log.warning("%s rate limit. WT waits %d s.", service, seconds)
            await clock.sleep(seconds)
    raise FetchError(
        f"{service} rate limit: WT stopped after {MAX_RATE_LIMIT_WAITS} waits"
    )
