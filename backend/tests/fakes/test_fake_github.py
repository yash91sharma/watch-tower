"""The fake GitHub API of the E2E stack (e2e/fakes/github, task 16.1)."""

import json

import httpx
import pytest
from fakes.github.app import create_app, seed_from_env

pytestmark = pytest.mark.anyio

REPO = "/repos/acme/web"


def client(seed: dict[str, list[dict[str, object]]] | None = None) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_app(seed or {}))
    return httpx.AsyncClient(transport=transport, base_url="http://github")


async def add(http: httpx.AsyncClient, tag: str, body: str = "", **flags: bool) -> None:
    response = await http.post(
        f"/_control{REPO}/releases", json={"tag_name": tag, "body": body, **flags}
    )
    assert response.status_code == 204


async def test_the_seed_gives_the_latest_release() -> None:
    async with client({"acme/web": [{"tag_name": "v1.0.0", "body": "First"}]}) as http:
        response = await http.get(f"{REPO}/releases/latest")

    assert response.status_code == 200
    assert response.json() == {
        "tag_name": "v1.0.0",
        "body": "First",
        "draft": False,
        "prerelease": False,
    }


async def test_no_release_gives_404() -> None:
    async with client() as http:
        assert (await http.get(f"{REPO}/releases/latest")).status_code == 404


async def test_latest_skips_drafts_and_pre_releases() -> None:
    async with client() as http:
        await add(http, "v1.0.0")
        await add(http, "v1.1.0-rc1", prerelease=True)
        await add(http, "v1.1.0", draft=True)

        response = await http.get(f"{REPO}/releases/latest")

    assert response.json()["tag_name"] == "v1.0.0"


async def test_the_etag_gives_304_until_a_new_release() -> None:
    async with client() as http:
        await add(http, "v1.0.0")
        etag = (await http.get(f"{REPO}/releases/latest")).headers["ETag"]
        cached = {"If-None-Match": etag}

        assert (
            await http.get(f"{REPO}/releases/latest", headers=cached)
        ).status_code == 304
        await add(http, "v1.1.0")
        response = await http.get(f"{REPO}/releases/latest", headers=cached)

    assert response.status_code == 200
    assert response.json()["tag_name"] == "v1.1.0"


async def test_releases_gives_the_list_newest_first_with_per_page() -> None:
    async with client() as http:
        for tag in ["v1.0.0", "v1.1.0", "v1.2.0"]:
            await add(http, tag, body=f"Notes {tag}")

        response = await http.get(f"{REPO}/releases", params={"per_page": "2"})
        other = await http.get("/repos/other/repo/releases")

    assert [item["tag_name"] for item in response.json()] == ["v1.2.0", "v1.1.0"]
    assert other.json() == []


async def test_rate_limit_mode_gives_403_with_the_reset_headers() -> None:
    async with client() as http:
        await add(http, "v1.0.0")

        on = await http.put("/_control/rate-limit", json={"on": True})
        limited = await http.get(f"{REPO}/releases/latest")
        await http.put("/_control/rate-limit", json={"on": False})
        after = await http.get(f"{REPO}/releases/latest")

    assert on.status_code == 204
    assert limited.status_code == 403
    assert limited.headers["x-ratelimit-remaining"] == "0"
    assert limited.headers["Retry-After"] == "60"
    assert after.status_code == 200


async def test_reset_goes_back_to_the_seed() -> None:
    async with client({"acme/web": [{"tag_name": "v1.0.0"}]}) as http:
        await add(http, "v2.0.0")
        await http.put("/_control/rate-limit", json={"on": True})

        assert (await http.post("/_control/reset")).status_code == 204
        response = await http.get(f"{REPO}/releases/latest")

    assert response.json()["tag_name"] == "v1.0.0"


def test_seed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    seed = {"acme/web": [{"tag_name": "v1.0.0"}]}
    monkeypatch.setenv("FAKE_GITHUB_SEED", json.dumps(seed))

    assert seed_from_env() == seed
    monkeypatch.delenv("FAKE_GITHUB_SEED")
    assert seed_from_env() == {}
