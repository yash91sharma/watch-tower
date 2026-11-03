"""Tests for the GitHub rate limit (respx, clock)."""

from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import respx

from wt.clock import FakeClock
from wt.versions.github import (
    Fetched,
    GitHub,
    GitHubError,
    RateLimitedError,
    wait_on_rate_limit,
)

pytestmark = pytest.mark.anyio

API = "http://github.test"
LATEST = f"{API}/repos/owner/app/releases/latest"
OK = httpx.Response(200, json={"tag_name": "v1.0"})


@pytest.fixture
async def github() -> AsyncIterator[GitHub]:
    client = GitHub(API, token=None)
    yield client
    await client.close()


def limited(clock: FakeClock, status: int = 403, seconds: int = 600) -> httpx.Response:
    reset = int(clock.now().timestamp()) + seconds
    return httpx.Response(
        status, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)}
    )


@pytest.mark.parametrize("status", [403, 429])
async def test_limit_headers_raise_rate_limited(
    github: GitHub, clock: FakeClock, status: int
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(return_value=limited(clock, status))

        with pytest.raises(RateLimitedError) as error:
            await github.latest("owner/app", etag=None)

    assert error.value.reset_at == clock.now() + timedelta(seconds=600)


async def test_retry_after_raises_rate_limited(
    github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "30"})
        )

        with pytest.raises(RateLimitedError) as error:
            await github.latest("owner/app", etag=None)

    assert error.value.reset_at == clock.now() + timedelta(seconds=30)


async def test_403_with_requests_left_is_a_github_error(
    github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            return_value=httpx.Response(403, headers={"x-ratelimit-remaining": "10"})
        )

        with pytest.raises(GitHubError) as error:
            await github.latest("owner/app", etag=None)

    assert not isinstance(error.value, RateLimitedError)


async def test_run_waits_until_the_reset_then_finishes(
    github: GitHub, clock: FakeClock
) -> None:
    start = clock.now()
    with respx.mock:
        respx.get(LATEST).mock(side_effect=[limited(clock), OK])

        result = await wait_on_rate_limit(lambda: github.latest("owner/app", etag=None))

    assert isinstance(result, Fetched)
    assert clock.now() - start == timedelta(seconds=601)


async def test_a_reset_in_the_past_waits_one_second(
    github: GitHub, clock: FakeClock
) -> None:
    start = clock.now()
    with respx.mock:
        respx.get(LATEST).mock(side_effect=[limited(clock, seconds=-100), OK])

        await wait_on_rate_limit(lambda: github.latest("owner/app", etag=None))

    assert clock.now() - start == timedelta(seconds=1)


async def test_gives_up_after_3_waits(github: GitHub, clock: FakeClock) -> None:
    with respx.mock:
        respx.get(LATEST).mock(return_value=limited(clock, seconds=10))

        with pytest.raises(GitHubError, match="rate limit"):
            await wait_on_rate_limit(lambda: github.latest("owner/app", etag=None))


async def test_limit_with_no_reset_header_waits_one_minute(
    github: GitHub, clock: FakeClock
) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            return_value=httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
        )

        with pytest.raises(RateLimitedError) as error:
            await github.latest("owner/app", etag=None)

    assert error.value.reset_at == clock.now() + timedelta(minutes=1)
