"""Docker Hub tags API client. The base URL comes from WT_DOCKERHUB_API_URL (tests use a
fake). Docker Hub has no release notes, so WT gets only the tag names.
"""

from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, ValidationError

from wt import clock
from wt.versions.fetch import TIMEOUT_SECONDS, USER_AGENT, FetchError, RateLimitedError

# The most recent tags. Enough for the current tag kinds of an image.
PAGE_SIZE = 100


class DockerHubError(FetchError):
    """A Docker Hub fetch failed."""


class _Tag(BaseModel):
    name: str


class _TagPage(BaseModel):
    results: list[_Tag]


class DockerHub:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )

    async def tags(self, repo: str) -> list[str]:
        """The newest tags of "namespace/repo", newest first."""
        namespace, _, name = repo.partition("/")
        try:
            response = await self._client.get(
                f"/v2/namespaces/{namespace}/repositories/{name}/tags",
                params={"page_size": str(PAGE_SIZE), "ordering": "last_updated"},
            )
        except httpx.HTTPError as error:
            raise DockerHubError(
                f"Docker Hub request failed: {type(error).__name__}"
            ) from None
        if response.status_code == 429:
            raise RateLimitedError("Docker Hub", _reset_at(response))
        if response.status_code == 404:
            raise DockerHubError("The image is not on Docker Hub")
        if response.status_code != 200:
            raise DockerHubError(f"Docker Hub answered HTTP {response.status_code}")
        try:
            page = _TagPage.model_validate_json(response.content)
        except ValidationError:
            raise DockerHubError("Docker Hub sent data that WT cannot read") from None
        return [tag.name for tag in page.results]

    async def close(self) -> None:
        await self._client.aclose()


def _reset_at(response: httpx.Response) -> datetime:
    """When a rate limit ends: Retry-After, else X-RateLimit-Reset, else in 1 minute."""
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return clock.now() + timedelta(seconds=int(retry_after))
    reset = response.headers.get("X-RateLimit-Reset", "")
    if reset.isdigit():
        return datetime.fromtimestamp(int(reset), UTC)
    return clock.now() + timedelta(minutes=1)
