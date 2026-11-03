"""Tests for the notification priority in wt.notify.messages."""

import pytest

from wt.db.models import EventKind, Severity
from wt.notify.messages import (
    UpdateInfo,
    digest_message,
    health_message,
    update_message,
)

NORMAL = UpdateInfo("web", "1.0", "1.2", Severity.NORMAL, "")
CRITICAL = UpdateInfo("db", "16.3", "16.4", Severity.CRITICAL, "")


@pytest.mark.parametrize(
    ("updates", "priority"),
    [([NORMAL], "default"), ([CRITICAL], "high")],
)
def test_update_priority(updates: list[UpdateInfo], priority: str) -> None:
    assert update_message(updates[0], None).priority == priority


@pytest.mark.parametrize(
    ("updates", "priority"),
    [([NORMAL, NORMAL], "default"), ([NORMAL, CRITICAL], "high")],
)
def test_digest_priority(updates: list[UpdateInfo], priority: str) -> None:
    assert digest_message(updates, None).priority == priority


@pytest.mark.parametrize(
    ("kind", "priority"),
    [
        (EventKind.BECAME_UNHEALTHY, "high"),
        (EventKind.RESTART_LOOP, "default"),
        (EventKind.RECOVERED_HEALTH, "default"),
        (EventKind.RECOVERED_LOOP, "default"),
    ],
)
def test_health_priority(kind: EventKind, priority: str) -> None:
    assert health_message("web", kind, None).priority == priority
