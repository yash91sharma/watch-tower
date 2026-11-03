"""The shared objects of the app. The lifespan (wt.main) makes them."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine

from wt.auth.limit import LoginLimit
from wt.auth.setup_token import SetupToken
from wt.bus import Bus
from wt.config import Env
from wt.docker.connection import DockerState
from wt.docker.inventory import Inventory


@dataclass(frozen=True)
class AppContext:
    """Workers get it as an argument. Routes get it with the dependency in wt.api.deps."""

    env: Env
    engine: Engine
    bus: Bus
    setup_token: SetupToken
    inventory: Inventory
    docker_state: DockerState = field(default_factory=DockerState)
    login_limit: LoginLimit = field(default_factory=LoginLimit)


# A worker runs until WT stops it (task cancel).
Worker = Callable[[AppContext], Coroutine[Any, Any, None]]
