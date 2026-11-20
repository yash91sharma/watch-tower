"""Cleanup worker: each hour, delete expired sessions, old health events and old metric rows."""

import asyncio

from sqlalchemy import Engine
from sqlmodel import Session, col, delete

from wt import clock
from wt.db.models import (
    EVENT_MAX_AGE,
    METRIC_MAX_AGE,
    AuthSession,
    ContainerSample,
    Event,
    VmSample,
)

INTERVAL_SECONDS = 3600


def delete_old_rows(engine: Engine) -> None:
    """Delete expired sessions, events older than 7 days, and the metric rows that are
    older than the retention of their tier.
    """
    now = clock.now()
    with Session(engine) as session:
        session.exec(delete(AuthSession).where(col(AuthSession.expires) <= now))
        session.exec(delete(Event).where(col(Event.time) < now - EVENT_MAX_AGE))
        for tier, max_age in METRIC_MAX_AGE.items():
            for table in (ContainerSample, VmSample):
                session.exec(
                    delete(table).where(
                        col(table.tier) == tier, col(table.time) < now - max_age
                    )
                )
        session.commit()


async def run(engine: Engine) -> None:
    """Clean up at start, then each hour."""
    while True:
        await asyncio.to_thread(delete_old_rows, engine)
        await clock.sleep(INTERVAL_SECONDS)
