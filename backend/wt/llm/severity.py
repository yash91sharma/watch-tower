"""Keyword severity: the rule when WT has no LLM result."""

from wt.db.models import Severity

CRITICAL_WORDS = ("cve-", "security")


def keyword_severity(notes: str) -> Severity:
    """Critical if the notes contain "CVE-" or "security" (any case). Else normal."""
    text = notes.lower()
    return (
        Severity.CRITICAL
        if any(word in text for word in CRITICAL_WORDS)
        else Severity.NORMAL
    )
