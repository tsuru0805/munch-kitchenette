"""The menu (dishes waiting on the table) and eating.

A menu row is a dish put up for one role, either by the human or by the
kitchen when one of the role's own pots is served. ``eaten_at`` empty means it
is still there.

Eating records a meal, crosses matching dishes off the menu and settles the
body (satiety, stamina, dizziness). What is neither on the menu, nor a pot
just served, nor edible straight from the fridge cannot be eaten: it has to be
cooked first.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from . import clock, config, db, fridge, kitchen, potion, roles, snacks, stamina
from .texts import t

DISH_MAX = 200
MENU_LEFT_MAX = 5
RECENT_EATEN_N = 2


class MenuError(Exception):
    def __init__(self, text: str, code: str):
        super().__init__(text)
        self.text = text
        self.code = code            # bad_request | not_found | already_eaten


class EatRefused(Exception):
    """Nothing was eaten; text is the sentence for the role."""

    def __init__(self, text: str):
        super().__init__(text)
        self.text = text


def _now() -> float:
    return clock.now()


def _conn():
    return db.connect()


def _out(r) -> dict:
    return {"id": r["id"], "dish": r["dish"], "note": r["note"], "by": r["by"], "for_who": r["for_who"],
            "eaten_at": clock.iso(r["eaten_at"]), "created_at": clock.iso(r["created_at"]),
            "updated_at": clock.iso(r["updated_at"]),
            "eaten_ts": r["eaten_at"], "created_ts": r["created_at"]}


def _to_ts(value) -> float | None:
    """eaten_at as sent by a client: epoch seconds, an ISO string, or null."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise MenuError(t("detail_eaten_at"), "bad_request")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise MenuError(t("detail_eaten_at"), "bad_request") from None
    return (d if d.tzinfo else d.replace(tzinfo=clock.local(_now()).tzinfo)).timestamp()


# ── rows ────────────────────────────────────────────────────────────────

def list_rows(for_who: str | None = None, pending: bool = False) -> list[dict]:
    """Menu rows, newest first; pending=True keeps only those not eaten yet."""
    clauses, params = [], []
    if pending:
        clauses.append("eaten_at IS NULL")
    if for_who:
        clauses.append("for_who = ?")
        params.append(for_who)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = _conn()
    try:
        return [_out(r) for r in conn.execute(
            f"SELECT * FROM menu {where} ORDER BY created_at DESC, rowid DESC", params).fetchall()]
    finally:
        conn.close()


def get(row_id: str) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM menu WHERE id=?", (str(row_id),)).fetchone()
        return _out(r) if r else None
    finally:
        conn.close()


def add(dish: str, by: str, for_who: str, note: str | None = None, now: float | None = None) -> dict:
    """Put a dish up for a role. by = who put it there (the role's own id for its own pots)."""
    dish = (dish or "").strip() if isinstance(dish, str) else ""
    if not dish or not by or not for_who:
        raise MenuError(t("detail_menu_required"), "bad_request")
    if len(dish) > DISH_MAX:
        raise MenuError(t("detail_dish_long", max=DISH_MAX), "bad_request")
    if not roles.valid(for_who):
        raise MenuError(t("detail_menu_for_who"), "bad_request")
    now = now or _now()
    rid = uuid.uuid4().hex
    conn = _conn()
    try:
        conn.execute("INSERT INTO menu (id, dish, note, by, for_who, eaten_at, created_at, updated_at)"
                     " VALUES (?,?,?,?,?,NULL,?,?)", (rid, dish, note or None, str(by), for_who, now, now))
        conn.commit()
    finally:
        conn.close()
    return get(rid)


def patch(row_id: str, changes: dict, now: float | None = None) -> dict:
    """Change eaten_at / note / dish. With if_pending=true only a row still on the table can be
    written (so "the role just ate it" and "the human feeds it" cannot both win)."""
    now = now or _now()
    allowed = {k: changes[k] for k in ("eaten_at", "note", "dish") if k in changes}
    if "dish" in allowed:
        if not isinstance(allowed["dish"], str) or not allowed["dish"].strip():
            raise MenuError(t("detail_dish_empty"), "bad_request")
        allowed["dish"] = allowed["dish"].strip()
        if len(allowed["dish"]) > DISH_MAX:
            raise MenuError(t("detail_dish_long", max=DISH_MAX), "bad_request")
    if "eaten_at" in allowed:
        allowed["eaten_at"] = _to_ts(allowed["eaten_at"])
    if not allowed:
        raise MenuError(t("detail_nothing_to_patch"), "bad_request")
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute("SELECT eaten_at FROM menu WHERE id=?", (str(row_id),)).fetchone()
        if r is None:
            conn.rollback()
            raise MenuError(t("detail_not_found"), "not_found")
        if changes.get("if_pending") is True and r["eaten_at"] is not None:
            conn.rollback()
            raise MenuError(t("detail_already_eaten"), "already_eaten")
        sets = ", ".join(f"{k}=?" for k in allowed)
        conn.execute(f"UPDATE menu SET {sets}, updated_at=? WHERE id=?", (*allowed.values(), now, str(row_id)))
        conn.commit()
    finally:
        conn.close()
    return get(row_id)


def delete(row_id: str) -> bool:
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM menu WHERE id=?", (str(row_id),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def mark_eaten(row_id: str, now: float | None = None) -> bool:
    try:
        patch(row_id, {"eaten_at": now or _now()})
        return True
    except MenuError:
        return False


# ── what the kitchen scan needs from the menu ───────────────────────────

def find_for_session(session: dict):
    """Is this pot's dish already on the menu? (put there by the role itself, same name, still on
    the table, created no earlier than the pot was served)."""
    who = session["who"]
    for row in list_rows(for_who=who, pending=True):
        if (row["dish"] or "").strip() != session["dish"] or row["by"] != who:
            continue
        if row["created_ts"] >= float(session["served_at"]) - 5:
            return row["id"]
    return None


def add_for_session(session: dict):
    who = session["who"]
    return add(session["dish"], who, who, kitchen.menu_note(session) or None)["id"]


def table_ids(who: str) -> set[str]:
    return {str(r["id"]) for r in list_rows(for_who=who, pending=True)}


def set_note(row_id, note: str) -> None:
    try:
        patch(row_id, {"note": note})
    except MenuError as e:
        if e.code != "not_found":      # a row that is gone has nothing to write
            raise


def remove_row(row_id) -> None:
    delete(row_id)


# ── eating ──────────────────────────────────────────────────────────────

def _format_gap(delta: timedelta) -> str:
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return t("gap_just_now")
    days, rem = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(rem, 60)
    parts = []
    if days:
        parts.append(t("gap_days", n=days))
    if hours:
        parts.append(t("gap_hours", n=hours))
    if minutes or not parts:
        parts.append(t("gap_minutes", n=minutes))
    return "".join(parts)


def _dish_keys(s: str) -> tuple[str, str]:
    """Two keys for matching a dish name: as written (blanks removed, case folded), and with
    everything but word characters stripped (so an emoji in the menu name does not block a match)."""
    base = re.sub(r"\s+", "", s).casefold()
    return base, re.sub(r"[^\w]", "", base)


def _meal_stats(who: str, now: float) -> tuple[str, int, int]:
    """(time since the previous meal, which meal of today this is, which of this week)."""
    local = clock.local(now)
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    monday = (day_start - timedelta(days=local.weekday())).timestamp()
    conn = _conn()
    try:
        week = conn.execute("SELECT COUNT(*) FROM meals WHERE who=? AND at>=? AND at<=?",
                            (who, monday, now)).fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM meals WHERE who=? AND at>=? AND at<=?",
                             (who, day_start.timestamp(), now)).fetchone()[0]
        prev = conn.execute("SELECT at FROM meals WHERE who=? AND at<=? ORDER BY at DESC LIMIT 1",
                            (who, now)).fetchone()
    finally:
        conn.close()
    gap = _format_gap(timedelta(seconds=now - float(prev["at"]))) if prev else t("eat_first")
    return gap, int(today) + 1, int(week) + 1


def meals_since(who: str, since: float | None = None, now: float | None = None) -> dict:
    """The meals a role has had since a moment, oldest first. since=None means "today": from
    midnight in the configured zone. Snacks and potions are not meals."""
    roles.check(who)
    now = now or _now()
    if since is None:
        since = clock.local(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    conn = _conn()
    try:
        rows = conn.execute("SELECT id, meal, note, at FROM meals WHERE who=? AND at>=? AND at<=?"
                            " ORDER BY at, rowid", (who, float(since), now)).fetchall()
    finally:
        conn.close()
    return {"now": now, "who": who, "since": float(since), "meals": [dict(r) for r in rows]}


def _record_meal(who: str, meal: str, note: str | None, now: float) -> None:
    conn = _conn()
    try:
        conn.execute("INSERT INTO meals (id, who, meal, note, at) VALUES (?,?,?,?,?)",
                     (uuid.uuid4().hex, who, meal, note or None, now))
        conn.commit()
    finally:
        conn.close()


def _drink_potion(who: str, now: float) -> str:
    """Drink one potion bottle hanging on the menu. Not a meal: nothing else is touched."""
    pending = [d for d in list_rows(for_who=who, pending=True) if (d["dish"] or "").strip()]
    bottles = [d for d in pending if potion.is_potion_meal(d["dish"])]
    if not bottles:
        raise EatRefused(t("potion_none_on_menu", potion=potion.NAME))
    try:
        got = potion.drink(who, [str(d["id"]) for d in bottles], now=now)
    except potion.PotionError as e:
        for rid in e.rows:              # drunk earlier but never crossed off: tidy up
            mark_eaten(rid, now)
        raise EatRefused(e.text) from None
    drunk = {str(x) for x in got["drunk"]}
    for rid in drunk:
        mark_eaten(rid, now)
    out = got["text"]
    left = [d["dish"].strip() for d in pending if str(d["id"]) not in drunk]
    if left:
        out += "\n" + t("eat_left", left="、".join(left[:MENU_LEFT_MAX]))
    return out


def eat(who: str, meal: str, note: str = "", *, key: str | None = None, now: float | None = None) -> str:
    """Eat one meal and return the receipt. Raises EatRefused when nothing could be eaten.

    key makes the body settlement idempotent (give the same key when retrying the same bite).
    Runs under the role's after-serving lock, so a pot coming due at the same moment is either on
    the menu before the meal is matched or already marked eaten before the serving pass looks.
    """
    roles.check(who)
    with kitchen.due_lock(who):
        return _eat_locked(who, meal, note, key=key, now=now)


def _eat_locked(who: str, meal: str, note: str, *, key: str | None, now: float | None) -> str:
    meal = (meal or "").strip()
    if not meal:
        raise EatRefused(t("eat_empty"))
    now = now or _now()
    if potion.is_potion_meal(meal):
        return _drink_potion(who, now)
    gap, today_n, week_n = _meal_stats(who, now)

    # A dish is crossed off when its full name appears in what was eaten (one meal can cross off
    # several). The reverse, an abbreviation of a dish name, only earns a hint.
    meal_base, meal_txt = _dish_keys(meal)

    def _hit(dish: str) -> bool:
        base, txt = _dish_keys(dish)
        return (len(txt) >= 2 and bool(meal_txt) and txt in meal_txt) or base in meal_base

    def _abbrev(dish: str) -> bool:
        base, txt = _dish_keys(dish)
        return (len(meal_txt) >= 2 and bool(txt) and meal_txt in txt) or meal_base in base

    pending = [d for d in list_rows(for_who=who, pending=True) if (d["dish"] or "").strip()]
    foods = [d for d in pending if not potion.is_potion_meal(d["dish"])]   # a potion is never food
    potion_aside = len(foods) != len(pending) and potion._norm(potion.NAME) in meal_base
    hits = [d for d in foods if _hit(d["dish"])]
    fuzzy = None
    if not hits:
        fuzzy = next((d for d in pending if _abbrev(d["dish"])), None)
        verdict = kitchen.can_eat(who, meal, now)
        if verdict.get("ok") is False:
            if fuzzy is not None:
                raise EatRefused(t("eat_none_fuzzy", meal=meal, dish=fuzzy["dish"]))
            raise EatRefused(verdict.get("text") or t("eat_none", meal=meal))
    for d in hits:
        mark_eaten(d["id"], now)
    left = [d["dish"].strip() for d in pending if d not in hits]

    before = fridge.satiety(who, now)
    _record_meal(who, meal, note, now)
    detail = kitchen.eat_detail(who, meal, key=key or uuid.uuid4().hex, now=now)
    after = fridge.satiety(who, now)

    lines = [t("eat_ok", meal=meal, gap=gap, today=today_n, week=week_n)]
    if config.get().satiety_enabled:
        state = (t("eat_state_full") if before >= 60 else
                 (t("eat_state_due") if before >= config.get().satiety_hungry_below else t("eat_state_starved")))
        lines.append(t("eat_satiety", before=round(before), after=round(after), state=state))
    if detail and detail.get("raw_receipt"):
        lines.append(detail["raw_receipt"])
    if hits:
        for d in hits:
            lines.append(t("eat_crossed", dish=d["dish"])
                         + (t("eat_crossed_note", note=d["note"]) if d.get("note") else ""))
    elif fuzzy is not None:
        lines.append(t("eat_fuzzy", dish=fuzzy["dish"], why=t("eat_fuzzy_why")))
    if left:
        lines.append(t("eat_left", left="、".join(left[:MENU_LEFT_MAX])))
    if potion_aside:
        lines.append(t("eat_potion_aside", potion=potion.NAME))
    if note:
        lines.append(t("eat_note", preview=note[:30] + ("..." if len(note) > 30 else "")))
    return "\n".join(lines)


def feed(row_id: str, now: float | None = None) -> dict:
    """The human feeds a dish from the menu to the role it was put up for.
    Returns {row, text (the note for the role), outcome}. Raises MenuError when the row is gone or
    already eaten, PotionError when a potion row cannot be drunk."""
    now = now or _now()
    row = get(row_id)
    if row is None:
        raise MenuError(t("detail_not_found"), "not_found")
    who = row["for_who"]
    if potion.is_potion_meal(row["dish"]):
        got = potion.feed(who, str(row_id), now=now)
        mark_eaten(row_id, now)
        return {"row": get(row_id), "text": got["note"], "outcome": "potion", "reply": got["text"]}
    row = patch(row_id, {"eaten_at": now, "if_pending": True}, now=now)
    _record_meal(who, row["dish"], None, now)
    outcome = kitchen.on_eat(who, row["dish"].strip(), key=f"fed:{row_id}", by_her=True, now=now)
    return {"row": row, "text": "", "outcome": outcome, "reply": ""}


# ── reading the menu ────────────────────────────────────────────────────

def _md_hm(ts: float | None) -> str:
    return clock.local(ts).strftime("%m-%d %H:%M") if ts else ""


def _snack_lines(who: str) -> list[str]:
    data = snacks.state(who)
    show_gain = data.get("energy_enabled") is True

    def _gain(g) -> str:
        return f" +{g:.2f}" if show_gain and isinstance(g, (int, float)) else ""

    cfg = config.get()
    out = ["", t("menu_snacks_head", tz=cfg.server_timezone_label, reset=f"{cfg.snacks_day_boundary_hour:02d}:00")]
    for s in data["snacks"]:
        head = t("menu_snack_row", name=s["name"], tier=s["tier_label"], eaten=s["eaten"], cap=s["cap"])
        if s["variants"]:
            head += t("menu_snack_variants") + " / ".join(f"{v['name']}{_gain(v['gain'])}" for v in s["variants"])
        else:
            head += _gain(s["gain"])
        out.append(head)
    out.append(t("menu_snacks_how"))
    return out


def read_menu(who: str, now: float | None = None) -> str:
    """The role's menu as text: what is on the table, the last couple of dishes eaten,
    the snack shelf and the fridge."""
    roles.check(who)
    rows = [d for d in list_rows(for_who=who) if (d["dish"] or "").strip()]
    dishes = [d for d in rows if d["eaten_ts"] is None]
    recent = sorted((d for d in rows if d["eaten_ts"] is not None),
                    key=lambda d: d["eaten_ts"], reverse=True)[:RECENT_EATEN_N]
    tail: list[str] = []
    for d in recent:
        line = t("menu_recent", dish=d["dish"].strip())
        if d.get("note"):
            line += t("menu_row_note", note=d["note"])
        line += t("menu_recent_hung", hung=_md_hm(d["created_ts"]))
        line += t("menu_recent_eaten", eaten=_md_hm(d["eaten_ts"]))
        tail.append(line)
    extra = _snack_lines(who) + ["", t("menu_fridge", text=fridge.status_text(who, now))]
    if not dishes:
        return "\n".join([t("menu_empty")] + tail + extra)
    lines = [t("menu_head")]
    potion_notes = ({p["menu_row_id"]: p["note"] for p in potion.pending(who)}
                    if stamina.enabled() and any(potion.is_potion_meal(d["dish"]) for d in dishes) else {})
    for d in dishes:
        line = t("menu_row", dish=d["dish"].strip())
        # for a potion, the registered amount wins over whatever the row's note still says
        d_note = potion_notes.get(str(d["id"])) or d.get("note")
        if d_note:
            line += t("menu_row_note", note=d_note)
        line += t("menu_row_hung", hung=_md_hm(d["created_ts"]))
        lines.append(line)
    lines.append(t("menu_how"))
    return "\n".join(lines + tail + extra)
