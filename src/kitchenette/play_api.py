"""REST for the upgrade (mounted by :func:`kitchenette.api.create_app`). See docs/API.md.

Everything a switched-off feature offers answers 409 with "this is off"; ``GET /api/features`` says
what is on so a page can hide what is not. Nothing here deletes data.
"""
from __future__ import annotations

import uuid

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

from . import clock, db, play, service
from .texts_play import tp


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

    @app.put("/api/prefs", dependencies=guarded)
    def prefs(body: dict = Body(...)):
        """Ingredients the human does not want recommended (the whole list, replaced)."""
        need("recipes_public")
        from . import fridge
        w = who_of(body)
        items = [str(x) for x in (body.get("dislike") or [])][:60]
        bad = [i for i in items if fridge.item(i) is None]
        if bad:
            raise HTTPException(400, f"unknown items: {bad}")
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM kitchen_prefs WHERE who=? AND kind='dislike'", (w,))
            conn.executemany("INSERT INTO kitchen_prefs (who, kind, item, at) VALUES (?,?,?,?)",
                             [(w, "dislike", i, clock.now()) for i in items])
            conn.commit()
        finally:
            conn.close()
        return {"dislike": items}

    @app.get("/api/prefs", dependencies=guarded)
    def prefs_get(who: str | None = None, viewer: str | None = None):
        need("recipes_public")
        from . import recipes
        conn = db.connect()
        try:
            return {"dislike": sorted(recipes.dislikes(conn, role(who, viewer)))}
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
            out = dex.build(conn, w)
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
        need("dex")
        w = who_of(body)
        conn = db.connect()
        try:
            conn.execute("INSERT INTO dex_merges (who, dish, page_key, at) VALUES (?,?,?,?)"
                         " ON CONFLICT(who, dish) DO UPDATE SET page_key=excluded.page_key, at=excluded.at",
                         (w, "".join(str(body.get("dish") or "").split()), str(body.get("page_key") or ""),
                          clock.now()))
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

    @app.post("/api/vendor/flowers/{req_id}", dependencies=guarded)
    def flower_decide(req_id: str, body: dict = Body(...)):
        need("vendor")
        from . import vendor
        try:
            return {"ok": True, "request": vendor.decide(req_id, bool(body.get("approve")))}
        except KeyError:
            raise HTTPException(404, "no such request") from None

    @app.post("/api/vendor/flowers/ready", dependencies=guarded)
    def flower_ready(body: dict = Body(...)):
        """A kind the human agreed to is ready to be sold (after its pictures are drawn, if you draw any)."""
        need("vendor")
        from . import vendor
        return {"changed": vendor.mark_ready(str(body.get("name") or ""))}

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
