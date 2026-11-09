"""Cleanup worker: each hour, delete expired sessions and old health events."""

import asyncio

from sqlalchemy import Engine
from sqlmodel import Session, col, delete

from wt import clock
from wt.db.models import EVENT_MAX_AGE, AuthSession, Event

INTERVAL_SECONDS = 3600


def delete_old_rows(engine: Engine) -> None:
    """Delete expired sessions and events older than 7 days."""
    now = clock.now()
    with Session(engine) as session:
        session.exec(delete(AuthSession).where(col(AuthSession.expires) <= now))
        session.exec(delete(Event).where(col(Event.time) < now - EVENT_MAX_AGE))
        session.commit()


async def run(engine: Engine) -> None:
    """Clean up at start, then each hour."""
    while True:
        await asyncio.to_thread(delete_old_rows, engine)
        await clock.sleep(INTERVAL_SECONDS)
