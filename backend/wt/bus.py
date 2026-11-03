"""In-process event bus.

Each subscriber has its own asyncio queue. `publish` never blocks: if a queue is full,
the subscriber loses its oldest item. Make the bus in the event loop (the app lifespan).
`publish` also works from other threads (FastAPI runs sync routes in threads).
"""

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import TracebackType
from typing import Any, Self


class Topic(StrEnum):
    CONTAINER = "container"
    CHECK = "check"
    DOCKER = "docker"
    SETTINGS = "settings"


@dataclass(frozen=True)
class Message:
    topic: Topic
    data: Mapping[str, Any] = field(default_factory=dict[str, Any])


class Subscription:
    """A queue of the messages for some topics. Close it when you do not need it."""

    def __init__(self, bus: Bus, topics: frozenset[Topic], max_queue: int) -> None:
        self._bus = bus
        self.topics = topics
        self._queue: asyncio.Queue[Message] = asyncio.Queue(max_queue)

    async def get(self) -> Message:
        """Wait for the next message."""
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

    def close(self) -> None:
        """Stop the messages to this subscriber."""
        self._bus.remove(self)

    def put(self, message: Message) -> None:
        """Add a message. If the queue is full, drop the oldest message first."""
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(message)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class Bus:
    def __init__(self, max_queue: int = 100) -> None:
        self._loop = asyncio.get_running_loop()
        self._max_queue = max_queue
        self._subscriptions: set[Subscription] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    def subscribe(self, topics: Iterable[Topic] = tuple(Topic)) -> Subscription:
        """Get the messages for `topics` (default: all topics)."""
        subscription = Subscription(self, frozenset(topics), self._max_queue)
        self._subscriptions.add(subscription)
        return subscription

    def remove(self, subscription: Subscription) -> None:
        self._subscriptions.discard(subscription)

    def publish(self, topic: Topic, data: Mapping[str, Any] | None = None) -> None:
        """Send a message to all subscribers of `topic`. Never blocks."""
        message = Message(topic, data or {})
        if _in_loop(self._loop):
            self._deliver(message)
        else:
            self._loop.call_soon_threadsafe(self._deliver, message)

    def _deliver(self, message: Message) -> None:
        for subscription in list(self._subscriptions):
            if message.topic in subscription.topics:
                subscription.put(message)


def _in_loop(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False
