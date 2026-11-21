"""The dish book (one page per dish made) and the kitchen achievements.

Pages are worked out from the pots, never stored as a fourth truth:

- a pot that followed a recipe goes on that recipe's page; a free pot, or one that changed the recipe,
  goes on the page of its dish name (spaces removed); a name that matches no recipe is "unsorted" and
  the human can merge it into a page;
- made / made well / eaten are counted apart: a cancelled pot was never made; burnt or ruined counts
  as made, not made well;
- pots from before the upgrade are read too (read-only, any number of times);
- silhouettes only for recipes the role collected and has not made yet;
- one picture per page: every version is kept, the human can switch back; with no picture drawer
  configured the page shows a placeholder.

Achievements earned are stored and never taken back (cancelled pots, switching things off and on do
not undo them); what is not earned yet is worked out fresh each time. **The role only ever sees the
ones it has earned**: :func:`earned_for_role` cannot list the others. All of them are for the human's page.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from . import clock, config, play
from .texts_play import ACHIEVEMENTS, METHOD_CN, tp

log = logging.getLogger(__name__)
_ACH = {a[0]: a for a in ACHIEVEMENTS}
GOOD_OUTCOMES = ("great", "ok")
_RANK = {"great": 4, "ok": 3, "spoiled": 2, "burnt": 1, "ruined": 0}
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _norm(d: str) -> str:
    return "".join((d or "").split())


def _md(ts: float) -> str:
    return clock.local(ts).strftime("%m-%d")


def _kday(ts: float) -> str:
    from . import recipes
    return recipes.kitchen_day(ts)


def _pots(conn, who: str) -> list:
    return conn.execute(
        "SELECT s.*, st.outcome AS st_outcome, st.link AS st_link FROM cook_sessions s"
        " LEFT JOIN cook_settlements st ON st.session_id=s.id WHERE s.who=? ORDER BY s.started_at",
        (who,)).fetchall()


def _true_outcome(p) -> str:
    """The settlement's word wins (worms rewrite the pot's, never the settlement's)."""
    if p["st_outcome"]:
        return p["st_outcome"]
    if p["status"] == "ruined":
        return "ruined"
    return p["outcome"] or "ok"


def _method(p) -> str:
    from . import kitchen
    return kitchen._method_of(p)


def _public_names() -> dict[str, str]:
    try:
        from . import recipes
        out: dict[str, str] = {}
        for r in recipes.load()["list"]:
            out.setdefault(_norm(r["name"]), r["id"])
            for a in r.get("aliases", []):
                out.setdefault(_norm(a), r["id"])
        return out
    except Exception:  # noqa: BLE001
        return {}


def _merges(conn, who: str) -> dict[str, str]:
    return {r["dish"]: r["page_key"] for r in conn.execute(
        "SELECT dish, page_key FROM dex_merges WHERE who=?", (who,)).fetchall()}


def page_key(p, merges: dict[str, str]) -> str:
    if (p["st_link"] or p["recipe_link"]) == "follow" and p["recipe_id"]:
        return f"r:{p['recipe_id']}"
    nd = _norm(p["dish"])
    return merges.get(nd) or f"d:{nd}"


def build(conn, who: str) -> dict:
    """The whole book for the human's page, with the five back-fill counts. Read only."""
    merges = _merges(conn, who)
    names = _public_names()
    own_names: dict[str, str] = {}
    for p in conn.execute("SELECT p.id, v.name FROM recipe_pages p JOIN recipe_page_versions v ON v.page_id=p.id"
                          " AND v.version=p.cur_version WHERE p.who=? AND p.deleted_at IS NULL", (who,)).fetchall():
        own_names.setdefault(_norm(p["name"]), p["id"])
    pages: dict[str, dict] = {}
    scanned = excluded = counted = 0
    for p in _pots(conn, who):
        scanned += 1
        if p["status"] in ("cancelled", "cooking"):
            excluded += 1
            continue
        counted += 1
        key = page_key(p, merges)
        oc = _true_outcome(p)
        pg = pages.setdefault(key, {"key": key, "name": p["dish"], "first_at": p["started_at"], "made": 0,
                                    "good": 0, "eaten": 0, "best": None, "ingredients": [], "method": _method(p),
                                    "pending": False, "recipe_id": p["recipe_id"] if key.startswith("r:") else None})
        pg["made"] += 1
        pg["good"] += 1 if oc in GOOD_OUTCOMES else 0
        pg["eaten"] += 1 if p["eaten_at"] else 0
        if pg["best"] is None or _RANK.get(oc, 0) > _RANK.get(pg["best"], 0):
            pg["best"] = oc
        try:
            ings = [u.get("name") for u in json.loads(p["ingredients_json"] or "[]") if u.get("name")]
        except ValueError:
            ings = []
        if ings:
            pg["ingredients"] = ings
            pg["method"] = _method(p)
    for key, pg in pages.items():
        if key.startswith("d:"):
            nd = key[2:]
            pg["pending"] = nd not in names and nd not in own_names
            pg["recipe_id"] = names.get(nd) or own_names.get(nd)
    notes = {r["page_key"]: r["text"] for r in conn.execute(
        "SELECT page_key, text FROM dex_notes WHERE who=?", (who,)).fetchall()}
    arts = art_index(conn)
    for key, pg in pages.items():
        pg["human_note"] = notes.get(key, "")
        pg["art"] = arts.get(key)
        pg["role_note"] = _role_note(conn, who, pg["recipe_id"]) if pg["recipe_id"] else ""
    made_ids = {pg["recipe_id"] for pg in pages.values() if pg.get("recipe_id")}
    silhouettes = [{"recipe_id": f["ref_id"], "name": f["name"]} for f in conn.execute(
        "SELECT p.ref_id, v.name FROM recipe_pages p JOIN recipe_page_versions v ON v.page_id=p.id"
        " AND v.version=p.cur_version WHERE p.who=? AND p.kind='fav' AND p.deleted_at IS NULL", (who,)).fetchall()
        if f["ref_id"] not in made_ids]
    try:
        from . import recipes
        public_ids = set(recipes.load()["by_id"])
        total_public = len(public_ids)
    except Exception:  # noqa: BLE001
        public_ids, total_public = set(), None
    page_list = sorted(pages.values(), key=lambda x: x["first_at"])
    return {"pages": page_list, "silhouettes": silhouettes,
            "totals": {"public": total_public, "made_public": len(made_ids & public_ids), "pages": len(page_list),
                       "art_missing": sum(1 for pg in page_list if not (pg["art"] and pg["art"].get("state") == "ready"))},
            "backfill": {"scanned": scanned, "counted": counted, "excluded": excluded,
                         "pages": len(page_list), "pending": sum(1 for pg in page_list if pg["pending"])}}


def _role_note(conn, who: str, ref: str) -> str:
    r = conn.execute("SELECT v.note FROM recipe_pages p JOIN recipe_page_versions v ON v.page_id=p.id"
                     " AND v.version=p.cur_version WHERE p.who=? AND (p.id=? OR p.ref_id=?) AND p.deleted_at IS NULL"
                     " ORDER BY p.created_at LIMIT 1", (who, ref, ref)).fetchone()
    return r["note"] if r else ""


# ── pictures ────────────────────────────────────────────────────────────

def art_index(conn) -> dict[str, dict]:
    out: dict[str, dict] = {}
    choice = {r["page_key"]: r["version"] for r in conn.execute("SELECT * FROM dex_art_choice").fetchall()}
    for r in conn.execute("SELECT * FROM dex_art ORDER BY page_key, version").fetchall():
        out.setdefault(r["page_key"], {"versions": []})["versions"].append(
            {"version": r["version"], "state": r["state"], "err": r["err"]})
    for k, v in out.items():
        ready = [x for x in v["versions"] if x["state"] == "ready"]
        pick = next((x for x in ready if x["version"] == choice.get(k)), None) or (ready[-1] if ready else None)
        v["state"] = "ready" if pick else v["versions"][-1]["state"]
        v["chosen"] = pick["version"] if pick else None
    return out


def art_register(conn, page_key: str, state: str, path: str = "", err: str = "", now: float | None = None) -> int:
    """Record one version (pending / ready / failed). Redrawing adds a version; the old ones stay."""
    if state not in ("pending", "ready", "failed"):
        raise ValueError("state")
    now = now or clock.now()
    v = conn.execute("SELECT MAX(version) FROM dex_art WHERE page_key=?", (page_key,)).fetchone()[0] or 0
    last = conn.execute("SELECT state FROM dex_art WHERE page_key=? AND version=?", (page_key, v)).fetchone()
    if last is not None and last["state"] == "pending":
        conn.execute("UPDATE dex_art SET state=?, path=?, err=? WHERE page_key=? AND version=?",
                     (state, path, err[:200], page_key, v))
        return v
    conn.execute("INSERT INTO dex_art (page_key, version, state, path, err, created_at) VALUES (?,?,?,?,?,?)",
                 (page_key, v + 1, state, path, err[:200], now))
    return v + 1


def art_choose(conn, page_key: str, version: int, now: float | None = None) -> bool:
    if not conn.execute("SELECT 1 FROM dex_art WHERE page_key=? AND version=? AND state='ready'",
                        (page_key, version)).fetchone():
        return False
    conn.execute("INSERT INTO dex_art_choice (page_key, version, at) VALUES (?,?,?)"
                 " ON CONFLICT(page_key) DO UPDATE SET version=excluded.version, at=excluded.at",
                 (page_key, version, now or clock.now()))
    return True


def art_file(page_key: str, version: int) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else f"_{ord(c):x}" for c in page_key)
    return Path(config.get().art_dir) / "dex" / f"{safe}.v{int(version)}.png"


_drawer = None
_draw_lock = threading.Lock()


def set_drawer(fn) -> None:
    """Install a dish-picture drawer directly (overrides [art] dish_provider)."""
    global _drawer
    _drawer = fn


def drawer():
    """The configured drawer: (name, ingredients, method) -> PNG bytes; None = placeholders."""
    if _drawer is not None:
        return _drawer
    spec = config.get().art_dish_provider
    if not spec:
        return None
    mod, _, attr = spec.partition(":")
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    return getattr(importlib.import_module(mod), attr or "draw")


def draw_one(who: str) -> str | None:
    """Draw the picture of one page that has none (or asked for a redraw). One at a time, called by
    the periodic scan. Returns the page key drawn, or None."""
    fn = drawer()
    if fn is None or not play.on("dex") or not _draw_lock.acquire(blocking=False):
        return None
    try:
        from . import db
        conn = db.connect()
        try:
            book = build(conn, who)
            todo = next((pg for pg in book["pages"]
                         if pg["art"] is None or pg["art"]["versions"][-1]["state"] == "pending"), None)
            if todo is None:
                return None
            v = art_register(conn, todo["key"], "pending")
            conn.commit()
        finally:
            conn.close()
        try:
            png = fn(todo["name"], list(todo["ingredients"]), todo["method"])
            if not isinstance(png, (bytes, bytearray)) or not bytes(png).startswith(_PNG_SIG):
                raise ValueError("the drawer did not return PNG bytes")
            p = art_file(todo["key"], v)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(bytes(png))
            os.replace(tmp, p)
            state, err = "ready", ""
        except Exception as e:  # noqa: BLE001
            log.warning("drawing the dish picture failed: %r", e)
            state, err = "failed", f"{type(e).__name__}: {e}"
        conn = db.connect()
        try:
            art_register(conn, todo["key"], state, str(art_file(todo["key"], v)) if state == "ready" else "", err)
            conn.commit()
        finally:
            conn.close()
        return todo["key"]
    finally:
        _draw_lock.release()


def request_redraw(conn, page_key: str) -> int:
    """Ask for a new version (drawn by the next scan); the current one stays until it is ready."""
    v = conn.execute("SELECT MAX(version) FROM dex_art WHERE page_key=?", (page_key,)).fetchone()[0] or 0
    last = conn.execute("SELECT state FROM dex_art WHERE page_key=? AND version=?", (page_key, v)).fetchone()
    if last is not None and last["state"] == "pending":
        return v
    conn.execute("INSERT INTO dex_art (page_key, version, state, created_at) VALUES (?,?,?,?)",
                 (page_key, v + 1, "pending", clock.now()))
    return v + 1


# ── achievements ────────────────────────────────────────────────────────

def _why(ach: str, **kw) -> str:
    try:
        return _ACH[ach][2].format(**kw)
    except (KeyError, IndexError):
        return ""


def _earn(conn, who: str, ach: str, at: float, evidence: str, why: str) -> None:
    conn.execute("INSERT OR IGNORE INTO achievements_earned (who, ach, earned_at, evidence, why) VALUES (?,?,?,?,?)",
                 (who, ach, at, evidence, why))


def evaluate_in_tx(conn, who: str, now: float | None = None) -> list[str]:
    """Work everything out from the facts and store what is newly earned (never removes). Running it
    twice gives the same result. Returns the keys earned this time."""
    now = now or clock.now()
    before = {r["ach"] for r in conn.execute("SELECT ach FROM achievements_earned WHERE who=?", (who,)).fetchall()}
    pots = [p for p in _pots(conn, who) if p["status"] in ("served", "ruined")]
    per_method: dict[str, list] = {}
    days: set[str] = set()
    from . import fridge
    for p in pots:
        oc = _true_outcome(p)
        at = p["served_at"] or p["started_at"]
        if p["status"] == "served":
            days.add(_kday(at))
        if oc in ("great", "ok", "spoiled"):
            per_method.setdefault(_method(p), []).append(p)
        if oc == "burnt":
            _earn(conn, who, "first_burnt", at, p["id"], _why("first_burnt", dish=p["dish"]))
        h = clock.local(p["started_at"]).hour
        if p["status"] == "served" and 0 <= h < 4:
            _earn(conn, who, "late_night", at, p["id"],
                  _why("late_night", hm=clock.local(p["started_at"]).strftime("%H:%M"), dish=p["dish"]))
        if oc in GOOD_OUTCOMES:
            try:
                used = json.loads(p["ingredients_json"] or "[]")
            except ValueError:
                used = []
            meh = [u for u in used if u.get("freshness") == "meh" and not fridge.hidden_freshness(u.get("item_id"))]
            if meh:
                _earn(conn, who, "rescued", at, p["id"], _why("rescued", item=meh[0].get("name"), dish=p["dish"]))
    for m, ps in per_method.items():
        if len(ps) >= 3:
            _earn(conn, who, "one_method", ps[2]["served_at"] or ps[2]["started_at"], ps[2]["id"],
                  _why("one_method", method=METHOD_CN.get(m, m)))
    if all(len(per_method.get(m, [])) >= 3 for m in METHOD_CN):
        last = max(per_method[m][2]["served_at"] or per_method[m][2]["started_at"] for m in METHOD_CN)
        _earn(conn, who, "all_methods", last, "", _why("all_methods"))
    if days:
        dset = {datetime.strptime(d, "%Y-%m-%d").date() for d in days}
        for d in sorted(dset):
            if sum(1 for i in range(-6, 1) if d + timedelta(days=i) in dset) >= 5:
                _earn(conn, who, "five_of_seven", now, d.isoformat(), _why("five_of_seven"))
                break
    for st in conn.execute("SELECT s.session_id, s.dish, s.settled_at FROM cook_settlements s JOIN recipe_pages p"
                           " ON p.id=s.recipe_id WHERE s.who=? AND s.link='follow' AND p.kind='own'"
                           " AND s.outcome IN ('great','ok','spoiled') ORDER BY s.settled_at LIMIT 1",
                           (who,)).fetchall():
        _earn(conn, who, "own_dish", st["settled_at"], st["session_id"], _why("own_dish", dish=st["dish"]))
    w = conn.execute("SELECT dish, wormed_at FROM cook_sessions WHERE who=? AND wormed_at IS NOT NULL"
                     " ORDER BY wormed_at LIMIT 1", (who,)).fetchone()
    if w:
        _earn(conn, who, "first_worm", w["wormed_at"], "", _why("first_worm", dish=w["dish"]))
    egg_pages = set()
    merges = _merges(conn, who)
    for p in pots:
        try:
            used = json.loads(p["ingredients_json"] or "[]")
        except ValueError:
            used = []
        if any(u.get("item_id") == "egg" for u in used):
            egg_pages.add(page_key(p, merges))
    if len(egg_pages) >= 50:
        _earn(conn, who, "fifty_eggs", now, "", _why("fifty_eggs"))
    clean = conn.execute("SELECT COUNT(*), MAX(done_at) FROM dishes WHERE who=? AND state='clean'", (who,)).fetchone()
    if clean[0] >= 100:
        _earn(conn, who, "hundred_plates", clean[1] or now, "", _why("hundred_plates"))
    if play.on("seal_jars"):
        j = conn.execute("SELECT name, opened_at FROM jar_goods WHERE who=? AND ok=1 ORDER BY opened_at LIMIT 1",
                         (who,)).fetchone()
        if j:
            _earn(conn, who, "first_jar", j["opened_at"], "", _why("first_jar", goods=j["name"]))
    if play.on("vendor"):
        n = conn.execute("SELECT COUNT(*) FROM vendor_orders WHERE who=? AND payer='self' AND state='delivered'",
                         (who,)).fetchone()[0]
        if n >= 10:
            _earn(conn, who, "vendor_regular", now, "", _why("vendor_regular"))
    after = {r["ach"] for r in conn.execute("SELECT ach FROM achievements_earned WHERE who=?", (who,)).fetchall()}
    return sorted(after - before)


def earned_for_role(conn, who: str) -> list[str]:
    """What the role may read: only what it has earned (this function cannot name the others)."""
    out = []
    for r in conn.execute("SELECT ach, earned_at, why FROM achievements_earned WHERE who=? ORDER BY earned_at",
                          (who,)).fetchall():
        a = _ACH.get(r["ach"])
        if a is not None:
            out.append(tp("ach_line", name=a[1], md=_md(r["earned_at"]), why=r["why"]))
    return out


def all_for_human(conn, who: str) -> list[dict]:
    """Every achievement for the human's page, earned or not ("first jar" and "vendor regular" only
    while jars / vendors are on, unless already earned)."""
    got = {r["ach"]: dict(r) for r in conn.execute("SELECT * FROM achievements_earned WHERE who=?", (who,)).fetchall()}
    out = []
    for key, name, _w in ACHIEVEMENTS:
        if key == "first_jar" and not play.on("seal_jars") and key not in got:
            continue
        if key == "vendor_regular" and not play.on("vendor") and key not in got:
            continue
        g = got.get(key)
        out.append({"key": key, "name": name, "earned": bool(g), "earned_at": g["earned_at"] if g else None,
                    "why": g["why"] if g else ""})
    return out
