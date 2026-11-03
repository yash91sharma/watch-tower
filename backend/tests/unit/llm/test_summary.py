"""Tests for wt.llm.summary (respx)."""

import json

import httpx
import pytest
import respx

from wt.config import Settings
from wt.db.models import Severity
from wt.llm.summary import Summary, summarize

pytestmark = pytest.mark.anyio

URL = "http://llm.test:11434"
NOTES = "Fixes CVE-2026-1 in the parser."


@pytest.mark.parametrize(
    "settings",
    [Settings(), Settings(llm_url=URL), Settings(llm_model="m")],
    ids=["nothing-set", "no-model", "no-url"],
)
async def test_llm_off_uses_keywords_and_no_summary(settings: Settings) -> None:
    with respx.mock:
        route = respx.post(f"{URL}/v1/chat/completions")

        result = await summarize(NOTES, settings, api_key=None)

    assert result == Summary(Severity.CRITICAL, "")
    assert not route.called


async def test_llm_error_uses_keywords_and_no_summary() -> None:
    with respx.mock:
        respx.post(f"{URL}/v1/chat/completions").mock(return_value=httpx.Response(500))

        result = await summarize(
            NOTES, Settings(llm_url=URL, llm_model="m"), api_key=None
        )

    assert result == Summary(Severity.CRITICAL, "")


async def test_llm_good_uses_the_llm_result() -> None:
    content = json.dumps(
        {"severity": "normal", "summary": "The update adds dark mode."}
    )
    reply = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    with respx.mock:
        route = respx.post(f"{URL}/v1/chat/completions").mock(return_value=reply)

        result = await summarize(
            "New dark mode.", Settings(llm_url=URL, llm_model="m"), None
        )

    assert result == Summary(Severity.NORMAL, "The update adds dark mode.")
    assert (
        json.loads(route.calls.last.request.content)["messages"][1]["content"]
        == "New dark mode."
    )
