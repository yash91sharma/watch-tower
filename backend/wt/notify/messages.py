"""Notification texts (pure). Messages are short and link to WT."""

from dataclasses import dataclass
from urllib.parse import quote

from wt.db.models import EventKind, Severity

MAX_BODY = 500

HEALTH_TITLES = {
    EventKind.BECAME_UNHEALTHY: "{name} is unhealthy",
    EventKind.RESTART_LOOP: "{name} restarts in a loop",
    EventKind.RECOVERED_HEALTH: "{name} is healthy again",
    EventKind.RECOVERED_LOOP: "{name} does not restart now",
}
PROBLEMS = {EventKind.BECAME_UNHEALTHY, EventKind.RESTART_LOOP}


@dataclass(frozen=True)
class UpdateInfo:
    name: str
    from_version: str
    to_version: str
    severity: Severity
    summary: str


@dataclass(frozen=True)
class Message:
    # Title and click go in HTTP headers, so they are ASCII.
    title: str
    body: str
    # ntfy tags (emoji short codes).
    tags: tuple[str, ...]
    # The link that opens WT. None if the public URL is not set.
    click: str | None
    # ntfy priority: "high" or "default".
    priority: str = "default"


def update_message(update: UpdateInfo, public_url: str | None) -> Message:
    return Message(
        title=_ascii(
            f"Update: {update.name} {update.from_version} -> {update.to_version}"
        ),
        body=_short(update.summary or "Release notes are available"),
        tags=_update_tags([update]),
        click=_click(public_url, f"/containers/{quote(update.name)}"),
        priority=_update_priority([update]),
    )


def digest_message(updates: list[UpdateInfo], public_url: str | None) -> Message:
    lines = [
        f"{update.name} {update.from_version} -> {update.to_version}"
        + (" (critical)" if update.severity is Severity.CRITICAL else "")
        for update in updates
    ]
    return Message(
        title=f"{len(updates)} updates",
        body=_short("\n".join(lines)),
        tags=_update_tags(updates),
        click=_click(public_url, "/"),
        priority=_update_priority(updates),
    )


def health_message(name: str, kind: EventKind, public_url: str | None) -> Message:
    text = HEALTH_TITLES[kind].format(name=name)
    return Message(
        title=_ascii(text),
        body=text,
        tags=("warning",) if kind in PROBLEMS else ("white_check_mark",),
        click=_click(public_url, f"/containers/{quote(name)}"),
        priority="high" if kind is EventKind.BECAME_UNHEALTHY else "default",
    )


def _update_priority(updates: list[UpdateInfo]) -> str:
    """High if one of the updates is critical."""
    return (
        "high"
        if any(update.severity is Severity.CRITICAL for update in updates)
        else "default"
    )


def _update_tags(updates: list[UpdateInfo]) -> tuple[str, ...]:
    if any(update.severity is Severity.CRITICAL for update in updates):
        return ("warning", "package")
    return ("package",)


def _click(public_url: str | None, path: str) -> str | None:
    return _ascii(public_url + path) if public_url else None


def _ascii(text: str) -> str:
    return text.encode("ascii", errors="replace").decode()


def _short(text: str) -> str:
    return text if len(text) <= MAX_BODY else text[: MAX_BODY - 3] + "..."
