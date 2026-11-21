"""The role's own recipe pages (collected, adapted, its own, a whole menu, someone else's code),
tasting notes, the human's orders, recipe codes, and buying what a recipe lacks.

Identity: a public recipe is its id (every page that collects it counts as the same recipe); an
adapted page, an own page or an imported code is the page's own id, and editing it adds a version
without resetting anything; importing the same code twice gives the same page. A dish name is only
for searching, never an identity. The role can use the public recipes and the pages in its own book.

Every write happens in one transaction of the kitchen's database; marker keys come from the reply id
and the line number, so running the same reply twice writes nothing twice.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import uuid
import zlib

from . import play, recipes
from .texts_play import CODE_MAX_CHARS, MENU_MAX_DISHES, METHOD_CN, TAG_ITEMS_MAX, TAG_NAME_MAX, TAG_NOTE_MAX, tp

PAGE_PREFIX = "p-"
CODE_PREFIX = "KC1."
_CODE_FIELDS = {"v", "name", "items", "optional", "method", "minutes", "note", "source", "by"}
_STRIP_RE = re.compile(r"[\[\]【】\r\n\t]")
_METHOD_WORDS = {v: k for k, v in METHOD_CN.items()}


class BookError(Exception):
    def __init__(self, text: str, code: str = "book_error"):
        super().__init__(text)
        self.text = text
        self.code = code


def _clean(s, n: int) -> str:
    return _STRIP_RE.sub("", str(s or "")).strip()[:n]


def _new_page_id() -> str:
    return PAGE_PREFIX + uuid.uuid4().hex[:8]


def _too_long() -> BookError:
    return BookError(tp("rec_too_long", name_max=TAG_NAME_MAX, items_max=TAG_ITEMS_MAX, note_max=TAG_NOTE_MAX),
                     "too_long")


# ── ids ─────────────────────────────────────────────────────────────────

def _page_row(conn, who: str, pid: str):
    return conn.execute("SELECT * FROM recipe_pages WHERE id=? AND who=? AND deleted_at IS NULL",
                        (pid, who)).fetchone()


def page_version(conn, pid: str, version: int | None = None):
    if version is None:
        r = conn.execute("SELECT cur_version FROM recipe_pages WHERE id=?", (pid,)).fetchone()
        if r is None:
            return None
        version = r["cur_version"]
    return conn.execute("SELECT * FROM recipe_page_versions WHERE page_id=? AND version=?",
                        (pid, version)).fetchone()


def _content(v) -> dict:
    return {"name": v["name"], "main": json.loads(v["items_json"] or "[]"),
            "optional": json.loads(v["optional_json"] or "[]"), "method": v["method"] or "stirfry",
            "minutes": v["minutes"] or 15, "note": v["note"] or ""}


def _public(r: dict, page_id: str | None) -> dict:
    return {"identity": r["id"], "version": 1, "name": r["name"], "main": r["main"],
            "optional": r.get("optional", []), "method": r["method"], "minutes": r["minutes"],
            "kind": "public", "page_id": page_id, "note": ""}


def resolve_ref(conn, who: str, ref: str, *, allow_menu: bool = False) -> dict | None:
    """An id -> {identity, version, name, main, optional, method, minutes, kind, page_id}; None when
    not found, someone else's, deleted, or belonging to something switched off."""
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.startswith(PAGE_PREFIX):
        if not play.on("recipe_book"):
            return None
        p = _page_row(conn, who, ref)
        if p is None:
            return None
        if p["kind"] == "menu":
            if not play.on("menus"):
                return None
            if not allow_menu:
                return {"kind": "menu", "name": page_version(conn, ref)["name"], "identity": ref}
        if p["kind"] == "fav":
            r = recipes.get(p["ref_id"]) if play.on("recipes_public") else None
            return _public(r, ref) if r else None
        v = page_version(conn, ref)
        return {"identity": ref, "version": v["version"], **_content(v), "kind": p["kind"], "page_id": ref,
                "menu": json.loads(v["menu_json"] or "[]") if p["kind"] == "menu" else None}
    if not play.on("recipes_public"):
        return None
    r = recipes.get(ref)
    return _public(r, None) if r else None


def find_public_by_name(q: str) -> dict | None:
    q = (q or "").strip()
    r = recipes.get(q)
    if r:
        return r
    hits = [r for r in recipes.load()["list"] if q == r["name"] or q in r.get("aliases", [])]
    return hits[0] if hits else None


# ── collecting and recording ───────────────────────────────────────────

def favorite(conn, who: str, q: str, now: float) -> str:
    if not play.on("recipes_public"):
        raise BookError(tp("fav_need_public"), "public_off")
    r = find_public_by_name(_clean(q, 60))
    if r is None:
        raise BookError(tp("fav_none"), "not_found")
    if conn.execute("SELECT id FROM recipe_pages WHERE who=? AND kind='fav' AND ref_id=? AND deleted_at IS NULL",
                    (who, r["id"])).fetchone():
        return tp("fav_dup", name=r["name"], rid=r["id"])
    pid = _new_page_id()
    conn.execute("INSERT INTO recipe_pages (id, who, kind, ref_id, ref_version, cur_version, created_at)"
                 " VALUES (?,?,?,?,?,1,?)", (pid, who, "fav", r["id"], 1, now))
    conn.execute("INSERT INTO recipe_page_versions (page_id, version, name, items_json, optional_json, method, minutes,"
                 " note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (pid, 1, r["name"], json.dumps(r["main"], ensure_ascii=False),
                  json.dumps(r.get("optional", []), ensure_ascii=False), r["method"], r["minutes"], "", now))
    return tp("fav_ok", name=r["name"], rid=r["id"])


def parse_record(line: str) -> dict:
    """[记菜 name ingredients… method minutes | a sentence], optionally with "改自 <id>"."""
    body, _, note = (line or "").partition("|")
    toks = body.split()
    if len(toks) < 4:
        raise BookError(tp("rec_bad"), "bad_format")
    name, rest = toks[0], toks[1:]
    from_ref = None
    if "改自" in rest:
        i = rest.index("改自")
        if i + 1 >= len(rest):
            raise BookError(tp("rec_bad_from"), "bad_from")
        from_ref = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    method = minutes = None
    items: list[str] = []
    for t in rest:
        if t in _METHOD_WORDS and method is None:
            method = _METHOD_WORDS[t]
        elif re.fullmatch(r"\d{1,4}(分钟)?", t) and minutes is None:
            minutes = int(re.match(r"\d+", t).group())
        else:
            items.append(t)
    if not method or not minutes or not items or not (1 <= minutes <= 1440):
        raise BookError(tp("rec_bad"), "bad_format")
    note = note.strip()
    if len(name) > TAG_NAME_MAX or len(items) > TAG_ITEMS_MAX or len(note) > TAG_NOTE_MAX:
        raise _too_long()
    return {"name": _clean(name, TAG_NAME_MAX), "items": items, "method": method, "minutes": minutes,
            "note": _clean(note, TAG_NOTE_MAX), "from": from_ref}


def _resolve_items(names: list[str]) -> tuple[list[dict], list[str]]:
    from . import fridge
    out: list[dict] = []
    unknown: list[str] = []
    for raw in names:
        for n, q in fridge.parse_list(raw):
            if fridge.is_staple(n):
                continue
            iid = fridge.resolve(n, gone=True)
            if iid is None:
                unknown.append(n)
                continue
            iid = fridge.canon(iid)
            hit = next((e for e in out if e["item"] == iid), None)
            if hit:
                hit["qty"] += q
            else:
                out.append({"item": iid, "qty": q})
    return out, unknown


def record(conn, who: str, line: str, now: float) -> str:
    f = parse_record(line)
    items, unknown = _resolve_items(f["items"])
    if unknown:
        raise BookError(tp("rec_unknown", names="、".join(unknown)), "unknown_item")
    if not items:
        raise BookError(tp("rec_no_items"), "no_items")
    kind, ref_id, ref_ver = "own", None, None
    if f["from"]:
        src = resolve_ref(conn, who, f["from"])
        if src is None or src.get("kind") == "menu":
            raise BookError(tp("rec_bad_from"), "bad_from")
        kind, ref_id, ref_ver = "adapt", src["identity"], src.get("version")
    # Same name as an own or adapted page: a new version of that page (old pots still find what they followed).
    old = conn.execute("SELECT p.id, p.cur_version FROM recipe_pages p JOIN recipe_page_versions v"
                       " ON v.page_id=p.id AND v.version=p.cur_version WHERE p.who=? AND p.kind IN ('own','adapt')"
                       " AND p.deleted_at IS NULL AND v.name=? ORDER BY p.created_at LIMIT 1",
                       (who, f["name"])).fetchone()
    if old:
        pid, ver = old["id"], old["cur_version"] + 1
        conn.execute("UPDATE recipe_pages SET cur_version=? WHERE id=?", (ver, pid))
    else:
        pid, ver = _new_page_id(), 1
        conn.execute("INSERT INTO recipe_pages (id, who, kind, ref_id, ref_version, cur_version, created_at)"
                     " VALUES (?,?,?,?,?,1,?)", (pid, who, kind, ref_id, ref_ver, now))
    conn.execute("INSERT INTO recipe_page_versions (page_id, version, name, items_json, optional_json, method,"
                 " minutes, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (pid, ver, f["name"], json.dumps(items, ensure_ascii=False), "[]", f["method"], f["minutes"],
                  f["note"], now))
    return tp("rec_ok", name=f["name"], rid=pid)


def my_pages(conn, who: str) -> list[dict]:
    show_menus = play.on("menus")
    out = []
    for p in conn.execute("SELECT * FROM recipe_pages WHERE who=? AND deleted_at IS NULL ORDER BY created_at",
                          (who,)).fetchall():
        if p["kind"] == "menu" and not show_menus:
            continue
        v = page_version(conn, p["id"])
        if v is None:
            continue
        c = _content(v)
        for e in c["main"] + c["optional"]:
            e.setdefault("name", recipes.item_name(e["item"]))
        out.append({"id": p["id"], "kind": p["kind"], "ref_id": p["ref_id"], "version": v["version"],
                    "menu": json.loads(v["menu_json"] or "null"), "created_at": p["created_at"], **c})
    return out


def delete_page(conn, who: str, pid: str, now: float) -> bool:
    return conn.execute("UPDATE recipe_pages SET deleted_at=? WHERE id=? AND who=? AND deleted_at IS NULL",
                        (now, pid, who)).rowcount == 1


# ── tasting notes ───────────────────────────────────────────────────────

def add_note(conn, who: str, line: str, key: str, now: float) -> str:
    toks = (line or "").split(None, 1)
    if len(toks) < 2 or not toks[1].strip():
        raise BookError(tp("note_bad"), "bad_format")
    ref, text = toks[0], toks[1].strip()
    if len(text) > TAG_NOTE_MAX:
        raise _too_long()
    page_id = None
    if ref.startswith(PAGE_PREFIX):
        if _page_row(conn, who, ref) is not None:
            page_id = ref
    else:     # a public id: it counts as a page in the book only if collected
        p = conn.execute("SELECT id FROM recipe_pages WHERE who=? AND kind='fav' AND ref_id=? AND deleted_at IS NULL",
                         (who, ref)).fetchone()
        page_id = p["id"] if p else None
    if page_id is None:
        raise BookError(tp("note_none"), "not_found")
    ident = resolve_ref(conn, who, page_id)
    s = conn.execute("SELECT id FROM cook_sessions WHERE who=? AND recipe_id=? AND status='served'"
                     " ORDER BY served_at DESC LIMIT 1", (who, ident["identity"] if ident else page_id)).fetchone()
    conn.execute("INSERT OR IGNORE INTO recipe_notes (key, who, page_id, session_id, text, created_at)"
                 " VALUES (?,?,?,?,?,?)", (key, who, page_id, s["id"] if s else None, _clean(text, TAG_NOTE_MAX), now))
    return tp("note_ok")


def notes_for(conn, who: str, page_id: str) -> list[dict]:
    """A page's notes; under each, the mishap of that pot (only while mishaps are on)."""
    from . import progress
    show = play.on("mishaps")
    out = []
    for r in conn.execute("SELECT * FROM recipe_notes WHERE who=? AND page_id=? ORDER BY created_at",
                          (who, page_id)).fetchall():
        d = {"text": r["text"], "at": r["created_at"], "session_id": r["session_id"], "mishap": None}
        if show and r["session_id"]:
            st = conn.execute("SELECT mishap_id, mishap_ver FROM cook_settlements WHERE session_id=?",
                              (r["session_id"],)).fetchone()
            if st:
                d["mishap"] = progress.mishap_text(st["mishap_id"], st["mishap_ver"])
        out.append(d)
    return out


# ── orders ──────────────────────────────────────────────────────────────

def her_order(conn, who: str, ref: str, now: float) -> dict:
    r = resolve_ref(conn, who, ref)
    if r is None or r.get("kind") == "menu":
        raise BookError(tp("order_no_recipe"), "not_found")
    oid = "o-" + uuid.uuid4().hex[:8]
    conn.execute("INSERT INTO recipe_orders (id, who, identity, name, state, created_at, updated_at)"
                 " VALUES (?,?,?,?,?,?,?)", (oid, who, r["identity"], r["name"], "received", now, now))
    return {"id": oid, "identity": r["identity"], "name": r["name"], "state": "received"}


def her_withdraw(conn, who: str, oid: str, now: float) -> bool:
    return conn.execute("UPDATE recipe_orders SET state='withdrawn', updated_at=? WHERE id=? AND who=?"
                        " AND state IN ('received','planned')", (now, oid, who)).rowcount == 1


def accept(conn, who: str, line: str, now: float) -> str:
    toks = (line or "").split(None, 1)
    if not toks:
        raise BookError(tp("order_none", name=""), "bad_format")
    q, note = toks[0], (toks[1].strip() if len(toks) > 1 else "")
    rows = conn.execute("SELECT * FROM recipe_orders WHERE who=? AND state='received' ORDER BY created_at",
                        (who,)).fetchall()
    hit = next((o for o in rows if q in (o["name"], o["identity"], o["id"])), None)
    if hit is None:
        raise BookError(tp("order_none", name=q), "not_found")
    note = _clean(note, TAG_NOTE_MAX)
    conn.execute("UPDATE recipe_orders SET state='planned', his_note=?, updated_at=? WHERE id=?", (note, now, hit["id"]))
    return tp("order_note_saved", name=hit["name"], note=note) if note else tp("order_accept", name=hit["name"])


def on_cook_started(conn, who: str, identity: str, session_id: str, now: float) -> None:
    o = conn.execute("SELECT id FROM recipe_orders WHERE who=? AND identity=? AND state IN ('received','planned')"
                     " ORDER BY created_at LIMIT 1", (who, identity)).fetchone()
    if o:
        conn.execute("UPDATE recipe_orders SET state='cooking', session_id=?, updated_at=? WHERE id=?",
                     (session_id, now, o["id"]))


def reconcile_orders(conn, who: str, now: float) -> None:
    """After orders were off for a while: the one "cooking" is done if its pot was served, otherwise back to received."""
    for o in conn.execute("SELECT o.id, s.status FROM recipe_orders o LEFT JOIN cook_sessions s"
                          " ON s.id=o.session_id WHERE o.who=? AND o.state='cooking'", (who,)).fetchall():
        if o["status"] == "served":
            conn.execute("UPDATE recipe_orders SET state='done', updated_at=? WHERE id=?", (now, o["id"]))
        elif o["status"] in ("cancelled", "ruined", None):
            conn.execute("UPDATE recipe_orders SET state='received', session_id=NULL, updated_at=? WHERE id=?",
                         (now, o["id"]))


def on_cook_finished(conn, session_id: str, ok: bool, now: float) -> None:
    conn.execute("UPDATE recipe_orders SET state=?, updated_at=?, session_id=CASE WHEN ? THEN session_id END"
                 " WHERE session_id=? AND state='cooking'", ("done" if ok else "received", now, 1 if ok else 0,
                                                              session_id))


def open_orders(conn, who: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM recipe_orders WHERE who=? AND state IN ('received','planned','cooking') ORDER BY created_at",
        (who,)).fetchall()]


def orders_text(conn, who: str, now: float) -> str:
    from . import fridge
    reconcile_orders(conn, who, now)
    have = recipes.fridge_snapshot(fridge._batches(conn, who, now))
    lines = []
    for o in open_orders(conn, who):
        if o["state"] == "cooking":
            continue
        r = resolve_ref(conn, who, o["identity"])
        if r is None:
            continue
        if o["state"] == "planned":
            lines.append(tp("order_line_planned", name=o["name"], rid=o["identity"]))
            continue
        f = recipes.feasibility([r["main"]], have)
        lines.append(tp("order_line", name=o["name"], rid=o["identity"]) if f["ok"] else
                     tp("order_line_short", name=o["name"], rid=o["identity"], missing=recipes.short_text(f["short"])))
    return "\n".join(lines)


# ── a whole menu ────────────────────────────────────────────────────────

def make_menu(conn, who: str, line: str, now: float) -> str:
    from . import fridge
    body, _, note = (line or "").partition("|")
    ids = body.split()
    if not (2 <= len(ids) <= MENU_MAX_DISHES):
        raise BookError(tp("menu_bad", max=MENU_MAX_DISHES), "bad_format")
    if len(note.strip()) > TAG_NOTE_MAX:
        raise _too_long()
    refs, missing = [], []
    for i in ids:
        r = resolve_ref(conn, who, i)
        if r is None or r.get("kind") == "menu":
            missing.append(i)
        else:
            refs.append(r)
    if missing:
        raise BookError(tp("menu_missing", ids="、".join(missing)), "not_found")
    pid = _new_page_id()
    name = "、".join(r["name"] for r in refs)[:TAG_NAME_MAX * 2]
    conn.execute("INSERT INTO recipe_pages (id, who, kind, cur_version, created_at) VALUES (?,?,?,1,?)",
                 (pid, who, "menu", now))
    conn.execute("INSERT INTO recipe_page_versions (page_id, version, name, items_json, optional_json, method, minutes,"
                 " note, menu_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (pid, 1, name, "[]", "[]", None, None, _clean(note, TAG_NOTE_MAX),
                  json.dumps([{"ref": r["page_id"] or r["identity"], "version": r["version"]} for r in refs],
                             ensure_ascii=False), now))
    have = recipes.fridge_snapshot(fridge._batches(conn, who, now))
    f = recipes.feasibility([r["main"] for r in refs], have)
    return (tp("menu_ok", n=len(refs)) if f["ok"]
            else tp("menu_ok_short", n=len(refs), missing=recipes.short_text(f["short"])))


def menu_view(conn, who: str, pid: str) -> list[dict]:
    """A page a menu points at may be gone: the menu stays, that dish says so."""
    v = page_version(conn, pid)
    out = []
    for e in json.loads((v["menu_json"] if v else None) or "[]"):
        r = resolve_ref(conn, who, e["ref"])
        out.append({"ref": e["ref"], "gone": r is None, "name": r["name"] if r else tp("menu_gone")})
    return out


# ── recipe codes ────────────────────────────────────────────────────────

def _checksum(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()[:6]


def export_code(conn, who: str, ref: str) -> str:
    """The page, its public sentence and its source only: never the human's comments, never the cooking history."""
    pid = (ref or "").strip()
    if not pid.startswith(PAGE_PREFIX):     # a public id: only if this role collected it
        if conn.execute("SELECT id FROM recipe_pages WHERE who=? AND kind='fav' AND ref_id=? AND deleted_at IS NULL",
                        (who, pid)).fetchone() is None:
            raise BookError(tp("code_none"), "not_found")
    r = resolve_ref(conn, who, pid)
    if r is None or r.get("kind") == "menu":
        raise BookError(tp("code_none"), "not_found")
    src = {"public": "HowToCook", "adapt": "改编", "own": "自创"}.get(r["kind"], "")
    by = who
    if r["kind"] == "code" and r.get("page_id"):
        pr = conn.execute("SELECT src_label, src_by FROM recipe_pages WHERE id=?", (r["page_id"],)).fetchone()
        if pr is not None:      # someone else's code goes out with its own source and author
            src, by = pr["src_label"] or "", pr["src_by"] or ""
    payload = {"v": 1, "name": r["name"],
               "items": [[recipes.item_name(e["item"]), int(e.get("qty") or 1)] for e in r["main"]],
               "optional": [recipes.item_name(e["item"]) for e in r.get("optional", [])],
               "method": r["method"], "minutes": r["minutes"], "note": r.get("note", ""), "source": src, "by": by}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode().rstrip("=")
    code = f"{CODE_PREFIX}{body}.{_checksum(raw)}"
    if len(code) > CODE_MAX_CHARS:
        raise BookError(tp("tag_too_long"), "too_long")
    return code


def export_receipt(conn, who: str, ref: str, limit: int = 240) -> str:
    code = export_code(conn, who, ref)
    text = tp("code_ok", code=code)
    if len(text) <= limit:
        return text
    r = resolve_ref(conn, who, ref)
    return tp("code_ok_page", name=r["name"] if r else ref)


def decode_code(code: str) -> dict:
    """A code -> a preview. Text only: nothing is run, nothing is fetched, nothing is granted."""
    code = (code or "").strip()
    bad = BookError(tp("code_bad"), "bad_code")
    if len(code) > CODE_MAX_CHARS or not code.startswith(CODE_PREFIX):
        raise bad
    try:
        body, chk = code[len(CODE_PREFIX):].rsplit(".", 1)
        comp = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        d = zlib.decompressobj()
        raw = d.decompress(comp, 8192)
        if d.unconsumed_tail:
            raise ValueError("too big")
        if _checksum(raw) != chk:
            raise ValueError("checksum")
        p = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise bad from e
    if not isinstance(p, dict) or set(p) - _CODE_FIELDS or p.get("v") != 1 or p.get("method") not in METHOD_CN:
        raise bad
    try:
        minutes = int(p.get("minutes"))
        items = [(_clean(n, TAG_NAME_MAX), max(1, min(9, int(q)))) for n, q in (p.get("items") or [])]
        optional = [_clean(n, TAG_NAME_MAX) for n in (p.get("optional") or [])]
    except Exception as e:  # noqa: BLE001
        raise bad from e
    if not (1 <= minutes <= 1440) or not items or len(items) > TAG_ITEMS_MAX:
        raise bad
    return {"name": _clean(p.get("name"), TAG_NAME_MAX), "items": items, "optional": optional[:TAG_ITEMS_MAX],
            "method": p["method"], "minutes": minutes, "note": _clean(p.get("note"), TAG_NOTE_MAX),
            "source": _clean(p.get("source"), 12), "by": _clean(p.get("by"), 20)}


def _entries(names: list[tuple[str, int]]) -> list[dict]:
    from . import fridge
    from .texts_play import vendor_id
    return [{"item": fridge.resolve(n, gone=True) or recipes._alias_index().get(n) or vendor_id(n), "qty": q, "name": n}
            for n, q in names]


def import_code(conn, who: str, code: str, now: float) -> dict:
    c = decode_code(code)
    canon = json.dumps({k: c[k] for k in ("name", "items", "optional", "method", "minutes", "note")},
                       ensure_ascii=False, sort_keys=True)
    cid = hashlib.sha1(canon.encode("utf-8")).hexdigest()[:12]
    old = conn.execute("SELECT id FROM recipe_pages WHERE who=? AND content_id=? AND deleted_at IS NULL",
                       (who, cid)).fetchone()
    if old:
        return {"page_id": old["id"], "duplicate": True, **c}
    pid = _new_page_id()
    conn.execute("INSERT INTO recipe_pages (id, who, kind, content_id, cur_version, created_at, src_label, src_by)"
                 " VALUES (?,?,?,?,1,?,?,?)", (pid, who, "code", cid, now, c["source"], c["by"]))
    conn.execute("INSERT INTO recipe_page_versions (page_id, version, name, items_json, optional_json, method, minutes,"
                 " note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (pid, 1, c["name"], json.dumps(_entries(c["items"]), ensure_ascii=False),
                  json.dumps(_entries([(n, 1) for n in c["optional"]]), ensure_ascii=False),
                  c["method"], c["minutes"], c["note"], now))
    return {"page_id": pid, "duplicate": False, **c}


# ── buying what a recipe lacks ──────────────────────────────────────────

def buy_for_recipe(who: str, ref: str, *, key: str, now: float) -> str:
    """[买菜 照 <id>]: what the fridge lacks right now for this recipe, rounded up to whole packs,
    for one coupon and without the usual limit on kinds. Checking, the coupon, the fridge and the
    log share one transaction. Raises fridge.FridgeError."""
    from . import db, fridge
    from .texts import t
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = conn.execute("SELECT receipt FROM recipe_buys WHERE key=?", (key,)).fetchone()
        if done is not None:
            conn.rollback()
            return done["receipt"]
        r = resolve_ref(conn, who, ref)
        if r is None or r.get("kind") == "menu":
            conn.rollback()
            raise fridge.FridgeError(tp("buy_no_recipe"), "no_recipe")

        def _record(receipt: str, ids: list[str]) -> str:
            conn.execute("INSERT INTO recipe_buys (key, who, identity, items_json, receipt, at) VALUES (?,?,?,?,?,?)",
                         (key, who, r["identity"], json.dumps(ids, ensure_ascii=False), receipt, now))
            conn.commit()
            return receipt
        short = recipes.feasibility([r["main"]], recipes.fridge_snapshot(fridge._batches(conn, who, now)))["short"]
        if not short:
            return _record(tp("buy_nothing", name=r["name"]), [])
        sold = {k: n for k, n in short.items() if recipes.item_sold(k)}
        not_sold = [recipes.item_name(k) for k in short if k not in sold]
        if not sold:
            return _record(tp("buy_not_sold", name=r["name"], not_sold="、".join(not_sold)), [])
        n_c = fridge.coupon_count(conn, who)
        if n_c <= 0:
            conn.rollback()
            hint = fridge.earn_hint()
            raise fridge.FridgeError(t("buy_no_coupon") + (t("buy_no_coupon_hint", hint=hint) if hint else "")
                                     + fridge.coupons_from_human(), "no_coupon")
        ids: list[str] = []
        for k, n in sold.items():
            pack = int((fridge.item(k) or {}).get("pack_qty") or 1)
            ids += [k] * max(1, math.ceil(n / pack))
        conn.execute("UPDATE coupons SET count=count-1 WHERE who=?", (who,))
        added = fridge._add_batches(conn, who, ids, fridge.BY_SELF, "coupon_recipe", now)
        merged: dict[str, int] = {}
        for a in added:
            merged[a["name"]] = merged.get(a["name"], 0) + a["qty"]
        items = "、".join(f"{n}×{q}" for n, q in merged.items())
        receipt = (tp("buy_ok_partial", name=r["name"], items=items, left=n_c - 1, not_sold="、".join(not_sold))
                   if not_sold else tp("buy_ok", name=r["name"], items=items, left=n_c - 1))
        fridge._log(conn, who, "bought", tp("buy_log", name=r["name"], items=items), now)
        return _record(receipt, ids)
    finally:
        conn.close()


def missing_for_human(conn, who: str, ref: str, now: float) -> dict:
    """What the page needs to buy a recipe's missing ingredients for the role (through the usual buying)."""
    from . import fridge
    r = resolve_ref(conn, who, ref)
    if r is None or r.get("kind") == "menu":
        raise BookError(tp("order_no_recipe"), "not_found")
    short = recipes.feasibility([r["main"]], recipes.fridge_snapshot(fridge._batches(conn, who, now)))["short"]
    out = []
    for k, n in short.items():
        pack = int((fridge.item(k) or {}).get("pack_qty") or 1)
        out.append({"item_id": k, "name": recipes.item_name(k), "short": n, "sold": recipes.item_sold(k),
                    "packs": max(1, math.ceil(n / pack))})
    return {"identity": r["identity"], "name": r["name"], "missing": out}
