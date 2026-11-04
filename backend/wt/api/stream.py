"""GET /api/stream: one SSE stream with live updates for the UI.

On connect it sends the current Docker connection state first. Then it sends the bus
messages for `container`, `check` and `docker`. After 15 s with no message it sends a
keep-alive comment. After a reconnect, the UI gets all data again.
"""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from wt import clock
from wt.api.deps import Ctx
from wt.bus import Message, Subscription, Topic

router = APIRouter(tags=["stream"])

KEEP_ALIVE_SECONDS = 15
TOPICS = (Topic.CONTAINER, Topic.CHECK, Topic.DOCKER)


def sse(message: Message) -> str:
    return f"event: {message.topic.value}\ndata: {json.dumps(dict(message.data))}\n\n"


def sse_response(events: AsyncGenerator[str]) -> StreamingResponse:
    """An SSE response. No cache, and no buffer in a reverse proxy."""
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/stream", response_class=StreamingResponse)
async def stream(ctx: Ctx) -> StreamingResponse:
    subscription = ctx.bus.subscribe(TOPICS)
    first = Message(Topic.DOCKER, {"connected": ctx.docker_state.connected})
    return sse_response(_events(subscription, first))


async def _events(subscription: Subscription, first: Message) -> AsyncGenerator[str]:
    """Run until the client goes (Starlette cancels it). Then close the subscription."""
    with subscription:
        yield sse(first)
        next_message = asyncio.ensure_future(subscription.get())
        try:
            while True:
                keep_alive = asyncio.ensure_future(clock.sleep(KEEP_ALIVE_SECONDS))
                done, _ = await asyncio.wait(
                    {next_message, keep_alive}, return_when=asyncio.FIRST_COMPLETED
                )
                keep_alive.cancel()
                if next_message in done:
                    yield sse(next_message.result())
                    next_message = asyncio.ensure_future(subscription.get())
                else:
                    yield ": keep-alive\n\n"
        finally:
            next_message.cancel()
