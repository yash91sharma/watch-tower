"""Tests for wt.versions.dockerhub (respx, clock)."""

from collections.abc import AsyncIterator
from datetime import timedelta
from importlib.metadata import version

import httpx
import pytest
import respx

from wt.clock import FakeClock
from wt.versions.dockerhub import DockerHub, DockerHubError
from wt.versions.fetch import RateLimitedError

pytestmark = pytest.mark.anyio

API = "http://hub.test"
TAGS = f"{API}/v2/namespaces/searxng/repositories/searxng/tags"


@pytest.fixture
async def hub() -> AsyncIterator[DockerHub]:
    client = DockerHub(API)
    yield client
    await client.close()


async def test_tags_gives_the_names_newest_first(hub: DockerHub) -> None:
    body = {"results": [{"name": "latest"}, {"name": "2026.11.26-b5605b8f2"}]}
    with respx.mock:
        route = respx.get(TAGS).mock(return_value=httpx.Response(200, json=body))

        tags = await hub.tags("searxng/searxng")

    assert tags == ["latest", "2026.11.26-b5605b8f2"]
    request = route.calls.last.request
    assert request.url.params["page_size"] == "100"
    assert request.url.params["ordering"] == "last_updated"
    assert request.headers["User-Agent"] == f"watch-tower/{version('wt')}"


async def test_404_is_an_error(hub: DockerHub) -> None:
    with respx.mock:
        respx.get(TAGS).mock(return_value=httpx.Response(404))

        with pytest.raises(DockerHubError, match="The image is not on Docker Hub"):
            await hub.tags("searxng/searxng")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, json={"results": "x"}),
        httpx.Response(200, text="not json"),
    ],
)
async def test_bad_answers_are_errors(hub: DockerHub, response: httpx.Response) -> None:
    with respx.mock:
        respx.get(TAGS).mock(return_value=response)

        with pytest.raises(DockerHubError):
            await hub.tags("searxng/searxng")


async def test_a_network_error_is_an_error(hub: DockerHub) -> None:
    with respx.mock:
        respx.get(TAGS).mock(side_effect=httpx.ConnectError("down"))

        with pytest.raises(DockerHubError, match="ConnectError"):
            await hub.tags("searxng/searxng")


async def test_429_with_retry_after(hub: DockerHub, clock: FakeClock) -> None:
    with respx.mock:
        respx.get(TAGS).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "30"})
        )

        with pytest.raises(RateLimitedError) as error:
            await hub.tags("searxng/searxng")

    assert error.value.reset_at == clock.now() + timedelta(seconds=30)
    assert str(error.value).startswith("Docker Hub rate limit until")


async def test_429_with_a_reset_time(hub: DockerHub, clock: FakeClock) -> None:
    reset = int(clock.now().timestamp()) + 600
    with respx.mock:
        respx.get(TAGS).mock(
            return_value=httpx.Response(429, headers={"X-RateLimit-Reset": str(reset)})
        )

        with pytest.raises(RateLimitedError) as error:
            await hub.tags("searxng/searxng")

    assert error.value.reset_at == clock.now() + timedelta(seconds=600)


async def test_429_with_no_headers_waits_one_minute(
    hub: DockerHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(TAGS).mock(return_value=httpx.Response(429))

        with pytest.raises(RateLimitedError) as error:
            await hub.tags("searxng/searxng")

    assert error.value.reset_at == clock.now() + timedelta(minutes=1)
