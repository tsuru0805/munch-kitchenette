"""Where the upgrade plugs into the rest of the kitchen: the new markers, the teaching sentences, the
paragraphs added to the kitchen status, the one new tool ("翻食谱"), and the periodic work.

Everything here reads :mod:`kitchenette.play`. With every switch off the kitchen behaves exactly as
before the upgrade, word for word.
"""
from __future__ import annotations

import copy
import hashlib
import logging

from . import clock, config, db, play
from .texts_play import BROWSE_MAX_LINES, METHOD_CN, tp

log = logging.getLogger(__name__)

TOOL_BROWSE = "kitchen_recipes"
_BROWSE_OPS = ("today", "find", "category", "mine", "achievements")


def marker_key(name: str, message_key: str, idx: int) -> str:
    return hashlib.sha1(f"play:{name}:{message_key}:{idx}".encode()).hexdigest()[:16]


# ═══════════ markers ═══════════

def run_marker(who: str, name: str, args: str, *, key: str, now: float | None = None) -> tuple[bool, str]:
    """One line of a new marker -> (done, receipt). The switch is checked again here: a marker of
    something switched off answers that it is off."""
    now = now or clock.now()
    if not play.marker_enabled(name):
        return False, tp("feature_off")
    if len(args or "") > 300:
        return False, tp("tag_too_long")
    try:
        if name == "刷盘子":
            from . import dishes
            return True, dishes.start(who, key=key, now=now)
        if name == "封罐":
            from . import jars
            try:
                return True, jars.seal(who, args, key=key, now=now)
            except jars.JarError as e:
                return False, e.text
        if name in ("问小贩", "买", "送花", "想要花"):
            from . import vendor
            fn = {"问小贩": vendor.ask, "买": vendor.buy, "送花": vendor.gift, "想要花": vendor.want}[name]
            return fn(who, args, key=key, now=now)
        return _book_marker(who, name, args, key=key, now=now)
    except Exception:  # noqa: BLE001
        log.warning("marker %s failed", name, exc_info=True)
        return False, tp("store_failed", marker=name)


def marker_attachments(name: str, key: str) -> list[dict]:
    """Cards a marker hands the chat along with its receipt (by the key it ran under): the washing card of a
    [刷盘子] that started a washing. Empty for every other marker, and for a [刷盘子] that started nothing."""
    if name != "刷盘子":
        return []
    from . import dishes
    conn = db.connect()
    try:
        card = dishes.card_for_key(conn, key)
    finally:
        conn.close()
    return [card] if card else []


def _book_marker(who: str, name: str, args: str, *, key: str, now: float) -> tuple[bool, str]:
    from . import book, fridge
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = fridge._once(conn, f"play:{key}")
        if done is not None:
            conn.rollback()
            return True, done
        try:
            if name == "收藏":
                text = book.favorite(conn, who, args, now)
            elif name == "记菜":
                text = book.record(conn, who, args, now)
            elif name == "札记":
                text = book.add_note(conn, who, args, key, now)
            elif name == "接单":
                text = book.accept(conn, who, args, now)
            elif name == "配一桌":
                text = book.make_menu(conn, who, args, now)
            elif name == "出码":
                text = book.export_receipt(conn, who, args)
            else:
                conn.rollback()
                return False, tp("feature_off")
        except book.BookError as e:
            conn.rollback()
            return False, e.text
        fridge._mark_once(conn, f"play:{key}", text)
        conn.commit()
        return True, text
    finally:
        conn.close()


def buy_by_recipe(who: str, text: str, *, key: str, now: float | None = None) -> str | None:
    """[买菜 照 <id>]: the receipt (raises fridge.FridgeError on refusal); None when the line is not
    written that way or buying by recipe is off — then it is ordinary buying, unchanged."""
    toks = (text or "").split()
    if len(toks) != 2 or toks[0] != "照" or not play.on(play.BUY_RECIPE_FEATURE):
        return None
    from . import book
    return book.buy_for_recipe(who, toks[1], key=key, now=now or clock.now())


def snack_fallback(who: str, name: str, *, key: str, now: float | None = None) -> dict | None:
    """[零食 X] that is not a shelf snack: a jar treat of that exact name, if any; None otherwise."""
    if not play.on("seal_jars"):
        return None
    from . import jars
    if not jars.has_goods(who, name, now):
        return None
    return jars.take(who, name, key=f"jar:{key}", now=now)


# ═══════════ teaching ═══════════

def teaching_text() -> str:
    """The sentences that teach the markers of what is switched on (empty while markers are not in use)."""
    from .texts import markers_on
    if not markers_on():
        return ""
    eff = play.effective()
    parts = []
    if eff["recipe_book"]["on"]:
        parts.append(tp("teach_recipe_book") if eff["recipes_public"]["on"] else tp("teach_recipe_book_no_public"))
    for k in ("recipe_cook", "tasting_notes", "orders", "menus", "recipe_codes", "dishwash", "seal_jars", "vendor"):
        if eff[k]["on"]:
            parts.append(tp(f"teach_{k}", max=config.get().fridge_buy_max_items) if k == "recipe_cook"
                         else tp(f"teach_{k}"))
    return "".join(parts)


# ═══════════ the kitchen status ═══════════

def status_extra(who: str, now: float) -> str:
    """After the fridge paragraph. Each part fails on its own: today's picks that cannot be worked out
    say so in one line; the others are left out."""
    eff = play.effective()
    out: list[str] = []
    if eff["orders"]["on"]:
        try:
            from . import book
            conn = db.connect()
            try:
                text = book.orders_text(conn, who, now)
                conn.commit()
            finally:
                conn.close()
            if text:
                out.append(text)
        except Exception:  # noqa: BLE001
            log.warning("orders paragraph failed", exc_info=True)
    if eff["recipes_today"]["on"]:
        try:
            from . import recipes
            out.append(recipes.today_text(who, now))
        except Exception:  # noqa: BLE001
            log.warning("today's picks failed", exc_info=True)
            out.append(tp("rec_down"))
    if eff["seal_jars"]["on"] or eff["dishwash"]["on"]:
        try:
            conn = db.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                if eff["seal_jars"]["on"]:
                    from . import jars
                    jars.settle_in_tx(conn, who, now)
                    out.append(jars.status_text(conn, who, now))
                if eff["dishwash"]["on"]:
                    from . import dishes
                    dishes.settle_in_tx(conn, who, now)
                    line = dishes.status_line(conn, who, now)
                    if line:
                        out.append(line)
                conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            log.warning("jars / sink paragraph failed", exc_info=True)
    if eff["vendor"]["on"]:
        try:
            from . import vendor
            out.extend(vendor.status_lines(who, now))
        except Exception:  # noqa: BLE001
            log.warning("vendor paragraph failed", exc_info=True)
    return "\n".join(x for x in out if x)


# ═══════════ the periodic scan ═══════════

def tick(who: str, now: float | None = None) -> dict:
    """Plates, jars, achievements and one dish picture for one role. Each part fails on its own."""
    now = now or clock.now()
    out: dict = {}
    from . import dishes, jars
    for name, fn in (("plates", lambda: dishes.tick(who, now)), ("jars", lambda: jars.tick(who, now))):
        try:
            out[name] = fn()
        except Exception:  # noqa: BLE001
            log.warning("%s pass failed for %s", name, who, exc_info=True)
    if play.on("achievements"):
        try:
            from . import dex
            conn = db.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                dex.evaluate_in_tx(conn, who, now)
                conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            log.warning("achievement pass failed for %s", who, exc_info=True)
    if play.on("dex"):
        try:
            from . import dex
            out["drawn"] = dex.draw_one(who)
        except Exception:  # noqa: BLE001
            log.warning("dish picture failed for %s", who, exc_info=True)
    return out


def tick_all(now: float | None = None) -> dict:
    """Once per scan, not per role: the street."""
    try:
        from . import vendor
        return vendor.tick(now)
    except Exception:  # noqa: BLE001
        log.warning("vendor pass failed", exc_info=True)
        return {}


# ═══════════ eating ═══════════

def on_eat_in_tx(conn, who: str, *, sess_id: str | None, outcome: str, meal: str, key: str,
                 raw: bool, by_human: bool, now: float) -> list[str]:
    """Inside the eating transaction: a plate (not for eating straight from the fridge) and the
    new-dish bonus (not when fed by the human). Returns sentences for the receipt."""
    out = []
    if not raw:
        from . import dishes
        dishes.produce_in_tx(conn, who, f"eat:{key}", meal, now)
    if not by_human:
        from . import progress
        line = progress.on_eat_in_tx(conn, who, sess_id, outcome, f"eat:{key}", now)
        if line:
            out.append(line)
    return out


# ═══════════ the one new tool ═══════════

def _ops() -> list[str]:
    eff = play.effective()
    ops = []
    if eff["recipes_public"]["on"]:
        if eff["recipes_today"]["on"]:
            ops.append("today")
        ops += ["find", "category"]
    if eff["recipe_book"]["on"]:
        ops.append("mine")
    if eff["achievements"]["on"]:
        ops.append("achievements")
    return ops


def browse_schema() -> list[dict]:
    """The tool, cut down to what is switched on; nothing when none of it is."""
    ops = _ops()
    if not ops:
        return []
    props = {"what": {"type": "string", "enum": ops,
                      "description": " / ".join(f"{k}={tp('browse_' + k)}" for k in ops)}}
    if any(o in ops for o in ("find", "category")):
        props["q"] = {"type": "string", "description": tp("tool_browse_q")}
    return [{"name": TOOL_BROWSE, "description": tp("tool_browse"),
             "input_schema": {"type": "object", "properties": props, "required": ["what"],
                              "additionalProperties": False}}]


def adjust_cook_schema(schemas: list[dict]) -> list[dict]:
    """Opening a pot takes a recipe id only while cooking by recipe is on; the teaching for the markers
    rides along with the cooking tool's description."""
    out = []
    teach = teaching_text()
    for s in schemas:
        if s["name"] == "kitchen_cook":
            s = copy.deepcopy(s)
            if play.on("recipe_cook"):
                s["input_schema"]["properties"]["recipe"] = {"type": "string", "description": tp("tool_cook_recipe")}
            if teach:
                s["description"] += "\n\n" + teach
        out.append(s)
    return out


def browse(who: str, args: dict) -> tuple[str, bool]:
    what = str((args or {}).get("what") or "").strip()
    q = str((args or {}).get("q") or "").strip()[:40]
    if what not in _ops():
        return tp("feature_off"), True
    from . import recipes
    try:
        if what == "today":
            return recipes.today_text(who, clock.now()), False
        if what in ("find", "category"):
            if not q:
                if what == "category":
                    return tp("browse_categories", cats="、".join(recipes.categories())), False
                return tp("browse_need_q"), True
            conn = db.connect()
            try:
                hits = recipes.search(q, conn=conn, who=who, limit=500)
            finally:
                conn.close()
            if not hits:
                return tp("browse_empty"), False
            lines = [recipes.line(r) for r in hits[:BROWSE_MAX_LINES]]
            if len(hits) > BROWSE_MAX_LINES:
                lines.append(tp("browse_more", n=len(hits) - BROWSE_MAX_LINES))
            return "\n".join(lines), False
        conn = db.connect()
        try:
            if what == "mine":
                from . import book
                pages = book.my_pages(conn, who)
                if not pages:
                    return tp("browse_mine_empty"), False
                lines = []
                for p in pages[-BROWSE_MAX_LINES:]:
                    note = f" — {p['note']}" if p["note"] else ""
                    if p["kind"] == "menu":
                        lines.append(tp("browse_mine_menu", kind=tp("kind_menu"), name=p["name"], rid=p["id"], note=note))
                        continue
                    lines.append(tp("browse_mine_line", kind=tp(f"kind_{p['kind']}"), name=p["name"],
                                    rid=p["ref_id"] if p["kind"] == "fav" else p["id"],
                                    items=recipes.items_text(p["main"]), method=METHOD_CN.get(p["method"], p["method"]),
                                    minutes=p["minutes"], note=note))
                return "\n".join(lines), False
            from . import dex
            conn.execute("BEGIN IMMEDIATE")
            dex.evaluate_in_tx(conn, who)
            conn.commit()
            lines = dex.earned_for_role(conn, who)
            return ("\n".join(lines) if lines else tp("ach_none")), False
        finally:
            conn.close()
    except recipes.RecipesUnavailable:
        return tp("browse_unavailable"), True
