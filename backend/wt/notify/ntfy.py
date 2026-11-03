"""ntfy sender: POST {ntfy_url}/{topic} with the message headers."""

import logging

import httpx
from pydantic import SecretStr

from wt.config import Settings
from wt.notify.messages import Message

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10


async def send(message: Message, settings: Settings, token: SecretStr | None) -> bool:
    """Send the message. True if ntfy accepted it. False on an error or if ntfy is not set."""
    if not settings.ntfy_url or not settings.ntfy_topic:
        return False
    headers = {
        "Title": message.title,
        "Priority": message.priority,
        "Tags": ",".join(message.tags),
    }
    if message.click:
        headers["Click"] = message.click
    if token is not None:
        headers["Authorization"] = f"Bearer {token.get_secret_value()}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{settings.ntfy_url}/{settings.ntfy_topic}",
                content=message.body.encode(),
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        log.warning("Cannot send the ntfy message: %s", type(error).__name__)
        return False
    return True
