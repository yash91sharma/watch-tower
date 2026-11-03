"""Update summary: the LLM result if there is one, else the keyword severity."""

from dataclasses import dataclass

from pydantic import SecretStr

from wt.config import Settings
from wt.db.models import Severity
from wt.llm.client import complete
from wt.llm.prompt import build_messages
from wt.llm.severity import keyword_severity


@dataclass(frozen=True)
class Summary:
    severity: Severity
    # Empty with no LLM result. Then the UI shows the release notes only.
    summary: str


async def summarize(
    notes: str, settings: Settings, api_key: SecretStr | None
) -> Summary:
    """Use the LLM if its URL and model are set and it gives a result."""
    if settings.llm_url and settings.llm_model:
        result = await complete(
            settings.llm_url, settings.llm_model, build_messages(notes), api_key
        )
        if result is not None:
            return Summary(result.severity, result.summary)
    return Summary(keyword_severity(notes), "")
