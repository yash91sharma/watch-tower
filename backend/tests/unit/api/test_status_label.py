"""Tests for the update status text of a container."""

import pytest

from wt.api.containers import status_label
from wt.db.models import Severity
from wt.versions.rules import Status


@pytest.mark.parametrize(
    ("status", "severity", "label"),
    [
        (Status.UPDATE, Severity.CRITICAL, "critical update"),
        (Status.UPDATE, Severity.NORMAL, "update available"),
        # No release notes yet, so no severity.
        (Status.UPDATE, None, "update available"),
        (Status.UP_TO_DATE, None, "up to date"),
        (Status.NO_SOURCE, None, "no source"),
    ],
)
def test_status_label(status: Status, severity: Severity | None, label: str) -> None:
    assert status_label(status, severity) == label
