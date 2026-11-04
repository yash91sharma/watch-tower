"""Health monitor: applies Docker events to the health state and saves each change.

The Docker workers call it directly (not through the bus, which can drop items):
`on_sync` after each connect, `on_event` for each event. The health worker calls `tick`
each 30 s to find the restart loops that ended, and reloads N and M on `settings`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, select

from wt import clock
from wt.bus import Bus, Topic
from wt.config import Settings, load_settings
from wt.db import LOCAL_HOST_ID
from wt.db.models import Container, Event, EventKind
from wt.docker.client import ContainerInfo, DockerEvent
from wt.docker.parse import is_excluded
from wt.health.state import HealthState

log = logging.getLogger(__name__)

TICK_SECONDS = 30

# (container name, change, current settings)
OnChange = Callable[[str, EventKind, Settings], Awaitable[None]]


class HealthMonitor:
    def __init__(
        self, engine: Engine, settings: Settings, on_change: OnChange | None = None
    ) -> None:
        self._engine = engine
        self._state = HealthState()
        self._excluded: set[str] = set()
        self.settings = settings
        # Called for each change, after it is saved (the health notification, 10.5).
        self._on_change = on_change

    @property
    def _window(self) -> timedelta:
        return timedelta(minutes=self.settings.restart_window_minutes)

    def on_sync(self, infos: list[ContainerInfo]) -> None:
        """Set the baseline after a connect. No change."""
        self._excluded = {info.name for info in infos if is_excluded(info.labels)}
        self._state.baseline(
            [info for info in infos if info.name not in self._excluded]
        )

    async def on_event(self, event: DockerEvent) -> None:
        if event.name in self._excluded:
            return
        changes = self._state.handle(event, self.settings.restart_count, self._window)
        for kind in changes:
            await self._record(event.name, kind, event.time)

    async def tick(self) -> None:
        now = clock.now()
        for name, kind in self._state.tick(now, self._window):
            await self._record(name, kind, now)

    async def _record(self, name: str, kind: EventKind, time: datetime) -> None:
        log.info("Container %s: %s", name, kind.value)
        await asyncio.to_thread(_save_event, self._engine, name, kind, time)
        if self._on_change is not None:
            await self._on_change(name, kind, self.settings)


def _save_event(engine: Engine, name: str, kind: EventKind, time: datetime) -> None:
    with Session(engine) as session:
        container = session.exec(
            select(Container).where(
                Container.host_id == LOCAL_HOST_ID, Container.name == name
            )
        ).first()
        if container is None or container.id is None:
            log.warning(
                "No container row for %s. The %s event is not saved.", name, kind.value
            )
            return
        session.add(Event(container_id=container.id, kind=kind, time=time))
        session.commit()


async def run_health(monitor: HealthMonitor, engine: Engine, bus: Bus) -> None:
    """Tick each 30 s. Reload N and M when the settings change."""

    async def tick_loop() -> None:
        while True:
            await clock.sleep(TICK_SECONDS)
            await monitor.tick()

    async def settings_loop() -> None:
        while True:
            await subscription.get()
            monitor.settings = await asyncio.to_thread(load_settings, engine)

    with bus.subscribe([Topic.SETTINGS]) as subscription:
        await asyncio.gather(tick_loop(), settings_loop())
