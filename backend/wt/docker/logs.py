"""Docker log lines: the frame decoder and the timestamp parser (pure).

Docker sends `GET /containers/{id}/logs` with a timestamp on each line. With no TTY the
stream has frames that tell stdout from stderr.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

Stream = Literal["stdout", "stderr"]


@dataclass(frozen=True)
class LogLine:
    # From the Docker timestamp. None if the line has no timestamp.
    time: datetime | None
    stream: Stream
    text: str


def parse_log_line(raw: str, stream: Stream) -> LogLine:
    """Split "<RFC 3339 time with ns> <text>" into time and text."""
    stamp, _, text = raw.partition(" ")
    time = _parse_time(stamp)
    if time is None:
        return LogLine(None, stream, raw)
    return LogLine(time, stream, text)


def _parse_time(stamp: str) -> datetime | None:
    if not stamp.endswith("Z"):
        return None
    seconds, _, fraction = stamp[:-1].partition(".")
    # Python keeps microseconds. Docker gives nanoseconds.
    try:
        time = datetime.fromisoformat(seconds).replace(tzinfo=UTC)
    except ValueError:
        return None
    if fraction.isdigit():
        time = time.replace(microsecond=int(fraction[:6].ljust(6, "0")))
    return time


# The size of a frame header in the log stream.
_HEADER = 8


class LogDecoder:
    """Bytes from GET /containers/{id}/logs to lines.

    With no TTY, Docker sends frames: 1 byte stream (1 stdout, 2 stderr), 3 bytes zero,
    4 bytes length, then the data. aiodocker drops the stream byte, so WT reads the frames
    itself. With a TTY, Docker sends one raw stream: all lines are stdout.
    """

    def __init__(self, tty: bool) -> None:
        self._tty = tty
        self._buffer = b""
        self._partial: dict[Stream, bytes] = {"stdout": b"", "stderr": b""}

    def feed(self, data: bytes) -> list[LogLine]:
        if self._tty:
            return self._lines("stdout", data)
        self._buffer += data
        lines: list[LogLine] = []
        while len(self._buffer) >= _HEADER:
            length = int.from_bytes(self._buffer[4:_HEADER])
            if len(self._buffer) < _HEADER + length:
                break
            stream: Stream = "stderr" if self._buffer[0] == 2 else "stdout"
            payload = self._buffer[_HEADER : _HEADER + length]
            self._buffer = self._buffer[_HEADER + length :]
            lines += self._lines(stream, payload)
        return lines

    def flush(self) -> list[LogLine]:
        """The last lines with no newline."""
        lines: list[LogLine] = []
        for stream, rest in self._partial.items():
            if rest:
                lines.append(_line(rest, stream))
                self._partial[stream] = b""
        return lines

    def _lines(self, stream: Stream, data: bytes) -> list[LogLine]:
        *complete, self._partial[stream] = (self._partial[stream] + data).split(b"\n")
        return [_line(raw, stream) for raw in complete]


def _line(raw: bytes, stream: Stream) -> LogLine:
    return parse_log_line(raw.decode(errors="replace").removesuffix("\r"), stream)
