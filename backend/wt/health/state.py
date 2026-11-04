"""Health state machine (pure). The time always comes from the caller.

Per container name: the flags `unhealthy` and `restart_loop`. Each Docker event can
change a flag. Each flag change gives one state change (an `EventKind`), which WT saves
and sends as one notification. The state is kept by name, so that it stays after a
recreate.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from wt.db.models import EventKind
from wt.docker.client import ContainerInfo, DockerEvent


@dataclass
class RestartWindow:
    """Restarts of one container: `start` events that follow a `die`.

    N or more restarts in M minutes is a restart loop. The loop ends when no restart
    comes in M minutes.
    """

    restart_times: list[datetime] = field(default_factory=list[datetime])
    _died: bool = False

    def die(self) -> None:
        self._died = True

    def start(self, time: datetime) -> None:
        if self._died:
            self.restart_times.append(time)
            self._died = False

    def in_loop(self, now: datetime, count: int, window: timedelta) -> bool:
        """True if `count` or more restarts came in the last `window`."""
        self._drop_old(now, window)
        return len(self.restart_times) >= count

    def quiet(self, now: datetime, window: timedelta) -> bool:
        """True if no restart came in the last `window`."""
        self._drop_old(now, window)
        return not self.restart_times

    def _drop_old(self, now: datetime, window: timedelta) -> None:
        self.restart_times = [
            time for time in self.restart_times if now - time < window
        ]


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
            container.window.die()
        elif event.action == "start":
            container.window.start(event.time)
            if not container.restart_loop and container.window.in_loop(
                event.time, count, window
            ):
                container.restart_loop = True
                return [EventKind.RESTART_LOOP]
        return []

    def baseline(self, infos: list[ContainerInfo]) -> None:
        """Set the state from inspect, with no change (at start and after a resync).

        The health comes from Docker. A restart loop stays, so that its end gives a change.
        Containers that are not in `infos` are removed.
        """
        containers: dict[str, _Container] = {}
        for info in infos:
            container = self._containers.get(info.name) or _Container(info.id)
            container.docker_id = info.id
            container.unhealthy = info.health == "unhealthy"
            containers[info.name] = container
        self._containers = containers

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
