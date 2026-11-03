"""Tests for wt.llm.client (respx)."""

import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from wt.db.models import Severity
from wt.llm.client import LlmResult, complete

pytestmark = pytest.mark.anyio

URL = "http://llm.test:11434"
ENDPOINT = f"{URL}/v1/chat/completions"
MESSAGES = [{"role": "user", "content": "Release notes"}]


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_good_reply(caplog: pytest.LogCaptureFixture) -> None:
    content = json.dumps(
        {"severity": "critical", "summary": "Fixes a security problem."}
    )
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=reply(content))

        result = await complete(
            URL, "qwen3:4b", MESSAGES, api_key=SecretStr("s3cret-key")
        )

    assert result == LlmResult(
        severity=Severity.CRITICAL, summary="Fixes a security problem."
    )
    request = route.calls.last.request
    body: dict[str, Any] = json.loads(request.content)
    assert body["model"] == "qwen3:4b"
    assert body["messages"] == MESSAGES
    assert body["temperature"] == 0
    schema = body["response_format"]["json_schema"]
    assert body["response_format"]["type"] == "json_schema"
    assert schema["strict"] is True
    assert schema["schema"]["properties"]["severity"]["enum"] == ["critical", "normal"]
    assert request.headers["Authorization"] == "Bearer s3cret-key"
    assert "s3cret" not in caplog.text


async def test_no_key_sends_no_authorization() -> None:
    content = json.dumps({"severity": "normal", "summary": "New features."})
    with respx.mock:
        route = respx.post(ENDPOINT).mock(return_value=reply(content))

        await complete(URL, "m", MESSAGES, api_key=None)

    assert "Authorization" not in route.calls.last.request.headers


@pytest.mark.parametrize(
    "response",
    [
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("no server"),
        httpx.Response(500, text="error"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        reply("not json"),
        reply(json.dumps({"severity": "high", "summary": "x"})),
        reply(json.dumps({"summary": "no severity"})),
    ],
    ids=[
        "timeout",
        "connect",
        "http-500",
        "bad-body",
        "no-choices",
        "bad-json",
        "bad-enum",
        "missing",
    ],
)
async def test_errors_give_no_result_and_a_warning(
    response: httpx.Response | Exception, caplog: pytest.LogCaptureFixture
) -> None:
    with respx.mock:
        route = respx.post(ENDPOINT)
        if isinstance(response, Exception):
            route.mock(side_effect=response)
        else:
            route.mock(return_value=response)

        result = await complete(URL, "m", MESSAGES, api_key=None)

    assert result is None
    assert "LLM" in caplog.text
