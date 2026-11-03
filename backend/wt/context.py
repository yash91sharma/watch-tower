"""The shared objects of the app. The lifespan (wt.main) makes them."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine

from wt.bus import Bus
from wt.config import Env


@dataclass(frozen=True)
class AppContext:
    """Workers get it as an argument. Routes get it with the dependency in wt.api.deps."""

    env: Env
    engine: Engine
    bus: Bus


# A worker runs until WT stops it (task cancel).
Worker = Callable[[AppContext], Coroutine[Any, Any, None]]
