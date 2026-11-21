"""The HTTP server: REST under /api for a kitchen page, MCP at /mcp for the model, and the
kitchen page itself (the built web app, static files) under /page/.

All live in one process and one port. When ``server.token`` is set, every
request to /api (except /api/health) and /mcp must carry
``Authorization: Bearer <token>``. The files under /page/ are public: the page asks for the
token itself and sends it as that header, never in an address.

Role ids are passed as ``who``. ``viewer`` is accepted as an alias everywhere.
"""
from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
import mimetypes
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import AliasChoices, BaseModel, Field

from . import (__version__, art, clock, config, fridge, inline, kitchen, menu, notify, play, potion, roles,
               service, sleep, snacks, stamina)
from .texts import t

log = logging.getLogger(__name__)

_WHO = Field(default=None, validation_alias=AliasChoices("who", "viewer"))


class BuyIn(BaseModel):
    who: str | None = _WHO
    items: list[str]


class WhoIn(BaseModel):
    who: str | None = _WHO


class KindIn(BaseModel):
    name: str
    category: str
    raw_edible: bool | None = None
    pack_qty: int = 1
    shelf_days: float | None = None


class SnackEatIn(BaseModel):
    who: str | None = _WHO
    snack: str
    variant: str | None = None


class SnackCapsIn(BaseModel):
    who: str | None = _WHO
    caps: dict        # values are checked one by one in snacks.set_caps (no lenient coercion)


class PotionIn(BaseModel):
    who: str | None = _WHO
    menu_row_id: str
    pct: int
    memo: str | None = None


class PotionPct(BaseModel):
    who: str | None = _WHO
    pct: int
    memo: str | None = None      # omitted = leave the memo as it is


class PotionHangIn(BaseModel):
    who: str | None = _WHO
    pct: int
    memo: str | None = None
    by: str = "human"


class DrinkIn(BaseModel):
    who: str | None = _WHO
    menu_row_ids: list[str]


class MenuIn(BaseModel):
    dish: str
    by: str
    for_who: str
    note: str | None = None


class SettleIn(BaseModel):
    who: str | None = _WHO
    tools: list = Field(default_factory=list)
    round_id: str | None = None


class EarnIn(BaseModel):
    who: str | None = _WHO
    source: str
    key: str


class SleepIn(BaseModel):
    who: str | None = _WHO
    asleep: bool | None = None
    until: float | None = None
    factor: float | None = None


class InlineIn(BaseModel):
    who: str | None = _WHO
    text: str
    message_id: str | None = None
    told: bool = False


class ClockIn(BaseModel):
    advance_seconds: float = 0.0
    reset: bool = False


# The kitchen page: the web build that ships inside the package (rebuilt from web/page/).
PAGE_DIR = Path(__file__).with_name("page")
PAGE_MISSING = ("The kitchen page is not in this install. Build it from web/page/ (npm install && npm run build); "
                "see docs/PAGE.md. / 这份安装里没有厨房页。请在 web/page/ 里构建（npm install && npm run build），"
                "见 docs/PAGE.md。")


# Content types of the page's files that must not depend on the system's mimetypes table
_PAGE_TYPES = {".webp": "image/webp", ".woff2": "font/woff2"}


def _origin_list(values: list[str]) -> list[str]:
    """Origins as browsers compare them: no trailing slash, and nothing that is not scheme://host[:port]."""
    out = []
    for v in values:
        o = (v or "").strip().rstrip("/")
        if o and "://" in o and not any(c in o for c in " ;,'\"*") and "/" not in o.split("://", 1)[1]:
            out.append(o)
    return out


def _page_headers(rel: str) -> dict[str, str]:
    """Who may frame the page, and how long a file may be cached. Files under _expo/ and assets/
    carry a hash of their content in the name, so they never change; the rest is checked each time."""
    frames = " ".join(["'self'", *_origin_list(config.get().server_embed_origins)])
    hashed = rel.startswith(("_expo/", "assets/"))
    return {"Content-Security-Policy": f"frame-ancestors {frames}",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
            "Cache-Control": "public, max-age=31536000, immutable" if hashed else "no-cache"}


def _role(who: str | None, viewer: str | None = None) -> str:
    try:
        return roles.resolve(who or viewer)
    except ValueError:
        raise HTTPException(400, t("detail_role")) from None


def _token_ok(header: str | None) -> bool:
    token = config.get().server_token
    if not token:
        return True
    scheme, _, given = (header or "").partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(given.strip(), token)


def auth(request: Request) -> None:
    if not _token_ok(request.headers.get("authorization")):
        raise HTTPException(401, t("detail_token"))


class _McpAuth:
    """Guards the mounted MCP app with the same bearer token as /api."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if not _token_ok(headers.get("authorization")):
                await JSONResponse({"detail": t("detail_token")}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(*, scheduler: bool = True, with_mcp: bool = True) -> FastAPI:
    """Build the app from the active settings (see :mod:`kitchenette.config`)."""
    mcp_server = None
    if with_mcp:
        from . import mcp_server as mcp_mod
        mcp_server = mcp_mod.build()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = asyncio.Event()
        task = asyncio.create_task(service.run_forever(stop)) if scheduler else None
        art.resume_pending()
        async with contextlib.AsyncExitStack() as stack:
            if mcp_server is not None:
                await stack.enter_async_context(mcp_server.session_manager.run())
            try:
                yield
            finally:
                stop.set()
                if task is not None:
                    await task

    app = FastAPI(title="kitchenette", version=__version__, lifespan=lifespan)
    origins = [o.rstrip("/") for o in config.get().server_cors_origins if o]
    if origins:
        # A cooking card or a kitchen page on someone else's site fetches /api from the browser;
        # without this the browser refuses to hand it the answer. Nothing is allowed unless it is listed.
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"],
                           allow_headers=["Authorization", "Content-Type"])
    guarded = [Depends(auth)]

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__, "now": clock.now()}

    @app.get("/api/roles", dependencies=guarded)
    def roles_list():
        return {"default": config.get().roles_default,
                "roles": sorted(set(roles.known()) | {config.get().roles_default})}

    @app.get("/api/about", dependencies=guarded)
    def about():
        """What a page needs to know before it draws anything: who lives here, which parts of the
        kitchen are switched on, and the words the settings use for the human. Read-only."""
        cfg = config.get()
        listed = [r for r in cfg.roles_allowed if roles.valid(r)]
        return {"version": __version__, "now": clock.now(),
                "timezone": cfg.server_timezone, "timezone_label": cfg.server_timezone_label,
                "roles": {"default": cfg.roles_default,
                          "list": sorted(set(roles.known()) | set(listed) | {cfg.roles_default})},
                "switches": {"stamina": bool(cfg.stamina_enabled), "satiety": bool(cfg.satiety_enabled),
                             "worms": bool(cfg.kitchen_worm_enabled), "dev_clock": bool(cfg.server_dev_clock),
                             "art": art.enabled()},
                "features": {f["key"]: f["on"] for f in play.capabilities()["features"]},
                "words": {"human_name": cfg.words_human_name, "human_pronoun": cfg.words_human_pronoun,
                          "app_name": cfg.words_app_name},
                "limits": {"coupon_max": cfg.fridge_coupon_max, "buy_max_items": cfg.fridge_buy_max_items,
                           "hungry_below": cfg.satiety_hungry_below}}

    # ── kitchen ─────────────────────────────────────────────────────────
    @app.get("/api/kitchen", dependencies=guarded)
    def kitchen_overview(session_id: str | None = None, who: str | None = None, viewer: str | None = None):
        if session_id:
            return kitchen.overview(session_id=session_id)
        w = _role(who, viewer)
        service.serve_due(w)
        return kitchen.overview(w)

    @app.get("/api/kitchen/can_eat", dependencies=guarded)
    def kitchen_can_eat(meal: str, who: str | None = None, viewer: str | None = None):
        return kitchen.can_eat(_role(who, viewer), meal)

    # ── fridge ──────────────────────────────────────────────────────────
    @app.get("/api/fridge", dependencies=guarded)
    def fridge_overview(who: str | None = None, viewer: str | None = None):
        w = _role(who, viewer)
        return {**fridge.overview(w), "text": fridge.status_text(w)}

    @app.get("/api/fridge/catalog", dependencies=guarded)
    def fridge_catalog():
        return fridge.catalog()

    @app.post("/api/fridge/kinds", dependencies=guarded)
    def fridge_kind_add(body: KindIn):
        try:
            k = fridge.add_kind(body.name, body.category, raw_edible=body.raw_edible,
                                pack_qty=body.pack_qty, shelf_days=body.shelf_days, art=art.enabled())
        except fridge.FridgeError as e:
            raise HTTPException(409 if e.code in ("duplicate", "too_many") else 400, e.text) from None
        if k["art"]["state"] == fridge.ART_PENDING:
            art.start(k["id"])
        return {"ok": True, "kind": k}

    @app.delete("/api/fridge/kinds/{kind_id}", dependencies=guarded)
    def fridge_kind_remove(kind_id: str):
        try:
            return {"ok": True, "kind": fridge.remove_kind(kind_id)}
        except fridge.FridgeError as e:
            raise HTTPException(404, e.text) from None

    @app.post("/api/fridge/kinds/{kind_id}/redraw", dependencies=guarded)
    def fridge_kind_redraw(kind_id: str):
        if not art.enabled():
            raise HTTPException(409, t("detail_no_art"))
        try:
            k = fridge.redraw_kind(kind_id)
        except fridge.FridgeError as e:
            raise HTTPException(404, e.text) from None
        art.start(kind_id)
        return {"ok": True, "kind": k}

    @app.get("/api/fridge/art/{kind_id}/{state}.png", dependencies=guarded)
    def fridge_kind_art(kind_id: str, state: str, v: int | None = None):
        k = next((x for x in fridge.kinds() if x["id"] == kind_id), None)
        if k is None or state not in art.STATES:
            raise HTTPException(404, t("art_unknown"))
        p = art.art_path(kind_id, state, k["art"]["v"] if v is None else v)
        if not p.is_file():
            raise HTTPException(404, t("art_not_ready"))
        return FileResponse(str(p), media_type="image/png", headers={"Cache-Control": "private, max-age=31536000"})

    @app.post("/api/fridge/buy", dependencies=guarded)
    def fridge_buy(body: BuyIn, background: BackgroundTasks):
        w = _role(body.who)
        try:
            res = fridge.buy_her(w, body.items)
        except fridge.FridgeError as e:
            raise HTTPException(400, e.text) from None
        items = "、".join(f"{a['name']}×{a['qty']}" for a in res["added"])[:200]
        notify.emit(w, notify.KIND_BOUGHT, payload={"items": items})
        background.add_task(notify.flush)
        return {"ok": True, **res}

    @app.post("/api/fridge/coupon", dependencies=guarded)
    def fridge_coupon(body: WhoIn, background: BackgroundTasks):
        w = _role(body.who)
        try:
            n = fridge.grant_coupon_by_her(w)
        except fridge.FridgeError as e:
            raise HTTPException(409, e.text) from None
        notify.emit(w, notify.KIND_COUPON, payload={"count": str(n)})
        background.add_task(notify.flush)
        return {"ok": True, "count": n, "text": t("her_coupon_ok", n=n)}

    @app.post("/api/coupons/earn", dependencies=guarded)
    def coupons_earn(body: EarnIn):
        """The role finished something that earns a coupon (for setups that do not report rounds)."""
        res = kitchen.coupon_for_work(_role(body.who), body.source, body.key)
        return {"ok": res["ok"], "granted": res["ok"], "text": res["text"], "reason": res["reason"]}

    # ── snacks ──────────────────────────────────────────────────────────
    @app.get("/api/snacks", dependencies=guarded)
    def snacks_get(who: str | None = None, viewer: str | None = None):
        return snacks.state(_role(who, viewer))

    @app.post("/api/snacks/eat", dependencies=guarded)
    def snacks_eat(body: SnackEatIn, background: BackgroundTasks):
        w = _role(body.who)
        # told=True: the note written below carries the worm sentence, no second notice is owed
        r = snacks.eat(w, body.snack, body.variant, snacks.BY_HER, told=True)
        if not r["ok"]:
            if r["reason"] == "cap":
                raise HTTPException(409, {
                    "reason": "cap", "eaten": r["eaten"], "cap": r["cap"], "resets_at": r["resets_at"],
                    "message": t("snack_cap_conflict", name=snacks.by_id(r["snack"])["name"],
                                 eaten=r["eaten"], cap=r["cap"], hm=clock.hm(r["resets_at"]))})
            raise HTTPException(400, snacks.err_text(r["reason"] or "", body.snack))
        notified = notify.emit(w, notify.KIND_SNACK_FED, payload=snacks.fed_payload(r),
                               key=f"snack:{r['id']}") is not None
        background.add_task(notify.flush)
        return {"result": {k: r[k] for k in ("id", "snack", "variant", "name", "tier", "gain",
                                              "energy_delta", "energy", "eaten", "cap")},
                "notified": notified, "state": snacks.state(w)}

    @app.put("/api/snacks/caps", dependencies=guarded)
    def snacks_caps(body: SnackCapsIn):
        w = _role(body.who)
        try:
            snacks.set_caps(w, body.caps)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return snacks.state(w)

    # ── potions ─────────────────────────────────────────────────────────
    def _potion_fail(e: potion.PotionError):
        code = 409 if e.code in ("used", "gone", "busy", "unregistered", "stamina_off") else (
            503 if e.code == "energy" else 400)
        raise HTTPException(code, {"message": e.text, "code": e.code, "rows": e.rows})

    @app.get("/api/potions", dependencies=guarded)
    def potions_pending(who: str | None = None, viewer: str | None = None):
        try:
            return {"name": potion.NAME, "note_fmt": potion.NOTE_FMT, "memo_sep": potion.MEMO_SEP,
                    "memo_max": potion.MEMO_MAX, "pct_min": potion.PCT_MIN,
                    "enabled": stamina.enabled(), "items": potion.pending(_role(who, viewer))}
        except potion.PotionError as e:
            _potion_fail(e)

    @app.post("/api/potions", dependencies=guarded)
    def potions_register(body: PotionIn):
        try:
            return {"ok": True, "potion": potion.register_potion(_role(body.who), body.menu_row_id, body.pct, body.memo)}
        except potion.PotionError as e:
            _potion_fail(e)

    @app.post("/api/potions/hang", dependencies=guarded)
    def potions_hang(body: PotionHangIn, background: BackgroundTasks):
        """Put a potion on the menu and record its amount in one step (all or nothing)."""
        w = _role(body.who)
        try:
            got = potion.hang(w, body.pct, body.memo, body.by)
        except potion.PotionError as e:
            _potion_fail(e)
        row = got["row"]
        notify.emit(w, notify.KIND_MENU_POSTED, payload={"dish": row["dish"], "note": row["note"] or ""},
                    key=f"menu.posted:{row['id']}")
        background.add_task(notify.flush)
        return {"ok": True, **got}

    @app.patch("/api/potions/{menu_row_id}", dependencies=guarded)
    def potions_update(menu_row_id: str, body: PotionPct):
        try:
            return {"ok": True, "potion": potion.register_potion(_role(body.who), menu_row_id, body.pct, body.memo)}
        except potion.PotionError as e:
            _potion_fail(e)

    @app.delete("/api/potions/{menu_row_id}", dependencies=guarded)
    def potions_remove(menu_row_id: str):
        return {"ok": True, "removed": potion.remove_potion(menu_row_id)}

    @app.post("/api/potions/drink", dependencies=guarded)
    def potions_drink(body: DrinkIn):
        try:
            return {"ok": True, **potion.drink(_role(body.who), body.menu_row_ids)}
        except potion.PotionError as e:
            _potion_fail(e)

    @app.post("/api/potions/{menu_row_id}/feed", dependencies=guarded)
    def potions_feed(menu_row_id: str, body: WhoIn, background: BackgroundTasks):
        w = _role(body.who)
        try:
            got = potion.feed(w, menu_row_id)
        except potion.PotionError as e:
            _potion_fail(e)
        menu.mark_eaten(menu_row_id)
        notify.emit(w, notify.KIND_POTION_FED, got["note"], key=f"potion_fed:{got['menu_row_id']}")
        background.add_task(notify.flush)
        return {"ok": True, **{k: got[k] for k in ("menu_row_id", "pct", "energy", "text")}}

    # ── menu ────────────────────────────────────────────────────────────
    def _menu_fail(e: menu.MenuError):
        raise HTTPException({"bad_request": 400, "not_found": 404, "already_eaten": 409}[e.code], e.text) from None

    @app.get("/api/menu", dependencies=guarded)
    def menu_list(pending: str | None = None, for_who: str | None = None):
        if for_who and roles.valid(for_who):
            service.serve_due(for_who)
        return menu.list_rows(for_who=for_who, pending=pending == "1")

    @app.post("/api/menu", status_code=201, dependencies=guarded)
    def menu_add(body: MenuIn, background: BackgroundTasks):
        try:
            if body.by and body.by == body.for_who and roles.valid(body.for_who):
                # a role putting up its own dish: the serving pass may be checking for the same one
                with kitchen.due_lock(body.for_who):
                    row = menu.add(body.dish, body.by, body.for_who, body.note)
            else:
                row = menu.add(body.dish, body.by, body.for_who, body.note)
        except menu.MenuError as e:
            _menu_fail(e)
        if row["by"] != row["for_who"]:
            notify.emit(row["for_who"], notify.KIND_MENU_POSTED,
                        payload={"dish": row["dish"], "note": row["note"] or ""}, key=f"menu.posted:{row['id']}")
            background.add_task(notify.flush)
        return row

    @app.patch("/api/menu/{row_id}", dependencies=guarded)
    async def menu_patch(row_id: str, request: Request):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, t("detail_body_object"))
        try:
            return menu.patch(row_id, body)
        except menu.MenuError as e:
            _menu_fail(e)

    @app.delete("/api/menu/{row_id}", dependencies=guarded)
    def menu_delete(row_id: str):
        if not menu.delete(row_id):
            raise HTTPException(404, t("detail_not_found"))
        potion.remove_potion(row_id)
        return {"deleted": row_id}

    @app.post("/api/menu/{row_id}/feed", dependencies=guarded)
    def menu_feed(row_id: str, background: BackgroundTasks):
        try:
            got = menu.feed(row_id)
        except menu.MenuError as e:
            _menu_fail(e)
        except potion.PotionError as e:
            _potion_fail(e)
        row = got["row"]
        if got["outcome"] == "potion":
            note = notify.emit(row["for_who"], notify.KIND_POTION_FED, got["text"], key=f"menu.fed:{row_id}")
        else:
            note = notify.emit(row["for_who"], notify.KIND_MENU_FED,
                               payload={"dish": row["dish"], "note": row["note"] or ""}, key=f"menu.fed:{row_id}")
        background.add_task(notify.flush)
        return {"ok": True, "row": row, "outcome": got["outcome"], "text": got["reply"], "notified": note is not None}

    @app.get("/api/meals", dependencies=guarded)
    def meals_list(who: str | None = None, viewer: str | None = None, since: float | None = None):
        """The meals a role has had since `since` (epoch seconds); left out = today."""
        return menu.meals_since(_role(who, viewer), since)

    # ── body: stamina, satiety, per-turn lines ──────────────────────────
    @app.get("/api/stamina", dependencies=guarded)
    def stamina_get(who: str | None = None, viewer: str | None = None):
        w = _role(who, viewer)
        v = stamina.read(w)
        return {"enabled": stamina.enabled(), "energy": None if v is None else round(v, 4),
                "line": stamina.body_line(w), "recent": stamina.history(w) if stamina.enabled() else []}

    @app.get("/api/turn-lines", dependencies=guarded)
    def turn_lines(who: str | None = None, viewer: str | None = None):
        """Status worth carrying into the role's next turn: dizzy / hungry lines and the stamina line."""
        w = _role(who, viewer)
        return {"kitchen": fridge.turn_lines(w), "body": stamina.body_line(w)}

    @app.post("/api/rounds/settle", dependencies=guarded)
    def rounds_settle(body: SettleIn):
        return service.settle_round(_role(body.who), body.tools, body.round_id)

    @app.get("/api/sleep", dependencies=guarded)
    def sleep_get(who: str | None = None, viewer: str | None = None):
        return sleep.state(_role(who, viewer))

    @app.put("/api/sleep", dependencies=guarded)
    def sleep_put(body: SleepIn):
        try:
            return sleep.report(_role(body.who), asleep=body.asleep, until=body.until, factor=body.factor)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    # ── notes for the role ──────────────────────────────────────────────
    @app.get("/api/notes", dependencies=guarded)
    def notes_peek(who: str | None = None, viewer: str | None = None):
        w = _role(who, viewer)
        service.serve_due(w)
        return {"notes": notify.pending(w)}

    @app.post("/api/notes/take", dependencies=guarded)
    def notes_take(body: WhoIn):
        w = _role(body.who)
        service.serve_due(w)
        notes = notify.take(w)
        return {"notes": notes, "text": "\n".join(n["text"] for n in notes)}

    # ── bracket markers ─────────────────────────────────────────────────
    @app.post("/api/inline", dependencies=guarded)
    def inline_run(body: InlineIn):
        if config.get().inline_enabled is False:        # "auto" accepts replies: the first one switches it on
            raise HTTPException(409, t("detail_inline_off"))
        receipts = inline.execute(_role(body.who), body.text, body.message_id, told=body.told)
        return {"receipts": [r.__dict__ for r in receipts], "stripped": inline.strip(body.text)}

    # ── housekeeping ────────────────────────────────────────────────────
    @app.post("/api/scan", dependencies=guarded)
    def scan_now():
        """Run the periodic scan right now instead of waiting for the next tick."""
        return service.scan_all()

    @app.post("/api/dev/clock", dependencies=guarded)
    def dev_clock(body: ClockIn):
        if not config.get().server_dev_clock:
            raise HTTPException(404, t("detail_dev_clock_off"))
        if body.reset:
            clock.reset()
        scan = service.fast_forward(body.advance_seconds)
        return {"offset": clock.offset(), "now": clock.now(), "scan": scan}

    # ── the upgrade (recipes, dish book, plates, jars, vendors) ─────────
    from . import play_api
    play_api.register(app, guarded, _role)

    # ── the kitchen page (static files; no token: the page sends it itself) ─────
    @app.get("/page", include_in_schema=False)
    def page_root():
        return RedirectResponse("/page/", status_code=307)

    @app.get("/page/{rel:path}", include_in_schema=False)
    def page_file(rel: str = ""):
        if not (PAGE_DIR / "index.html").is_file():
            raise HTTPException(404, PAGE_MISSING)
        rel = rel or "index.html"
        target = (PAGE_DIR / rel).resolve()
        if PAGE_DIR.resolve() not in target.parents or not target.is_file():
            raise HTTPException(404, "Not found")
        # the types the page's own files need, not left to the system's mimetypes table (which may not know them)
        kind = _PAGE_TYPES.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return FileResponse(str(target), media_type=kind, headers=_page_headers(rel))

    if mcp_server is not None:
        from . import mcp_server as mcp_mod
        app.mount("/", _McpAuth(mcp_mod.asgi_app(mcp_server)))
    return app
