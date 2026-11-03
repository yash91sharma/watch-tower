"""Tests for wt.notify.messages (text snapshots)."""

import pytest

from wt.db.models import EventKind, Severity
from wt.notify.messages import (
    Message,
    UpdateInfo,
    digest_message,
    health_message,
    update_message,
)

URL = "https://wt.example.com"
WEB = UpdateInfo("web", "1.0", "1.2", Severity.NORMAL, "The update adds dark mode.")
DB = UpdateInfo("db", "16.3", "16.4", Severity.CRITICAL, "")


def test_one_update_with_a_summary() -> None:
    assert update_message(WEB, URL) == Message(
        title="Update: web 1.0 -> 1.2",
        body="The update adds dark mode.",
        tags=("package",),
        click="https://wt.example.com/containers/web",
    )


def test_one_critical_update_with_no_summary() -> None:
    assert update_message(DB, URL) == Message(
        title="Update: db 16.3 -> 16.4",
        body="Release notes are available",
        tags=("warning", "package"),
        click="https://wt.example.com/containers/db",
        priority="high",
    )


def test_digest() -> None:
    assert digest_message([WEB, DB], URL) == Message(
        title="2 updates",
        body="web 1.0 -> 1.2\ndb 16.3 -> 16.4 (critical)",
        tags=("warning", "package"),
        click="https://wt.example.com/",
        priority="high",
    )


def test_digest_with_no_critical_update() -> None:
    message = digest_message([WEB, WEB], URL)

    assert message.tags == ("package",)


@pytest.mark.parametrize(
    ("kind", "title", "tags"),
    [
        (EventKind.BECAME_UNHEALTHY, "web is unhealthy", ("warning",)),
        (EventKind.RESTART_LOOP, "web restarts in a loop", ("warning",)),
        (EventKind.RECOVERED_HEALTH, "web is healthy again", ("white_check_mark",)),
        (EventKind.RECOVERED_LOOP, "web does not restart now", ("white_check_mark",)),
    ],
)
def test_health_messages(kind: EventKind, title: str, tags: tuple[str, ...]) -> None:
    message = health_message("web", kind, URL)

    assert (message.title, message.body, message.tags, message.click) == (
        title,
        title,
        tags,
        "https://wt.example.com/containers/web",
    )


def test_no_click_link_with_no_public_url() -> None:
    assert update_message(WEB, None).click is None
    assert digest_message([WEB], None).click is None
    assert health_message("web", EventKind.RESTART_LOOP, None).click is None


def test_title_and_click_are_ascii_and_body_is_short() -> None:
    update = UpdateInfo("wéb", "1.0", "1.2", Severity.NORMAL, "x" * 2000)

    message = update_message(update, "https://wt.example.com")

    assert message.title == "Update: w?b 1.0 -> 1.2"
    assert message.click == "https://wt.example.com/containers/w%C3%A9b"
    assert len(message.body) <= 500
    assert message.body.endswith("...")
