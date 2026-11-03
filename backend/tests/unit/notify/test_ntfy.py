"""Tests for wt.notify.ntfy (respx)."""

import httpx
import pytest
import respx
from pydantic import SecretStr

from wt.config import Settings
from wt.notify.messages import Message
from wt.notify.ntfy import send

pytestmark = pytest.mark.anyio

NTFY = "https://ntfy.test"
SETTINGS = Settings(ntfy_url=NTFY, ntfy_topic="wt")
MESSAGE = Message(
    title="Update: web 1.0 -> 1.2",
    body="The update adds dark mode. ✓",
    tags=("warning", "package"),
    click="https://wt.example.com/containers/web",
    priority="high",
)


async def test_headers_and_body(caplog: pytest.LogCaptureFixture) -> None:
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        assert await send(MESSAGE, SETTINGS, token=None) is True

    request = route.calls.last.request
    assert request.headers["Title"] == "Update: web 1.0 -> 1.2"
    assert request.headers["Priority"] == "high"
    assert request.headers["Tags"] == "warning,package"
    assert request.headers["Click"] == "https://wt.example.com/containers/web"
    assert "Authorization" not in request.headers
    assert request.content.decode() == "The update adds dark mode. ✓"


async def test_no_click_header_with_no_link() -> None:
    message = Message("t", "b", ("package",), None)
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await send(message, SETTINGS, token=None)

    assert "Click" not in route.calls.last.request.headers
    assert route.calls.last.request.headers["Priority"] == "default"


async def test_token_is_sent_as_bearer(caplog: pytest.LogCaptureFixture) -> None:
    with respx.mock:
        route = respx.post(f"{NTFY}/wt").mock(return_value=httpx.Response(200))

        await send(MESSAGE, SETTINGS, token=SecretStr("s3cret"))

    assert route.calls.last.request.headers["Authorization"] == "Bearer s3cret"
    assert "s3cret" not in caplog.text


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(403),
        httpx.ConnectError("down"),
        httpx.ReadTimeout("slow"),
    ],
    ids=["500", "403", "connect", "timeout"],
)
async def test_errors_give_fail(
    response: httpx.Response | Exception, caplog: pytest.LogCaptureFixture
) -> None:
    with respx.mock:
        route = respx.post(f"{NTFY}/wt")
        if isinstance(response, Exception):
            route.mock(side_effect=response)
        else:
            route.mock(return_value=response)

        assert await send(MESSAGE, SETTINGS, token=None) is False

    assert "ntfy" in caplog.text


@pytest.mark.parametrize(
    "settings",
    [Settings(), Settings(ntfy_url=NTFY), Settings(ntfy_topic="wt")],
    ids=["nothing", "no-topic", "no-url"],
)
async def test_not_set_sends_nothing(settings: Settings) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(url__regex=r".*")

        assert await send(MESSAGE, settings, token=None) is False

    assert not route.called
