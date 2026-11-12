"""The one clock every rule reads.

``now()`` is wall time plus an offset. The offset stays zero in normal use;
tests and demos move it forward to watch food spoil without waiting days.
"""
from __future__ import annotations

import time
from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo

from . import config

_offset = 0.0


def now() -> float:
    return time.time() + _offset


def advance(seconds: float) -> float:
    """Move the clock forward (or back, with a negative value). Returns the new offset."""
    global _offset
    _offset += float(seconds)
    return _offset


def reset() -> None:
    global _offset
    _offset = 0.0


def offset() -> float:
    return _offset


def tz() -> tzinfo | None:
    """The configured zone, or None for the machine's local time."""
    name = config.get().server_timezone
    return ZoneInfo(name) if name else None


def local(ts: float) -> datetime:
    """Epoch seconds -> aware datetime in the configured zone."""
    zone = tz()
    return datetime.fromtimestamp(ts, tz=zone) if zone else datetime.fromtimestamp(ts).astimezone()


def hm(ts: float) -> str:
    return local(ts).strftime("%H:%M")


def iso(ts: float | None) -> str | None:
    return None if ts is None else local(ts).isoformat(timespec="seconds")
