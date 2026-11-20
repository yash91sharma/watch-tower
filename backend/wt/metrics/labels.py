"""The text of the metric values for the UI. The backend makes all labels.

Bytes use binary units (KiB = 1024 B), the same as `docker stats`. No value gives "-".
"""

NO_VALUE = "-"
UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def _unit(value: float) -> tuple[float, str]:
    """The value in the largest unit that keeps it at 1 or more."""
    index = 0
    while value >= 1024 and index < len(UNITS) - 1:
        value /= 1024
        index += 1
    return value, UNITS[index]


def _number(value: float, unit: str) -> str:
    return f"{value:.0f}" if unit == "B" else f"{value:.1f}"


def bytes_label(value: int | None) -> str:
    """For example "3.1 GiB"."""
    if value is None:
        return NO_VALUE
    number, unit = _unit(value)
    return f"{_number(number, unit)} {unit}"


def used_of_label(used: int | None, total: int) -> str:
    """For example "3.1 / 8.0 GiB", or "18.4 MiB / 7.8 GiB" when the units are different."""
    if used is None:
        return NO_VALUE
    used_number, used_unit = _unit(used)
    number, unit = _unit(total)
    if used_unit == unit:
        return f"{_number(used_number, unit)} / {_number(number, unit)} {unit}"
    return f"{bytes_label(used)} / {bytes_label(total)}"


def rate_label(value: float | None) -> str:
    """For example "1.2 MiB/s"."""
    if value is None:
        return NO_VALUE
    number, unit = _unit(value)
    return f"{_number(number, unit)} {unit}/s"


def network_label(rx: float | None, tx: float | None) -> str:
    """The network in and out, for example "In 1.2 KiB/s, out 300 B/s"."""
    return f"In {rate_label(rx)}, out {rate_label(tx)}"


def disk_io_label(read: float | None, write: float | None) -> str:
    """The disk read and write, for example "Read 0 B/s, write 4.0 KiB/s"."""
    return f"Read {rate_label(read)}, write {rate_label(write)}"


def cpu_label(percent: float | None, cores: float | None) -> str:
    """For example "9.1% (1.0 core)". Below 10% the percent has one decimal. Below 1
    core the cores have 2 decimals, so that a small value does not show as 0.0.
    """
    if percent is None or cores is None:
        return NO_VALUE
    text = f"{percent:.1f}%" if percent < 10 else f"{percent:.0f}%"
    number = f"{cores:.2f}" if cores < 1 else f"{cores:.1f}"
    word = "core" if cores <= 1 else "cores"
    return f"{text} ({number} {word})"


def load_label(load_1: float, load_5: float, load_15: float) -> str:
    """The load average of 1, 5 and 15 minutes, for example "0.52 / 0.40 / 0.35"."""
    return f"{load_1:.2f} / {load_5:.2f} / {load_15:.2f}"


def uptime_label(seconds: float) -> str:
    """For example "3 d 4 h", "4 h 12 min" or "12 min"."""
    minutes = int(seconds // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"
