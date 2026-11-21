"""Cooking in real time.

- A pot stores started_at + duration_seconds; nothing ticks. Whoever reads
  the kitchen settles the pots that are due (served_at is the true due time,
  not the time of the read).
- Opening a pot takes ingredients from the role's fridge in the same
  transaction that creates the pot. Turning the heat off does not give them
  back.
- When a pot is served its result is fixed from the freshness of what went
  in: great / ok / burnt / spoiled. A hidden bad egg ruins the pot the moment
  it is cracked.
- Two follow-ups happen after serving and are driven by the periodic scan
  (:func:`process_due`): the dish goes onto the role's menu, and the role is
  told once.
- A dish left on the table overnight grows worms (:func:`process_worms`); so
  does fruit that spoils in the fridge. The worm crawls into a snack and is
  found when that snack is eaten.
"""
from __future__ import annotations

import json
import logging
import random
import sqlite3
import threading
import uuid
from datetime import timedelta

from . import clock, config, db, fridge, roles
from .texts import METHOD_LABELS, OUTCOME_LABEL, OUTCOME_NOTE, OUTCOME_SENTENCE, WORM_NOTE, WORM_SNACK_HEAD, t

log = logging.getLogger(__name__)

TOOL_COOK = "kitchen_cook"
TOOL_STATUS = "kitchen_status"
TOOL_CANCEL = "kitchen_cancel"
TOOL_TOSS = "kitchen_toss"

ATT_KIND = "kitchen_cooking"      # kind of the cooking-card attachment a successful cook returns

_DISH_MAX = 60
_NOTE_MAX = 200
_RECENT_N = 5

WAKE_SENT = "sent"                # delivered
WAKE_NOT_SENT = "not_sent"        # definitely did not happen: retry next scan
WAKE_UNKNOWN = "unknown"          # cannot tell: treated as delivered, never repeated

RECEIPT_SEEN, RECEIPT_WAITING, RECEIPT_GONE = "seen", "waiting", "gone"

WORM_DEFAULT_SNACK = "pudding"

# Opening a pot is "check for a same-name pot, take ingredients, create the pot": serialised per role.
_COOK_LOCKS: dict[str, threading.Lock] = {}
# The after-serving steps are "is the dish on the menu? if not, add it; mark the pot": serialised
# per role too, or two reads arriving together both see "not yet" and add the dish twice. Eating, and
# the role putting a dish on its own menu, take the same lock (see menu.eat, POST /api/menu).
_DUE_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _cfg():
    return config.get()


def _now() -> float:
    return clock.now()


def _hm(ts: float) -> str:
    return clock.hm(ts)


def _conn() -> sqlite3.Connection:
    return db.connect()


def _cook_lock(who: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _COOK_LOCKS.setdefault(who, threading.Lock())


def due_lock(who: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _DUE_LOCKS.setdefault(who, threading.Lock())


# ── settling (on read) ──────────────────────────────────────────────────

def _settle_due(conn: sqlite3.Connection, who: str) -> None:
    """Pots past their time become served, with served_at = the true due time.
    The update is conditional, so a concurrent cancel and a settle cannot both win."""
    now = _now()
    conn.execute(
        "UPDATE cook_sessions SET status='served', served_at=started_at+duration_seconds"
        " WHERE who=? AND status='cooking' AND started_at+duration_seconds<=?", (who, now))
    for r in conn.execute("SELECT id, ingredients_json FROM cook_sessions"
                          " WHERE who=? AND status='served' AND outcome IS NULL", (who,)).fetchall():
        conn.execute("UPDATE cook_sessions SET outcome=? WHERE id=? AND outcome IS NULL",
                     (fridge.decide_outcome(r["id"], _ingredients(r)), r["id"]))
    conn.commit()
    # The upgrade: each pot served from now on gets its settlement, once (proficiency, orders,
    # achievements). A failure here never undoes the serving; the next read tries again.
    try:
        from . import progress
        progress.settle_due(conn, who, now)
    except Exception:  # noqa: BLE001
        log.warning("settling a served pot failed (tried again on the next read)", exc_info=True)
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass


def _ingredients(r) -> list[dict]:
    try:
        return json.loads(r["ingredients_json"] or "[]")
    except Exception:  # noqa: BLE001
        return []


def _fmt_remaining(sec: float) -> str:
    sec = max(0, int(sec))
    if sec < 60:
        return t("remain_seconds", s=sec)
    m, s = divmod(sec, 60)
    if m < 60:
        return t("remain_minutes", m=m) if s == 0 else t("remain_minutes_seconds", m=m, s=s)
    h, m = divmod(m, 60)
    return t("remain_hours", h=h) if m == 0 else t("remain_hours_minutes", h=h, m=m)


def _row_dict(r: sqlite3.Row, now: float) -> dict:
    d = dict(r)
    d["ingredients"] = [{"name": u.get("name"), "qty": u.get("qty"), "freshness": u.get("freshness")}
                        for u in _ingredients(r)]
    d.pop("ingredients_json", None)
    d["method"] = _method_of(r)
    if r["status"] == "cooking":
        d["remaining_seconds"] = max(0, int(r["started_at"] + r["duration_seconds"] - now))
    else:
        d["remaining_seconds"] = 0
    return d


# ── cooking method ──────────────────────────────────────────────────────
# The cooking animation comes in seven kinds. The role may name one when opening a pot;
# otherwise it is guessed from the characters in the dish name, falling back to stir-fry.

METHODS = dict(zip(METHOD_LABELS, ("stirfry", "fry", "deepfry", "boil", "steam", "bake", "mix")))
METHOD_DEFAULT = "stirfry"
# Technique characters win by earliest position in the name; the "boil" family is checked after.
_METHOD_VERBS = (("stirfry", ("炒", "烹", "爆", "熘")), ("fry", ("煎", "烙", "贴")), ("deepfry", ("炸", "酥")),
                 ("steam", ("蒸",)), ("bake", ("烤", "焗")), ("mix", ("拌", "沙拉", "凉")))
_METHOD_BOIL = ("煮", "汤", "炖", "焖", "烧", "粥", "面", "卤", "羹", "煲", "涮", "锅")
# Words whose characters are not a technique (炸酱面 is boiled; 锅贴 is handled by name below).
_METHOD_NOT_VERB = ("炸酱", "锅贴", "酥油", "凉茶")
# Well-known dish names are matched first (otherwise the 烧 in 烧麦 would read as "boil").
_METHOD_NAMES = (("steam", ("烧麦", "烧卖", "叉烧包", "包子", "馒头", "小笼", "肠粉", "花卷", "粽")),
                 ("bake", ("叉烧", "烧鹅", "烧鸭", "烧鸡", "披萨", "蛋挞", "面包", "蛋糕", "饼干")),
                 ("fry", ("锅贴", "荷包蛋", "煎蛋", "牛排", "铜锣烧", "松饼")),
                 ("mix", ("寿司", "三明治", "刺身")))


def guess_method(dish: str) -> str:
    """Guess the method from the dish name; stir-fry when nothing matches."""
    d = dish or ""
    for key, words in _METHOD_NAMES:
        if any(w in d for w in words):
            # A name that also carries its own technique character (蒸饺, 炸馒头) is decided below.
            if not any(v in d for _k, vs in _METHOD_VERBS for v in vs if v not in ("酥", "凉", "贴")):
                return key
    for w in _METHOD_NOT_VERB:
        d = d.replace(w, "＿" * len(w))
    best = None
    for key, words in _METHOD_VERBS:
        for w in words:
            i = d.find(w)
            if i >= 0 and (best is None or i < best[0]):
                best = (i, key)
    if best:
        return best[1]
    if any(w in d for w in _METHOD_BOIL):
        return "boil"
    return METHOD_DEFAULT


def resolve_method(given, dish: str) -> str | None:
    """The chosen method (one Chinese character, or a key) -> key. Not chosen = guessed;
    chosen but unknown = None, for the caller to report."""
    g = str(given or "").strip()
    if not g:
        return guess_method(dish)
    if g in METHODS:
        return METHODS[g]
    return g if g in METHODS.values() else None


def _method_of(r) -> str:
    try:
        m = r["method"]
    except (KeyError, IndexError):
        m = None
    return m if m in METHODS.values() else guess_method(r["dish"])


def _card_entry(r: sqlite3.Row | dict) -> dict:
    """The cooking-card attachment: only the facts needed to draw it. The countdown and the
    move from "on the fire" to "served" are computed by whoever displays the card."""
    return {
        "kind": ATT_KIND,
        "session_id": r["id"],
        "who": r["who"],
        "dish": r["dish"],
        "note": r["note"] or "",
        "duration_seconds": r["duration_seconds"],
        "started_at": r["started_at"],
        "method": _method_of(r),
    }


# ── tool schemas ────────────────────────────────────────────────────────

def tool_schemas() -> list[dict]:
    from . import playkit
    return playkit.adjust_cook_schema(_base_tool_schemas()) + playkit.browse_schema()


def _base_tool_schemas() -> list[dict]:
    lo, hi = _cfg().kitchen_minutes_min, _cfg().kitchen_minutes_max
    return [
        {
            "name": TOOL_COOK,
            "description": t("tool_cook", min=lo, max=hi, eat=t("tool_cook_eat"),
                             wake=t("tool_cook_wake") or "。"),   # notify.mode "none": nobody is told
            "input_schema": {
                "type": "object",
                "properties": {
                    "dish": {"type": "string", "description": t("tool_cook_dish")},
                    "minutes": {"type": "integer", "minimum": lo, "maximum": hi,
                                "description": t("tool_cook_minutes")},
                    "note": {"type": "string", "description": t("tool_cook_note")},
                    "method": {"type": "string", "enum": list(METHOD_LABELS),
                               "description": t("tool_cook_method")},
                    "ingredients": {"type": "array", "items": {"type": "string"},
                                    "description": t("tool_cook_ingredients")},
                },
                "required": ["dish", "minutes", "ingredients"],
                "additionalProperties": False,
            },
        },
        {
            "name": TOOL_STATUS,
            "description": t("tool_status"),
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": TOOL_CANCEL,
            "description": t("tool_cancel"),
            "input_schema": {
                "type": "object",
                "properties": {"dish": {"type": "string", "description": t("tool_cancel_dish")}},
                "additionalProperties": False,
            },
        },
        {
            "name": TOOL_TOSS,
            "description": t("tool_toss"),
            "input_schema": {
                "type": "object",
                "properties": {"what": {"type": "string", "description": t("tool_toss_what")}},
                "required": ["what"],
                "additionalProperties": False,
            },
        },
    ]


# ── tool bodies: each returns (text, is_error) ──────────────────────────

def _cooking_rows(conn: sqlite3.Connection, who: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cook_sessions WHERE who=? AND status='cooking' ORDER BY started_at", (who,)).fetchall()


def _parse_ingredients(raw) -> list[tuple[str, int]] | None:
    """ingredients may be a list (preferred) or one line of text; any other shape = None."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return fridge.parse_list(raw)
    if isinstance(raw, list):
        out: list[tuple[str, int]] = []
        for x in raw:
            if not isinstance(x, str):
                return None
            out += fridge.parse_list(x)
        return out
    return None


def _exec_cook(collector: list | None, args: dict, who: str) -> tuple[str, bool]:
    if not roles.valid(who):
        return t("cook_role_unknown"), True
    with _cook_lock(who):
        return _exec_cook_locked(collector, args, who)


def _exec_cook_locked(collector: list | None, args: dict, who: str) -> tuple[str, bool]:
    lo, hi = _cfg().kitchen_minutes_min, _cfg().kitchen_minutes_max
    dish = str(args.get("dish") or "").strip()
    note = str(args.get("note") or "").strip()
    raw_min = args.get("minutes")
    if not dish:
        return t("cook_no_dish"), True
    if len(dish) > _DISH_MAX:
        return t("cook_dish_long", max=_DISH_MAX), True
    if len(note) > _NOTE_MAX:
        return t("cook_note_long", max=_NOTE_MAX), True
    # bool is a subclass of int: True would pass as "1 minute", so refuse it explicitly
    if isinstance(raw_min, bool) or not isinstance(raw_min, (int, float)) or int(raw_min) != raw_min:
        return t("cook_minutes_type", min=lo, max=hi, got=repr(raw_min)), True
    minutes = int(raw_min)
    if not (lo <= minutes <= hi):
        return t("cook_minutes_range", min=lo, max=hi, got=minutes), True
    wanted = _parse_ingredients(args.get("ingredients"))
    if wanted is None:
        return t("cook_ingredients_shape"), True
    method = resolve_method(args.get("method"), dish)
    if method is None:
        return t("cook_method_bad", labels=" / ".join(METHOD_LABELS), got=str(args.get("method"))[:10]), True
    from . import play
    from .texts_play import tp
    raw_recipe = str(args.get("recipe") or "").strip()
    if raw_recipe and not play.on("recipe_cook"):
        return tp("feature_off"), True
    try:
        conn = _conn()
    except Exception as e:  # noqa: BLE001
        return t("cook_db_open", err=type(e).__name__), True
    used: list[dict] = []
    recipe = None
    link = "free"
    changed_missing: list[str] = []
    egg_note = ""
    try:
        _settle_due(conn, who)
        now = _now()
        for r in _cooking_rows(conn, who):
            if r["dish"] == dish:
                # Idempotent retry: a pot of the same name already on the fire is returned as is,
                # with its card, instead of opening a second one or taking ingredients twice.
                remain = r["started_at"] + r["duration_seconds"] - now
                if collector is not None:
                    collector.append(_card_entry(r))
                return t("cook_already", dish=dish, started=_hm(r["started_at"]),
                         remain=_fmt_remaining(remain)), False
        if raw_recipe:
            # Cooking by a recipe: the ingredients are still exactly what the role wrote; the recipe
            # is only compared with them. An id that is not found opens nothing.
            from . import book, recipes
            recipe = book.resolve_ref(conn, who, raw_recipe)
            if recipe is None:
                return tp("cook_no_recipe"), True
            if recipe.get("kind") == "menu":
                return tp("cook_menu", name=recipe["name"]), True
            want_ids: dict[str, int] = {}
            for nm, n in wanted:
                if fridge.is_staple(nm):
                    continue
                iid = fridge.resolve(nm, gone=True)
                if iid:
                    want_ids[iid] = want_ids.get(iid, 0) + n
            changed_missing = recipes.covers(recipe["main"], want_ids)
            link = "changed" if changed_missing else "follow"
            if not str(args.get("method") or "").strip():
                method = recipe["method"]
        guard = False
        if play.on("proficiency"):
            from . import progress
            guard = progress.tier_now(conn, who, link, recipe["identity"] if recipe else None, dish) != "生疏"
        sid = uuid.uuid4().hex
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("SAVEPOINT play_cook")
            used = fridge.take_in_tx(conn, who, wanted, now)
            # A hidden-freshness item that turns out spoiled ruins the pot on the spot:
            # the ingredients are gone, nothing is served, nothing reaches the menu.
            bad_eggs = [u for u in used
                        if fridge.hidden_freshness(u["item_id"]) and u["freshness"] == fridge.BAD]
            if bad_eggs and guard:
                # A practised hand cracks each egg into a bowl first: only the bad ones are thrown away.
                used, egg_note, fail = _egg_guard(conn, who, used, now)
                if fail is not None:
                    conn.commit()
                    return fail, True
                bad_eggs = []
            conn.execute("RELEASE play_cook")
            conn.execute(
                "INSERT INTO cook_sessions (id, who, dish, note, duration_seconds,"
                " started_at, status, created_at, ingredients_json, outcome, served_at, method)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, who, dish, note, minutes * 60, now,
                 "ruined" if bad_eggs else "cooking", now, json.dumps(used, ensure_ascii=False),
                 "ruined" if bad_eggs else None, now if bad_eggs else None, method))
            if bad_eggs:
                fridge._log(conn, who, "ruined", t("log_ruined", dish=dish), now)
            if play.any_on("recipe_cook", "proficiency", "mishaps", "orders", "settle_card", "dex"):
                from . import progress
                progress.on_cook_start(conn, who=who, sid=sid, dish=dish, method=method, recipe=recipe,
                                       link=link, ruined=bool(bad_eggs), now=now)
        except fridge.FridgeError as fe:
            conn.rollback()
            text = fe.text
            if recipe is not None and fe.code == "short":
                text += _recipe_short_suffix(conn, who, recipe, now)
            return text, True
        except Exception:
            conn.rollback()
            raise
        conn.commit()
        if bad_eggs:
            box = bad_eggs[0]
            left = conn.execute("SELECT COALESCE(SUM(qty),0) FROM batches WHERE id=? AND who=?",
                                (box["batch_id"], who)).fetchone()[0]
            return ruined_text(dish, now, used, fridge.bought_md(float(box["bought_at"])), int(left)), False
        row = conn.execute("SELECT * FROM cook_sessions WHERE id=?", (sid,)).fetchone()
        n_on = len(_cooking_rows(conn, who))
    except Exception as e:  # noqa: BLE001
        return t("cook_db_write", err=type(e).__name__), True
    finally:
        conn.close()
    text = t("cook_ok", dish=dish, started=_hm(now), minutes=minutes,
             served=_hm(now + minutes * 60), used=_used_text(used))
    if n_on > 1:
        text += t("cook_ok_count", n=n_on)
    if egg_note:
        text += egg_note
    if recipe is not None and link == "changed":
        from . import recipes
        from .texts import markers_on
        text += tp("cook_changed" if markers_on() else "cook_changed_tools", name=recipe["name"],
                   missing="、".join(recipes.item_name(i) for i in changed_missing))
    if collector is not None:
        collector.append(_card_entry(row))
    return text, False


def _recipe_short_suffix(conn, who: str, recipe: dict, now: float) -> str:
    """Not enough in the fridge while cooking by a recipe: also say what that recipe still lacks."""
    try:
        from . import recipes
        from .texts_play import tp
        short = recipes.feasibility([recipe["main"]], recipes.fridge_snapshot(fridge._batches(conn, who, now)))["short"]
        return tp("cook_recipe_short", name=recipe["name"], missing=recipes.short_text(short)) if short else ""
    except Exception:  # noqa: BLE001
        return ""


def _egg_guard(conn, who: str, used: list[dict], now: float) -> tuple[list[dict], str, str | None]:
    """A bad egg met by a practised hand: the bad ones already cracked are thrown away (not put back),
    as many are taken again, and again while those are bad, until the eggs are good or there are none.
    Enough -> (new list used, sentence, None). Not enough -> back to before the pot (everything else
    restored), only the cracked bad eggs are gone, one log line -> (used, "", refusal). The caller commits."""
    from .texts_play import tp

    def bad(u):
        return fridge.hidden_freshness(u["item_id"]) and u["freshness"] == fridge.BAD
    nth = 1
    for u in used:
        if not fridge.hidden_freshness(u["item_id"]):
            continue
        if bad(u):
            break
        nth += u["qty"]
    opened_bad = [u for u in used if bad(u)]
    good = [u for u in used if not bad(u)]
    need = sum(u["qty"] for u in opened_bad)
    egg_name = fridge.item(opened_bad[0]["item_id"])["name"]
    while need > 0:
        try:
            more = fridge.take_in_tx(conn, who, [(egg_name, need)], now)
        except fridge.FridgeError:
            conn.execute("ROLLBACK TO play_cook")
            for u in opened_bad:
                conn.execute("UPDATE batches SET qty=qty-? WHERE id=? AND who=?", (u["qty"], u["batch_id"], who))
            conn.execute("DELETE FROM batches WHERE who=? AND qty<=0", (who,))
            conn.execute("RELEASE play_cook")
            fridge._log(conn, who, "egg_tossed", tp("log_egg_tossed_none", n=sum(u["qty"] for u in opened_bad)), now)
            return used, "", tp("egg_no_spare")
        newbad = [u for u in more if bad(u)]
        good += [u for u in more if not bad(u)]
        opened_bad += newbad
        need = sum(u["qty"] for u in newbad)
    n_bad = sum(u["qty"] for u in opened_bad)
    first = opened_bad[0]
    left = conn.execute("SELECT COALESCE(SUM(qty),0) FROM batches WHERE id=? AND who=?",
                        (first["batch_id"], who)).fetchone()[0]
    box = fridge.bought_md(float(first["bought_at"]))
    fridge._log(conn, who, "egg_tossed", tp("log_egg_tossed", n=n_bad), now)
    note = (tp("egg_saved", nth=nth, box=box, left=int(left)) if n_bad == 1
            else tp("egg_saved_many", n=n_bad, box=box, left=int(left)))
    merged: dict[str, dict] = {}
    for u in good:
        k = u["batch_id"]
        merged[k] = {**merged[k], "qty": merged[k]["qty"] + u["qty"]} if k in merged else dict(u)
    return list(merged.values()), note, None


def ruined_text(dish: str, now: float, used: list[dict], box_md: str, left: int) -> str:
    """What the role is told the moment a spoiled egg ruins the pot."""
    choice = t("ruined_left", left=left, box=box_md) if left > 0 else t("ruined_none_left")
    return t("ruined", dish=dish, hm=_hm(now), box=box_md, used=_used_text(used)) + choice


def _used_text(used: list[dict]) -> str:
    parts = []
    for u in used:
        tag = (fridge.tag_for_him(u["item_id"], u.get("freshness") or fridge.FRESH, float(u["bought_at"]))
               if u.get("item_id") and u.get("bought_at") else "")
        parts.append(f"{u['name']}×{u['qty']}{tag}")
    return "、".join(parts) or t("cook_used_none")


def _exec_status(args: dict, who: str) -> tuple[str, bool]:
    try:
        conn = _conn()
    except Exception as e:  # noqa: BLE001
        return t("status_unavailable", err=type(e).__name__), True
    try:
        _settle_due(conn, who)
        now = _now()
        on = _cooking_rows(conn, who)
        recent = conn.execute(
            "SELECT * FROM cook_sessions WHERE who=? AND status='served'"
            " ORDER BY served_at DESC LIMIT ?", (who, _RECENT_N)).fetchall()
    except Exception as e:  # noqa: BLE001
        return t("status_unavailable", err=type(e).__name__), True
    finally:
        conn.close()
    lines: list[str] = []
    if on:
        lines.append(t("status_on_fire", n=len(on)))
        for r in on:
            remain = r["started_at"] + r["duration_seconds"] - now
            line = t("status_pot", dish=r["dish"], started=_hm(r["started_at"]),
                     minutes=r["duration_seconds"] // 60, remain=_fmt_remaining(remain))
            if r["note"]:
                line += t("status_pot_note", note=r["note"])
            lines.append(line)
    else:
        lines.append(t("status_no_pot"))
    if recent:
        lines.append(t("status_recent"))
        for r in recent:
            day = clock.local(r["served_at"]).strftime("%m-%d")
            res = WORM_NOTE if r["wormed_at"] else OUTCOME_LABEL.get(r["outcome"] or "", "")
            lines.append(t("status_recent_row", dish=r["dish"], day=day, hm=_hm(r["served_at"]),
                           minutes=r["duration_seconds"] // 60)
                         + (t("status_recent_result", result=res) if res and r["outcome"] != fridge.OK else ""))
    try:
        lines.append(fridge.status_text(who, now))
    except Exception as e:  # noqa: BLE001
        lines.append(t("status_fridge_unavailable", err=type(e).__name__))
    return "\n".join(lines), False


def _exec_toss(args: dict, who: str) -> tuple[str, bool]:
    """Toss right now: a wormy dish on the table first, otherwise something in the fridge."""
    what = str(args.get("what") or "")
    key = uuid.uuid4().hex
    try:
        return (toss_wormed_dish(who, what, key=key) or fridge.toss_self(who, what, key=key)), False
    except fridge.FridgeError as fe:
        return fe.text, True
    except Exception as e:  # noqa: BLE001
        return t("toss_store_failed", err=type(e).__name__), True


def _exec_cancel(args: dict, who: str) -> tuple[str, bool]:
    dish = str(args.get("dish") or "").strip()
    try:
        conn = _conn()
    except Exception as e:  # noqa: BLE001
        return t("cancel_db_open", err=type(e).__name__), True
    try:
        _settle_due(conn, who)
        now = _now()
        on = _cooking_rows(conn, who)
        if not on:
            return t("cancel_no_pot"), True
        names = "、".join(t("dish_quoted", dish=r["dish"]) for r in on)
        if dish:
            hit = [r for r in on if r["dish"] == dish]
            if not hit:
                return t("cancel_not_found", dish=dish, names=names), True
            target = hit[0]
        elif len(on) == 1:
            target = on[0]
        else:
            return t("cancel_which", n=len(on), names=names), True
        cur = conn.execute(
            "UPDATE cook_sessions SET status='cancelled', cancelled_at=?"
            " WHERE id=? AND status='cooking'", (now, target["id"]))
        if cur.rowcount == 1:
            from . import progress
            progress.on_cancel(conn, target["id"], now)
        conn.commit()
        if cur.rowcount != 1:
            return t("cancel_too_late", dish=target["dish"]), True
    except Exception as e:  # noqa: BLE001
        return t("cancel_db_write", err=type(e).__name__), True
    finally:
        conn.close()
    return t("cancel_ok", dish=target["dish"]), False


def local_tools(collector: list | None = None, who: str | None = None) -> dict:
    """name -> callable(args) -> (text, is_error). collector receives cooking-card attachments;
    None means pots still open, just without a card. An invalid role gets no tools."""
    if not roles.valid(who):
        return {}
    from . import playkit
    out = {
        TOOL_COOK: lambda args: _exec_cook(collector, args or {}, who),
        TOOL_STATUS: lambda args: _exec_status(args or {}, who),
        TOOL_CANCEL: lambda args: _exec_cancel(args or {}, who),
        TOOL_TOSS: lambda args: _exec_toss(args or {}, who),
    }
    if playkit.browse_schema():
        out[playkit.TOOL_BROWSE] = lambda args: playkit.browse(who, args or {})
    return out


# ── what the page reads ─────────────────────────────────────────────────

def overview(who: str | None = None, session_id: str | None = None) -> dict:
    """{now, cooking, recent} for a role, or {now, session} for one pot by id."""
    conn = _conn()
    try:
        now = _now()
        if session_id:
            r = conn.execute("SELECT * FROM cook_sessions WHERE id=?", (session_id,)).fetchone()
            if r is not None:
                _settle_due(conn, r["who"])
                r = conn.execute("SELECT * FROM cook_sessions WHERE id=?", (session_id,)).fetchone()
            out = {"now": now, "timezone": _cfg().server_timezone, "session": _row_dict(r, now) if r else None}
            if r is not None:
                from . import play, progress
                if play.on("settle_card"):
                    try:
                        out["settlement"] = progress.card(conn, session_id)
                    except Exception:  # noqa: BLE001
                        log.warning("reading the settled card failed", exc_info=True)
                        out["settlement"] = {"has": False, "why": "error"}
            return out
        roles.check(who)
        _settle_due(conn, who)
        on = _cooking_rows(conn, who)
        recent = conn.execute(
            "SELECT * FROM cook_sessions WHERE who=? AND status IN ('served','cancelled')"
            " ORDER BY COALESCE(served_at, cancelled_at) DESC LIMIT 50", (who,)).fetchall()
        return {"now": now, "timezone": _cfg().server_timezone, "cooking": [_row_dict(r, now) for r in on],
                "recent": [_row_dict(r, now) for r in recent]}
    finally:
        conn.close()


# ── after serving: menu + telling the role ──────────────────────────────

def due_work(who: str) -> list[dict]:
    """Served pots whose "onto the menu" or "tell the role" step is still open, oldest first.
    Settles first: the periodic scan calling this is what makes pots come due on time."""
    conn = _conn()
    try:
        _settle_due(conn, who)
        rows = conn.execute(
            "SELECT * FROM cook_sessions WHERE who=? AND status='served'"
            " AND (woke_at IS NULL OR (menu_added_at IS NULL AND served_at>?))"
            " ORDER BY served_at", (who, _now() - _cfg().kitchen_menu_retry_max_seconds)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_menu_added(session_id: str, menu_row_id: str | None) -> None:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE cook_sessions SET menu_added_at=?, menu_row_id=?"
            " WHERE id=? AND menu_added_at IS NULL", (_now(), menu_row_id, session_id))
        conn.commit()
    finally:
        conn.close()


def mark_woke(session_id: str) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE cook_sessions SET woke_at=? WHERE id=? AND woke_at IS NULL",
                     (_now(), session_id))
        conn.commit()
    finally:
        conn.close()


def outcome_sentence(outcome: str | None) -> str:
    return OUTCOME_SENTENCE.get(outcome or "", "")


def served_body(sessions: list[dict], menu_ok: bool = True, sep: str = "\n") -> str:
    """"Your dish is ready", one line per pot, facts only."""
    lines = [t("served_line", started=_hm(s["started_at"]), dish=s["dish"],
               minutes=s["duration_seconds"] // 60) + outcome_sentence(s.get("outcome"))
             for s in sessions]
    return sep.join(lines) + (t("served_menu_ok") if menu_ok else t("served_menu_failed"))


def build_wake_message(sessions: list[dict], menu_ok: bool = True) -> str:
    """served_body behind the kitchen header, for delivery as a message of its own.
    menu_ok=False says plainly that the dish never made it onto the menu."""
    return t("head") + served_body(sessions, menu_ok)


def menu_note(s: dict) -> str:
    """Note for the menu row: the pot's own note plus the result word (none for a plain result)."""
    parts = [p for p in ((s.get("note") or "").strip(), OUTCOME_NOTE.get(s.get("outcome") or "", "")) if p]
    return " · ".join(parts)


def served_extra(s: dict) -> str:
    """The upgrade's sentences after "your dish is ready" (a mishap, a tier change); empty when off."""
    if not s.get("id"):
        return ""
    try:
        from . import progress
        return "".join(progress.served_lines(s["id"]))
    except Exception:  # noqa: BLE001
        log.warning("the sentences after serving could not be read", exc_info=True)
        return ""


def served_event_payload(s: dict, menu_ok: bool) -> dict:
    out = {"dish": s["dish"], "started_hm": _hm(s["started_at"]),
           "minutes": str(s["duration_seconds"] // 60), "menu_ok": "1" if menu_ok else "0",
           "outcome": s.get("outcome") or ""}
    extra = served_extra(s)
    if extra:
        out["extra"] = extra[:160]
    return out


def process_due(*, find_menu, add_menu, wake, float_event, in_quiet: bool, busy,
                who: str, round_running=lambda: False) -> dict:
    """Run the after-serving steps for one role. Everything external is injected.

    find_menu(session) -> row id | None   is this pot's dish already on the menu?
    add_menu(session) -> row id           put it there; raises on failure
    wake(message) -> WAKE_*               deliver a message of its own, right now
    float_event(session, menu_ok)         queue a note that rides along with the next turn; raises on
                                          failure; must be safe to repeat (deduplicated by pot id)
    busy() -> bool                        the human is talking to the role right now
    round_running() -> bool               the role is mid-turn: wait rather than interrupt
    in_quiet                              quiet hours, or the role is asleep: hold the wake

    Two ways to tell the role, one per pot: if the human is talking, do not take a turn, queue the
    note; otherwise wake. Idempotency: the menu is read back before adding (a timed-out add may
    have landed); a wake is at most once (only WAKE_NOT_SENT is retried). Calls for the same role
    run one at a time (the periodic scan and every read call this), so a dish is added once.
    """
    with due_lock(who):
        return _process_due_locked(find_menu=find_menu, add_menu=add_menu, wake=wake,
                                   float_event=float_event, in_quiet=in_quiet, busy=busy,
                                   who=who, round_running=round_running)


def _process_due_locked(*, find_menu, add_menu, wake, float_event, in_quiet: bool, busy,
                        who: str, round_running) -> dict:
    out = {"menu_added": 0, "menu_failed": 0, "woke": 0, "floated": 0, "deferred": ""}
    due = due_work(who)
    if not due:
        return out
    now = _now()
    eaten = [s for s in due if s.get("eaten_at") is not None and s["menu_added_at"] is None]
    for s in eaten:          # eaten before it reached the menu: never add it, or it could be eaten twice
        mark_menu_added(s["id"], None)
        mark_woke(s["id"])
    due = [s for s in due if s not in eaten]
    for s in due:
        if s["menu_added_at"] is not None or now - s["served_at"] > _cfg().kitchen_menu_retry_max_seconds:
            continue
        try:
            rid = find_menu(s)
            if rid is None:
                rid = add_menu(s)
            mark_menu_added(s["id"], str(rid) if rid is not None else None)
            s["menu_added_at"] = now
            s["menu_row_id"] = str(rid) if rid is not None else None
            out["menu_added"] += 1
        except Exception as e:  # noqa: BLE001
            out["menu_failed"] += 1
            log.warning("could not put %r on the menu, retrying next scan: %r", s["dish"], e)

    ready = [s for s in due if s["woke_at"] is None and s["menu_added_at"] is not None]
    gave_up = [s for s in due if s["woke_at"] is None and s["menu_added_at"] is None
               and now - s["served_at"] >= _cfg().kitchen_menu_giveup_seconds]
    if not ready and not gave_up:
        return out
    if busy():
        for batch, menu_ok in ((ready, True), (gave_up, False)):
            for s in batch:
                try:
                    float_event(s, menu_ok)
                except Exception as e:  # noqa: BLE001
                    log.warning("could not queue the note for %r, retrying next scan: %r", s["dish"], e)
                    continue
                mark_woke(s["id"])
                out["floated"] += 1
        return out
    if round_running():
        out["deferred"] = "round"
        return out
    if in_quiet:
        out["deferred"] = "quiet"
        return out
    for batch, menu_ok in ((ready, True), (gave_up, False)):
        if not batch:
            continue
        res = wake(build_wake_message(batch, menu_ok=menu_ok))
        if res == WAKE_NOT_SENT:
            log.warning("wake not delivered, retrying next scan (%d pots)", len(batch))
            continue
        if res == WAKE_UNKNOWN:
            log.warning("wake result unclear, treating as delivered (%d pots)", len(batch))
        for s in batch:
            mark_woke(s["id"])
        out["woke"] += len(batch)
    return out


# ── worms ───────────────────────────────────────────────────────────────
# A served dish still on the table after the worm hour, having sat long enough, grows worms: its
# result becomes "spoiled" (eating it anyway causes dizziness) and its menu note says so. The worm
# crawls into one snack, chosen when it appears (at most one pending per role); the role finds it on
# eating that snack. Fruit that spoils in the fridge does the same. The role is never told where the
# worm went. worm_state: NULL -> skipped (no longer on the table) / wormed -> noted (menu note
# written) -> tossed -> gone (menu row removed).

def worm_due_at(served_at: float) -> float:
    """Earliest time this dish counts as "left overnight": the next worm hour, and old enough."""
    d = clock.local(served_at)
    cut = d.replace(hour=_cfg().kitchen_worm_day_hour, minute=0, second=0, microsecond=0)
    if d >= cut:
        cut += timedelta(days=1)
    return max(cut.timestamp(), served_at + _cfg().kitchen_worm_min_age_hours * 3600.0)


def worm_text(dish: str, made_at: float, snack: str = WORM_DEFAULT_SNACK, source: str = "dish") -> str:
    """The sentence for biting into the worm: which dish (or fruit) it crawled over from."""
    d = clock.local(made_at)
    where = (t("worm_where_fruit", month=d.month, day=d.day) if source == "fruit"
             else t("worm_where_dish", month=d.month, day=d.day, hour=d.hour, minute=d.minute))
    return t("worm", head=WORM_SNACK_HEAD[snack], where=where, dish=dish)


def _worm_snack(who: str) -> str | None:
    """Which snack the worm goes into: random among those on the shelf today.
    None when none can be eaten (the worm would sit there forever)."""
    from . import snacks
    picks = [s for s in WORM_SNACK_HEAD if snacks.known(s)]
    try:
        caps = snacks.caps_for_viewer(who)
        picks = [s for s in picks if caps.get(s, 1) > 0]
    except Exception:  # noqa: BLE001
        log.warning("could not read snack caps; treating every snack as available", exc_info=True)
    return random.choice(picks) if picks else None


def _worm_into_snack(conn, who: str, source_id: str, name: str, made_at: float, source: str, now: float) -> None:
    snack = _worm_snack(who)
    if snack is None:
        return
    conn.execute("INSERT OR IGNORE INTO worm_pending (who, session_id, dish, made_at, at, snack, source)"
                 " VALUES (?,?,?,?,?,?,?)", (who, source_id, name, made_at, now, snack, source))


def worm_menu_note(s: dict) -> str:
    return " · ".join(p for p in ((s.get("note") or "").strip(), WORM_NOTE) if p)


def process_worms(*, list_table, set_note, remove_row, who: str, now: float | None = None) -> dict:
    """Grow worms and keep the menu in step. list_table() -> ids of menu rows still on the table
    (raising = skip this scan); set_note(row_id, note) / remove_row(row_id) write the menu and may
    raise to be retried next scan."""
    out = {"wormed": 0, "skipped": 0, "noted": 0, "removed": 0}
    if not _cfg().kitchen_worm_enabled:
        return out
    now = now or _now()
    conn = _conn()
    try:
        _settle_due(conn, who)
        since = conn.execute("SELECT at FROM once_keys WHERE key='worm_since'").fetchone()["at"]
        cands = [r for r in conn.execute(
            "SELECT id, dish, served_at, menu_row_id FROM cook_sessions WHERE who=? AND status='served'"
            " AND eaten_at IS NULL AND worm_state IS NULL AND menu_row_id IS NOT NULL AND served_at>=?"
            " ORDER BY served_at", (who, since)).fetchall() if now >= worm_due_at(float(r["served_at"]))]
        table: set[str] = set()
        if cands:
            try:
                table = {str(x) for x in list_table()}
            except Exception as e:  # noqa: BLE001
                log.warning("cannot see the table; not judging worms this scan: %r", e)
                cands = []
        for r in cands:
            conn.execute("BEGIN IMMEDIATE")
            if str(r["menu_row_id"]) not in table:     # eaten or taken down: the table is the truth
                conn.execute("UPDATE cook_sessions SET worm_state='skipped' WHERE id=? AND worm_state IS NULL",
                             (r["id"],))
                out["skipped"] += 1
            elif conn.execute("UPDATE cook_sessions SET worm_state='wormed', wormed_at=?, outcome=?"
                              " WHERE id=? AND worm_state IS NULL AND eaten_at IS NULL",
                              (now, fridge.SPOILED, r["id"])).rowcount:
                _worm_into_snack(conn, who, r["id"], r["dish"], float(r["served_at"]), "dish", now)
                fridge._log(conn, who, "wormed", t("log_wormed_dish", dish=r["dish"]), now)
                out["wormed"] += 1
            conn.commit()
        # Fruit: spoiled means wormy. Independent of the table and the menu.
        fruit_since = conn.execute("SELECT at FROM once_keys WHERE key='fruit_worm_since'").fetchone()["at"]
        conn.execute("BEGIN IMMEDIATE")
        for b in fridge._batches(conn, who, now):
            if (b["category"] == "fruit" and b["freshness"] == fridge.BAD and not b["wormed"]
                    and b["expires_at"] >= fruit_since and conn.execute(
                        "UPDATE batches SET wormed_at=? WHERE id=? AND wormed_at IS NULL",
                        (now, b["batch_id"])).rowcount):
                _worm_into_snack(conn, who, b["batch_id"], b["name"], float(b["bought_at"]), "fruit", now)
                fridge._log(conn, who, "wormed", t("log_wormed_fruit", name=b["name"]), now)
                out["wormed"] += 1
        conn.commit()
        for r in conn.execute("SELECT * FROM cook_sessions WHERE who=? AND worm_state IN ('wormed','tossed')",
                              (who,)).fetchall():
            try:
                if r["worm_state"] == "wormed":
                    set_note(r["menu_row_id"], worm_menu_note(dict(r)))
                    conn.execute("UPDATE cook_sessions SET worm_state='noted' WHERE id=? AND worm_state='wormed'",
                                 (r["id"],))
                    out["noted"] += 1
                else:
                    remove_row(r["menu_row_id"])
                    conn.execute("UPDATE cook_sessions SET worm_state='gone' WHERE id=? AND worm_state='tossed'",
                                 (r["id"],))
                    out["removed"] += 1
                conn.commit()
            except Exception as e:  # noqa: BLE001
                log.warning("menu not updated for %r, retrying next scan: %r", r["dish"], e)
    finally:
        conn.close()
    return out


def take_worm(who: str, rid: str, snack: str, now: float | None = None, told: bool = False) -> str | None:
    """Eating a snack takes the worm hiding in it: returns the sentence, or None when there is none.
    A worm is found once; retrying the same serving (same rid) returns the same sentence.
    told=True means the caller hands the sentence to the role itself, so no separate notice is owed."""
    now = now or _now()
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = fridge._once(conn, f"worm:{rid}")
        if done is not None:
            conn.rollback()
            return done
        p = conn.execute("SELECT * FROM worm_pending WHERE who=? AND snack=?", (who, snack)).fetchone()
        if p is None:
            conn.rollback()
            return None
        text = worm_text(p["dish"], float(p["made_at"]), snack, p["source"])
        conn.execute("DELETE FROM worm_pending WHERE who=?", (who,))
        fridge._log(conn, who, "worm_eaten",
                    t("log_worm_eaten", snack=fridge_snack_name(snack), dish=p["dish"]), now)
        fridge._mark_once(conn, f"worm:{rid}", text)
        conn.execute("INSERT OR IGNORE INTO worm_wakes (rid, who, at, text, done_at, how) VALUES (?,?,?,?,?,?)",
                     (rid, who, now, text, now if told else None, RECEIPT_SEEN if told else None))
        conn.commit()
        return text
    finally:
        conn.close()


def worm_wake_text() -> str:
    return t("worm_wake", head=t("head"))


def process_worm_wakes(*, who: str, wake, busy, receipt, in_quiet: bool, now: float | None = None) -> dict:
    """Tell the role about a worm it bit into when the receipt may not have reached it.

    receipt(at) -> the state of the receipt written at/after `at`: RECEIPT_SEEN (already delivered,
    nothing to do), RECEIPT_WAITING (queued; the wake will carry it), RECEIPT_GONE (lost: put the
    worm sentence into the wake itself). busy() / in_quiet hold the wake. At most once: only
    WAKE_NOT_SENT is retried; several pending are merged into one wake.
    """
    out = {"woke": 0, "seen": 0, "deferred": ""}
    now = now or _now()
    conn = _conn()
    try:
        rows = conn.execute("SELECT rid, at, text FROM worm_wakes WHERE who=? AND done_at IS NULL ORDER BY at",
                            (who,)).fetchall()
        if not rows:
            return out
        how = None
        state = receipt(float(rows[-1]["at"]))
        if state == RECEIPT_SEEN:
            how, out["seen"] = "seen", len(rows)
        elif busy():
            out["deferred"] = "busy"
        elif in_quiet:
            out["deferred"] = "quiet"
        else:
            res = wake(worm_wake_text() if state == RECEIPT_WAITING
                       else worm_wake_text() + "".join(r["text"] for r in rows))
            if res == WAKE_NOT_SENT:
                out["deferred"] = "not_sent"
            else:
                how, out["woke"] = res, len(rows)
        if how:
            conn.executemany("UPDATE worm_wakes SET done_at=?, how=? WHERE rid=? AND done_at IS NULL",
                             [(now, how, r["rid"]) for r in rows])
            conn.commit()
        return out
    finally:
        conn.close()


def fridge_snack_name(snack: str) -> str:
    from . import snacks
    s = snacks.by_id(snack)
    return s["name"] if s else snack


def worm_of(rid: str) -> str | None:
    """The worm sentence a serving ran into, if any (for repeated handling of the same serving)."""
    conn = _conn()
    try:
        return fridge._once(conn, f"worm:{rid}")
    finally:
        conn.close()


def toss_wormed_dish(who: str, text: str, *, key: str, now: float | None = None) -> str | None:
    """If the text names a wormy dish on the table, toss it and return the receipt (its menu row is
    removed by the next scan). Otherwise None, and the fridge gets to interpret the text."""
    name = (text or "").strip()
    now = now or _now()
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = fridge._once(conn, f"toss_dish:{key}") or fridge._once(conn, f"toss:{key}")
        if done is not None:
            conn.rollback()
            return done
        r = conn.execute("SELECT id, menu_row_id FROM cook_sessions WHERE who=? AND dish=? AND eaten_at IS NULL"
                         " AND worm_state IN ('wormed','noted') ORDER BY served_at LIMIT 1",
                         (who, name)).fetchone()
        if r is None:
            conn.rollback()
            return None
        # Off the table at once: the menu row goes in this same transaction, so the dish can no
        # longer be eaten. If the row is not there to delete (it is kept somewhere this server
        # cannot reach), the state stays "tossed" and the next scan removes it.
        gone = conn.execute("DELETE FROM menu WHERE id=?", (str(r["menu_row_id"]),)).rowcount > 0
        conn.execute("UPDATE cook_sessions SET worm_state=? WHERE id=?", ("gone" if gone else "tossed", r["id"]))
        fridge._log(conn, who, "tossed", t("log_tossed_dish", name=name), now)
        receipt = t("toss_dish_ok", name=name)
        fridge._mark_once(conn, f"toss_dish:{key}", receipt)
        conn.commit()
        return receipt
    finally:
        conn.close()


# ── can this be eaten? ──────────────────────────────────────────────────
# The menu is checked by the eating flow itself. This answers the other cases: a pot just served and
# not yet on the menu, or something edible straight from the fridge. Anything else has to be cooked
# first. Food the human feeds does not come through here.

def can_eat(who: str, meal: str, now: float | None = None) -> dict:
    """{"ok": bool, "why": pot | raw | cooking | none, "text": the refusal sentence}."""
    meal = (meal or "").strip()
    now = now or _now()
    conn = _conn()
    try:
        _settle_due(conn, who)
        # Only pots that were just served and are not on the menu yet pass here. Older pots are
        # the menu's business; letting them through would make every past dish edible again.
        if conn.execute("SELECT 1 FROM cook_sessions WHERE who=? AND status='served' AND eaten_at IS NULL AND dish=?"
                        " AND menu_added_at IS NULL AND served_at>? LIMIT 1",
                        (who, meal, now - _cfg().kitchen_menu_retry_max_seconds)).fetchone():
            return {"ok": True, "why": "pot", "text": ""}
        fire = conn.execute("SELECT started_at, duration_seconds FROM cook_sessions WHERE who=? AND status='cooking'"
                            " AND dish=? ORDER BY started_at LIMIT 1", (who, meal)).fetchone()
        if fire is not None:
            conn.commit()
            return {"ok": False, "why": "cooking",
                    "text": t("eat_cooking", meal=meal, hm=_hm(fire["started_at"] + fire["duration_seconds"]))}
        iid = fridge.resolve(meal, gone=True)
        if fridge.is_raw_edible(iid) and any(fridge.canon(b["item_id"]) == fridge.canon(iid)
                                             for b in fridge._batches(conn, who, now)):
            conn.commit()
            return {"ok": True, "why": "raw", "text": ""}
        conn.commit()
    finally:
        conn.close()
    return {"ok": False, "why": "none", "text": t("eat_none", meal=meal)}


# ── eating: what it does to the body ────────────────────────────────────

def is_potion_meal(meal: str) -> bool:
    from . import potion
    return potion.is_potion_meal(meal)


def eat_detail(who: str, meal: str, *, key: str, by_her: bool = False, now: float | None = None) -> dict | None:
    """Settle one bite. Returns {"outcome", "session_id", "raw", "raw_receipt"}; None when the key repeats.

    - meal matches a served, uneaten pot of this role: settled by that pot's result;
    - otherwise, something edible straight from the fridge and in stock (not when fed by the human):
      one piece is taken and eaten; fresh/stale count as raw/raw_meh, spoiled still causes dizziness;
    - otherwise (a dish the human put on the menu, or eaten elsewhere): a plain meal.
    Satiety, dizziness and "this pot was eaten" share one transaction with the idempotency key.
    Stamina gets only the difference the result makes; the meal itself is credited by the rest table.
    """
    if not roles.valid(who):
        return None
    now = now or _now()
    meal = (meal or "").strip()
    if is_potion_meal(meal):       # a potion is not a meal: no satiety, handled by potion.drink/feed
        return {"outcome": "potion", "session_id": None, "raw": None, "raw_receipt": None}
    outcome = "her"
    sess_id = None
    conn = _conn()
    try:
        _settle_due(conn, who)
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute(
            "SELECT id, outcome, ingredients_json FROM cook_sessions WHERE who=? AND status='served'"
            " AND eaten_at IS NULL AND dish=? AND COALESCE(worm_state,'') NOT IN ('tossed','gone')"
            " ORDER BY served_at DESC LIMIT 1", (who, meal)).fetchone()
        raw_taken = None
        if r is not None:
            sess_id, outcome = r["id"], (r["outcome"] or fridge.OK)
        elif not by_her and fridge.is_raw_edible(fridge.resolve(meal, gone=True)):
            try:
                raw_taken = fridge.take_in_tx(conn, who, [(meal, 1)], now)[0]
            except fridge.FridgeError:
                raw_taken = None            # not in the fridge: counts as a plain meal eaten elsewhere
            if raw_taken is not None:
                f = raw_taken["freshness"]
                outcome = fridge.SPOILED if f == fridge.BAD else ("raw_meh" if f == fridge.MEH else "raw")
                fridge._log(conn, who, "ate_raw", t("log_ate_raw", name=raw_taken["name"]), now)
        gains = _cfg().satiety_gain
        gain = gains.get(outcome, gains["her"])
        try:
            v = fridge.settle_meal_in_tx(conn, who, gain, key=f"eat:{key}",
                                         dizzy_dish=meal if outcome == fridge.SPOILED else None, now=now)
            if v is None:
                conn.rollback()
                return None
            if sess_id is not None:
                conn.execute("UPDATE cook_sessions SET eaten_at=? WHERE id=? AND eaten_at IS NULL",
                             (now, sess_id))
            from . import playkit
            extra_lines = playkit.on_eat_in_tx(conn, who, sess_id=sess_id, outcome=outcome, meal=meal, key=key,
                                               raw=raw_taken is not None, by_human=by_her, now=now)
        except Exception:
            conn.rollback()
            raise
        left = None
        if raw_taken is not None:
            same = fridge.canon(raw_taken["item_id"])
            left = sum(b["qty"] for b in fridge._batches(conn, who, now) if fridge.canon(b["item_id"]) == same)
        conn.commit()
    finally:
        conn.close()
    raw_receipt = None
    if raw_taken is not None:
        tail = t("eat_raw_spoiled") if outcome == fridge.SPOILED else (
            t("eat_raw_meh") if outcome == "raw_meh" else "")
        raw_receipt = t("eat_raw", name=raw_taken["name"], left=left) + tail
    # Stamina lives in its own row: credited after the bite is committed. A failure here only
    # means this bite counted as a plain meal.
    delta = _cfg().stamina_outcome_delta.get(outcome, 0.0)
    if delta and not by_her:
        try:
            from . import stamina
            stamina.pulse(who, delta, now=now, rule=f"kitchen:{outcome}")
        except Exception:  # noqa: BLE001
            log.warning("stamina difference for a kitchen dish was not recorded", exc_info=True)
    return {"outcome": outcome, "session_id": sess_id, "raw": raw_taken, "raw_receipt": raw_receipt,
            "extra": extra_lines}


def on_eat(who: str, meal: str, *, key: str, by_her: bool = False, now: float | None = None) -> str | None:
    """eat_detail, returning just the outcome word (great/ok/burnt/spoiled/raw/raw_meh/her/potion)."""
    d = eat_detail(who, meal, key=key, by_her=by_her, now=now)
    return None if d is None else d["outcome"]


def grant_writing_coupon(who: str, source: str, key: str) -> dict | None:
    """The role finished a piece of work that earns a coupon. Returns {"ok", "text"} to pass on to
    the role, or None when nothing is owed (already granted for this key, or at the cap; the cap is
    still visible in the log). A storage failure is reported, never swallowed."""
    if not roles.valid(who):
        return None
    res = coupon_for_work(who, source, key)
    if res["reason"] in ("full", "duplicate"):
        return None
    return {"ok": res["ok"], "text": res["text"]}


def coupon_for_work(who: str, source: str, key: str) -> dict:
    """grant_writing_coupon with the reason spelled out: {"ok", "text", "reason"} where reason is
    "" (granted), "full" (at the cap), "duplicate" (this key was already used) or "failed"."""
    try:
        n, reason = fridge.grant_coupon_ex(who, source, key)
    except Exception:  # noqa: BLE001
        log.warning("coupon was not granted", exc_info=True)
        return {"ok": False, "text": t("coupon_failed", label=source), "reason": "failed"}
    if n is None:
        return {"ok": False, "text": "", "reason": reason}
    return {"ok": True, "text": fridge.coupon_receipt(n), "reason": ""}


def on_round_tools(who: str, tool_calls: list[dict]) -> list[dict]:
    """Settle one finished round of tool calls made outside this server.

    Each call is {"name", "id", "input"?, "is_error"?}. A tool listed under coupons.earn grants a
    coupon; a call to an "eat" tool settles the bite. The call id is the idempotency key, so
    reporting the same round twice changes nothing. Returns the receipts owed to the role.
    """
    out: list[dict] = []
    if not roles.valid(who):
        return out
    for call in tool_calls or []:
        if call.get("is_error"):
            continue
        name = call.get("name") or ""
        tid = str(call.get("id") or "")
        if not tid:
            continue
        src = fridge.coupon_source_for_tool(name)
        if src:
            res = grant_writing_coupon(who, src, f"tool:{tid}")
            if res:
                out.append({"kind": "coupon", **res})
        elif name.split("__")[-1] == "eat":
            meal = str((call.get("input") or {}).get("meal") or "")
            if meal:
                try:
                    on_eat(who, meal, key=f"tool:{tid}")
                except Exception:  # noqa: BLE001
                    log.warning("the bite was not settled", exc_info=True)
    return out

