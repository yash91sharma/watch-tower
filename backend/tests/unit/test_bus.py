"""Tests for wt.bus."""

import asyncio

import pytest

from wt.bus import Bus, Message, Topic


@pytest.mark.anyio
async def test_two_subscribers_get_an_event() -> None:
    bus = Bus()
    first = bus.subscribe()
    second = bus.subscribe()

    bus.publish(Topic.CONTAINER, {"name": "app"})

    expected = Message(Topic.CONTAINER, {"name": "app"})
    assert await first.get() == expected
    assert await second.get() == expected


@pytest.mark.anyio
async def test_subscriber_gets_only_its_topics() -> None:
    bus = Bus()
    settings_only = bus.subscribe([Topic.SETTINGS])

    bus.publish(Topic.CONTAINER, {"name": "app"})
    bus.publish(Topic.SETTINGS)

    assert await settings_only.get() == Message(Topic.SETTINGS, {})
    assert settings_only.empty()


@pytest.mark.anyio
async def test_close_removes_the_subscriber() -> None:
    bus = Bus()
    subscription = bus.subscribe()

    subscription.close()
    bus.publish(Topic.DOCKER, {"connected": True})

    assert bus.subscriber_count == 0
    assert subscription.empty()


@pytest.mark.anyio
async def test_context_manager_closes_the_subscriber() -> None:
    bus = Bus()

    with bus.subscribe():
        assert bus.subscriber_count == 1

    assert bus.subscriber_count == 0


@pytest.mark.anyio
async def test_slow_subscriber_does_not_block_and_loses_oldest() -> None:
    bus = Bus(max_queue=3)
    slow = bus.subscribe()
    fast = bus.subscribe()

    for number in range(5):
        bus.publish(Topic.CHECK, {"n": number})
        assert (await fast.get()).data == {"n": number}

    received = [(await slow.get()).data["n"] for _ in range(3)]
    assert received == [2, 3, 4]
    assert slow.empty()


@pytest.mark.anyio
async def test_publish_from_another_thread() -> None:
    bus = Bus()
    subscription = bus.subscribe()

    await asyncio.to_thread(bus.publish, Topic.SETTINGS)

    assert await asyncio.wait_for(subscription.get(), timeout=1) == Message(
        Topic.SETTINGS, {}
    )
