"""Tests for the Docker log decoder in wt.docker.client, and FakeDocker logs."""

import struct
from datetime import UTC, datetime

import pytest

from wt.docker.client import LogDecoder, LogLine, parse_log_line
from wt.docker.fake import FakeDocker

T1 = "2026-01-01T00:00:01.123456789Z"
TIME1 = datetime(2026, 1, 1, 0, 0, 1, 123456, tzinfo=UTC)


def frame(stream: int, payload: bytes) -> bytes:
    return struct.pack(">BxxxL", stream, len(payload)) + payload


def test_parse_log_line_with_a_timestamp() -> None:
    assert parse_log_line(f"{T1} hello world", "stdout") == LogLine(
        TIME1, "stdout", "hello world"
    )


@pytest.mark.parametrize(
    ("raw", "text", "has_time"),
    [
        (f"{T1} ", "", True),
        (f"{T1}", "", True),
        ("no time here", "no time here", False),
        ("2026-99-99T00:00:00Z bad", "2026-99-99T00:00:00Z bad", False),
    ],
)
def test_parse_log_line_edge_cases(raw: str, text: str, has_time: bool) -> None:
    line = parse_log_line(raw, "stderr")

    assert line.text == text
    assert (line.time is not None) is has_time
    assert line.stream == "stderr"


def test_multiplexed_frames_give_lines_per_stream() -> None:
    decoder = LogDecoder(tty=False)
    data = frame(1, f"{T1} out\n".encode()) + frame(2, f"{T1} err\n".encode())

    lines = decoder.feed(data)

    assert lines == [LogLine(TIME1, "stdout", "out"), LogLine(TIME1, "stderr", "err")]


def test_frames_split_over_chunks() -> None:
    decoder = LogDecoder(tty=False)
    data = frame(1, f"{T1} first\n{T1} second\n".encode())

    lines = [
        *decoder.feed(data[:5]),
        *decoder.feed(data[5:20]),
        *decoder.feed(data[20:]),
    ]

    assert [line.text for line in lines] == ["first", "second"]


def test_a_line_over_two_frames_and_flush() -> None:
    decoder = LogDecoder(tty=False)

    first = decoder.feed(frame(1, f"{T1} par".encode()))
    second = decoder.feed(frame(1, b"tial\n") + frame(1, f"{T1} no newline".encode()))
    rest = decoder.flush()

    assert first == []
    assert [line.text for line in second] == ["partial"]
    assert [line.text for line in rest] == ["no newline"]
    assert decoder.flush() == []


def test_tty_stream_is_raw_and_all_stdout() -> None:
    decoder = LogDecoder(tty=True)

    lines = decoder.feed(f"{T1} tick 1\r\n{T1} tick".encode()) + decoder.feed(b" 2\r\n")

    assert lines == [
        LogLine(TIME1, "stdout", "tick 1"),
        LogLine(TIME1, "stdout", "tick 2"),
    ]


def test_bad_utf8_is_replaced() -> None:
    decoder = LogDecoder(tty=True)

    [line] = decoder.feed(b"\xff\xfe text\n")

    assert line.text.endswith("text")


@pytest.mark.anyio
async def test_fake_docker_logs_tail_and_since() -> None:
    fake = FakeDocker()
    lines = [
        LogLine(
            datetime(2026, 1, 1, 0, 0, second, tzinfo=UTC), "stdout", f"line {second}"
        )
        for second in range(5)
    ]
    fake.log_lines["web"] = lines

    tail = [line async for line in fake.logs("web", tail=2, since=None, follow=False)]
    since = [
        line
        async for line in fake.logs(
            "web",
            tail=None,
            since=datetime(2026, 1, 1, 0, 0, 3, tzinfo=UTC),
            follow=False,
        )
    ]

    assert tail == lines[3:]
    assert since == lines[3:]
