"""The stamina potion: something the human can put on the menu like a dish,
with one extra number, how much stamina it restores.

- It is not a meal: satiety does not move and no meal is recorded.
- The amount has no upper limit; stamina itself still tops out at 100%.
- The role sees the amount on the menu. The human can also feed it directly.
- The name is reserved. A menu row with this exact name is a potion and is
  never eaten as food; eating "exactly this name" means drinking one bottle.

Stamina is granted exactly once, here: the bottle is claimed, stamina is
added, and only when that landed is the bottle marked used. If stamina could
not be added the bottle goes back on the menu and the failure is reported.

The amount is stored in the ``potions`` table, keyed by the menu row id; the
note on the menu row is only what the role reads.
"""
from __future__ import annotations

import logging
import re

from . import clock, db, roles, stamina
from .texts import POTION_MEMO_SEP, POTION_NAME, POTION_NOTE_FMT, t

log = logging.getLogger(__name__)

NAME = POTION_NAME
NOTE_FMT = POTION_NOTE_FMT        # the menu note the role reads, e.g. "回 30% 体力"
MEMO_SEP = POTION_MEMO_SEP        # the human's own memo follows it: "回 30% 体力 · 慢慢喝"
MEMO_MAX = 60
PCT_MIN = 1
PCT_SANE = 1_000_000              # not a rule (there is no limit); only stops a slipped keystroke
TAKING_STALE_S = 60.0             # a bottle claimed this long ago with no outcome counts as drunk
BY_SELF, BY_HER = "self", "her"
PENDING, TAKING, USED = "pending", "taking", "used"


class PotionError(Exception):
    def __init__(self, text: str, code: str = "potion_error", rows: list[str] | None = None):
        super().__init__(text)
        self.text = text
        self.code = code
        self.rows = rows or []     # with code "gone": menu rows that were in fact already drunk


def _now() -> float:
    return clock.now()


# Whitespace ignored when recognising the name: exactly these five (space, tab, CR, LF, ideographic
# space). Any client that recognises the name must use the same set; "\s" differs between languages.
_BLANKS_RE = re.compile("[ \t\r\n　]+")


def _norm(s: str) -> str:
    return _BLANKS_RE.sub("", s or "").casefold()


def is_potion_meal(meal: str) -> bool:
    """Is this bite the potion (the whole text is the reserved name, ignoring blanks and case)?"""
    return _norm(meal) == _norm(NAME)


def is_potion_call(tool_name: str, tool_input) -> bool:
    """Is this tool call "drink the potion": an eat tool whose meal is the reserved name?
    Round settlement uses this to keep it out of both the meal and the work accounts."""
    if (tool_name or "").split("__")[-1] != "eat":
        return False
    return is_potion_meal(str((tool_input or {}).get("meal") or "")) if isinstance(tool_input, dict) else False


def _conn():
    return db.connect()


def _check_viewer(who: str) -> None:
    if not roles.valid(who):
        raise PotionError(t("role_bad", got=repr(who)), "bad_viewer")


def _check_pct(pct) -> int:
    try:
        n = int(pct)
    except (TypeError, ValueError):
        raise PotionError(t("potion_bad_pct_type"), "bad_pct") from None
    if n < PCT_MIN or n > PCT_SANE:
        raise PotionError(t("potion_bad_pct"), "bad_pct")
    return n


# Characters folded into one space in a memo: blanks and every kind of line break.
_MEMO_BLANKS_RE = re.compile("[ \t\r\n\x0b\x0c\x1c-\x1f\x85  　]+")


def clean_memo(memo) -> str:
    """The human's memo: one line, trimmed, cut to MEMO_MAX characters."""
    return _MEMO_BLANKS_RE.sub(" ", str(memo or "")).strip(" ")[:MEMO_MAX]


def note_for(pct: int, memo: str = "") -> str:
    """The note on the menu row: the amount, then the memo if there is one."""
    m = clean_memo(memo)
    return NOTE_FMT.format(pct=int(pct)) + (MEMO_SEP + m if m else "")


def _row(r) -> dict:
    return {"menu_row_id": r["menu_row_id"], "who": r["who"], "pct": int(r["pct"]),
            "memo": r["memo"] or "", "note": note_for(r["pct"], r["memo"]),
            "created_at": r["created_at"], "state": r["state"], "used_at": r["used_at"], "used_by": r["used_by"]}


def _settle_stale(conn, now: float) -> None:
    """Bottles claimed and then abandoned (the process died mid-way) count as drunk."""
    conn.execute("UPDATE potions SET state=?, used_at=taken_at WHERE state=? AND taken_at<?",
                 (USED, TAKING, now - TAKING_STALE_S))


# ── the human hangs / edits / removes ───────────────────────────────────

def register_potion(who: str, menu_row_id: str, pct, memo: str | None = None, now: float | None = None) -> dict:
    """Record the amount (and memo) for a potion row just put on the menu. Registering the same row
    again edits it, as long as it has not been drunk; memo=None leaves the memo as it was."""
    _check_viewer(who)
    if not stamina.enabled():
        raise PotionError(t("potion_stamina_off", potion=NAME), "stamina_off")
    rid = (menu_row_id or "").strip()
    if not rid or len(rid) > 80:
        raise PotionError(t("potion_bad_row"), "bad_row")
    n = _check_pct(pct)
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute("SELECT * FROM potions WHERE menu_row_id=?", (rid,)).fetchone()
        if r is not None and r["state"] != PENDING:
            conn.rollback()
            raise PotionError(t("potion_used"), "used")
        # The amount belongs to a potion row that is really on this role's menu, still undrunk.
        row = conn.execute("SELECT dish, for_who, eaten_at FROM menu WHERE id=?", (rid,)).fetchone()
        if row is None or row["for_who"] != who or row["eaten_at"] is not None or not is_potion_meal(row["dish"]):
            conn.rollback()
            raise PotionError(t("potion_no_row", potion=NAME), "bad_row")
        if r is None:
            conn.execute("INSERT INTO potions (menu_row_id, who, pct, memo, created_at) VALUES (?,?,?,?,?)",
                         (rid, who, n, clean_memo(memo), now or _now()))
        else:
            conn.execute("UPDATE potions SET pct=?, who=?, memo=? WHERE menu_row_id=?",
                         (n, who, r["memo"] if memo is None else clean_memo(memo), rid))
        conn.commit()
        return _row(conn.execute("SELECT * FROM potions WHERE menu_row_id=?", (rid,)).fetchone())
    finally:
        conn.close()


def hang(who: str, pct, memo: str | None = None, by: str = "human", now: float | None = None) -> dict:
    """Put a potion on the role's menu and record its amount, in one step: either both happen or
    neither does. Returns {"row": the menu row, "potion": the registered potion}."""
    import uuid

    _check_viewer(who)
    if not stamina.enabled():
        raise PotionError(t("potion_stamina_off", potion=NAME), "stamina_off")
    n = _check_pct(pct)
    now = now or _now()
    rid = uuid.uuid4().hex
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO menu (id, dish, note, by, for_who, eaten_at, created_at, updated_at)"
                     " VALUES (?,?,?,?,?,NULL,?,?)", (rid, NAME, note_for(n, memo or ""), str(by or "human"), who, now, now))
        conn.execute("INSERT INTO potions (menu_row_id, who, pct, memo, created_at) VALUES (?,?,?,?,?)",
                     (rid, who, n, clean_memo(memo), now))
        conn.commit()
        potion = _row(conn.execute("SELECT * FROM potions WHERE menu_row_id=?", (rid,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    from . import menu
    return {"row": menu.get(rid), "potion": potion}


def remove_potion(menu_row_id: str) -> bool:
    """The row was taken off the menu without being drunk: the bottle is void. Used ones stay."""
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM potions WHERE menu_row_id=? AND state=?",
                           ((menu_row_id or "").strip(), PENDING))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def pending(who: str) -> list[dict]:
    _check_viewer(who)
    conn = _conn()
    try:
        return [_row(r) for r in conn.execute(
            "SELECT * FROM potions WHERE who=? AND state=? ORDER BY created_at, menu_row_id",
            (who, PENDING)).fetchall()]
    finally:
        conn.close()


# ── drinking ────────────────────────────────────────────────────────────

def _pulse(who: str, delta: float, rule: str, now: float) -> float | None:
    """Add stamina. Returns the stamina after (0-1); None when it did not land. Never raises."""
    if delta <= 0:
        return None
    try:
        v = stamina.pulse(who, delta, now=now, rule=rule)
        return None if v is None else float(v)
    except Exception:  # noqa: BLE001
        log.warning("stamina was not added (%s)", rule, exc_info=True)
        return None


def _take_one(who: str, menu_row_ids: list[str], by: str, now: float) -> dict:
    """Drink one bottle: among these rows, the earliest registered one still pending.
    Claim it, add stamina, and only then mark it used; if stamina fails, put it back."""
    ids = list(dict.fromkeys(str(x).strip() for x in (menu_row_ids or []) if str(x).strip()))
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _settle_stale(conn, now)
        rows = [r for r in (conn.execute("SELECT * FROM potions WHERE menu_row_id=? AND who=?", (i, who)).fetchone()
                            for i in ids) if r is not None]
        if not rows:
            conn.commit()
            raise PotionError(t("potion_unregistered", potion=NAME), "unregistered")
        live = sorted((r for r in rows if r["state"] == PENDING), key=lambda r: (r["created_at"], r["menu_row_id"]))
        if not live:
            conn.commit()
            busy = any(r["state"] == TAKING for r in rows)
            raise PotionError(t("potion_busy", potion=NAME) if busy else t("potion_gone", potion=NAME),
                              "busy" if busy else "gone", rows=[r["menu_row_id"] for r in rows if r["state"] == USED])
        pick = live[0]
        conn.execute("UPDATE potions SET state=?, taken_at=? WHERE menu_row_id=?", (TAKING, now, pick["menu_row_id"]))
        conn.commit()
    finally:
        conn.close()
    rid, pct = pick["menu_row_id"], int(pick["pct"])
    v = _pulse(who, pct / 100.0, f"potion:{'fed' if by == BY_HER else 'drink'}({pct})", now)
    conn = _conn()
    try:
        if v is None:
            conn.execute("UPDATE potions SET state=?, taken_at=NULL WHERE menu_row_id=? AND state=?",
                         (PENDING, rid, TAKING))
            conn.commit()
            raise PotionError(t("potion_energy_down", potion=NAME), "energy")
        conn.execute("UPDATE potions SET state=?, used_at=?, used_by=?, energy_after=? WHERE menu_row_id=?",
                     (USED, now, by, v, rid))
        conn.commit()
    finally:
        conn.close()
    return {"menu_row_id": rid, "pct": pct, "energy": v}


def _effect(pct: int, v: float) -> str:
    return t("potion_effect", pct=pct, now=round(v * 100))


def drink(who: str, menu_row_ids: list[str], now: float | None = None) -> dict:
    """The role drinks. menu_row_ids = the menu rows carrying the reserved name; one bottle per call
    (the earliest). Returns {drunk: [row id], pct, energy, text}; raises PotionError with the sentence
    to show (code "gone" carries rows = menu rows that should be crossed off)."""
    _check_viewer(who)
    got = _take_one(who, menu_row_ids, BY_SELF, now or _now())
    return {"drunk": [got["menu_row_id"]], "pct": got["pct"], "energy": got["energy"],
            "text": t("potion_drunk", potion=NAME, effect=_effect(got["pct"], got["energy"]))}


def feed(who: str, menu_row_id: str, now: float | None = None) -> dict:
    """The human feeds a bottle directly. Returns {text (for the human), note (for the role), ...}."""
    _check_viewer(who)
    try:
        got = _take_one(who, [menu_row_id], BY_HER, now or _now())
    except PotionError as e:
        if e.code == "unregistered":
            raise PotionError(t("potion_feed_unregistered"), "unregistered") from None
        if e.code == "gone":
            raise PotionError(t("potion_feed_gone"), "gone", rows=e.rows) from None
        if e.code == "busy":
            raise PotionError(t("potion_feed_busy"), "busy") from None
        raise PotionError(t("potion_feed_energy_down"), "energy") from None
    effect = _effect(got["pct"], got["energy"])
    return {"menu_row_id": got["menu_row_id"], "pct": got["pct"], "energy": got["energy"],
            "text": t("potion_fed_her", effect=effect),
            "note": t("potion_fed_him", potion=NAME, effect=effect)}
