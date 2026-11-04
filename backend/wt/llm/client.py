"""OpenAI-compatible chat client for a local LLM (Ollama, llama.cpp, LM Studio).

WT asks for JSON that matches a strict schema: {severity, summary}. On any error, WT logs
a warning and gives no result. Then it shows the release notes only.
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from wt.db.models import Severity

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "update_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["critical", "normal"]},
                "summary": {"type": "string"},
            },
            "required": ["severity", "summary"],
            "additionalProperties": False,
        },
    },
}


class LlmResult(BaseModel):
    severity: Severity
    summary: str


async def complete(
    url: str, model: str, messages: list[dict[str, str]], api_key: SecretStr | None
) -> LlmResult | None:
    """Ask the LLM. Give the checked result, or None on any error."""
    headers = (
        {"Authorization": f"Bearer {api_key.get_secret_value()}"} if api_key else {}
    )
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "response_format": RESPONSE_FORMAT,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{url}/v1/chat/completions", json=body, headers=headers
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return LlmResult.model_validate_json(content)
    except httpx.HTTPError as error:
        log.warning("LLM request failed: %s", type(error).__name__)
    except ValidationError:
        log.warning("LLM reply is not usable: the reply does not match the schema")
    except ValueError, KeyError, IndexError, TypeError:
        # JSON errors are ValueErrors.
        log.warning("LLM reply is not usable: the reply is not valid")
    return None
