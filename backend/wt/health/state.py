"""Health state machine (pure).

Per container name: the flags `unhealthy` and `restart_loop`. Each Docker event can
change a flag. Each flag change gives one state change (an `EventKind`), which WT saves
and sends as one notification. The state is kept by name, so that it stays after a
recreate.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from wt.db.models import EventKind
from wt.docker.client import DockerEvent
from wt.health.rules import RestartWindow


@dataclass
class _Container:
    docker_id: str
    unhealthy: bool = False
    restart_loop: bool = False
    window: RestartWindow = field(default_factory=RestartWindow)


class HealthState:
    def __init__(self) -> None:
        self._containers: dict[str, _Container] = {}

    def handle(
        self, event: DockerEvent, count: int, window: timedelta
    ) -> list[EventKind]:
        """Apply one event. Give the state changes (zero or one).

        `count` and `window` are N and M of the restart loop rule.
        """
        if event.action == "destroy":
            current = self._containers.get(event.name)
            if current is not None and current.docker_id == event.container_id:
                del self._containers[event.name]
            return []
        container = self._containers.setdefault(
            event.name, _Container(event.container_id)
        )
        container.docker_id = event.container_id
        if event.action == "health_status":
            return self._health(container, event.health == "unhealthy")
        if event.action == "die":
            container.window.die(event.time)
        elif event.action == "start":
            container.window.start(event.time)
            if not container.restart_loop and container.window.in_loop(
                event.time, count, window
            ):
                container.restart_loop = True
                return [EventKind.RESTART_LOOP]
        return []

    def tick(self, now: datetime, window: timedelta) -> list[tuple[str, EventKind]]:
        """Find the restart loops that ended: no restart in the last `window`."""
        changes: list[tuple[str, EventKind]] = []
        for name, container in self._containers.items():
            if container.restart_loop and container.window.quiet(now, window):
                container.restart_loop = False
                changes.append((name, EventKind.RECOVERED_LOOP))
        return changes

    def _health(self, container: _Container, unhealthy: bool) -> list[EventKind]:
        if unhealthy == container.unhealthy:
            return []
        container.unhealthy = unhealthy
        return [EventKind.BECAME_UNHEALTHY if unhealthy else EventKind.RECOVERED_HEALTH]
