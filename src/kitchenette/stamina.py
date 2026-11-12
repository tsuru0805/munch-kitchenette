"""Stamina: one number per role, 0-1.

- It drifts toward the equilibrium of the current local hour (the 24-slot
  ``stamina.schedule``) with time constant ``stamina.tau_hours``. Nothing
  ticks: the value is integrated hour by hour whenever it is read.
- Talking costs nothing. A finished round costs stamina only for the work
  it contained: a base cost plus a cost per distinct kind of work, capped.
  Which tools are work, and of which kind, is the ``stamina.work`` table.
- Tools in the ``stamina.rest`` table restore stamina instead; what a single
  round can restore is capped.
- Other parts add their own pulses: how a kitchen dish turned out, snacks,
  potions.
- Lack of sleep can scale the whole schedule down (see :mod:`kitchenette.sleep`).

With ``stamina.enabled`` off every write is a no-op returning None, and the
rest of the kitchen carries on without it.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Iterable

from . import clock, config, db, roles, sleep
from .texts import t

log = logging.getLogger(__name__)


def _cfg():
    return config.get()


def enabled() -> bool:
    return bool(_cfg().stamina_enabled)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _toward(x: float, eq: float, tau_h: float, dt_sec: float) -> float:
    if dt_sec <= 0 or tau_h <= 0:
        return x
    return eq + (x - eq) * math.exp(-dt_sec / (tau_h * 3600.0))


def integrate(x: float, t0: float, t1: float, eq_factor: float = 1.0) -> float:
    """Pure: carry a value from t0 to t1, relaxing toward each hour's equilibrium in turn."""
    schedule, tau = _cfg().stamina_schedule, _cfg().stamina_tau_hours
    cur = t0
    while cur < t1:
        hour_end = (math.floor(cur / 3600.0) + 1) * 3600.0
        b = min(hour_end, t1)
        x = _toward(x, float(schedule[clock.local(cur).hour]) * eq_factor, tau, b - cur)
        cur = b
    return _clamp(x)


def _row(conn, who: str, now: float):
    r = conn.execute("SELECT * FROM stamina WHERE who=?", (who,)).fetchone()
    if r is None:
        conn.execute("INSERT OR IGNORE INTO stamina (who, value, updated_at) VALUES (?,?,?)",
                     (who, _cfg().stamina_init, now))
        r = conn.execute("SELECT * FROM stamina WHERE who=?", (who,)).fetchone()
    return r


def read(who: str, now: float | None = None) -> float | None:
    """Stamina right now; None when stamina is switched off."""
    if not enabled():
        return None
    roles.check(who)
    now = now or clock.now()
    conn = db.connect()
    try:
        r = _row(conn, who, now)
        conn.commit()
    finally:
        conn.close()
    return integrate(float(r["value"]), float(r["updated_at"]), now, sleep.factor(who, now))


def pulse(who: str, delta: float, now: float | None = None, rule: str = "") -> float | None:
    """Add (or, negative, take) stamina: integrate to now, apply delta, store.
    Returns the stored value; None when stamina is off or the write failed (nothing was added)."""
    if not enabled():
        return None
    roles.check(who)
    now = now or clock.now()
    f = sleep.factor(who, now)
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = _row(conn, who, now)
        v = _clamp(integrate(float(r["value"]), float(r["updated_at"]), now, f) + delta)
        conn.execute("UPDATE stamina SET value=?, updated_at=? WHERE who=?", (v, now, who))
        if delta:
            conn.execute("INSERT INTO stamina_log (who, at, delta, value, rule) VALUES (?,?,?,?,?)",
                         (who, now, delta, v, rule))
        conn.commit()
        return v
    except Exception:  # noqa: BLE001
        log.warning("stamina pulse failed (%s)", rule, exc_info=True)
        return None
    finally:
        conn.close()


def _lookup(table: dict, name: str):
    """Match a tool by its bare name or as the tail of "server__tool"."""
    bare = (name or "").split("__")[-1]
    return table.get(name, table.get(bare))


def round_delta(tool_names: Iterable[str]) -> tuple[float, str]:
    """Tools that succeeded in one round -> (stamina change, what it was made of).
    A round of pure talk is (0, "")."""
    cfg = _cfg()
    recharge = 0.0
    kinds: list[str] = []
    for name in tool_names or []:
        gain = _lookup(cfg.stamina_rest, name)
        if gain is not None:
            recharge += float(gain)
            continue
        kind = _lookup(cfg.stamina_work, name)
        if kind and kind not in kinds:
            kinds.append(kind)
    delta = 0.0
    parts = []
    if kinds:
        delta -= min(cfg.stamina_cost_cap, cfg.stamina_cost_base + cfg.stamina_cost_per_kind * len(kinds))
        parts.append("work")
    if recharge > 0.0:
        delta += min(cfg.stamina_recharge_cap, recharge)
        parts.append("rest")
    return delta, "+".join(parts)


def settle(who: str, tool_names: Iterable[str], now: float | None = None) -> float | None:
    """Settle one finished round. Never raises; returns the stamina after, or None if unchanged."""
    if not enabled():
        return None
    try:
        delta, rule = round_delta(list(tool_names or []))
        if delta:
            return pulse(who, delta, now=now, rule=rule)
    except Exception:  # noqa: BLE001
        log.warning("round settlement failed", exc_info=True)
    return None


def settle_call(who: str, tool_name: str, now: float | None = None) -> float | None:
    """Settle one of this server's own tool calls as it happens (stamina.auto_account).

    A model usually makes several calls in one turn, and the rule charges work per round, not per
    call. Calls arriving within stamina.auto_round_seconds of the first one are treated as the same
    round: the base cost is charged once, each kind of work once, and the total stays under the cap.
    Rest is credited per call, each capped like a round. Never raises.
    """
    if not enabled():
        return None
    cfg = _cfg()
    now = now or clock.now()
    try:
        gain = _lookup(cfg.stamina_rest, tool_name)
        if gain is not None:
            return pulse(who, min(cfg.stamina_recharge_cap, float(gain)), now=now, rule="rest")
        kind = _lookup(cfg.stamina_work, tool_name)
        if not kind:
            return None
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            r = _row(conn, who, now)
            same_round = r["round_at"] is not None and 0 <= now - float(r["round_at"]) < cfg.stamina_auto_round_seconds
            kinds = json.loads(r["round_kinds"] or "[]") if same_round else []
            spent = float(r["round_cost"]) if same_round else 0.0
            if kind in kinds:
                conn.rollback()
                return None
            cost = cfg.stamina_cost_per_kind + (0.0 if same_round else cfg.stamina_cost_base)
            cost = max(0.0, min(cost, cfg.stamina_cost_cap - spent))
            conn.execute("UPDATE stamina SET round_at=?, round_kinds=?, round_cost=? WHERE who=?",
                         (float(r["round_at"]) if same_round else now, json.dumps(kinds + [kind]),
                          spent + cost, who))
            conn.commit()
        finally:
            conn.close()
        return pulse(who, -cost, now=now, rule="work") if cost else None
    except Exception:  # noqa: BLE001
        log.warning("settling a tool call failed", exc_info=True)
        return None


def body_line(who: str, now: float | None = None) -> str | None:
    """A one-line status for the role's turn; None when stamina is off."""
    v = read(who, now)
    if v is None:
        return None
    return t("body_line", hm=clock.hm(now or clock.now()), value=f"{v:.2f}")


def history(who: str, limit: int = 20) -> list[dict]:
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT at, delta, value, rule FROM stamina_log WHERE who=? ORDER BY id DESC LIMIT ?", (who, limit))]
    finally:
        conn.close()
