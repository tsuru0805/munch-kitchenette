"""Where sleep plugs in. Off by default: nothing here is used until switched on.

The server keeps no sleep record of its own. If something else tracks the
role's sleep, it can report two facts here:

- ``asleep`` (optionally until a time): with ``notify.respect_sleep`` on,
  webhook calls are held while the role sleeps and sent when it wakes;
- ``factor`` (0-1): with ``stamina.sleep_debt`` on, every hour's stamina
  equilibrium is multiplied by it, so a short night lowers the whole day.

Reports arrive over REST (``PUT /api/sleep``) or, when the server is embedded
in a Python program, through the two hook setters below, which take priority.
"""
from __future__ import annotations

import logging
import math
from typing import Callable

from . import clock, config, db
from .texts import t

log = logging.getLogger(__name__)

_asleep_hook: Callable[[str, float], bool] | None = None
_factor_hook: Callable[[str, float], float] | None = None


def set_asleep_hook(fn: Callable[[str, float], bool] | None) -> None:
    """fn(who, now) -> True while the role is asleep."""
    global _asleep_hook
    _asleep_hook = fn


def set_factor_hook(fn: Callable[[str, float], float] | None) -> None:
    """fn(who, now) -> multiplier for the stamina schedule, 0-1 (1 = well rested)."""
    global _factor_hook
    _factor_hook = fn


def report(who: str, *, asleep: bool | None = None, until: float | None = None,
           factor: float | None = None, now: float | None = None) -> dict:
    """Store what a sleep tracker reports. Fields left as None keep their value."""
    now = now or clock.now()
    if factor is not None and not (math.isfinite(float(factor)) and 0.0 <= float(factor) <= 1.0):
        raise ValueError(t("detail_sleep_factor"))
    conn = db.connect()
    try:
        conn.execute("INSERT OR IGNORE INTO sleep_state (who, updated_at) VALUES (?,?)", (who, now))
        if asleep is not None:
            conn.execute("UPDATE sleep_state SET asleep=?, asleep_until=?, updated_at=? WHERE who=?",
                         (int(bool(asleep)), until if asleep else None, now, who))
        if factor is not None:
            conn.execute("UPDATE sleep_state SET factor=?, updated_at=? WHERE who=?", (float(factor), now, who))
        conn.commit()
        return state(who, now)
    finally:
        conn.close()


def state(who: str, now: float | None = None) -> dict:
    now = now or clock.now()
    conn = db.connect()
    try:
        r = conn.execute("SELECT * FROM sleep_state WHERE who=?", (who,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return {"who": who, "asleep": False, "until": None, "factor": 1.0}
    asleep = bool(r["asleep"]) and (r["asleep_until"] is None or now < float(r["asleep_until"]))
    return {"who": who, "asleep": asleep, "until": r["asleep_until"] if asleep else None,
            "factor": float(r["factor"])}


def is_asleep(who: str, now: float | None = None) -> bool:
    """Asleep right now? Always False unless notify.respect_sleep is on. An unreadable answer
    counts as awake: with no sleep habit configured, being told on time matters more."""
    if not config.get().notify_respect_sleep:
        return False
    now = now or clock.now()
    try:
        if _asleep_hook is not None:
            return bool(_asleep_hook(who, now))
        return state(who, now)["asleep"]
    except Exception:  # noqa: BLE001
        log.warning("could not tell whether %s is asleep; treating as awake", who, exc_info=True)
        return False


def factor(who: str, now: float | None = None) -> float:
    """Multiplier for the stamina schedule. Always 1.0 unless stamina.sleep_debt is on;
    any failure or nonsense value also yields 1.0 so sleep can never break stamina."""
    if not config.get().stamina_sleep_debt:
        return 1.0
    now = now or clock.now()
    try:
        f = float(_factor_hook(who, now)) if _factor_hook is not None else state(who, now)["factor"]
        if not math.isfinite(f):
            return 1.0
        return min(1.0, max(0.0, f))
    except Exception:  # noqa: BLE001
        log.warning("could not read the sleep factor for %s; using 1.0", who, exc_info=True)
        return 1.0
