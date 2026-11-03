"""Fake GitHub releases API for the E2E stack (task 16.1).

WT reads `/repos/{owner}/{repo}/releases/latest` (with ETag) and `/repos/{owner}/{repo}/releases`.
The seed (env FAKE_GITHUB_SEED, JSON {"owner/repo": [releases, newest first]}) gives the
running versions, so the stack starts with no updates. Each E2E flow adds its releases
with the control routes under /_control. Run: uvicorn fakes.github.app:app
"""

import hashlib
import json
import os
from typing import Annotated

from fastapi import Body, FastAPI, Header, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, TypeAdapter

# Rate limit mode: WT waits this long, then tries again.
RETRY_AFTER_SECONDS = 60


class Release(BaseModel):
    tag_name: str
    body: str = ""
    draft: bool = False
    prerelease: bool = False


Seed = dict[str, list[dict[str, object]]]
_SEED = TypeAdapter(Seed)


def seed_from_env() -> Seed:
    return _SEED.validate_json(os.environ.get("FAKE_GITHUB_SEED") or "{}")


def create_app(seed: Seed) -> FastAPI:
    app = FastAPI(title="Fake GitHub")
    # Repo "owner/repo" -> releases, newest first.
    releases: dict[str, list[Release]] = {}
    rate_limited = False

    def reset() -> None:
        nonlocal rate_limited
        releases.clear()
        for repo, items in seed.items():
            releases[repo] = [Release.model_validate(item) for item in items]
        rate_limited = False

    def limit() -> Response | None:
        if not rate_limited:
            return None
        return JSONResponse(
            {"message": "API rate limit exceeded"},
            status_code=403,
            headers={
                "x-ratelimit-remaining": "0",
                "Retry-After": str(RETRY_AFTER_SECONDS),
            },
        )

    @app.get("/repos/{owner}/{repo}/releases/latest")
    def latest(
        owner: str,
        repo: str,
        if_none_match: Annotated[str | None, Header()] = None,
    ) -> Response:
        if (limited := limit()) is not None:
            return limited
        found = [
            item
            for item in releases.get(f"{owner}/{repo}", [])
            if not item.draft and not item.prerelease
        ]
        if not found:
            return JSONResponse({"message": "Not Found"}, status_code=404)
        body = found[0].model_dump_json()
        etag = f'"{hashlib.sha256(body.encode()).hexdigest()[:16]}"'
        if if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return Response(body, media_type="application/json", headers={"ETag": etag})

    @app.get("/repos/{owner}/{repo}/releases")
    def all_releases(
        owner: str, repo: str, per_page: Annotated[int, Query(ge=1, le=100)] = 30
    ) -> Response:
        if (limited := limit()) is not None:
            return limited
        items = releases.get(f"{owner}/{repo}", [])[:per_page]
        return Response(
            json.dumps([item.model_dump() for item in items]),
            media_type="application/json",
        )

    @app.post("/_control/repos/{owner}/{repo}/releases", status_code=204)
    def add_release(owner: str, repo: str, release: Release) -> None:
        """Add a release as the newest one."""
        releases.setdefault(f"{owner}/{repo}", []).insert(0, release)

    @app.put("/_control/rate-limit", status_code=204)
    def set_rate_limit(on: Annotated[bool, Body(embed=True)]) -> None:
        nonlocal rate_limited
        rate_limited = on

    @app.post("/_control/reset", status_code=204)
    def reset_route() -> None:
        reset()

    reset()
    return app


app = create_app(seed_from_env())
