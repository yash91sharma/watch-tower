"""Update summary: the LLM result if there is one, else the keyword severity."""

from pydantic import SecretStr

from wt.config import Settings
from wt.llm.client import LlmResult, complete
from wt.llm.prompt import build_messages
from wt.llm.severity import keyword_severity


async def summarize(
    notes: str, settings: Settings, api_key: SecretStr | None
) -> LlmResult:
    """Use the LLM if its URL and model are set and it gives a result.

    Else the keyword severity and an empty summary (the UI shows the release notes only).
    """
    if settings.llm_url and settings.llm_model:
        result = await complete(
            settings.llm_url, settings.llm_model, build_messages(notes), api_key
        )
        if result is not None:
            return result
    return LlmResult(severity=keyword_severity(notes), summary="")
