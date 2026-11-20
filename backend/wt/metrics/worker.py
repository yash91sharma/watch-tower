"""The metrics worker loop: poll, wait the interval of the settings, poll again.

The loop keeps one Docker client. When a poll cannot reach Docker, it closes the client
and makes a new one for the next poll. A settings change sets the new interval.
"""

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy import Engine

from wt import clock
from wt.bus import Bus, Topic
from wt.config import load_settings
from wt.docker.client import DockerApi

# One poll. False: Docker was not available (see Sampler.poll).
Poll = Callable[[DockerApi], Awaitable[bool]]


async def run_metrics(
    poll: Poll, make_client: Callable[[], DockerApi], engine: Engine, bus: Bus
) -> None:
    """Run until WT stops it (task cancel)."""
    interval = (await asyncio.to_thread(load_settings, engine)).metrics_interval_seconds

    async def settings_loop() -> None:
        nonlocal interval
        while True:
            await subscription.get()
            settings = await asyncio.to_thread(load_settings, engine)
            interval = settings.metrics_interval_seconds

    async def poll_loop() -> None:
        client = make_client()
        try:
            while True:
                if not await poll(client):
                    await client.close()
                    client = make_client()
                await clock.sleep(interval)
        finally:
            await client.close()

    with bus.subscribe([Topic.SETTINGS]) as subscription:
        await asyncio.gather(settings_loop(), poll_loop())
