"""Health rules (pure). The time always comes from the caller."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class RestartWindow:
    """Restarts of one container: `start` events that follow a `die`.

    N or more restarts in M minutes is a restart loop. The loop ends when no restart
    comes in M minutes.
    """

    restart_times: list[datetime] = field(default_factory=list[datetime])
    _died: bool = False

    def die(self, time: datetime) -> None:
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
