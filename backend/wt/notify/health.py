"""Health notifications: one message for each health state change, at once."""

import logging

from pydantic import SecretStr

from wt.config import Settings
from wt.db.models import EventKind
from wt.notify.messages import health_message
from wt.notify.ntfy import send

log = logging.getLogger(__name__)


async def notify_health(
    name: str, kind: EventKind, settings: Settings, token: SecretStr | None
) -> None:
    """Send the message. Log a fail. With no ntfy settings, do nothing."""
    if not settings.ntfy_url or not settings.ntfy_topic:
        return
    if not await send(health_message(name, kind, settings.public_url), settings, token):
        log.warning("The health message for %s is not sent (%s)", name, kind.value)
