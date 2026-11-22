"""Proficiency, mishaps, the settled card, and the new-dish bonus.

- **Proficiency** keeps two books. A pot that followed a recipe (covering all its main ingredients)
  counts on that recipe; a free pot, or one that changed the recipe, counts on the dish name (the same
  name once spaces are removed). 3 pots made well = practised, 8 = signature (``[recipes]``). The tier
  read when the pot is opened decides the mishap chance and whether a bad egg gets caught; the count
  goes up **when the pot is served** (eaten or not).
- **Mishaps** are decided when the pot is opened and stored on it: whatever reads it later, and after
  any restart, it is the same one. One sentence only: never changes the result, never costs stamina.
  A ruined pot has none; a cancelled pot shows none.
- **The settlement** of a pot is written once, the moment it is served, and never changed (worms,
  eating, later tier changes do not touch it).
- **The new-dish bonus**: only for a pot that followed a recipe, eaten without being burnt, spoiled or
  wormy, the first time that recipe is eaten. The "first time" and the stamina land in the same
  transaction as the bite.
"""
from __future__ import annotations

import hashlib
import json

from . import config, play
from .texts_play import MISHAP_VERSION, MISHAPS, TIER_NAMES, tp

LINK_FOLLOW, LINK_CHANGED, LINK_FREE = "follow", "changed", "free"
OK_OUTCOMES = ("great", "ok", "spoiled")      # it was served (spoiled ingredients still make a dish)
FIRST_OK_OUTCOMES = ("great", "ok")


def norm_dish(dish: str) -> str:
    return "".join((dish or "").split())


def tier_of(n: int | None) -> str:
    n = n or 0
    cfg = config.get()
    if n >= cfg.recipes_signature_at:
        return TIER_NAMES[2]
    if n >= cfg.recipes_skilled_at:
        return TIER_NAMES[1]
    return TIER_NAMES[0]


def book_count(conn, who: str, book: str, key: str) -> int:
    if book == "recipe":
        r = conn.execute("SELECT n FROM recipe_counts WHERE who=? AND identity=?", (who, key)).fetchone()
    else:
        r = conn.execute("SELECT n FROM dish_counts WHERE who=? AND dish=?", (who, key)).fetchone()
    return int(r["n"]) if r else 0


def book_of(link: str, identity: str | None, dish: str) -> tuple[str, str]:
    if link == LINK_FOLLOW and identity:
        return "recipe", identity
    return "dish", norm_dish(dish)


def tier_now(conn, who: str, link: str, identity: str | None, dish: str) -> str:
    book, key = book_of(link, identity, dish)
    return tier_of(book_count(conn, who, book, key))


# ── mishaps ─────────────────────────────────────────────────────────────

def _h(seed: str) -> float:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def mishap_rate(tier: str) -> float:
    cfg = config.get()
    return {TIER_NAMES[0]: cfg.recipes_mishap_rate_new, TIER_NAMES[1]: cfg.recipes_mishap_rate_skilled}.get(tier, 0.0)


def decide_mishap(session_id: str, method: str, tier: str) -> str | None:
    """Pure: does this pot have one, and which ("stirfry.02"), or None. Same pot, same answer."""
    rate = mishap_rate(tier)
    if rate <= 0 or _h(f"mishap:{session_id}") >= rate:
        return None
    pool = [(method, i) for i in range(len(MISHAPS.get(method, ())))] + \
           [("general", i) for i in range(len(MISHAPS["general"]))]
    g, i = pool[int(_h(f"mishap_pick:{session_id}") * len(pool)) % len(pool)]
    return f"{g}.{i + 1:02d}"


def mishap_text(mishap_id: str | None, ver: int | None) -> str | None:
    """The sentence; a pot from an older sentence list shows nothing rather than the wrong one."""
    if not mishap_id or ver != MISHAP_VERSION:
        return None
    try:
        g, n = mishap_id.split(".")
        return MISHAPS[g][int(n) - 1]
    except (ValueError, KeyError, IndexError):
        return None


# ── when a pot is opened (inside the cooking transaction) ───────────────

def on_cook_start(conn, *, who: str, sid: str, dish: str, method: str, recipe: dict | None,
                  link: str, ruined: bool, now: float) -> None:
    mishap = None
    drawn = not ruined and play.on("mishaps")
    if drawn:
        mishap = decide_mishap(sid, method, tier_now(conn, who, link, recipe["identity"] if recipe else None, dish))
    # mishap_ver set = this pot was drawn (an empty id then means "none"); unset = not drawn = unknown
    conn.execute("UPDATE cook_sessions SET recipe_id=?, recipe_version=?, recipe_link=?, mishap_id=?, mishap_ver=?"
                 " WHERE id=?", (recipe["identity"] if recipe else None, recipe["version"] if recipe else None,
                                 link, mishap, MISHAP_VERSION if drawn else None, sid))
    if recipe and play.on("orders"):
        from . import book
        book.on_cook_started(conn, who, recipe["identity"], sid, now)
    if ruined:
        conn.execute("INSERT OR IGNORE INTO cook_settlements (session_id, who, dish, method, outcome, link, recipe_id,"
                     " recipe_version, started_at, settled_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (sid, who, dish, method, "ruined", link, recipe["identity"] if recipe else None,
                      recipe["version"] if recipe else None, now, now))
        if recipe and play.on("orders"):
            from . import book
            book.on_cook_finished(conn, sid, False, now)


def on_cancel(conn, sid: str, now: float) -> None:
    """Heat off: an order goes back to "received". With orders off it stays frozen and is caught up later."""
    if play.on("orders"):
        from . import book
        book.on_cook_finished(conn, sid, False, now)


def settlements_wanted() -> bool:
    return play.any_on("proficiency", "settle_card", "dex", "achievements", "orders", "recipe_cook")


# ── when a pot is served (kitchen._settle_due) ──────────────────────────

def settle_in_tx(conn, r, now: float) -> None:
    """One served pot: the settlement row (once), proficiency, orders, achievements."""
    sid = r["id"]
    if conn.execute("SELECT 1 FROM cook_settlements WHERE session_id=?", (sid,)).fetchone():
        return
    link = r["recipe_link"] or LINK_FREE
    identity = r["recipe_id"]
    outcome = r["outcome"] or "ok"
    bk = key = before = after = None
    first = 0
    if play.on("proficiency"):
        bk, key = book_of(link, identity, r["dish"])
        before = book_count(conn, r["who"], bk, key)
        after = before + (1 if outcome in OK_OUTCOMES else 0)
        if after != before:
            table, col = ("recipe_counts", "identity") if bk == "recipe" else ("dish_counts", "dish")
            conn.execute(f"INSERT INTO {table} (who, {col}, n) VALUES (?,?,1)"
                         f" ON CONFLICT(who, {col}) DO UPDATE SET n=n+1", (r["who"], key))
        first = 1 if before == 0 and after == 1 else 0
    rescued = None
    if outcome in ("great", "ok"):
        try:
            used = json.loads(r["ingredients_json"] or "[]")
        except ValueError:
            used = []
        from . import fridge
        meh = [u for u in used if u.get("freshness") == "meh" and not fridge.hidden_freshness(u.get("item_id"))]
        rescued = meh[0]["name"] if meh else None
    conn.execute("INSERT OR IGNORE INTO cook_settlements (session_id, who, dish, method, outcome, link, recipe_id,"
                 " recipe_version, book, book_key, before_n, after_n, before_tier, after_tier, first_time, mishap_id,"
                 " mishap_ver, rescued_item, started_at, settled_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, r["who"], r["dish"], r["method"], outcome, link, identity, r["recipe_version"], bk, key,
                  before, after, tier_of(before) if bk else None, tier_of(after) if bk else None, first,
                  r["mishap_id"], r["mishap_ver"], rescued, r["started_at"], r["served_at"] or now))
    if identity and play.on("orders"):
        from . import book
        book.on_cook_finished(conn, sid, True, now)
    if play.on("achievements"):
        from . import dex
        dex.evaluate_in_tx(conn, r["who"], now)


def settle_due(conn, who: str, now: float) -> None:
    """Settle every served pot that has no settlement yet, but only pots served after the upgrade's
    first use: older pots are never back-filled."""
    if not settlements_wanted():
        return
    conn.execute("INSERT OR IGNORE INTO once_keys (key, at, result) VALUES ('play_since', ?, '')", (now,))
    conn.commit()
    since = conn.execute("SELECT at FROM once_keys WHERE key='play_since'").fetchone()["at"]
    rows = conn.execute(
        "SELECT * FROM cook_sessions s WHERE who=? AND status='served' AND outcome IS NOT NULL"
        " AND served_at>=? AND NOT EXISTS (SELECT 1 FROM cook_settlements c WHERE c.session_id=s.id)"
        " ORDER BY served_at", (who, since)).fetchall()
    if not rows:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        for r in rows:
            settle_in_tx(conn, r, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def settlement(conn, sid: str) -> dict | None:
    r = conn.execute("SELECT * FROM cook_settlements WHERE session_id=?", (sid,)).fetchone()
    return dict(r) if r else None


def _recipe_name(st: dict) -> str:
    if st.get("book") == "recipe" and st.get("recipe_id"):
        from . import recipes
        r = recipes.get(st["recipe_id"], st.get("recipe_version"))
        if r:
            return r["name"]
    return st["dish"]


def served_lines(sid: str) -> list[str]:
    """What follows "your dish is ready": the mishap, and the tier change. Nothing for what is off."""
    from . import db
    conn = db.connect()
    try:
        st = settlement(conn, sid)
    finally:
        conn.close()
    if not st:
        return []
    out = []
    if play.on("mishaps"):
        m = mishap_text(st["mishap_id"], st["mishap_ver"])
        if m:
            out.append(m)
    if play.on("proficiency") and st["book"] and st["before_tier"] != st["after_tier"]:
        out.append(tp("tier_up", name=_recipe_name(st), n=st["after_n"], tier=st["after_tier"]))
    return out


_ICON_RULES: dict | None = None


def dish_icon(dish: str) -> str:
    """Which small dish picture the cook holds up on the settled card (src/kitchenette/data/dish_icons.json:
    the first rule with a keyword found in the name wins; none = the plain bowl)."""
    global _ICON_RULES
    if _ICON_RULES is None:
        import os
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dish_icons.json"),
                  encoding="utf-8") as f:
            _ICON_RULES = json.load(f)["rules"]
    name = (dish or "").lower()
    for rule in _ICON_RULES["ordered"]:
        if any(k.lower() in name for k in rule["keywords"]):
            return rule["category"]
    return _ICON_RULES["fallback"]


def card(conn, sid: str) -> dict:
    """The settled card, complete: whether there is one, the facts of that moment, or why not."""
    s = conn.execute("SELECT * FROM cook_sessions WHERE id=?", (sid,)).fetchone()
    if s is None:
        return {"has": False, "why": "no_session"}
    if not play.on("settle_card"):
        return {"has": False, "why": "feature_off"}
    st = settlement(conn, sid)
    if st is None:
        if s["status"] == "cooking":
            return {"has": False, "why": "not_settled"}
        if s["status"] == "cancelled":
            return {"has": False, "why": "cancelled"}
        oc = None if s["wormed_at"] else (s["outcome"] or None)
        return {"has": False, "why": "legacy", "legacy_outcome": oc}
    cfg = config.get()
    out = {"has": True, "outcome": st["outcome"], "link": st["link"], "dish": st["dish"], "method": st["method"],
           "recipe_id": st["recipe_id"], "icon": dish_icon(_recipe_name(st) if st["link"] == LINK_FOLLOW else st["dish"])}
    if play.on("proficiency") and st["book"]:
        n = st["after_n"]
        nxt = cfg.recipes_skilled_at if n < cfg.recipes_skilled_at else (
            cfg.recipes_signature_at if n < cfg.recipes_signature_at else None)
        # where this tier started (the card's short bar runs from there) and the name of the next one
        idx = 0 if n < cfg.recipes_skilled_at else (1 if n < cfg.recipes_signature_at else 2)
        frm = (0, cfg.recipes_skilled_at, cfg.recipes_signature_at)[idx]
        out["proficiency"] = {"tier": st["after_tier"], "n": n, "before_tier": st["before_tier"],
                              "to_next": (nxt - n) if nxt else None,
                              "next_tier": TIER_NAMES[idx + 1] if nxt else None, "tier_from": frm}
    else:
        out["proficiency"] = None
    if play.on("mishaps") and st["outcome"] != "ruined":
        m = mishap_text(st["mishap_id"], st["mishap_ver"])
        if st["mishap_ver"] is None:
            out["mishap"] = None
        elif not st["mishap_id"]:
            # "一路顺利" only for a dish that came out fine; a burnt or spoiled one shows no mishap line
            out["mishap"] = None if st["outcome"] in ("burnt", "spoiled") else {"state": "none", "text": tp("card_smooth")}
        else:
            out["mishap"] = {"state": "had", "text": m} if m else {"state": "unknown", "text": None}
    else:
        out["mishap"] = None
    stamps = []
    if st["first_time"]:
        stamps.append("first")
    if st["link"] in (LINK_FOLLOW, LINK_CHANGED) and st["outcome"] in OK_OUTCOMES:
        stamps.append(st["link"])
    out["stamps"] = [{"key": k, "text": tp(f"stamp_{k}")} for k in stamps]
    return out


# ── the new-dish bonus (inside the eating transaction) ──────────────────

def on_eat_in_tx(conn, who: str, sess_id: str | None, outcome: str, key: str, now: float) -> str | None:
    """Is this bite the first of a recipe? Then record it and add the stamina, here, in the same
    transaction. Returns the sentence for the receipt, or None."""
    if not sess_id or outcome not in FIRST_OK_OUTCOMES or not play.on("new_dish_bonus"):
        return None
    s = conn.execute("SELECT recipe_id, recipe_version, recipe_link, wormed_at, dish FROM cook_sessions WHERE id=?",
                     (sess_id,)).fetchone()
    if s is None or s["recipe_link"] != LINK_FOLLOW or not s["recipe_id"] or s["wormed_at"]:
        return None
    name = s["dish"]
    from . import book
    try:
        ref = book.resolve_ref(conn, who, s["recipe_id"], version=s["recipe_version"])
        name = ref["name"] if ref else name
    except Exception:  # noqa: BLE001
        pass
    if conn.execute("INSERT OR IGNORE INTO recipe_firsts (who, identity, eat_key, session_id, name, created_at)"
                    " VALUES (?,?,?,?,?,?)", (who, s["recipe_id"], key, sess_id, name, now)).rowcount != 1:
        return None
    from . import stamina
    if stamina.pulse_in_tx(conn, who, config.get().recipes_new_dish_bonus, now, rule="new_dish") is None:
        return None
    return tp("new_dish_bonus", name=name)
