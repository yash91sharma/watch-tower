"""The fake LLM API of the E2E stack (e2e/fakes/llm, task 16.2)."""

import time

import httpx
import pytest
from fakes.llm.app import create_app

from wt.db.models import Severity
from wt.llm.client import LlmResult

pytestmark = pytest.mark.anyio

CHAT = "/v1/chat/completions"


def client(slow_seconds: float = 0.2) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_app("good", slow_seconds))
    return httpx.AsyncClient(transport=transport, base_url="http://llm")


def chat(notes: str, system: str = "Rate the update.") -> dict[str, object]:
    return {
        "model": "fake",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": notes},
        ],
    }


def result(response: httpx.Response) -> LlmResult:
    content = response.json()["choices"][0]["message"]["content"]
    return LlmResult.model_validate_json(content)


async def test_good_mode_gives_a_reply_that_wt_can_read() -> None:
    async with client() as http:
        normal = await http.post(CHAT, json=chat("- New dark mode"))
        critical = await http.post(CHAT, json=chat("- Fix CVE-2026-1234"))

    assert normal.status_code == critical.status_code == 200
    assert result(normal) == LlmResult(
        severity=Severity.NORMAL, summary="Fake LLM summary."
    )
    assert result(critical).severity == Severity.CRITICAL


async def test_only_the_user_message_sets_the_severity() -> None:
    async with client() as http:
        response = await http.post(
            CHAT, json=chat("- New dark mode", system="A CVE-1 is critical.")
        )

    assert result(response).severity == Severity.NORMAL


async def test_error_mode_gives_500() -> None:
    async with client() as http:
        await http.put("/_control/mode", json={"mode": "error"})
        response = await http.post(CHAT, json=chat("notes"))

    assert response.status_code == 500


async def test_slow_mode_waits_before_the_reply() -> None:
    async with client(slow_seconds=0.2) as http:
        await http.put("/_control/mode", json={"mode": "slow"})
        start = time.monotonic()
        response = await http.post(CHAT, json=chat("notes"))

    assert time.monotonic() - start >= 0.2
    assert response.status_code == 200


async def test_the_fake_counts_the_requests_and_reset_clears_them() -> None:
    async with client() as http:
        await http.post(CHAT, json=chat("a"))
        await http.post(CHAT, json=chat("b"))
        count = (await http.get("/_control/requests")).json()
        await http.put("/_control/mode", json={"mode": "error"})
        await http.post("/_control/reset")
        after = (await http.get("/_control/requests")).json()
        good = await http.post(CHAT, json=chat("c"))

    assert count == {"count": 2}
    assert after == {"count": 0}
    assert good.status_code == 200


async def test_a_bad_mode_gives_422() -> None:
    async with client() as http:
        response = await http.put("/_control/mode", json={"mode": "fast"})

    assert response.status_code == 422
