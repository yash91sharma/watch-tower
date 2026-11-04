"""LLM eval (marker llm_eval, run by hand): severity of known release notes with a real LLM.

Set WT_EVAL_LLM_URL (default http://ollama:11434) and WT_EVAL_LLM_MODEL (default
qwen2.5:3b). The notes in cases.json are made up for this test.
"""

import json
import os
from pathlib import Path

import pytest

from wt.llm.client import complete
from wt.llm.prompt import build_messages

pytestmark = [pytest.mark.llm_eval, pytest.mark.anyio]

CASES: list[dict[str, str]] = json.loads(
    (Path(__file__).parent / "cases.json").read_text()
)
URL = os.environ.get("WT_EVAL_LLM_URL", "http://ollama:11434")
MODEL = os.environ.get("WT_EVAL_LLM_MODEL", "qwen2.5:3b")


def test_there_are_20_cases_with_both_severities() -> None:
    assert len(CASES) == 20
    assert {case["severity"] for case in CASES} == {"critical", "normal"}


@pytest.mark.parametrize("case", CASES, ids=[f"case-{n}" for n in range(len(CASES))])
async def test_severity_matches_and_the_reply_matches_the_schema(
    case: dict[str, str],
) -> None:
    result = await complete(URL, MODEL, build_messages(case["notes"]), api_key=None)

    assert result is not None, "The reply does not match the schema (see the log)"
    assert result.severity.value == case["severity"]
    assert result.summary.strip()
