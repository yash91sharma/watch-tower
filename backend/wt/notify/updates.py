"""Update notifications after each check run.

WT sends the current updates (9.9) that have no `notified_at`: one message for one update,
one digest for more. On success it sets `notified_at`, so that it sends each version once.
On a fail it keeps the rows for the next run.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from wt import clock
from wt.config import Env, load_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, Update
from wt.notify.messages import UpdateInfo, digest_message, update_message
from wt.notify.ntfy import send
from wt.versions.updates import current_update


@dataclass(frozen=True)
class _Pending:
    update_id: int
    info: UpdateInfo


async def notify_updates(engine: Engine, env: Env) -> None:
    pending = await asyncio.to_thread(_pending, engine)
    if not pending:
        return
    settings = await asyncio.to_thread(load_settings, engine)
    infos = [item.info for item in pending]
    if len(infos) == 1:
        message = update_message(infos[0], settings.public_url)
    else:
        message = digest_message(infos, settings.public_url)
    if await send(message, settings, env.ntfy_token):
        await asyncio.to_thread(
            _mark_notified, engine, [item.update_id for item in pending]
        )


def _pending(engine: Engine) -> list[_Pending]:
    pending: list[_Pending] = []
    with Session(engine) as session:
        containers = session.exec(
            select(Container)
            .where(Container.host_id == LOCAL_HOST_ID, col(Container.enabled))
            .order_by(col(Container.name))
        )
        for container in containers:
            update = current_update(session, container)
            if update is None or update.notified_at is not None or update.id is None:
                continue
            info = UpdateInfo(
                container.name,
                update.from_version,
                update.to_version,
                update.severity,
                update.summary,
            )
            pending.append(_Pending(update.id, info))
    return pending


def _mark_notified(engine: Engine, update_ids: list[int]) -> None:
    now = clock.now()
    with Session(engine) as session:
        for update in session.exec(
            select(Update).where(col(Update.id).in_(update_ids))
        ):
            update.notified_at = now
            session.add(update)
        session.commit()
