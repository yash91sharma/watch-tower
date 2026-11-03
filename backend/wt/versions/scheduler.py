"""Check scheduler: run a check when the last run + the interval is past.

With no last run, it runs at once. It sleeps in steps of at most 5 minutes and reads the
settings and the last run again after each step, so that a new interval takes effect
within 5 minutes (also if a bus message is lost). "Check now" calls the runner directly.
"""

import asyncio
from datetime import timedelta
from typing import Protocol

from sqlalchemy import Engine

from wt import clock
from wt.config import load_settings
from wt.versions.check import load_check_status

MAX_STEP_SECONDS = 300


class Runner(Protocol):
    async def run(self) -> bool: ...


async def run_scheduler(runner: Runner, engine: Engine) -> None:
    while True:
        settings = await asyncio.to_thread(load_settings, engine)
        status = await asyncio.to_thread(load_check_status, engine)
        now = clock.now()
        due = (
            now
            if status.last_run is None
            else (status.last_run + timedelta(hours=settings.check_interval_hours))
        )
        wait = (due - now).total_seconds()
        if wait <= 0:
            await runner.run()
        else:
            await clock.sleep(min(wait, MAX_STEP_SECONDS))
