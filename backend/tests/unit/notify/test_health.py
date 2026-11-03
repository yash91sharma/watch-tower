"""Tests for health notifications (respx)."""

import httpx
import pytest
import respx

from wt.config import Settings
from wt.db.models import EventKind
from wt.notify.health import notify_health

pytestmark = pytest.mark.anyio

NTFY = "https://ntfy.test"
SETTINGS = Settings(ntfy_url=NTFY, ntfy_topic="wt")


@pytest.mark.parametrize(
    ("kind", "title", "priority"),
    [
        (EventKind.BECAME_UNHEALTHY, "web is unhealthy", "high"),
        (EventKind.RESTART_LOOP, "web restarts in a loop", "default"),
        (EventKind.RECOVERED_HEALTH, "web is healthy again", "default"),
        (EventKind.RECOVERED_LOOP, "web does not restart now", "default"),
    ],
)
async def test_each_change_sends_one_message(
    kind: EventKind, title: str, priority: str
) -> None:
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await notify_health("web", kind, SETTINGS, token=None)

    assert route.call_count == 1
    headers = route.calls.last.request.headers
    assert (headers["Title"], headers["Priority"]) == (title, priority)


async def test_a_failed_send_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with respx.mock:
        respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(500))

        await notify_health("web", EventKind.BECAME_UNHEALTHY, SETTINGS, token=None)

    assert "The health message for web is not sent" in caplog.text


async def test_no_ntfy_sends_nothing_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    await notify_health("web", EventKind.BECAME_UNHEALTHY, Settings(), token=None)

    assert "not sent" not in caplog.text
