"""GitHub releases API client. The base URL comes from WT_GITHUB_API_URL (tests use a fake)."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, SecretStr, TypeAdapter, ValidationError

from wt import clock
from wt.versions.rules import Release

TIMEOUT_SECONDS = 30
# A run waits for the rate limit this many times, then fails.
MAX_RATE_LIMIT_WAITS = 3
USER_AGENT = "watch-tower/0.0.0"

log = logging.getLogger(__name__)


class GitHubError(Exception):
    """The fetch failed. WT saves the text in repo_cache.error."""


class RateLimitedError(GitHubError):
    """GitHub rate limit: wait until `reset_at`, then try again."""

    def __init__(self, reset_at: datetime) -> None:
        super().__init__(f"GitHub rate limit until {reset_at.isoformat()}")
        self.reset_at = reset_at


@dataclass(frozen=True)
class Fetched:
    release: Release
    etag: str | None


class _NotModified:
    """304: the latest release did not change since the ETag."""


class _NoRelease:
    """404: the repo has no release (or does not exist)."""


NOT_MODIFIED = _NotModified()
NO_RELEASE = _NoRelease()
Latest = Fetched | _NotModified | _NoRelease


class _ReleaseJson(BaseModel):
    tag_name: str
    body: str | None = None
    draft: bool = False
    prerelease: bool = False

    def release(self) -> Release:
        return Release(self.tag_name, self.body or "", self.draft, self.prerelease)


_RELEASE_LIST = TypeAdapter(list[_ReleaseJson])


class GitHub:
    def __init__(self, base_url: str, token: SecretStr | None) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token.get_secret_value()}"
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=TIMEOUT_SECONDS
        )

    async def latest(self, repo: str, etag: str | None) -> Latest:
        """GET /repos/{repo}/releases/latest. GitHub skips drafts and pre-releases."""
        headers = {"If-None-Match": etag} if etag else {}
        response = await self._get(f"/repos/{repo}/releases/latest", headers=headers)
        if response.status_code == 304:
            return NOT_MODIFIED
        if response.status_code == 404:
            return NO_RELEASE
        release = _parse(response, _ReleaseJson.model_validate_json).release()
        return Fetched(release, response.headers.get("ETag"))

    async def releases(self, repo: str) -> list[Release]:
        """One page (100) of releases, newest first."""
        response = await self._get(
            f"/repos/{repo}/releases", params={"per_page": "100"}
        )
        return [
            item.release() for item in _parse(response, _RELEASE_LIST.validate_json)
        ]

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.get(path, headers=headers, params=params)
        except httpx.HTTPError as error:
            raise GitHubError(
                f"GitHub request failed: {type(error).__name__}"
            ) from None
        reset_at = _rate_limit_reset(response)
        if reset_at is not None:
            raise RateLimitedError(reset_at)
        if response.status_code not in (200, 304, 404):
            raise GitHubError(f"GitHub answered HTTP {response.status_code}")
        return response


def _parse[T](response: httpx.Response, validate: Callable[[bytes], T]) -> T:
    try:
        return validate(response.content)
    except ValidationError:
        raise GitHubError("GitHub sent data that WT cannot read") from None


def _rate_limit_reset(response: httpx.Response) -> datetime | None:
    """The reset time if the response is a rate limit (403 or 429), else None."""
    if response.status_code not in (403, 429):
        return None
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return clock.now() + timedelta(seconds=int(retry_after))
    if response.headers.get("x-ratelimit-remaining") != "0":
        return None
    reset = response.headers.get("x-ratelimit-reset", "")
    if reset.isdigit():
        return datetime.fromtimestamp(int(reset), UTC)
    return clock.now() + timedelta(minutes=1)


async def wait_on_rate_limit[T](call: Callable[[], Awaitable[T]]) -> T:
    """Run `call`. On a rate limit, wait until the reset (through clock) and run it again."""
    for _ in range(MAX_RATE_LIMIT_WAITS):
        try:
            return await call()
        except RateLimitedError as error:
            seconds = max((error.reset_at - clock.now()).total_seconds(), 0) + 1
            log.warning("GitHub rate limit. WT waits %d s.", seconds)
            await clock.sleep(seconds)
    raise GitHubError("GitHub rate limit: WT stopped after 3 waits")
