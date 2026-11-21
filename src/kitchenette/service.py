"""What the server does on its own: the periodic scan, and settling rounds.

The scan is the kitchen's clock. Once a minute, for every role, it

1. grows worms on dishes left out overnight and on spoiled fruit, and keeps
   the menu notes in step;
2. serves the pots that are due, puts each dish on its role's menu and
   writes the "your dish is ready" note;
3. writes a note for a worm bitten into when the receipt may have been missed;
4. writes the "getting hungry" note the first time satiety drops low;
5. pushes any notes waiting for the webhook.

Reads settle due pots too, so nothing depends on the scan for correctness;
the scan only makes things happen on time when nobody is looking.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from . import clock, config, db, fridge, kitchen, menu, notify, potion, roles, stamina

log = logging.getLogger(__name__)


def _served_note(session: dict, menu_ok: bool) -> None:
    notify.emit(session["who"], notify.KIND_SERVED,
                payload={**kitchen.served_event_payload(session, menu_ok), "session_id": session["id"]},
                key=f"kitchen.served:{session['id']}")


def _worm_note(who: str, text: str) -> str:
    notify.emit(who, notify.KIND_WORM, text, body=text)
    return kitchen.WAKE_SENT


def serve_due(who: str) -> dict | None:
    """Serve the pots that have come due for one role: onto the menu, and a note written.

    Called by the scan, and also right before the role (or a page) looks at anything, so that a
    pot the kitchen shows as served always has its note waiting and its dish on the menu at that
    same moment, not a scan later. Never raises.
    """
    try:
        # Every served pot becomes a note; holding notes back for quiet hours or sleep is the
        # notifier's job (notify.flush), so here the "queue a note" path is always taken.
        return kitchen.process_due(
            find_menu=menu.find_for_session, add_menu=menu.add_for_session,
            wake=lambda message: kitchen.WAKE_SENT, float_event=_served_note,
            in_quiet=False, busy=lambda: True, who=who)
    except Exception as e:  # noqa: BLE001
        log.error("serving pass failed for %s: %r", who, e)
        return None


def scan(who: str, now: float | None = None) -> dict:
    """One pass for one role. Each step is isolated: a failure in one never blocks the others."""
    out: dict = {"who": who}
    try:
        out["worms"] = kitchen.process_worms(
            list_table=lambda: menu.table_ids(who), set_note=menu.set_note,
            remove_row=menu.remove_row, who=who, now=now)
    except Exception as e:  # noqa: BLE001
        log.error("worm pass failed for %s: %r", who, e)
    out["due"] = serve_due(who)
    try:
        out["worm_notes"] = kitchen.process_worm_wakes(
            who=who, wake=lambda text: _worm_note(who, text), busy=lambda: False,
            receipt=lambda at: kitchen.RECEIPT_GONE, in_quiet=False, now=now)
    except Exception as e:  # noqa: BLE001
        log.error("worm note pass failed for %s: %r", who, e)
    try:
        line = fridge.hungry_due(who, now)
        if line:
            notify.emit(who, notify.KIND_HUNGRY, line, body=line)
        out["hungry"] = bool(line)
    except Exception as e:  # noqa: BLE001
        log.error("hunger pass failed for %s: %r", who, e)
    try:
        from . import playkit
        out["play"] = playkit.tick(who, now)
    except Exception as e:  # noqa: BLE001
        log.error("upgrade pass failed for %s: %r", who, e)
    return out


def scan_all(now: float | None = None) -> dict:
    try:
        from . import playkit
        street = playkit.tick_all(now)
    except Exception as e:  # noqa: BLE001
        log.error("vendor pass failed: %r", e)
        street = {}
    results = [scan(who, now) for who in roles.known()]
    try:
        pushed = notify.flush(now)
    except Exception as e:  # noqa: BLE001
        log.error("pushing notes failed: %r", e)
        pushed = {}
    return {"roles": results, "push": pushed, "street": street}


def settle_round(who: str, calls: list, round_id: str | None = None, now: float | None = None) -> dict:
    """Tell the kitchen what tools a role used in one finished round.

    calls: tool names, or {"name", "id"?, "input"?, "is_error"?} objects, for the tools that ran
    outside this server (this server's own tools are settled as they are called, unless
    stamina.auto_account is off). Effects: stamina (work costs, rest restores) and coupons (tools
    listed under coupons.earn). round_id makes the whole settlement idempotent.
    Returns {"stamina", "receipts", "duplicate"}.
    """
    roles.check(who)
    now = now or clock.now()
    if round_id:
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            seen = fridge._once(conn, f"round:{who}:{round_id}") is not None
            if not seen:
                fridge._mark_once(conn, f"round:{who}:{round_id}")
            conn.commit()
        finally:
            conn.close()
        if seen:
            return {"stamina": stamina.read(who, now), "receipts": [], "duplicate": True}
    norm = []
    for i, c in enumerate(calls or []):
        c = {"name": c} if isinstance(c, str) else dict(c)
        c.setdefault("id", f"{round_id}:{i}" if round_id else uuid.uuid4().hex)
        if c.get("name") and not c.get("is_error"):
            norm.append(c)
    from . import tools      # imported here: tools itself calls into this module
    own = set(tools.NAMES)
    auto = config.get().stamina_auto_account
    names = [c["name"] for c in norm
             if not potion.is_potion_call(c["name"], c.get("input"))
             and not (auto and c["name"].split("__")[-1] in own)]
    stamina.settle(who, names, now=now)
    earned = [c for c in norm if fridge.coupon_source_for_tool(c["name"])]
    receipts = kitchen.on_round_tools(who, earned)
    return {"stamina": stamina.read(who, now), "receipts": receipts, "duplicate": False}


def fast_forward(seconds: float, step: float = 600.0, max_steps: int = 2000) -> dict:
    """Move the clock forward as if the periodic scan had kept running all along (for demos and
    tests). The jump is walked in steps of `step` seconds, scanning after each, so pots are served
    and put on the menu when they come due rather than all at once at the end."""
    seconds = float(seconds)
    if seconds <= 0:
        if seconds:
            clock.advance(seconds)
        return scan_all()
    step = max(step, seconds / max_steps)
    left, last = seconds, {}
    while left > 0:
        hop = min(step, left)
        clock.advance(hop)
        left -= hop
        last = scan_all()
    return last


async def run_forever(stop: asyncio.Event) -> None:
    """Scan on the configured interval until stop is set."""
    while not stop.is_set():
        try:
            await asyncio.to_thread(scan_all)
        except Exception as e:  # noqa: BLE001
            log.error("scan failed: %r", e)
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(1.0, config.get().server_scan_interval_seconds))
        except asyncio.TimeoutError:
            pass
