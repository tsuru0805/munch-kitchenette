"""REST for the upgrade (mounted by :func:`kitchenette.api.create_app`). See docs/API.md.

Everything a switched-off feature offers answers 409 with "this is off" (one exception: reading back one
washing for a washing card already in the chat); ``GET /api/features`` says what is on so a page can hide
what is not. Nothing here deletes data.
"""
from __future__ import annotations

import uuid

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

from . import clock, config, db, play, roles, service
from .texts_play import tp


# One row per buying of what a recipe lacks, keyed by the page's op_id: a retry of the same buying answers
# the receipt kept here and buys nothing more. Written in the same transaction as the buying itself.
_BUY_OPS = ("CREATE TABLE IF NOT EXISTS recipe_buy_ops (op_id TEXT PRIMARY KEY, who TEXT NOT NULL,"
            " recipe TEXT NOT NULL, receipt TEXT NOT NULL, at REAL NOT NULL)")


def _norm(d: str) -> str:
    return "".join((d or "").split())


def _merge_rows(conn, who: str) -> dict[str, str]:
    return {r["dish"]: r["page_key"] for r in conn.execute("SELECT dish, page_key FROM dex_merges WHERE who=?", (who,))}


def _has_chain(rows: dict[str, str]) -> bool:
    return any(k.startswith("d:") and k[2:] in rows and k[2:] != d and rows[k[2:]] != k for d, k in rows.items())


def flatten_merges(conn, who: str, rows: dict[str, str] | None = None) -> int:
    """Unsorted dishes merged onto another unsorted dish's page (possible before merging was limited to
    sorted pages): point each straight at the page at the end of the chain, so its pots land where the
    page shows them and taking it back out works. A loop is cut by sending the dish where it was found home.

    Call it inside a write transaction (BEGIN IMMEDIATE) the caller commits. Each row is changed only if it
    still holds the value it was worked out from, so a merge another request committed in between is never
    written back over. Returns how many rows changed."""
    rows = dict(_merge_rows(conn, who) if rows is None else rows)
    changed = 0
    for dish, key in list(rows.items()):
        seen = {dish}
        cur = key
        while cur.startswith("d:") and cur[2:] in rows and rows[cur[2:]] != cur:
            nxt = cur[2:]
            if nxt in seen:            # a loop: nobody can tell which page was meant
                cur = f"d:{dish}"
                break
            seen.add(nxt)
            cur = rows[nxt]
        if cur != key:
            n = conn.execute("UPDATE dex_merges SET page_key=? WHERE who=? AND dish=? AND page_key=?",
                             (cur, who, dish, key)).rowcount
            if n:
                rows[dish] = cur
                changed += 1
    return changed


def straighten_merges(conn, who: str) -> int:
    """For reading the book: nothing is written unless there is a chain; then the table is read again under
    the write lock and straightened (a request that merged in between is seen, not overwritten)."""
    if not _has_chain(_merge_rows(conn, who)):
        return 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        n = flatten_merges(conn, who)
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise


def _recipe_target_problem(conn, who: str, rid: str) -> tuple[int, str] | None:
    """Can pots be merged onto the page of recipe ``rid``? It must be a recipe of the public index or a page of
    this role's own book that is not deleted and not a menu. Another role's page answers as if it did not
    exist. A page is one thing whatever its versions (pots carry the version, the page key does not), so
    there is no "old version" to merge onto. None = fine, else (status, sentence)."""
    from . import recipes
    try:
        if rid in recipes.load()["by_id"]:
            return None
    except Exception:  # noqa: BLE001
        pass             # the index is unreadable: only the role's own pages can be checked
    row = conn.execute("SELECT kind, deleted_at FROM recipe_pages WHERE id=? AND who=?", (rid, who)).fetchone()
    if row is None:
        return 404, "没有这道食谱,并不过去。"
    if row["deleted_at"] is not None:
        return 409, "这一页已经删了,并不过去。"
    if row["kind"] == "menu":
        return 409, "一桌菜单不是一道菜,并不过去。"
    return None


def prefs_version(items) -> str:
    """The version of a dislike list: its content (so no counter needs keeping), for PUT /api/prefs."""
    import hashlib
    return hashlib.sha1("\n".join(sorted(items)).encode()).hexdigest()[:12]


def register(app: FastAPI, guarded: list, role) -> None:

    def need(key: str) -> None:
        if not play.on(key):
            raise HTTPException(409, tp("feature_off"))

    def who_of(body: dict) -> str:
        return role(body.get("who"), body.get("viewer"))

    @app.get("/api/features", dependencies=guarded)
    def features():
        return play.capabilities()

    @app.get("/api/play/teaching", dependencies=guarded)
    def teaching():
        """The sentences that teach the role the markers of what is on (also appended to kitchen_cook)."""
        from . import playkit
        return {"text": playkit.teaching_text()}

    # ── recipes ─────────────────────────────────────────────────────────
    @app.get("/api/recipes", dependencies=guarded)
    def recipes_list(q: str = "", limit: int = 50, who: str | None = None, viewer: str | None = None):
        need("recipes_public")
        from . import recipes
        w = role(who, viewer)
        lim = min(max(1, limit), 400)
        conn = db.connect()
        try:
            hits = recipes.search(q, conn=conn, who=w, limit=lim) if q else recipes.load()["list"][:lim]
            stopped = recipes.stopped_ids(conn)
        finally:
            conn.close()
        data = recipes.load()
        return {"total": len(data["list"]), "source": data["source"], "categories": recipes.categories(),
                "recipes": [{**r, "items_text": recipes.items_text(r["main"]), "stopped": r["id"] in stopped}
                            for r in hits]}

    @app.get("/api/recipes/today", dependencies=guarded)
    def recipes_today(who: str | None = None, viewer: str | None = None):
        need("recipes_today")
        from . import recipes
        w = role(who, viewer)
        service.serve_due(w)
        try:
            return {"text": recipes.today_text(w, clock.now())}
        except Exception:  # noqa: BLE001
            return {"text": tp("rec_down"), "degraded": True}

    @app.get("/api/recipes/missing", dependencies=guarded)
    def recipes_missing(recipe: str, who: str | None = None, viewer: str | None = None):
        need("recipe_cook")
        from . import book
        conn = db.connect()
        try:
            return book.missing_for_human(conn, role(who, viewer), recipe, clock.now())
        except book.BookError as e:
            raise HTTPException(404, e.text) from None
        finally:
            conn.close()

    @app.post("/api/recipes/buy_missing", dependencies=guarded)
    def recipes_buy_missing(background: BackgroundTasks, body: dict = Body(...)):
        """The human buys what a recipe (or a page of the role's book) lacks, in whole packs, only what the
        shop sells (her usual buying: no coupon). ``op_id``: one per buying, the same for a retry of it.

        One write transaction: the receipt of this op_id (there = answer it again, buy nothing) -> what is
        missing now -> into the fridge -> the receipt. A second buying with a new op_id after the first works
        the shortage out again and finds nothing to buy. Answers what was put in the fridge and what is
        still missing."""
        need("recipe_cook")
        import json
        from . import book, fridge, notify
        w = who_of(body)
        ref = str(body.get("recipe") or "")
        op = str(body.get("op_id") or "").strip()[:80]
        if not op:
            raise HTTPException(400, "op_id required (one per buying; the same for a retry of it)")
        conn = db.connect()
        try:
            conn.execute(_BUY_OPS)
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT who, recipe, receipt FROM recipe_buy_ops WHERE op_id=?", (op,)).fetchone()
            if old is not None:
                conn.rollback()
                if old["who"] != w or old["recipe"] != ref:
                    raise HTTPException(409, "this op_id was used for another buying")
                # its note was written with the buying; if pushing it failed then, this is another try
                background.add_task(notify.flush_quietly)
                return {**json.loads(old["receipt"]), "replayed": True}
            now = clock.now()
            try:
                short = book.missing_for_human(conn, w, ref, now)["missing"]
                ids = [m["item_id"] for m in short if m["sold"] for _ in range(m["packs"])]
                res = fridge.buy_her_in_tx(conn, w, ids, now) if ids else {"added": [], "text": ""}
                after = book.missing_for_human(conn, w, ref, now)["missing"] if ids else short
            except book.BookError as e:
                conn.rollback()
                raise HTTPException(404, e.text) from None
            except fridge.FridgeError as e:
                conn.rollback()
                raise HTTPException(400, e.text) from None
            receipt = {"ok": True, "added": res["added"], "text": res["text"], "missing": after}
            if receipt["added"]:
                # the role's note goes into the same transaction (the notes table is the outbox): bought and
                # told both happen or neither; pushing it is flush's, after the commit, and retried if it fails
                items = "、".join(f"{a['name']}×{a['qty']}" for a in receipt["added"])[:200]
                notify.emit_in_tx(conn, w, notify.KIND_BOUGHT, payload={"items": items}, key=f"buy-missing:{op}", now=now)
            conn.execute("INSERT INTO recipe_buy_ops (op_id, who, recipe, receipt, at) VALUES (?,?,?,?,?)",
                         (op, w, ref, json.dumps(receipt, ensure_ascii=False), now))
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        if receipt["added"]:
            background.add_task(notify.flush_quietly)
        return {**receipt, "replayed": False}

    @app.put("/api/recipes/{rid}/stop", dependencies=guarded)
    def recipe_stop(rid: str, body: dict = Body(default={})):
        """A recipe with a mistake: out of recommendations and search (pots and pages stay). stopped=false undoes it."""
        need("recipes_public")
        stopped = bool(body.get("stopped", True))
        conn = db.connect()
        try:
            conn.execute("INSERT INTO recipe_flags (recipe_id, stopped, why, at) VALUES (?,?,?,?)"
                         " ON CONFLICT(recipe_id) DO UPDATE SET stopped=excluded.stopped, why=excluded.why, at=excluded.at",
                         (rid, 1 if stopped else 0, str(body.get("why") or "")[:100], clock.now()))
            conn.commit()
        finally:
            conn.close()
        return {"recipe_id": rid, "stopped": stopped}

    @app.get("/api/recipes/stopped", dependencies=guarded)
    def recipes_stopped():
        """The recipes taken out of picks and search (so the page can list them and undo it), newest first."""
        need("recipes_public")
        from . import recipes
        conn = db.connect()
        try:
            rows = conn.execute("SELECT recipe_id, why, at FROM recipe_flags WHERE stopped=1 ORDER BY at DESC").fetchall()
        finally:
            conn.close()
        by_id = recipes.load()["by_id"]
        return {"recipes": [{"id": r["recipe_id"], "name": (by_id.get(r["recipe_id"]) or {}).get("name") or r["recipe_id"],
                             "why": r["why"] or "", "at": r["at"]} for r in rows]}

    @app.put("/api/prefs", dependencies=guarded)
    def prefs(body: dict = Body(...)):
        """Ingredients the human does not want recommended (the whole list, replaced). Outdated: use the
        one-at-a-time POST / DELETE /api/prefs/dislike. With ``version`` (from any answer about the list) the
        list is replaced only if it is still that version, else 409 with nothing changed; without it the
        list is replaced whatever it is now (kept for older pages)."""
        need("recipes_public")
        from . import fridge, recipes
        w = who_of(body)
        items = [str(x) for x in (body.get("dislike") or [])][:60]
        bad = [i for i in items if fridge.item(i) is None]
        if bad:
            raise HTTPException(400, f"unknown items: {bad}")
        want = body.get("version")
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if want is not None and str(want) != prefs_version(recipes.dislikes(conn, w)):
                conn.rollback()
                raise HTTPException(409, "the list changed since it was read; read it again")
            conn.execute("DELETE FROM kitchen_prefs WHERE who=? AND kind='dislike'", (w,))
            conn.executemany("INSERT OR IGNORE INTO kitchen_prefs (who, kind, item, at) VALUES (?,?,?,?)",
                             [(w, "dislike", i, clock.now()) for i in items])
            conn.commit()
            now_list = recipes.dislikes(conn, w)
        finally:
            conn.close()
        return {"dislike": items, "version": prefs_version(now_list)}

    @app.post("/api/prefs/dislike", dependencies=guarded)
    def prefs_add(body: dict = Body(...)):
        """Add one ingredient not to recommend (already there = nothing changes). Answers the whole list."""
        need("recipes_public")
        from . import fridge, recipes
        w = who_of(body)
        item = str(body.get("item") or "")
        if fridge.item(item) is None:
            raise HTTPException(400, f"unknown item: {item!r}")
        conn = db.connect()
        try:
            conn.execute("INSERT OR IGNORE INTO kitchen_prefs (who, kind, item, at) VALUES (?,?,?,?)",
                         (w, "dislike", item, clock.now()))
            conn.commit()
            d = recipes.dislikes(conn, w)
            return {"dislike": sorted(d), "version": prefs_version(d)}
        finally:
            conn.close()

    @app.delete("/api/prefs/dislike/{item}", dependencies=guarded)
    def prefs_remove(item: str, who: str | None = None, viewer: str | None = None):
        """Take one ingredient off the list (not there = nothing changes). Answers the whole list."""
        need("recipes_public")
        from . import recipes
        w = role(who, viewer)
        conn = db.connect()
        try:
            conn.execute("DELETE FROM kitchen_prefs WHERE who=? AND kind='dislike' AND item=?", (w, item))
            conn.commit()
            d = recipes.dislikes(conn, w)
            return {"dislike": sorted(d), "version": prefs_version(d)}
        finally:
            conn.close()

    @app.get("/api/prefs", dependencies=guarded)
    def prefs_get(who: str | None = None, viewer: str | None = None):
        need("recipes_public")
        from . import recipes
        conn = db.connect()
        try:
            d = recipes.dislikes(conn, role(who, viewer))
            return {"dislike": sorted(d), "version": prefs_version(d)}
        finally:
            conn.close()

    # ── the role's book ─────────────────────────────────────────────────
    @app.get("/api/book", dependencies=guarded)
    def book_get(who: str | None = None, viewer: str | None = None):
        need("recipe_book")
        from . import book
        w = role(who, viewer)
        conn = db.connect()
        try:
            pages = book.my_pages(conn, w)
            for p in pages:
                if play.on("tasting_notes"):
                    p["notes"] = book.notes_for(conn, w, p["id"])
                if p["kind"] == "menu":
                    p["menu_view"] = book.menu_view(conn, w, p["id"])
            return {"pages": pages}
        finally:
            conn.close()

    @app.delete("/api/book/{page_id}", dependencies=guarded)
    def book_delete(page_id: str, who: str | None = None, viewer: str | None = None):
        need("recipe_book")
        from . import book
        conn = db.connect()
        try:
            ok = book.delete_page(conn, role(who, viewer), page_id, clock.now())
            conn.commit()
        finally:
            conn.close()
        if not ok:
            raise HTTPException(404, tp("code_none"))
        return {"ok": True}

    # ── orders ──────────────────────────────────────────────────────────
    @app.get("/api/orders", dependencies=guarded)
    def orders_get(who: str | None = None, viewer: str | None = None):
        need("orders")
        from . import book
        w = role(who, viewer)
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            text = book.orders_text(conn, w, clock.now())
            conn.commit()
            rows = [dict(r) for r in conn.execute("SELECT * FROM recipe_orders WHERE who=? ORDER BY created_at DESC"
                                                  " LIMIT 50", (w,)).fetchall()]
        finally:
            conn.close()
        return {"orders": rows, "text": text}

    @app.post("/api/orders", dependencies=guarded)
    def orders_post(body: dict = Body(...)):
        need("orders")
        from . import book
        w = who_of(body)
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            o = book.her_order(conn, w, str(body.get("recipe") or ""), clock.now())
            conn.commit()
            return o
        except book.BookError as e:
            conn.rollback()
            raise HTTPException(404, e.text) from None
        finally:
            conn.close()

    @app.delete("/api/orders/{oid}", dependencies=guarded)
    def orders_withdraw(oid: str, who: str | None = None, viewer: str | None = None):
        need("orders")
        from . import book
        conn = db.connect()
        try:
            ok = book.her_withdraw(conn, role(who, viewer), oid, clock.now())
            conn.commit()
        finally:
            conn.close()
        return {"ok": ok}

    # ── recipe codes ────────────────────────────────────────────────────
    @app.get("/api/codes", dependencies=guarded)
    def code_get(page: str, who: str | None = None, viewer: str | None = None):
        need("recipe_codes")
        from . import book
        conn = db.connect()
        try:
            return {"code": book.export_code(conn, role(who, viewer), page)}
        except book.BookError as e:
            raise HTTPException(409, e.text) from None
        finally:
            conn.close()

    @app.post("/api/codes/preview", dependencies=guarded)
    def code_preview(body: dict = Body(...)):
        need("recipe_codes")
        from . import book
        try:
            return {"preview": book.decode_code(str(body.get("code") or ""))}
        except book.BookError as e:
            raise HTTPException(400, e.text) from None

    @app.post("/api/codes/import", dependencies=guarded)
    def code_import(body: dict = Body(...)):
        need("recipe_codes")
        from . import book
        w = who_of(body)
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            out = book.import_code(conn, w, str(body.get("code") or ""), clock.now())
            conn.commit()
            return out
        except book.BookError as e:
            conn.rollback()
            raise HTTPException(400, e.text) from None
        finally:
            conn.close()

    # ── the dish book and achievements ──────────────────────────────────
    @app.get("/api/dex", dependencies=guarded)
    def dex_get(who: str | None = None, viewer: str | None = None):
        need("dex")
        from . import dex
        w = role(who, viewer)
        service.serve_due(w)
        conn = db.connect()
        try:
            straighten_merges(conn, w)
            out = dex.build(conn, w)
            # for the page: the small dish picture a page without its own picture shows (the same
            # fourteen kinds the settled card uses), and which unsorted dishes were merged where (to undo it)
            from .progress import dish_icon
            for pg in out["pages"]:
                pg["icon"] = dish_icon(pg["name"])
            for sil in out["silhouettes"]:
                sil["icon"] = dish_icon(sil["name"])
            out["merges"] = [{"dish": r["dish"], "page_key": r["page_key"]} for r in conn.execute(
                "SELECT dish, page_key FROM dex_merges WHERE who=? ORDER BY at", (w,)).fetchall()
                if r["page_key"] != f"d:{r['dish']}"]
            if play.on("achievements"):
                conn.execute("BEGIN IMMEDIATE")
                dex.evaluate_in_tx(conn, w)
                conn.commit()
                out["achievements"] = dex.all_for_human(conn, w)
            out["drawing"] = dex.drawer() is not None
            return out
        finally:
            conn.close()

    @app.put("/api/dex/note", dependencies=guarded)
    def dex_note(body: dict = Body(...)):
        need("dex")
        w = who_of(body)
        conn = db.connect()
        try:
            conn.execute("INSERT INTO dex_notes (who, page_key, text, at) VALUES (?,?,?,?)"
                         " ON CONFLICT(who, page_key) DO UPDATE SET text=excluded.text, at=excluded.at",
                         (w, str(body.get("page_key") or ""), str(body.get("text") or "")[:300], clock.now()))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    @app.put("/api/dex/merge", dependencies=guarded)
    def dex_merge(body: dict = Body(...)):
        """Merge a dish's pots into a sorted page: a recipe's (``r:…``) or a page whose name is a recipe or one
        of the role's own (``d:…`` that is not unsorted). ``d:<dish>``, its own page, takes it back out.
        Never onto an unsorted page (that made chains nobody could take apart)."""
        need("dex")
        from . import dex
        w = who_of(body)
        dish = _norm(str(body.get("dish") or ""))
        target = str(body.get("page_key") or "")
        if not dish or not target:
            raise HTTPException(400, "dish and page_key are required")
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            flatten_merges(conn, w)
            if target != f"d:{dish}":
                if target.startswith("d:"):
                    pg = next((p for p in dex.build(conn, w)["pages"] if p["key"] == target), None)
                    if pg is None or pg["pending"]:
                        conn.rollback()
                        raise HTTPException(409, "只能并到已经归类的页(食谱的页或他自己的页),不能并到待归类的页。")
                elif target.startswith("r:") and len(target) > 2:
                    bad = _recipe_target_problem(conn, w, target[2:])
                    if bad:
                        conn.rollback()
                        raise HTTPException(*bad)
                else:
                    conn.rollback()
                    raise HTTPException(400, "page_key must be r:<recipe>, a sorted d:<dish> page, or d:<dish> to undo")
            conn.execute("INSERT INTO dex_merges (who, dish, page_key, at) VALUES (?,?,?,?)"
                         " ON CONFLICT(who, dish) DO UPDATE SET page_key=excluded.page_key, at=excluded.at",
                         (w, dish, target, clock.now()))
            flatten_merges(conn, w)    # dishes that were on this dish's page follow it
            conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/api/dex/art/redraw", dependencies=guarded)
    def dex_redraw(body: dict = Body(...)):
        need("dex")
        from . import dex
        if dex.drawer() is None:
            raise HTTPException(409, "no dish picture drawer is configured ([art] dish_provider)")
        conn = db.connect()
        try:
            v = dex.request_redraw(conn, str(body.get("page_key") or ""))
            conn.commit()
        finally:
            conn.close()
        return {"version": v}

    @app.put("/api/dex/art/choice", dependencies=guarded)
    def dex_choice(body: dict = Body(...)):
        need("dex")
        from . import dex
        version = body.get("version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise HTTPException(400, "version must be a whole number")
        conn = db.connect()
        try:
            ok = dex.art_choose(conn, str(body.get("page_key") or ""), version)
            conn.commit()
        finally:
            conn.close()
        if not ok:
            raise HTTPException(404, "no such picture")
        return {"ok": True}

    @app.get("/api/dex/art", dependencies=guarded)
    def dex_art(page_key: str, version: int):
        need("dex")
        from . import dex
        conn = db.connect()
        try:
            r = conn.execute("SELECT state FROM dex_art WHERE page_key=? AND version=?", (page_key, version)).fetchone()
        finally:
            conn.close()
        p = dex.art_file(page_key, version)
        if r is None or r["state"] != "ready" or not p.is_file():
            raise HTTPException(404, "no such picture")
        return FileResponse(str(p), media_type="image/png", headers={"Cache-Control": "private, max-age=31536000"})

    # ── plates ──────────────────────────────────────────────────────────
    @app.get("/api/dishes", dependencies=guarded)
    def dishes_get(who: str | None = None, viewer: str | None = None):
        need("dishwash")
        from . import dishes
        w = role(who, viewer)
        conn = db.connect()
        try:
            now = clock.now()
            conn.execute("BEGIN IMMEDIATE")
            dishes.settle_in_tx(conn, w, now)
            conn.commit()
            return dishes.view(conn, w, now)
        finally:
            conn.close()

    @app.get("/api/dishes/jobs/{job_id}", dependencies=guarded)
    def dishes_job(job_id: str):
        """One washing, for the washing card in the chat: how far it is and which plates broke (a plate's
        result only once its time is up). Answered with the feature switched off too: a card already in the
        chat then learns the washing was stopped."""
        from . import dishes
        conn = db.connect()
        try:
            now = clock.now()
            conn.execute("BEGIN IMMEDIATE")
            r = conn.execute("SELECT who FROM wash_jobs WHERE id=?", (job_id,)).fetchone()
            # the role boundary holds here too: a washing of a role this server does not serve is not there
            # (the feature switch is the only thing this endpoint does not ask for)
            if r is None or not roles.valid(r["who"]):
                conn.rollback()
                raise HTTPException(404, "no such washing")
            dishes.settle_in_tx(conn, r["who"], now)
            conn.commit()
            return {**dishes.job_detail(conn, job_id, now), "timezone": config.get().server_timezone}
        finally:
            conn.close()

    @app.put("/api/dishes/settings", dependencies=guarded)
    def dishes_settings(body: dict = Body(...)):
        """self_wash: let the role wash (true/false); quota: how many (a number; null = all in the sink)."""
        need("dishwash")
        from . import dishes
        q = body.get("quota", "keep")
        if q not in ("keep", None) and (isinstance(q, bool) or not isinstance(q, int) or q < 0):
            raise HTTPException(400, "quota must be a whole number, 0 or more, or null")
        sw = body.get("self_wash")
        if sw is not None and not isinstance(sw, bool):
            raise HTTPException(400, "self_wash must be true or false")
        return dishes.set_settings(who_of(body), self_wash=sw, quota=None if q in ("keep", None) else q,
                                   clear_quota=q is None)

    # ── jars ────────────────────────────────────────────────────────────
    @app.get("/api/jars", dependencies=guarded)
    def jars_get(who: str | None = None, viewer: str | None = None):
        need("seal_jars")
        from . import jars
        w = role(who, viewer)
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            jars.settle_in_tx(conn, w, clock.now())
            conn.commit()
            return {"jars": jars.jars_view(conn, w), "goods": jars.goods_view(conn, w), "cap": jars.cap_for(conn, w)}
        finally:
            conn.close()

    @app.put("/api/jars/cap", dependencies=guarded)
    def jars_cap(body: dict = Body(...)):
        need("seal_jars")
        from . import jars
        cap = body.get("cap")
        if isinstance(cap, bool) or not isinstance(cap, int):
            raise HTTPException(400, "cap must be a whole number")
        return {"cap": jars.set_cap(who_of(body), cap)}

    @app.post("/api/jars/feed", dependencies=guarded)
    def jars_feed(body: dict = Body(...)):
        need("seal_jars")
        from . import jars
        key = str(body.get("key") or "").strip()[:80]
        if not key:
            raise HTTPException(400, "key required (the same key for a retry of the same feeding)")
        r = jars.take(who_of(body), str(body.get("name") or ""), key=f"human:{key}", by=jars.BY_HUMAN)
        if not r["ok"]:
            raise HTTPException(409, r["text"])
        from . import notify
        notify.emit(who_of(body), "jar.fed", r["text"], body=r["text"], key=f"jar.fed:{key}")
        return r

    # ── vendors ─────────────────────────────────────────────────────────
    @app.get("/api/vendor", dependencies=guarded)
    def vendor_get(who: str | None = None, viewer: str | None = None):
        need("vendor")
        from . import vendor
        return vendor.overview(role(who, viewer))

    @app.get("/api/vendor/ledger", dependencies=guarded)
    def vendor_ledger(who: str | None = None, viewer: str | None = None):
        need("vendor")
        from . import vendor
        return {"orders": vendor.ledger(role(who, viewer))}

    @app.post("/api/vendor/treat", dependencies=guarded)
    def vendor_treat(body: dict = Body(...)):
        need("vendor")
        from . import vendor
        rid = str(body.get("request_id") or "").strip()
        if not rid:
            raise HTTPException(400, "request_id required")
        qty = body.get("qty", 1)
        if isinstance(qty, bool) or not isinstance(qty, int):
            raise HTTPException(400, "qty must be a whole number")
        try:
            o = vendor.treat(who_of(body), str(body.get("item_id") or ""), qty, request_id=rid[:80])
        except vendor.VendorError as e:
            raise HTTPException(409, e.text) from None
        return {"ok": o["state"] == vendor.DELIVERED, "order": o}

    @app.post("/api/vendor/flowers/ready", dependencies=guarded)
    def flower_ready(body: dict = Body(...)):
        """A kind the human agreed to is ready to be sold (after its pictures are drawn, if you draw any).
        Registered before /flowers/{req_id}: the other way round "ready" was taken for a request id."""
        need("vendor")
        from . import vendor
        return {"changed": vendor.mark_ready(str(body.get("name") or ""))}

    @app.post("/api/vendor/flowers/{req_id}", dependencies=guarded)
    def flower_decide(req_id: str, body: dict = Body(...)):
        need("vendor")
        from . import vendor
        try:
            return {"ok": True, "request": vendor.decide(req_id, bool(body.get("approve")))}
        except KeyError:
            raise HTTPException(404, "no such request") from None

    @app.get("/api/wallet", dependencies=guarded)
    def wallet_get(who: str | None = None, viewer: str | None = None):
        need("vendor")
        from . import vendor
        w = role(who, viewer)
        return {"local": vendor.wallet_is_local(), "balance": vendor._balance(vendor.wallet(), w)}

    @app.post("/api/wallet/grant", dependencies=guarded)
    def wallet_grant(body: dict = Body(...)):
        """Pocket money into the built-in ledger (only when no wallet of your own is configured)."""
        need("vendor")
        from . import vendor
        amount = body.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= 100000:
            raise HTTPException(400, "amount must be a whole number between 1 and 100000")
        key = str(body.get("key") or "").strip()[:80]
        if not key:
            raise HTTPException(400, "key required (the same key for a retry of the same grant)")
        w = vendor.wallet()
        if not isinstance(w, vendor.LocalWallet):
            raise HTTPException(409, "a wallet of your own is configured; give pocket money there")
        w_who = who_of(body)
        try:
            bal = w.grant(w_who, amount, str(body.get("note") or ""), key=key)
        except vendor.VendorError as e:
            raise HTTPException(409, e.text) from None
        # The role hears it on its next turn, once per grant (the note is keyed like the grant)
        from . import notify
        from .texts import t
        text = tp("pocket_given", amount=amount, balance=bal)
        notify.emit(w_who, "pocket.given", t("head") + text, body=text, key=f"pocket:{w_who}:{key}")
        return {"balance": bal}
