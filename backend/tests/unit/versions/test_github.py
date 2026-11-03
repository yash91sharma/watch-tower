"""Tests for wt.versions.github (respx)."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from pydantic import SecretStr

from wt.versions.github import NO_RELEASE, NOT_MODIFIED, Fetched, GitHub, GitHubError
from wt.versions.rules import Release

pytestmark = pytest.mark.anyio

API = "http://github.test"
LATEST = f"{API}/repos/owner/app/releases/latest"
RELEASES = f"{API}/repos/owner/app/releases"
RELEASE_JSON = {
    "tag_name": "v1.2.0",
    "body": "Fixes",
    "draft": False,
    "prerelease": False,
}


@pytest.fixture
async def github() -> AsyncIterator[GitHub]:
    client = GitHub(API, token=None)
    yield client
    await client.close()


async def test_latest_200_gives_the_release_and_etag(github: GitHub) -> None:
    with respx.mock:
        route = respx.get(LATEST).mock(
            return_value=httpx.Response(
                200, json=RELEASE_JSON, headers={"ETag": '"abc"'}
            )
        )

        result = await github.latest("owner/app", etag=None)

    assert result == Fetched(Release("v1.2.0", "Fixes"), etag='"abc"')
    headers = route.calls.last.request.headers
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["User-Agent"].startswith("watch-tower")
    assert "Authorization" not in headers
    assert "If-None-Match" not in headers


async def test_latest_304_with_etag(github: GitHub) -> None:
    with respx.mock:
        route = respx.get(LATEST).mock(return_value=httpx.Response(304))

        result = await github.latest("owner/app", etag='"abc"')

    assert result is NOT_MODIFIED
    assert route.calls.last.request.headers["If-None-Match"] == '"abc"'


async def test_latest_404_gives_no_release(github: GitHub) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )

        assert await github.latest("owner/app", etag=None) is NO_RELEASE


async def test_release_with_no_body_has_empty_notes(github: GitHub) -> None:
    with respx.mock:
        respx.get(LATEST).mock(
            return_value=httpx.Response(200, json={**RELEASE_JSON, "body": None})
        )

        result = await github.latest("owner/app", etag=None)

    assert result == Fetched(Release("v1.2.0", ""), etag=None)


async def test_token_is_sent_as_bearer() -> None:
    github = GitHub(API, token=SecretStr("s3cret"))
    with respx.mock:
        route = respx.get(LATEST).mock(return_value=httpx.Response(304))
        await github.latest("owner/app", etag=None)
    await github.close()

    assert route.calls.last.request.headers["Authorization"] == "Bearer s3cret"


async def test_releases_gets_one_page_of_100(github: GitHub) -> None:
    with respx.mock:
        route = respx.get(RELEASES).mock(
            return_value=httpx.Response(
                200,
                json=[
                    RELEASE_JSON,
                    {**RELEASE_JSON, "tag_name": "v1.3.0-rc1", "prerelease": True},
                ],
            )
        )

        releases = await github.releases("owner/app")

    assert releases == [
        Release("v1.2.0", "Fixes"),
        Release("v1.3.0-rc1", "Fixes", prerelease=True),
    ]
    assert route.calls.last.request.url.params["per_page"] == "100"


@pytest.mark.parametrize(
    "response",
    [
        httpx.ReadTimeout("timed out"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"no": "tag"}),
        httpx.Response(500),
        httpx.Response(401, json={"message": "Bad credentials"}),
    ],
    ids=["timeout", "bad-json", "bad-shape", "http-500", "http-401"],
)
async def test_errors_raise_github_error(
    github: GitHub, response: httpx.Response | Exception
) -> None:
    with respx.mock:
        route = respx.get(LATEST)
        if isinstance(response, Exception):
            route.mock(side_effect=response)
        else:
            route.mock(return_value=response)

        with pytest.raises(GitHubError):
            await github.latest("owner/app", etag=None)


async def test_releases_bad_json_raises_github_error(github: GitHub) -> None:
    with respx.mock:
        respx.get(RELEASES).mock(
            return_value=httpx.Response(200, json={"not": "a list"})
        )

        with pytest.raises(GitHubError):
            await github.releases("owner/app")
