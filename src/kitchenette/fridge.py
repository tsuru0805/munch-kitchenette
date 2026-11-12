"""The fridge: ingredients kept per purchase, coupons, satiety and dizziness.

- Stock is kept per batch: buying the same thing twice makes two batches,
  each ageing on its own. Freshness is computed when read, from the purchase
  time: under half the shelf life is fresh, up to the full shelf life is
  stale, beyond it is spoiled. Spoiled batches vanish a few days later.
- Staples (rice, oil, salt, soy sauce) are always there and never counted.
- Cooking takes the oldest unspoiled batches first and only then the spoiled
  ones; one pot's ingredients are taken atomically.
- A coupon buys up to a handful of kinds. Coupons are capped; the human can
  also hand one out, or buy groceries directly without a coupon.
- Some items (eggs by default) hide their freshness from the role: it only
  sees the purchase date and finds out when it cracks one open.
- Satiety falls over time and rises with meals and snacks. Eating a dish made
  from spoiled food leaves the role dizzy for a while.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import urllib.parse
import uuid

from . import clock, config, db, roles
from .texts import CATEGORY_LABEL, FRESH_LABEL, t

log = logging.getLogger(__name__)

DAY = 86400.0
BY_HER = "her"
BY_SELF = "self"
SOURCE_HER = "her"            # coupon source: handed out by the human

FRIDGE_LIST_MAX = 8           # batches listed when a receipt mentions what is in the fridge

FRESH, MEH, BAD = "fresh", "meh", "bad"
_RANK = {BAD: 0, MEH: 1, FRESH: 2}
GREAT, OK, BURNT, SPOILED = "great", "ok", "burnt", "spoiled"

KIND_ID_PREFIX = "u_"
KIND_NAME_MAX = 8
KIND_MAX = 200                # a guard against runaway growth, not a rule
KIND_PACK_MAX = 12
KIND_DAYS_MAX = 60
# art states of a custom kind; ART_NONE = no artwork source configured, show a text card
ART_PENDING, ART_READY, ART_FAILED, ART_NONE = "pending", "ready", "failed", "none"
_NAME_BAD_RE = re.compile(r"[\s、,，;；/×xX*\[\]【】()()\d]")
_KINDS_TTL = 2.0
_kinds_cache: dict[str, tuple[float, list[dict]]] = {}


def _cfg():
    return config.get()


def _now() -> float:
    return clock.now()


def _hm(ts: float) -> str:
    return clock.hm(ts)


def _conn() -> sqlite3.Connection:
    return db.connect()


def _db_path() -> str:
    return db.path()


def _check_viewer(who: str) -> None:
    roles.check(who)


class FridgeError(Exception):
    """A refusal with the sentence to show and a short machine-readable code."""

    def __init__(self, text: str, code: str = "fridge_error"):
        super().__init__(text)
        self.text = text
        self.code = code


# ── catalog ─────────────────────────────────────────────────────────────

_index_cache: tuple[int, dict, dict] | None = None


def _index() -> tuple[dict[str, dict], dict[str, str]]:
    """(by id, name-or-alias -> id) for the built-in catalog; rebuilt when settings change."""
    global _index_cache
    v = config.version()
    if _index_cache is None or _index_cache[0] != v:
        by_id = {it["id"]: it for it in _cfg().fridge_ingredients}
        names: dict[str, str] = {}
        for it in _cfg().fridge_ingredients:
            names[it["name"]] = it["id"]
            for a in it.get("aliases", ()):
                names[a] = it["id"]
        _index_cache = (v, by_id, names)
    return _index_cache[1], _index_cache[2]


def builtin(item_id: str) -> dict | None:
    return _index()[0].get(item_id)


def shelf_days(item: dict) -> float:
    """Days an item keeps: the per-item setting, else its own value, else its category's."""
    per_item = _cfg().fridge_shelf_days
    own = per_item.get(item["id"], per_item.get(item["name"])) if per_item else None
    return float(own or item.get("shelf_days") or _cfg().fridge_category_days[item["category"]])


def hidden_freshness(item_id: str) -> bool:
    """Items whose freshness the role cannot see."""
    return item_id in _cfg().fridge_hidden_freshness


def all_items() -> list[dict]:
    """Everything that can be bought now: the built-in catalog plus custom kinds still offered."""
    return list(_cfg().fridge_ingredients) + [k for k in kinds() if not k["removed"]]


def item(item_id: str) -> dict | None:
    """id -> kind. Removed custom kinds still resolve (batches of them may remain in a fridge)."""
    it = builtin(item_id)
    if it is not None or not str(item_id).startswith(KIND_ID_PREFIX):
        return it
    return next((k for k in kinds() if k["id"] == item_id), None)


def is_raw_edible(item_id: str | None) -> bool:
    """Can be eaten straight from the fridge, no pot needed."""
    if item_id in _cfg().fridge_raw_edible:
        return True
    it = item(item_id) if item_id else None
    return bool(it and it.get("raw_edible"))


def catalog() -> list[dict]:
    out = []
    for it in all_items():
        row = {"id": it["id"], "name": it["name"], "category": it["category"],
               "category_label": CATEGORY_LABEL.get(it["category"], it["category"]),
               "pack_qty": it["pack_qty"], "shelf_days": shelf_days(it),
               "raw_edible": is_raw_edible(it["id"]), "custom": bool(it.get("custom"))}
        if it.get("custom"):
            row["art"] = it["art"]
        out.append(row)
    return out


def catalog_names() -> str:
    return "、".join(it["name"] for it in all_items())


def catalog_by_category() -> str:
    """Buyable names grouped by category: "蔬菜 番茄/黄瓜…;叶菜 菠菜/…"."""
    groups: dict[str, list[str]] = {}
    for it in all_items():
        groups.setdefault(it["category"], []).append(it["name"])
    order = [c for c in CATEGORY_LABEL if c in groups] + [c for c in groups if c not in CATEGORY_LABEL]
    return ";".join(f"{CATEGORY_LABEL.get(c, c)} {'/'.join(groups[c])}" for c in order)


def resolve(name: str, *, gone: bool = False) -> str | None:
    """A name or alias -> catalog id, or None. With gone=True, removed custom kinds resolve too:
    buying must not find them, but using up, eating or tossing what is left must."""
    n = (name or "").strip()
    iid = _index()[1].get(n)
    if iid is None and n:
        ks = kinds()
        iid = next((k["id"] for k in ks if not k["removed"] and k["name"] == n), None)
        if iid is None and gone:
            iid = next((k["id"] for k in reversed(ks) if k["name"] == n), None)
    return iid


def is_staple(name: str) -> bool:
    return (name or "").strip() in _cfg().fridge_staple_aliases


_QTY_RE = re.compile(r"^(.+?)\s*[×xX*]\s*(\d+)$")
_SPLIT_RE = re.compile(r"[\s、,，;；/]+")


def parse_list(text: str) -> list[tuple[str, int]]:
    """"番茄 鸡蛋×2、牛奶" -> [(番茄,1),(鸡蛋,2),(牛奶,1)]."""
    out: list[tuple[str, int]] = []
    for tok in _SPLIT_RE.split((text or "").strip()):
        if not tok:
            continue
        m = _QTY_RE.match(tok)
        if m:
            out.append((m.group(1).strip(), max(1, int(m.group(2)))))
        else:
            out.append((tok, 1))
    return out


# ── small storage helpers ───────────────────────────────────────────────

def _log(conn, who: str, kind: str, text: str, at: float | None = None) -> None:
    conn.execute("INSERT INTO fridge_log (who, at, kind, text) VALUES (?,?,?,?)",
                 (who, at if at is not None else _now(), kind, text))


def _once(conn, key: str) -> str | None:
    r = conn.execute("SELECT result FROM once_keys WHERE key=?", (key,)).fetchone()
    return None if r is None else r["result"]


def _mark_once(conn, key: str, result: str = "") -> None:
    conn.execute("INSERT OR IGNORE INTO once_keys (key, at, result) VALUES (?,?,?)",
                 (key, _now(), result))


# ── custom kinds (added from the page) ──────────────────────────────────

def _kind_row(r) -> dict:
    try:
        sizes = json.loads(r["art_sizes"]) if r["art_sizes"] else {}
    except ValueError:
        sizes = {}
    k = {"id": r["id"], "name": r["name"], "category": r["category"], "pack_qty": int(r["pack_qty"]),
         "custom": True, "raw_edible": bool(r["raw_edible"]), "removed": r["removed_at"] is not None,
         "art": {"state": r["art_state"], "v": int(r["art_v"]), "sizes": sizes, "err": r["art_err"]},
         "art_req": int(r["art_req"])}
    if r["shelf_days"]:
        k["shelf_days"] = float(r["shelf_days"])
    return k


def kinds() -> list[dict]:
    """All custom kinds, removed ones included, oldest first. Cached briefly per process.

    Reads through a read-only connection: this is often called from inside
    someone else's write transaction, where opening a normal connection could
    wait on the very lock the caller holds.
    """
    path = _db_path()
    hit = _kinds_cache.get(path)
    if hit and time.monotonic() - hit[0] < _KINDS_TTL:
        return hit[1]
    if not os.path.isfile(path):
        return []
    conn = sqlite3.connect(f"file:{urllib.parse.quote(path)}?mode=ro", uri=True, timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        rows = [_kind_row(r) for r in conn.execute("SELECT * FROM kinds ORDER BY created_at, id").fetchall()]
    except sqlite3.OperationalError as e:
        if "no such table" not in str(e):
            log.error("reading custom kinds failed: %s", e)
            raise
        rows = []
    finally:
        conn.close()
    _kinds_cache[path] = (time.monotonic(), rows)
    return rows


def kind(kind_id: str) -> dict | None:
    _kinds_cache.pop(_db_path(), None)
    return next((k for k in kinds() if k["id"] == kind_id), None)


def _known(item_id: str) -> dict:
    it = item(item_id)
    if it is None:
        raise KeyError(item_id)
    return it


def add_kind(name: str, category: str, *, raw_edible: bool | None = None, pack_qty: int = 1,
             shelf_days: float | None = None, now: float | None = None, art: bool = True) -> dict:
    """Add an ingredient kind. Raises FridgeError with the sentence to show.

    art=False (no artwork source configured) leaves the kind as a text card.
    Re-adding a kind that was removed brings the same row back, artwork included.
    """
    now = now or _now()
    name = (name or "").strip()
    if not name:
        raise FridgeError(t("kind_empty"), "empty")
    if len(name) > KIND_NAME_MAX:
        raise FridgeError(t("kind_name_long", max=KIND_NAME_MAX), "bad_name")
    if _NAME_BAD_RE.search(name):
        raise FridgeError(t("kind_name_bad"), "bad_name")
    if is_staple(name):
        raise FridgeError(t("kind_is_staple", name=name), "duplicate")
    category = category_id(category)
    if category is None:
        options = "、".join(f"{CATEGORY_LABEL.get(c, c)}({c})" for c in _cfg().fridge_category_days)
        raise FridgeError(t("kind_bad_category", options=options), "bad_category")
    if not 1 <= int(pack_qty) <= KIND_PACK_MAX:
        raise FridgeError(t("kind_bad_qty", max=KIND_PACK_MAX), "bad_qty")
    if shelf_days is not None and not 1 <= float(shelf_days) <= KIND_DAYS_MAX:
        raise FridgeError(t("kind_bad_days", max=KIND_DAYS_MAX), "bad_days")
    by_id, names = _index()
    hit = names.get(name)
    if hit:
        own = by_id[hit]["name"]
        raise FridgeError(t("kind_duplicate", name=name) if own == name
                          else t("kind_alias_duplicate", name=name, own=own), "duplicate")
    raw = (category == "fruit") if raw_edible is None else bool(raw_edible)
    fresh_state = ART_PENDING if art else ART_NONE
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("SELECT * FROM kinds").fetchall()
        same = next((r for r in rows if r["name"] == name), None)
        if same is not None and same["removed_at"] is None:
            conn.rollback()
            raise FridgeError(t("kind_duplicate", name=name), "duplicate")
        if sum(1 for r in rows if r["removed_at"] is None) >= KIND_MAX:
            conn.rollback()
            raise FridgeError(t("kind_too_many", max=KIND_MAX), "too_many")
        if same is not None:
            kid = same["id"]
            keep_art = same["art_state"] == ART_READY
            conn.execute("UPDATE kinds SET category=?, pack_qty=?, shelf_days=?, raw_edible=?, removed_at=NULL,"
                         " art_state=?, art_err='', art_req=art_req+? WHERE id=?",
                         (category, int(pack_qty), shelf_days, int(raw), ART_READY if keep_art else fresh_state,
                          0 if keep_art else 1, kid))
        else:
            kid = KIND_ID_PREFIX + uuid.uuid4().hex[:10]
            conn.execute("INSERT INTO kinds (id, name, category, pack_qty, shelf_days, raw_edible, art_state,"
                         " created_at) VALUES (?,?,?,?,?,?,?,?)",
                         (kid, name, category, int(pack_qty), shelf_days, int(raw), fresh_state, now))
        conn.commit()
    finally:
        conn.close()
    return kind(kid)


def category_id(given: str) -> str | None:
    """A category as typed on the page -> its key. Both the key ("staple_food") and the label
    shown to people ("主食") are accepted."""
    g = (given or "").strip()
    if g in _cfg().fridge_category_days:
        return g
    return next((c for c, lab in CATEGORY_LABEL.items() if lab == g and c in _cfg().fridge_category_days), None)


def remove_kind(kind_id: str, now: float | None = None) -> dict:
    """Stop offering a custom kind. What is already in a fridge stays and can still be used."""
    k = kind(kind_id)
    if k is None or k["removed"]:
        raise FridgeError(t("kind_gone"), "unknown_item")
    conn = _conn()
    try:
        conn.execute("UPDATE kinds SET removed_at=? WHERE id=?", (now or _now(), kind_id))
        conn.commit()
    finally:
        conn.close()
    return kind(kind_id)


def redraw_kind(kind_id: str) -> dict:
    """Ask for the artwork again. The old picture stays until the new one is ready."""
    k = kind(kind_id)
    if k is None or k["removed"]:
        raise FridgeError(t("kind_gone"), "unknown_item")
    conn = _conn()
    try:
        conn.execute("UPDATE kinds SET art_state=?, art_err='', art_req=art_req+1 WHERE id=?", (ART_PENDING, kind_id))
        conn.commit()
    finally:
        conn.close()
    return kind(kind_id)


def set_art(kind_id: str, state: str, *, sizes: dict | None = None, err: str = "",
            v: int | None = None, req: int | None = None) -> bool:
    """Record the result of a drawing. req is the request number the drawing was started for:
    if a redraw was asked meanwhile the number no longer matches and this result is dropped (False)."""
    conn = _conn()
    try:
        cond, args = ("", ()) if req is None else (" AND art_req=?", (req,))
        if state == ART_READY:
            cur = conn.execute("UPDATE kinds SET art_state=?, art_v=COALESCE(?, art_v+1), art_sizes=?, art_err=''"
                               " WHERE id=?" + cond, (state, v, json.dumps(sizes or {}), kind_id, *args))
        else:
            cur = conn.execute("UPDATE kinds SET art_state=?, art_err=? WHERE id=?" + cond,
                               (state, (err or "")[:200], kind_id, *args))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
        _kinds_cache.pop(_db_path(), None)


# ── freshness ───────────────────────────────────────────────────────────

def bought_md(ts: float) -> str:
    d = clock.local(ts)
    return f"{d.month}-{d.day:02d}"


def tag_for_him(item_id: str, freshness: str, bought_at: float, wormed: bool = False) -> str:
    """The bracket the role sees after an item: purchase date for hidden-freshness items,
    "wormed" for wormy fruit, nothing when fresh, the freshness label otherwise."""
    if wormed:
        return t("tag_wormed")
    if hidden_freshness(item_id):
        return t("tag_bought", md=bought_md(bought_at))
    return "" if freshness == FRESH else t("tag_freshness", label=FRESH_LABEL[freshness])


def freshness(item_id: str, bought_at: float, now: float, days: float | None = None) -> str:
    """days = the shelf life recorded on the batch (custom kinds); otherwise from the catalog."""
    ratio = (now - bought_at) / ((days or shelf_days(_known(item_id))) * DAY)
    if ratio < 0.5:
        return FRESH
    if ratio <= 1.0:
        return MEH
    return BAD


def expires_at(item_id: str, bought_at: float, days: float | None = None) -> float:
    return bought_at + (days or shelf_days(_known(item_id))) * DAY


def _clear_spoiled(conn, who: str, now: float) -> None:
    """Remove batches that have been spoiled long enough, logging each one.
    Hidden-freshness items never vanish on their own: the role cannot tell they went bad."""
    rows = conn.execute("SELECT * FROM batches WHERE who=?", (who,)).fetchall()
    for r in rows:
        if item(r["item_id"]) is None or hidden_freshness(r["item_id"]):
            continue
        if now > expires_at(r["item_id"], r["bought_at"], r["shelf_days"]) + _cfg().fridge_clear_bad_after_days * DAY:
            conn.execute("DELETE FROM batches WHERE id=?", (r["id"],))
            _log(conn, who, "cleared", t("log_cleared", name=_known(r["item_id"])["name"]), now)


def _batches(conn, who: str, now: float) -> list[dict]:
    _clear_spoiled(conn, who, now)
    out = []
    for r in conn.execute("SELECT * FROM batches WHERE who=? AND qty>0 ORDER BY bought_at", (who,)).fetchall():
        it = item(r["item_id"])
        if it is None:
            continue
        f = freshness(r["item_id"], r["bought_at"], now, r["shelf_days"])
        b = {"batch_id": r["id"], "item_id": r["item_id"], "name": it["name"],
             "category": it["category"], "qty": r["qty"], "bought_at": r["bought_at"],
             "by": r["by_who"], "expires_at": expires_at(r["item_id"], r["bought_at"], r["shelf_days"]),
             "freshness": f, "wormed": bool(r["wormed_at"])}
        if it.get("custom"):
            b["art"] = it["art"]
        out.append(b)
    out.sort(key=lambda b: (_RANK[b["freshness"]], b["expires_at"]))
    return out


# ── reading ─────────────────────────────────────────────────────────────

def coupon_count(conn, who: str) -> int:
    r = conn.execute("SELECT count FROM coupons WHERE who=?", (who,)).fetchone()
    return int(r["count"]) if r else 0


def overview(who: str, now: float | None = None) -> dict:
    """Everything the kitchen page needs in one read."""
    _check_viewer(who)
    now = now or _now()
    conn = _conn()
    try:
        items = _batches(conn, who, now)
        coupons = coupon_count(conn, who)
        log_rows = conn.execute(
            "SELECT at, kind, text FROM fridge_log WHERE who=? ORDER BY at DESC, id DESC LIMIT 20",
            (who,)).fetchall()
        sat = _satiety_read(conn, who, now)
        dz = _dizzy_read(conn, who, now)
        conn.commit()
    finally:
        conn.close()
    return {"now": now, "who": who, "items": items, "staples": list(_cfg().fridge_staples),
            "coupons": {"count": coupons, "max": _cfg().fridge_coupon_max},
            "log": [dict(r) for r in log_rows], "satiety": sat, "dizzy": dz}


def _him_order(items: list[dict]) -> list[dict]:
    """Order shown to the role: hidden-freshness items first by purchase date, then soonest to spoil.
    Listing them among the spoiled ones would give their state away."""
    hidden = sorted((b for b in items if hidden_freshness(b["item_id"])), key=lambda b: b["bought_at"])
    return hidden + [b for b in items if not hidden_freshness(b["item_id"])]


def _item_text(b: dict) -> str:
    return f"{b['name']}×{b['qty']}{tag_for_him(b['item_id'], b['freshness'], b['bought_at'], b.get('wormed'))}"


def _fridge_brief(items: list[dict], limit: int = FRIDGE_LIST_MAX) -> str:
    """Short listing of the fridge for receipts; empty string when the fridge is empty."""
    parts = [_item_text(b) for b in _him_order(items)[:limit]]
    more = t("brief_more", n=len(items)) if len(items) > limit else ""
    return "、".join(parts) + more


def status_text(who: str, now: float | None = None) -> str:
    """The fridge paragraph attached to the kitchen status and the menu."""
    ov = overview(who, now)
    lines = []
    items = ov["items"]
    if items:
        lines.append(t("status_fridge", items="、".join(_item_text(b) for b in _him_order(items))))
    else:
        lines.append(t("status_fridge_empty"))
    lines.append(t("status_coupons", n=ov["coupons"]["count"], max=_cfg().fridge_coupon_max))
    lines.append(t("status_buyable", catalog=catalog_by_category()))
    dz = ov["dizzy"]
    if dz:
        lines.append(t("status_dizzy", hm=_hm(dz["until"])))
    if _cfg().satiety_enabled:
        lines.append(t("status_satiety", pct=round(ov["satiety"]["value"])))
    return "\n".join(lines)


# ── buying ──────────────────────────────────────────────────────────────

def _add_batches(conn, who: str, ids: list[str], by: str, source: str, now: float) -> list[dict]:
    added = []
    for iid in ids:
        it, days = builtin(iid), None
        if it is None:
            # Custom kinds are re-read inside this write transaction rather than trusted from the
            # cache: one removed a moment ago must not be bought (the caller rolls everything back).
            r = conn.execute("SELECT * FROM kinds WHERE id=?", (iid,)).fetchone()
            if r is None or r["removed_at"] is not None:
                raise FridgeError(t("buy_kind_removed", name=r["name"] if r else iid), "unknown_item")
            it = _kind_row(r)
            days = shelf_days(it)
        bid = uuid.uuid4().hex
        conn.execute("INSERT INTO batches (id, who, item_id, qty, bought_at, by_who, source, shelf_days)"
                     " VALUES (?,?,?,?,?,?,?,?)", (bid, who, iid, it["pack_qty"], now, by, source, days))
        added.append({"item_id": iid, "name": it["name"], "qty": it["pack_qty"]})
    return added


def _names_of(added: list[dict]) -> str:
    return "、".join(f"{a['name']}×{a['qty']}" for a in added)


def earn_hint() -> str:
    return (_cfg().coupons_earn_hint or "").strip()


def coupons_from_human() -> str:
    """Where coupons come from when nothing the role does earns one: said after "you have none",
    so that being out of coupons is never a dead end. Empty once earning is configured."""
    return "" if (_cfg().coupons_earn or earn_hint()) else t("coupon_from_human")


def buy_self(who: str, text: str, *, key: str, now: float | None = None) -> str:
    """The role buys groceries with one coupon. key makes the purchase idempotent:
    repeating the same order neither spends a second coupon nor buys twice.
    Returns the receipt; raises FridgeError with the reason otherwise."""
    _check_viewer(who)
    now = now or _now()
    wanted = parse_list(text)
    if not wanted:
        raise FridgeError(t("buy_empty"), "empty")
    ids: list[str] = []
    unknown: list[str] = []
    for name, _n in wanted:
        if is_staple(name):
            continue
        iid = resolve(name)
        if iid is None:
            unknown.append(name)
        elif iid not in ids:
            ids.append(iid)
    if unknown:
        raise FridgeError(t("buy_unknown", names="、".join(unknown), catalog=catalog_names()), "unknown_item")
    if not ids:
        raise FridgeError(t("buy_only_staples"), "only_staples")
    if len(ids) > _cfg().fridge_buy_max_items:
        raise FridgeError(t("buy_too_many", max=_cfg().fridge_buy_max_items, n=len(ids)), "too_many")
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = _once(conn, f"buy:{key}")
        if done is not None:
            conn.rollback()
            return done
        n = coupon_count(conn, who)
        if n <= 0:
            conn.rollback()
            hint = earn_hint()
            raise FridgeError(t("buy_no_coupon") + (t("buy_no_coupon_hint", hint=hint) if hint else "")
                              + coupons_from_human(), "no_coupon")
        before = _fridge_brief(_batches(conn, who, now))
        conn.execute("UPDATE coupons SET count=count-1 WHERE who=?", (who,))
        added = _add_batches(conn, who, ids, BY_SELF, "coupon", now)
        receipt = (t("buy_ok", names=_names_of(added), left=n - 1)
                   + (t("buy_before", before=before) if before else ""))
        _log(conn, who, "bought", t("log_bought_self", names=_names_of(added)), now)
        _mark_once(conn, f"buy:{key}", receipt)
        conn.commit()
        return receipt
    finally:
        conn.close()


_TOSS_BAD_WORDS = ("坏了的", "坏的", "坏掉的", "坏了")
_DATE_RE = re.compile(r"(\d{1,2})[-/.月](\d{1,2})日?")


def _box_cooked(conn, who: str, ids: list[str], days: set[str]) -> bool:
    """Whether a box bought on one of these days already went into a pot."""
    rows = conn.execute("SELECT ingredients_json FROM cook_sessions WHERE who=?"
                        " ORDER BY started_at DESC LIMIT 200", (who,)).fetchall()
    for r in rows:
        try:
            used = json.loads(r["ingredients_json"] or "[]")
        except ValueError:
            continue
        for u in used:
            if u.get("item_id") in ids and u.get("bought_at") and bought_md(float(u["bought_at"])) in days:
                return True
    return False


def toss_self(who: str, text: str, *, key: str, now: float | None = None) -> str:
    """The role throws things out of the fridge.

    "坏了的" tosses every batch known to be spoiled (never hidden-freshness items);
    a name tosses every batch of that item, fresh or not; a name plus a date
    ("鸡蛋 10-25") tosses only the batch bought that day. key makes it idempotent.
    Returns the receipt; raises FridgeError saying why nothing was tossed.
    """
    _check_viewer(who)
    now = now or _now()
    raw = (text or "").strip()
    if not raw:
        raise FridgeError(t("toss_empty"), "empty")
    want_bad = any(w in raw for w in _TOSS_BAD_WORDS)
    days = {f"{int(m)}-{int(d):02d}" for m, d in _DATE_RE.findall(raw)}
    raw_names = _DATE_RE.sub(" ", raw)
    names = [] if want_bad else [n for n, _ in parse_list(raw_names)]
    ids, unknown = [], []
    for n in names:
        iid = resolve(n, gone=True)
        if iid is None:
            unknown.append(n)
        elif iid not in ids:
            ids.append(iid)
    if unknown:
        raise FridgeError(t("toss_unknown", names="、".join(unknown)), "unknown_item")
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = _once(conn, f"toss:{key}")
        if done is not None:
            conn.rollback()
            return done
        batches = _batches(conn, who, now)
        hit = [b for b in batches
               if (b["freshness"] == BAD and not hidden_freshness(b["item_id"]) if want_bad
                   else b["item_id"] in ids)
               and (not days or bought_md(b["bought_at"]) in days)]
        if not hit:
            used_up = bool(days and ids) and _box_cooked(conn, who, ids, days)
            conn.rollback()
            if want_bad:
                raise FridgeError(t("toss_nothing_bad"), "nothing_bad")
            when = t("toss_when", days="、".join(sorted(days))) if days else ""
            if used_up:
                raise FridgeError(t("toss_used_up", when=when, names="、".join(names)), "used_up")
            raise FridgeError(t("toss_not_in_fridge", when=when, names="、".join(names)), "not_in_fridge")
        for b in hit:
            conn.execute("DELETE FROM batches WHERE id=? AND who=?", (b["batch_id"], who))
        what = "、".join(_item_text(b) for b in _him_order(hit))
        receipt = t("toss_ok", what=what)
        _log(conn, who, "tossed", t("log_tossed", what=what), now)
        _mark_once(conn, f"toss:{key}", receipt)
        conn.commit()
        return receipt
    finally:
        conn.close()


def buy_her(who: str, item_ids: list[str], now: float | None = None) -> dict:
    """The human buys for the role: no coupon needed. Returns {added, text}."""
    _check_viewer(who)
    now = now or _now()
    ids: list[str] = []
    for iid in item_ids or []:
        it = item(iid)
        if it is None or it.get("removed"):
            raise FridgeError(t("her_buy_unknown", id=iid), "unknown_item")
        ids.append(iid)
    if not ids:
        raise FridgeError(t("her_buy_empty"), "empty")
    if len(ids) > _cfg().fridge_human_buy_max_items:
        raise FridgeError(t("her_buy_too_many", max=_cfg().fridge_human_buy_max_items), "too_many")
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            added = _add_batches(conn, who, ids, BY_HER, "her", now)
        except FridgeError:
            conn.rollback()
            raise
        _log(conn, who, "bought", t("log_bought_her", names=_names_of(added)), now)
        conn.commit()
    finally:
        conn.close()
    return {"added": added, "text": t("her_buy_ok", names=_names_of(added))}


# ── coupons ─────────────────────────────────────────────────────────────

def grant_coupon(who: str, source: str, key: str, now: float | None = None) -> int | None:
    """One more coupon, up to the cap. source is SOURCE_HER or the label of what the role made
    ("日记"). key makes it idempotent (one coupon per piece of work).
    Returns the new count, or None when capped or repeated; a capped grant still leaves a log line."""
    return grant_coupon_ex(who, source, key, now)[0]


def grant_coupon_ex(who: str, source: str, key: str, now: float | None = None) -> tuple[int | None, str]:
    """grant_coupon that also says why nothing was granted: (count, "") or (None, "duplicate" | "full")."""
    _check_viewer(who)
    now = now or _now()
    cap = _cfg().fridge_coupon_max
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if _once(conn, f"coupon:{key}") is not None:
            conn.rollback()
            return None, "duplicate"
        _mark_once(conn, f"coupon:{key}")
        n = coupon_count(conn, who)
        label = t("coupon_source_her") if source == SOURCE_HER else source
        if n >= cap:
            _log(conn, who, "coupon_full", t("log_coupon_full", label=label, max=cap), now)
            conn.commit()
            return None, "full"
        conn.execute("INSERT INTO coupons (who, count) VALUES (?, 1)"
                     " ON CONFLICT(who) DO UPDATE SET count=count+1", (who,))
        _log(conn, who, "coupon",
             t("log_coupon_her") if source == SOURCE_HER else t("log_coupon", label=label), now)
        conn.commit()
        return n + 1, ""
    finally:
        conn.close()


def grant_coupon_by_her(who: str, now: float | None = None) -> int:
    """The human hands out a coupon; refused with FridgeError when the role is at the cap."""
    _check_viewer(who)
    cap = _cfg().fridge_coupon_max
    conn = _conn()
    try:
        full = coupon_count(conn, who) >= cap
    finally:
        conn.close()
    if full:
        raise FridgeError(t("her_coupon_full", max=cap), "coupon_full")
    n = grant_coupon(who, SOURCE_HER, f"her:{uuid.uuid4().hex}", now)
    if n is None:
        raise FridgeError(t("her_coupon_full", max=cap), "coupon_full")
    return n


def coupon_source_for_tool(tool_name: str) -> str | None:
    """Tool name (bare, or "server__tool") -> label of the work that earns a coupon, or None."""
    name = (tool_name or "").split("__")[-1]
    return _cfg().coupons_earn.get(name)


def coupon_receipt(n: int) -> str:
    return t("coupon_receipt", n=n, max=_cfg().fridge_coupon_max)


# ── taking ingredients for a pot ────────────────────────────────────────

def take_for_cooking(who: str, wanted: list[tuple[str, int]], now: float | None = None) -> list[dict]:
    """take_in_tx in a transaction of its own."""
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            used = take_in_tx(conn, who, wanted, now)
        except Exception:
            conn.rollback()
            raise
        conn.commit()
        return used
    finally:
        conn.close()


def take_in_tx(conn, who: str, wanted: list[tuple[str, int]], now: float | None = None) -> list[dict]:
    """Take ingredients inside the caller's transaction (no commit, no rollback here).

    wanted = [(name, count)]; staples are skipped. Unspoiled batches go first,
    oldest first; spoiled ones only when nothing else is left. Returns what was
    actually used, per batch. Unknown or missing items raise FridgeError and
    leave the stock untouched.
    """
    _check_viewer(who)
    now = now or _now()
    need: dict[str, int] = {}
    unknown: list[str] = []
    for name, n in wanted:
        if is_staple(name):
            continue
        iid = resolve(name, gone=True)
        if iid is None:
            unknown.append(name)
            continue
        need[iid] = need.get(iid, 0) + n
    if unknown:
        raise FridgeError(t("take_unknown", names="、".join(unknown), catalog=catalog_names()), "unknown_item")
    if not need:
        raise FridgeError(t("take_no_ingredients"), "no_ingredients")
    batches = _batches(conn, who, now)
    short = []
    plan: list[tuple[dict, int]] = []
    for iid, n in need.items():
        mine = [b for b in batches if b["item_id"] == iid]
        if hidden_freshness(iid):
            mine.sort(key=lambda b: b["bought_at"])          # cannot tell good from bad: oldest box first
        else:
            mine.sort(key=lambda b: (b["freshness"] == BAD, b["bought_at"]))
        have = sum(b["qty"] for b in mine)
        if have < n:
            short.append(t("take_short_item", name=_known(iid)["name"], n=n, have=have))
            continue
        left = n
        for b in mine:
            if left <= 0:
                break
            use = min(left, b["qty"])
            plan.append((b, use))
            left -= use
    if short:
        # Never point at a dead end: "go and buy" only with a coupon in hand, and how to earn one
        # only when something does earn one.
        hint, n_coupons = earn_hint(), coupon_count(conn, who)
        parts = ([t("take_short_hint", hint=hint)] if hint else []) + ([t("take_short_go")] if n_coupons > 0 else [])
        raise FridgeError(t("take_short", short="、".join(short), n=n_coupons,
                            how=t("take_short_how", parts=";".join(parts)) if parts else "")
                          + (coupons_from_human() if n_coupons <= 0 else ""), "short")
    used = []
    for b, use in plan:
        conn.execute("UPDATE batches SET qty=qty-? WHERE id=?", (use, b["batch_id"]))
        used.append({"item_id": b["item_id"], "name": b["name"], "qty": use, "freshness": b["freshness"],
                     "batch_id": b["batch_id"], "bought_at": b["bought_at"], "by": b["by"]})
    conn.execute("DELETE FROM batches WHERE who=? AND qty<=0", (who,))
    return used


def put_back(who: str, used: list[dict]) -> None:
    """Return ingredients to their batches (a batch already gone is rebuilt with its original date)."""
    conn = _conn()
    try:
        for u in used:
            cur = conn.execute("UPDATE batches SET qty=qty+? WHERE id=? AND who=?",
                               (u["qty"], u["batch_id"], who))
            if cur.rowcount == 0:
                conn.execute("INSERT INTO batches (id, who, item_id, qty, bought_at, by_who, source)"
                             " VALUES (?,?,?,?,?,?,?)", (u["batch_id"], who, u["item_id"], u["qty"],
                                                        u["bought_at"], u.get("by") or BY_SELF, "put_back"))
        conn.commit()
    finally:
        conn.close()


# ── how a pot turns out (pure: the same pot always gets the same result) ─

def decide_outcome(session_id: str, used: list[dict]) -> str:
    """All fresh = great; anything spoiled = spoiled (eating it causes dizziness);
    anything stale = a fixed chance to burn, decided by a hash of the pot id, otherwise ok."""
    if not used:
        return OK
    fs = {u.get("freshness") for u in used}
    if BAD in fs:
        return SPOILED
    if MEH in fs:
        h = int(hashlib.sha1(f"burn:{session_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return BURNT if h < _cfg().fridge_burn_chance_meh else OK
    return GREAT


# ── satiety and dizziness ───────────────────────────────────────────────

def _appetite_row(conn, who: str, now: float) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM appetite WHERE who=?", (who,)).fetchone()
    if r is None:
        conn.execute("INSERT OR IGNORE INTO appetite (who, satiety, satiety_at) VALUES (?,?,?)",
                     (who, _cfg().satiety_init, now))
        r = conn.execute("SELECT * FROM appetite WHERE who=?", (who,)).fetchone()
    return r


def _satiety_now(r, now: float) -> float:
    return max(0.0, float(r["satiety"])
               - _cfg().satiety_decay_per_hour * max(0.0, now - float(r["satiety_at"])) / 3600.0)


def _satiety_read(conn, who: str, now: float) -> dict:
    r = _appetite_row(conn, who, now)
    return {"value": round(_satiety_now(r, now), 1), "updated_at": float(r["satiety_at"]),
            "enabled": bool(_cfg().satiety_enabled)}


def satiety(who: str, now: float | None = None) -> float:
    """Current satiety, 0-100."""
    now = now or _now()
    conn = _conn()
    try:
        v = _satiety_now(_appetite_row(conn, who, now), now)
        conn.commit()
        return v
    finally:
        conn.close()


def _dizzy_read(conn, who: str, now: float) -> dict | None:
    r = _appetite_row(conn, who, now)
    if r["dizzy_until"] and now < float(r["dizzy_until"]):
        return {"until": float(r["dizzy_until"]), "dish": r["dizzy_dish"] or "",
                "since": float(r["dizzy_since"] or now)}
    return None


def _fill_in_tx(conn, who: str, gain: float, now: float) -> float:
    r = _appetite_row(conn, who, now)
    if not _cfg().satiety_enabled:
        return _satiety_now(r, now)
    v = min(_cfg().satiety_max, _satiety_now(r, now) + max(0.0, gain))
    conn.execute("UPDATE appetite SET satiety=?, satiety_at=? WHERE who=?", (v, now, who))
    return v


def fill(who: str, gain: float, *, key: str | None = None, why: str = "",
         now: float | None = None) -> float | None:
    """Raise satiety (capped). key makes it idempotent. Returns the new value; None when repeated."""
    _check_viewer(who)
    now = now or _now()
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if key is not None:
            if _once(conn, f"fill:{key}") is not None:
                conn.rollback()
                return None
            _mark_once(conn, f"fill:{key}")
        v = _fill_in_tx(conn, who, gain, now)
        conn.commit()
        return v
    finally:
        conn.close()


def settle_meal(who: str, gain: float, *, key: str, dizzy_dish: str | None = None,
                now: float | None = None) -> float | None:
    """settle_meal_in_tx in a transaction of its own."""
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        v = settle_meal_in_tx(conn, who, gain, key=key, dizzy_dish=dizzy_dish, now=now)
        if v is None:
            conn.rollback()
            return None
        conn.commit()
        return v
    finally:
        conn.close()


def settle_meal_in_tx(conn, who: str, gain: float, *, key: str, dizzy_dish: str | None = None,
                      now: float | None = None) -> float | None:
    """Inside the caller's transaction: raise satiety, start the dizziness for a spoiled dish,
    and record the idempotency key. A repeated bite returns None having written nothing."""
    _check_viewer(who)
    now = now or _now()
    if _once(conn, f"fill:{key}") is not None:
        return None
    _mark_once(conn, f"fill:{key}")
    v = _fill_in_tx(conn, who, gain, now)
    if dizzy_dish:
        conn.execute("UPDATE appetite SET dizzy_until=?, dizzy_dish=?, dizzy_since=?, dizzy_over_told=0"
                     " WHERE who=?", (now + _cfg().satiety_dizzy_hours * 3600.0, dizzy_dish, now, who))
        _log(conn, who, "dizzy", t("log_dizzy", dish=dizzy_dish), now)
    return v


def make_dizzy(who: str, dish: str, now: float | None = None) -> float:
    """Start (or restart) the dizziness. Returns when it ends."""
    _check_viewer(who)
    now = now or _now()
    until = now + _cfg().satiety_dizzy_hours * 3600.0
    conn = _conn()
    try:
        _appetite_row(conn, who, now)
        conn.execute("UPDATE appetite SET dizzy_until=?, dizzy_dish=?, dizzy_since=?, dizzy_over_told=0"
                     " WHERE who=?", (until, dish, now, who))
        _log(conn, who, "dizzy", t("log_dizzy", dish=dish), now)
        conn.commit()
    finally:
        conn.close()
    return until


def hungry_line(conn, who: str, now: float) -> str:
    brief = _fridge_brief(_batches(conn, who, now))
    return (t("turn_hungry", head=t("head"), pct=int(_cfg().satiety_hungry_below))
            + (t("turn_hungry_fridge", brief=brief) if brief else t("turn_hungry_empty")))


def turn_lines(who: str, now: float | None = None) -> str | None:
    """Kitchen status worth carrying into each of the role's turns, or None.

    - while dizzy: one fixed line (written from the end time, so it does not change by the minute);
    - just recovered: "it has passed", once;
    - while satiety is under the threshold: "a bit hungry" plus what is in the fridge.
    """
    if not roles.valid(who):
        return None
    now = now or _now()
    lines: list[str] = []
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = _appetite_row(conn, who, now)
        until = float(r["dizzy_until"]) if r["dizzy_until"] else None
        if until and now < until:
            lines.append(t("turn_dizzy", head=t("head"), since=_hm(float(r["dizzy_since"] or now)),
                           dish=r["dizzy_dish"] or "", until=_hm(until)))
        elif until and not r["dizzy_over_told"]:
            lines.append(t("turn_dizzy_over", head=t("head")))
            conn.execute("UPDATE appetite SET dizzy_over_told=1 WHERE who=?", (who,))
        if _cfg().satiety_enabled and _satiety_now(r, now) < _cfg().satiety_hungry_below:
            lines.append(hungry_line(conn, who, now))
        conn.commit()
    finally:
        conn.close()
    return "\n".join(lines) or None


def hungry_due(who: str, now: float | None = None) -> str | None:
    """The "a bit hungry" line the first time satiety drops under the threshold, None otherwise.
    The reminder is re-armed once satiety is back above it."""
    if not _cfg().satiety_enabled or not roles.valid(who):
        return None
    now = now or _now()
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = _appetite_row(conn, who, now)
        hungry = _satiety_now(r, now) < _cfg().satiety_hungry_below
        line = None
        if hungry and not r["hungry_told"]:
            line = hungry_line(conn, who, now)
            conn.execute("UPDATE appetite SET hungry_told=1 WHERE who=?", (who,))
        elif not hungry and r["hungry_told"]:
            conn.execute("UPDATE appetite SET hungry_told=0 WHERE who=?", (who,))
        conn.commit()
        return line
    finally:
        conn.close()


def on_snack(who: str, tier: str, rid: str, now: float | None = None) -> None:
    """A snack raises satiety a little, by tier."""
    try:
        fill(who, _cfg().satiety_snack_gain.get(tier, 5.0), key=f"snack:{rid}", now=now)
    except Exception:  # noqa: BLE001
        log.warning("satiety for a snack was not recorded", exc_info=True)

