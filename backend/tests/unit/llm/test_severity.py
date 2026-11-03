"""Tests for wt.llm.severity."""

import pytest

from wt.db.models import Severity
from wt.llm.severity import keyword_severity


@pytest.mark.parametrize(
    ("notes", "severity"),
    [
        ("Fixes CVE-2026-1234 in the parser", Severity.CRITICAL),
        ("fixes cve-2026-1234", Severity.CRITICAL),
        ("Security fix for the login page", Severity.CRITICAL),
        ("SECURITY: update the TLS library", Severity.CRITICAL),
        ("Improve security headers", Severity.CRITICAL),
        ("New dark mode. Faster startup.", Severity.NORMAL),
        ("CVE without a dash is not a match", Severity.NORMAL),
        ("", Severity.NORMAL),
    ],
)
def test_keyword_severity(notes: str, severity: Severity) -> None:
    assert keyword_severity(notes) is severity
