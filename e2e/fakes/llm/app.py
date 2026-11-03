"""Fake OpenAI-compatible LLM API for the E2E stack (task 16.2).

POST /v1/chat/completions answers by mode:
 - good: JSON {severity, summary}. Severity is critical if the user message has "CVE-".
 - slow: waits FAKE_LLM_SLOW_SECONDS (default 90, more than the WT timeout), then good.
 - error: HTTP 500.
The mode starts from FAKE_LLM_MODE (default good). E2E flows change it with the control
routes under /_control. Run: uvicorn fakes.llm.app:app
"""

import asyncio
import json
import os
from typing import Annotated, Any, Literal

from fastapi import Body, FastAPI, Response
from fastapi.responses import JSONResponse

Mode = Literal["good", "slow", "error"]
SUMMARY = "Fake LLM summary."


def create_app(mode: Mode, slow_seconds: float) -> FastAPI:
    app = FastAPI(title="Fake LLM")
    start_mode = mode
    count = 0

    @app.post("/v1/chat/completions")
    async def chat(body: Annotated[dict[str, Any], Body()]) -> Response:
        nonlocal count
        count += 1
        if mode == "error":
            return JSONResponse({"error": "Fake LLM error"}, status_code=500)
        if mode == "slow":
            # A real wait: the fake has no WT clock.
            await asyncio.sleep(slow_seconds)  # noqa: TID251
        # The user message has the release notes. The system prompt can name CVEs too.
        notes = " ".join(
            str(message.get("content", ""))
            for message in body["messages"]
            if message.get("role") == "user"
        )
        severity = "critical" if "CVE-" in notes else "normal"
        content = json.dumps({"severity": severity, "summary": SUMMARY})
        return JSONResponse(
            {"choices": [{"message": {"role": "assistant", "content": content}}]}
        )

    @app.put("/_control/mode", status_code=204)
    def set_mode(new_mode: Annotated[Mode, Body(embed=True, alias="mode")]) -> None:
        nonlocal mode
        mode = new_mode

    @app.get("/_control/requests")
    def requests() -> dict[str, int]:
        return {"count": count}

    @app.post("/_control/reset", status_code=204)
    def reset() -> None:
        nonlocal mode, count
        mode, count = start_mode, 0

    return app


def _env_mode() -> Mode:
    value = os.environ.get("FAKE_LLM_MODE", "good")
    return value if value in ("slow", "error") else "good"


app = create_app(_env_mode(), float(os.environ.get("FAKE_LLM_SLOW_SECONDS", "90")))
