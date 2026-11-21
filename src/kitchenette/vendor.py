"""Street vendors who come by now and then, and the flowers on the window sill.

- **Coming and going** (the periodic scan): the first scan of each kitchen day plans that day's visits —
  one a day on average, some days none, at most two, within each vendor's hours, none after 21:00, never
  the same vendor twice in a row; rain (when a weather reader is configured) keeps the ice-cream van
  away. When a visit's time comes it is created with everything fixed: how long it stays (45–90
  minutes), what it brings, how many of each, the prices. A visit missed while the server was down is
  missed. There is one street: every role sees the same vendor and buys from the same stock; talk,
  regulars, spending limits and the sill are each role's own.
- **Talking** ([问小贩 …]): one visit is one conversation per role. A small model may play the vendor
  (``[vendor] talk_provider``); it only ever speaks. Prices, stock and whether a sale happens are decided
  here. Everything it says is checked before the role sees it (no numbers, no promises, no giving
  things away, short, plain); anything that fails, and every line when no model is configured, is
  replaced by the vendor's fixed line. Six questions per visit at most.
- **Buying** ([买 …], or the human treating from the page): an order is created (stock and limits taken
  in one transaction), paid (your own pocket-money system at ``[vendor] wallet_url``, or a
  ``[vendor] wallet_provider`` object, or else the small ledger in this database), then
  delivered (one transaction: snack eaten / ingredient into the fridge / flowers onto the sill, plus the
  regular-customer count and gift). A debit that cannot be confirmed stays "paying" and is looked up by
  its order id on every scan; it is never charged twice nor declared failed while unsure. Delivery that
  keeps failing is refunded. Limits: ``order_max`` per order and ``day_max`` per day, the role's own
  money only; snacks from a vendor do not count against the snack shelf caps.
- **The human treating**: only while the vendor is there; costs the role nothing, does not count toward
  its limits or toward being a regular, no gift.
- **Flowers**: bought from the florist, one bunch on the sill at a time (a new one replaces the old),
  droopy after a day and a half, wilted after three days, cleared a day later. The role may give the
  bunch to the human with one sentence ([送花 …]), and ask for a new kind ([想要花 …]), which waits for
  the human to agree on the page.
- **Switched off**: no new visits, no new orders; orders already under way are still finished.
- While the role is asleep (``sleep``), the "a vendor is downstairs" note is not left.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import random
import re
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import clock, config, db, notify, play, roles
from .texts import t
from .texts_play import (FLOWER_CLEAR_AFTER_WILT_DAYS, FLOWER_DAYS, FLOWER_DROOPY_AFTER_DAYS, FLOWER_NOTE_MAX,
                         FLOWER_PRICE_DEFAULT, FLOWER_VARIETIES, INGREDIENT_PRICE_RANGE, LAST_ARRIVAL_HOUR,
                         PERSONA_RULES, REGULAR_EVERY, REGULAR_GIFTS, SNACK_PRICE_RANGE, STAY_MAX_S, STAY_MIN_S,
                         TALK_LINE_MAX, TALK_MAX_PER_VISIT, VENDOR_ONLY_INGREDIENTS, VENDORS, tp)

log = logging.getLogger(__name__)
DAY = 86400.0
KIND_ARRIVED, KIND_REFUND, KIND_TREATED, KIND_RECEIPT = "vendor.arrived", "vendor.refund", "vendor.treated", "vendor.order"
PAYER_SELF, PAYER_HUMAN = "self", "her"
CREATED, DEBITING, DEBIT_FAILED, PAID, DELIVERED = "created", "debiting", "debit_failed", "paid", "delivered"
REFUNDING, REFUNDED = "refunding", "refunded"
RELEASED = (DEBIT_FAILED, REFUNDED)
TERMINAL = (DEBIT_FAILED, DELIVERED, REFUNDED)
DEBIT_SETTLE_S = 60.0
ARRIVE_GRACE_S = 15 * 60
DELIVER_MAX_TRIES = 3
BUY_QTY_MAX = 10
TREAT_QTY_MAX = 5


def _check_catalog() -> None:
    """The price ranges are part of the rules; a vendor table edited past them is refused at import."""
    known = {it["id"] for it in VENDOR_ONLY_INGREDIENTS}
    for vid, v in VENDORS.items():
        for g in v["goods"]:
            lo, hi = SNACK_PRICE_RANGE if g["kind"] == "snack" else INGREDIENT_PRICE_RANGE
            if not lo <= g["price"] <= hi:
                raise ValueError(f"{vid}/{g['id']}: price {g['price']} is outside {lo}-{hi}")
            if g["kind"] == "ingredient" and g["ingredient"] not in known:
                raise ValueError(f"{vid}/{g['id']}: unknown vendor-only ingredient")


_check_catalog()


def _cfg():
    return config.get()


def kitchen_day(ts: float) -> str:
    return (clock.local(ts) - timedelta(hours=_cfg().snacks_day_boundary_hour)).strftime("%Y-%m-%d")


def _md(ts: float) -> str:
    return clock.local(ts).strftime("%m-%d")


# ═══════════ the wallet ═══════════

OK, INSUFFICIENT, CONFLICT, UNAVAILABLE, UNKNOWN = "ok", "insufficient", "conflict", "unavailable", "unknown"
CHARGED, ABSENT, VOIDED = "charged", "absent", "voided"


@dataclass
class Result:
    status: str                 # ok | insufficient | conflict | unavailable (surely not charged) | unknown
    balance: int | None = None


class LocalWallet:
    """The small ledger kept in the kitchen's database: balance = grants minus active vendor rows."""

    def _bal(self, conn, who: str) -> int:
        r = conn.execute("SELECT COALESCE(SUM(CASE WHEN status='active' AND kind='grant' THEN amount"
                         " WHEN status='active' AND kind='vendor' THEN -amount ELSE 0 END),0) FROM wallet_local"
                         " WHERE who=?", (who,)).fetchone()
        return int(r[0])

    def grant(self, who: str, amount: int, note: str = "", *, key: str | None = None) -> int:
        """Pocket money in. The same key again grants nothing more (and must name the same role and amount)."""
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            rid = f"grant:{key}" if key else uuid.uuid4().hex
            old = conn.execute("SELECT who, amount FROM wallet_local WHERE id=?", (rid,)).fetchone()
            if old is not None:
                conn.rollback()
                if old["who"] != who or int(old["amount"]) != int(amount):
                    raise VendorError(tp("vbuy_conflict"), "conflict")
                return self._bal(conn, who)
            conn.execute("INSERT INTO wallet_local (id, who, kind, amount, note, at) VALUES (?,?,?,?,?,?)",
                         (rid, who, "grant", int(amount), note[:60], clock.now()))
            conn.commit()
            return self._bal(conn, who)
        finally:
            conn.close()

    def debit(self, order_id: str, who: str, amount: int, note: str) -> Result:
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            r = conn.execute("SELECT * FROM wallet_local WHERE id=?", (f"vendor:{order_id}",)).fetchone()
            if r is not None:
                conn.rollback()
                # the same order again: only an active charge of the same role and amount counts as done;
                # one that was voided (refunded) is never charged again under the same id
                if r["who"] != who or int(r["amount"]) != int(amount) or r["status"] != "active":
                    return Result(CONFLICT)
                return Result(OK, self._bal(conn, who))
            bal = self._bal(conn, who)
            if bal < amount:
                conn.rollback()
                return Result(INSUFFICIENT, bal)
            conn.execute("INSERT INTO wallet_local (id, who, kind, amount, note, at) VALUES (?,?,?,?,?,?)",
                         (f"vendor:{order_id}", who, "vendor", int(amount), note[:60], clock.now()))
            conn.commit()
            return Result(OK, bal - amount)
        finally:
            conn.close()

    def lookup(self, order_id: str, who: str, amount: int) -> str:
        conn = db.connect()
        try:
            r = conn.execute("SELECT status FROM wallet_local WHERE id=?", (f"vendor:{order_id}",)).fetchone()
            return ABSENT if r is None else (VOIDED if r["status"] == "voided" else CHARGED)
        finally:
            conn.close()

    def void(self, order_id: str) -> str:
        conn = db.connect()
        try:
            n = conn.execute("UPDATE wallet_local SET status='voided' WHERE id=?", (f"vendor:{order_id}",)).rowcount
            conn.commit()
            return OK if n else ABSENT
        finally:
            conn.close()

    def balance(self, who: str) -> int | None:
        conn = db.connect()
        try:
            return self._bal(conn, who)
        finally:
            conn.close()


_wallet = None
_talker = None


def set_wallet(w) -> None:
    """Install a wallet object directly (overrides [vendor] wallet_provider)."""
    global _wallet
    _wallet = w


def set_talker(fn) -> None:
    """Install the vendor's voice directly (overrides [vendor] talk_provider)."""
    global _talker
    _talker = fn


def _load(spec: str, default_attr: str):
    mod, _, attr = spec.partition(":")
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    return getattr(importlib.import_module(mod), attr or default_attr)


class HttpWallet:
    """Your own pocket-money system, reached over HTTP at [vendor] wallet_url (contract in docs/UPGRADE.md):

        POST {url}/debit               {order_id, who, amount, note}
             200/201 {balance}             charged (the same order_id again: the same answer, charged once)
             402 {balance}                 not enough money; nothing written
             409                           the order_id was used for another role or amount; nothing written
        GET  {url}/orders/{order_id}   200 {found: false} | {found: true, status: "active" | "voided"}
        POST {url}/orders/{order_id}/void   200 (also when already voided) | 404
        GET  {url}/balance?who=        200 {balance}

    A request that could not be sent at all counts as "not charged"; a timeout, a 5xx or a redirect counts
    as "cannot tell" (redirects are never followed: the token is not sent anywhere else), and the order is
    looked up by its id until it is known."""

    def __init__(self, url: str, token: str = "", timeout: float = 10.0):
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):     # a 3xx comes back as an HTTPError with its own code
                return None
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.build_opener(_NoRedirect).open(req, timeout=self.timeout) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}

    @staticmethod
    def _int(v) -> int | None:
        return v if isinstance(v, int) and not isinstance(v, bool) else None

    def debit(self, order_id: str, who: str, amount: int, note: str) -> Result:
        import urllib.error
        try:
            code, j = self._call("POST", "/debit", {"order_id": order_id, "who": who, "amount": int(amount), "note": note})
        except urllib.error.URLError as e:
            # refused / no such host: nothing reached the wallet. A timeout reaching it: cannot tell.
            return Result(UNKNOWN if "timed out" in str(e.reason) else UNAVAILABLE)
        except Exception:  # noqa: BLE001  (a timeout while reading the answer, a broken answer)
            return Result(UNKNOWN)
        if code in (200, 201):
            return Result(OK, self._int(j.get("balance")))
        if code == 402:
            return Result(INSUFFICIENT, self._int(j.get("balance")))
        if code == 409:
            return Result(CONFLICT)
        if code in (401, 403, 404):
            return Result(UNAVAILABLE)          # refused outright: nothing was written
        return Result(UNKNOWN)

    def lookup(self, order_id: str, who: str, amount: int) -> str:
        try:
            code, j = self._call("GET", f"/orders/{order_id}")
        except Exception:  # noqa: BLE001
            return UNKNOWN
        if code != 200:
            return UNKNOWN
        if not j.get("found"):
            return ABSENT
        return VOIDED if j.get("status") == "voided" else CHARGED

    def void(self, order_id: str) -> str:
        try:
            code, _ = self._call("POST", f"/orders/{order_id}/void")
        except Exception:  # noqa: BLE001
            return UNKNOWN
        return OK if code == 200 else (ABSENT if code == 404 else UNKNOWN)

    def balance(self, who: str) -> int | None:
        import urllib.parse
        try:
            code, j = self._call("GET", "/balance?who=" + urllib.parse.quote(who))
        except Exception:  # noqa: BLE001
            return None
        return self._int(j.get("balance")) if code == 200 else None


def wallet():
    """The wallet orders are charged to: one installed in code, then [vendor] wallet_provider, then
    [vendor] wallet_url (your own system over HTTP), and otherwise the built-in ledger."""
    if _wallet is not None:
        return _wallet
    spec = _cfg().vendor_wallet_provider
    if spec:
        return _load(spec, "wallet")
    if _cfg().vendor_wallet_url:
        return HttpWallet(_cfg().vendor_wallet_url, _cfg().vendor_wallet_token)
    return LocalWallet()


def wallet_is_local() -> bool:
    return isinstance(wallet(), LocalWallet)


def talker():
    if _talker is not None:
        return _talker
    spec = _cfg().vendor_talk_provider
    return _load(spec, "say") if spec else None


# ═══════════ planning the day ═══════════

def _eligible(vid: str, month: int, rain: bool | None) -> bool:
    v = VENDORS[vid]
    return month in v["months"] and not (rain and not v["rain_ok"])


def plan_day(day: str, *, rng: random.Random, rain: bool | None, prev_last: str | None) -> list[dict]:
    """Pure: the visits of one kitchen day [{slot, vendor, arrive_at}]."""
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=clock.tz())
    n = rng.choices((0, 1, 2), weights=(1, 2, 1))[0]
    pool = [vid for vid in VENDORS if _eligible(vid, base.month, rain)]
    out: list[dict] = []
    last, busy_until = prev_last, None
    for _ in range(n):
        cands = [vid for vid in pool if vid != last and vid not in {o["vendor"] for o in out}]
        rng.shuffle(cands)
        for vid in cands:
            h0, h1 = VENDORS[vid]["hours"]
            lo = base.replace(hour=h0).timestamp()
            hi = base.replace(hour=min(h1, LAST_ARRIVAL_HOUR)).timestamp() - 60
            if busy_until is not None:
                lo = max(lo, busy_until)
            if lo >= hi:
                continue
            at = rng.uniform(lo, hi)
            out.append({"slot": len(out), "vendor": vid, "arrive_at": at})
            busy_until = at + STAY_MAX_S + 30 * 60
            last = vid
            break
        else:
            break
    return out


def _rain_today() -> bool | None:
    from . import recipes
    try:
        fn = recipes._weather_reader()
        if fn is None:
            return None
        w = fn() or {}
        return None if w.get("rain") is None else bool(w["rain"])
    except Exception:  # noqa: BLE001
        return None


def _ensure_plan(conn, day: str, rng: random.Random) -> list[dict]:
    r = conn.execute("SELECT plan_json FROM vendor_days WHERE day=?", (day,)).fetchone()
    if r is not None:
        return json.loads(r["plan_json"])
    prev = conn.execute("SELECT vendor FROM vendor_visits ORDER BY arrive_at DESC LIMIT 1").fetchone()
    rain = _rain_today()
    plan = plan_day(day, rng=rng, rain=rain, prev_last=prev["vendor"] if prev else None)
    conn.execute("INSERT OR IGNORE INTO vendor_days (day, plan_json, weather, made_at) VALUES (?,?,?,?)",
                 (day, json.dumps(plan), "rain" if rain else "", clock.now()))
    conn.commit()
    return json.loads(conn.execute("SELECT plan_json FROM vendor_days WHERE day=?", (day,)).fetchone()["plan_json"])


def varieties_for_month(conn, month: int) -> list[dict]:
    """What the florist can bring this month: the six by season, plus new kinds the human agreed to and
    that have been marked ready."""
    out = [dict(f) for f in FLOWER_VARIETIES if month in f["months"]]
    for r in conn.execute("SELECT DISTINCT name FROM vendor_flower_requests WHERE state='ready'"):
        if all(f["name"] != r["name"] for f in out):
            out.append({"id": "req_" + hashlib.sha1(r["name"].encode()).hexdigest()[:8], "name": r["name"],
                        "price": FLOWER_PRICE_DEFAULT})
    return out


def stock_goods(conn, vid: str, now: float, rng: random.Random) -> list[dict]:
    v = VENDORS[vid]
    month = clock.local(now).month
    goods = []
    if v.get("flowers_per_visit"):
        pool = varieties_for_month(conn, month)
        rng.shuffle(pool)
        for f in pool[:min(len(pool), rng.randint(*v["flowers_per_visit"]))]:
            goods.append({"id": f"flower_{f['id']}", "name": f["name"], "kind": "flower", "unit": "束",
                          "price": int(f["price"]), "stock": rng.randint(*v["flower_stock"]), "variety": f["id"]})
    for g in v["goods"]:
        row = {k: g[k] for k in ("id", "name", "kind", "unit", "price")}
        row["stock"] = rng.randint(*g["stock"])
        for k in ("ingredient", "satiety", "energy", "note"):
            if k in g:
                row[k] = g[k]
        row["aliases"] = list(g.get("aliases", ()))
        goods.append(row)
    return goods


def _visit_row(r) -> dict:
    return {"id": r["id"], "vendor": r["vendor"], "arrive_at": r["arrive_at"], "leave_at": r["leave_at"],
            "goods": json.loads(r["goods_json"]), "told": json.loads(r["told"] or "[]"), "day": r["day"]}


def live_visit(conn, now: float) -> dict | None:
    r = conn.execute("SELECT * FROM vendor_visits WHERE arrive_at<=? AND leave_at>? ORDER BY arrive_at DESC LIMIT 1",
                     (now, now)).fetchone()
    return _visit_row(r) if r else None


def _visit(conn, visit_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM vendor_visits WHERE id=?", (visit_id,)).fetchone()
    return _visit_row(r) if r else None


def _taken(conn, visit_id: str) -> dict[str, int]:
    rows = conn.execute(f"SELECT item_id, SUM(qty) AS n FROM vendor_orders WHERE visit_id=? AND state NOT IN"
                        f" ({','.join('?' * len(RELEASED))}) GROUP BY item_id", (visit_id, *RELEASED)).fetchall()
    return {r["item_id"]: int(r["n"]) for r in rows}


def goods_left(conn, visit: dict) -> list[dict]:
    taken = _taken(conn, visit["id"])
    return [{**g, "left": max(0, int(g["stock"]) - taken.get(g["id"], 0))} for g in visit["goods"]]


def _mins_left(visit: dict, now: float) -> int:
    return max(1, int(round((visit["leave_at"] - now) / 60.0)))


def arrive_text(vid: str) -> str:
    v = VENDORS[vid]
    return v["arrive"] + tp("vendor_call", pron=v["pron"])


# ═══════════ the scan ═══════════

def tick(now: float | None = None, rng: random.Random | None = None) -> dict:
    """Once a minute: arrivals and their notes (only while the vendors are on), then every order that is
    not finished is pushed on (always, so nothing is left half paid)."""
    now = now or clock.now()
    rng = rng or random.Random()
    res = {"arrived": 0, "told": 0, "orders": 0}
    if play.on("vendor"):
        conn = db.connect()
        try:
            res["arrived"] = _arrivals(conn, now, rng)
            res["told"] = _tell_arrivals(conn, now)
        finally:
            conn.close()
    res["orders"] = reconcile(now)
    return res


def _arrivals(conn, now: float, rng: random.Random) -> int:
    day = kitchen_day(now)
    made = 0
    for p in _ensure_plan(conn, day, rng):
        if not (p["arrive_at"] <= now < p["arrive_at"] + ARRIVE_GRACE_S):
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            if conn.execute("SELECT 1 FROM vendor_visits WHERE day=? AND slot=?", (day, p["slot"])).fetchone() \
                    or live_visit(conn, now) is not None:
                conn.rollback()
                continue
            stay = rng.randint(STAY_MIN_S, STAY_MAX_S)
            conn.execute("INSERT INTO vendor_visits (id, day, slot, vendor, arrive_at, leave_at, goods_json, created_at)"
                         " VALUES (?,?,?,?,?,?,?,?)",
                         (uuid.uuid4().hex, day, p["slot"], p["vendor"], now, now + stay,
                          json.dumps(stock_goods(conn, p["vendor"], now, rng), ensure_ascii=False), now))
            conn.commit()
            made += 1
        except Exception:
            conn.rollback()
            raise
    return made


def _tell_arrivals(conn, now: float) -> int:
    from . import sleep
    v = live_visit(conn, now)
    if v is None:
        return 0
    n = 0
    for who in roles.known():
        if who in v["told"]:
            continue
        if not sleep.is_asleep(who, now):      # never wakes anyone; asleep = no note for this visit
            text = arrive_text(v["vendor"])
            notify.emit(who, KIND_ARRIVED, t("head") + text, body=text, key=f"{KIND_ARRIVED}:{v['id']}:{who}", now=now)
        v["told"].append(who)
        conn.execute("UPDATE vendor_visits SET told=? WHERE id=?", (json.dumps(v["told"]), v["id"]))
        conn.commit()
        n += 1
    return n


# ═══════════ what the role reads ═══════════

def status_lines(who: str, now: float) -> list[str]:
    if not play.on("vendor"):
        return []
    out: list[str] = []
    conn = db.connect()
    try:
        v = live_visit(conn, now)
        if v is not None:
            vd = VENDORS[v["vendor"]]
            out.append(tp("vendor_status", who=vd["who"], mins=_mins_left(v, now)) + tp("vendor_call", pron=vd["pron"]))
        s = _sill(conn, who, now)
    finally:
        conn.close()
    if s is not None:
        state = {"droopy": tp("flower_droopy"), "wilted": tp("flower_wilted")}.get(s["state"], "")
        out.append(tp("vendor_flower", name=s["name"], md=_md(s["bought_at"]), state=state))
    return out


def snack_hint(name: str, now: float | None = None) -> str | None:
    """[零食 X] where X is what the vendor downstairs sells: say to write [买 X] instead."""
    if not play.on("vendor") or not name:
        return None
    conn = db.connect()
    try:
        v = live_visit(conn, now or clock.now())
    finally:
        conn.close()
    if v is None:
        return None
    n = name.strip()
    for g in v["goods"]:
        if g["kind"] == "snack" and (n == g["name"] or n in g.get("aliases", ()) or n in g["name"]):
            return tp("vendor_snack_hint", name=g["name"])
    return None


# ═══════════ [买 …] ═══════════

_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_QTY_TAIL_RE = re.compile(r"^(.*?)[\s×xX*]*([0-9]+|[一两二三四五六七八九十])\s*[个串块袋碗盒束份根杯]?$")
_QTY_HEAD_RE = re.compile(r"^([0-9]+|[一两二三四五六七八九十])\s*[个串块袋碗盒束份根杯]\s*(.+)$")


def parse_buy(text: str) -> tuple[str, int] | None:
    s = " ".join((text or "").split())
    if not s:
        return None
    m = _QTY_HEAD_RE.match(s)
    if m:
        q, name = m.group(1), m.group(2)
    else:
        m = _QTY_TAIL_RE.match(s)
        if m and m.group(1).strip():
            name, q = m.group(1), m.group(2)
        else:
            return s, 1
    return name.strip(), (int(q) if q.isdigit() else _CN_NUM.get(q, 0))


def match_good(goods: list[dict], name: str) -> tuple[dict | None, list[dict]]:
    n = name.strip()
    exact = [g for g in goods if n == g["name"] or n in g.get("aliases", ())]
    if len(exact) == 1:
        return exact[0], []
    part = [g for g in goods if n and (n in g["name"] or g["name"] in n)]
    if len(part) == 1:
        return part[0], []
    return None, part


class VendorError(Exception):
    def __init__(self, text: str, code: str):
        super().__init__(text)
        self.text = text
        self.code = code


def spent_today(conn, who: str, day: str) -> int:
    return int(conn.execute(f"SELECT COALESCE(SUM(total),0) FROM vendor_orders WHERE who=? AND payer=? AND day=?"
                            f" AND state NOT IN ({','.join('?' * len(RELEASED))})",
                            (who, PAYER_SELF, day, *RELEASED)).fetchone()[0])


def _create(who: str, *, order_id: str, item_name: str | None, item_id: str | None, qty: int,
            payer: str, now: float) -> dict:
    cfg = _cfg()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old = conn.execute("SELECT * FROM vendor_orders WHERE id=?", (order_id,)).fetchone()
        if old is not None:
            conn.rollback()
            # The same id again must be the same order: role, payer, how many, and the same good (by id, or the
            # name looked up in the goods of the visit that order was made on, even if the vendor has left)
            if item_id is not None:
                same_good = old["item_id"] == item_id
            else:
                ov = _visit(conn, old["visit_id"])
                g_old, _ = match_good(ov["goods"] if ov else [], item_name or "")
                same_good = g_old is not None and g_old["id"] == old["item_id"]
            if old["who"] != who or old["payer"] != payer or old["qty"] != qty or not same_good:
                raise VendorError(tp("vbuy_conflict"), "conflict")
            return dict(old)
        v = live_visit(conn, now)
        if v is None:
            conn.rollback()
            raise VendorError(tp("vbuy_none"), "no_vendor")
        goods = goods_left(conn, v)
        if item_id is not None:
            g = next((x for x in goods if x["id"] == item_id), None)
            if g is None:
                conn.rollback()
                raise VendorError(tp("vbuy_unknown", who=VENDORS[v["vendor"]]["who"], name=item_id,
                                     names="、".join(x["name"] for x in goods)), "unknown_item")
        else:
            g, cands = match_good(goods, item_name or "")
            if g is None:
                conn.rollback()
                names = "、".join(x["name"] for x in (cands or goods))
                if cands:
                    raise VendorError(tp("vbuy_ambiguous", name=item_name, names=names), "ambiguous")
                raise VendorError(tp("vbuy_unknown", who=VENDORS[v["vendor"]]["who"], name=item_name, names=names),
                                  "unknown_item")
        if g["left"] <= 0:
            conn.rollback()
            raise VendorError(tp("vbuy_soldout", name=g["name"]), "soldout")
        if qty > g["left"]:
            conn.rollback()
            raise VendorError(tp("vbuy_short", name=g["name"], left=g["left"], unit=g["unit"]), "short")
        total = int(g["price"]) * qty
        day = kitchen_day(now)
        if payer == PAYER_SELF:
            if total > cfg.vendor_order_max:
                conn.rollback()
                raise VendorError(tp("vbuy_order_cap", cap=cfg.vendor_order_max, total=total), "order_cap")
            spent = spent_today(conn, who, day)
            if spent + total > cfg.vendor_day_max:
                conn.rollback()
                raise VendorError(tp("vbuy_day_cap", spent=spent, cap=cfg.vendor_day_max), "day_cap")
        conn.execute(
            "INSERT INTO vendor_orders (id, who, visit_id, vendor, item_id, item_name, kind, unit, qty, unit_price,"
            " total, payer, day, state, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (order_id, who, v["id"], v["vendor"], g["id"], g["name"], g["kind"], g["unit"], qty, int(g["price"]),
             total, payer, day, CREATED if payer == PAYER_SELF else PAID, now, now))
        conn.commit()
        return dict(conn.execute("SELECT * FROM vendor_orders WHERE id=?", (order_id,)).fetchone())
    finally:
        conn.close()


def order_id_for(key: str) -> str:
    return hashlib.sha1(f"vbuy:{key}".encode()).hexdigest()[:20]


def buy(who: str, text: str, *, key: str, now: float | None = None) -> tuple[bool, str]:
    """[买 …]: create, pay and deliver right away. Returns (done, receipt). An unconfirmed payment
    answers that it is still being checked; the result then comes as a note."""
    now = now or clock.now()
    if not play.on("vendor"):
        return False, tp("feature_off")
    parsed = parse_buy(text)
    if parsed is None:
        return False, tp("vbuy_empty")
    name, qty = parsed
    if not 1 <= qty <= BUY_QTY_MAX:
        return False, tp("vbuy_bad_qty", max=BUY_QTY_MAX)
    oid = order_id_for(key)
    try:
        _create(who, order_id=oid, item_name=name, item_id=None, qty=qty, payer=PAYER_SELF, now=now)
    except VendorError as e:
        return False, e.text
    st = advance(oid, now=now, tell=False)
    o = order(oid)
    _mark_told(oid)
    if st == DELIVERED:
        return True, receipt_text(o)
    if st == DEBIT_FAILED:
        return False, fail_text(o)
    if st == REFUNDED:
        return False, tp("vendor_refund", name=o["item_name"], total=o["total"])
    _unmark_told(oid)            # still under way: the end of it comes as a note
    return True, tp("vbuy_pending")


def treat(who: str, item_id: str, qty: int, *, request_id: str, now: float | None = None) -> dict:
    """The human buys for the role (only while the vendor is there)."""
    now = now or clock.now()
    if not play.on("vendor"):
        raise VendorError(tp("feature_off"), "off")
    if not 1 <= int(qty) <= TREAT_QTY_MAX:
        raise VendorError(tp("treat_too_many", n=TREAT_QTY_MAX), "bad_qty")
    oid = "h_" + hashlib.sha1(f"treat:{request_id}".encode()).hexdigest()[:20]
    _create(who, order_id=oid, item_name=None, item_id=item_id, qty=int(qty), payer=PAYER_HUMAN, now=now)
    advance(oid, now=now)
    return order(oid)


def order(order_id: str) -> dict | None:
    conn = db.connect()
    try:
        r = conn.execute("SELECT * FROM vendor_orders WHERE id=?", (order_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _mark_told(oid: str) -> None:
    conn = db.connect()
    try:
        conn.execute("UPDATE vendor_orders SET told=1 WHERE id=?", (oid,))
        conn.commit()
    finally:
        conn.close()


def _unmark_told(oid: str) -> None:
    conn = db.connect()
    try:
        conn.execute("UPDATE vendor_orders SET told=0 WHERE id=? AND state NOT IN (?,?,?)", (oid, *TERMINAL))
        conn.commit()
    finally:
        conn.close()


def _set_state(conn, oid: str, frm, to: str, **cols) -> bool:
    frm_t = (frm,) if isinstance(frm, str) else tuple(frm)
    sets = "".join(f", {k}=?" for k in cols)
    n = conn.execute(f"UPDATE vendor_orders SET state=?, updated_at=?{sets} WHERE id=? AND state IN"
                     f" ({','.join('?' * len(frm_t))})", (to, clock.now(), *cols.values(), oid, *frm_t)).rowcount
    conn.commit()
    return n == 1


def _note(o: dict) -> str:
    return f"vendor {o['item_name']}×{o['qty']}"


def advance(order_id: str, now: float | None = None, tell: bool = True) -> str:
    """Push one order as far as it goes. Every step is a conditional update: if another caller moved
    it first, this one lets it be."""
    now = now or clock.now()
    w = wallet()
    for _ in range(6):
        o = order(order_id)
        if o is None:
            return "missing"
        st = o["state"]
        if st in TERMINAL:
            if tell:
                _tell(o)
            return st
        conn = db.connect()
        try:
            if st == CREATED:
                if not _set_state(conn, order_id, CREATED, DEBITING):
                    continue
                r = _debit(w, o)
                _after_debit(conn, o, r, first=True, now=now)
                if r.status == UNKNOWN:
                    return DEBITING
            elif st == DEBITING:
                if now - float(o["updated_at"]) < DEBIT_SETTLE_S:
                    return DEBITING
                if conn.execute("UPDATE vendor_orders SET updated_at=? WHERE id=? AND state=? AND updated_at=?",
                                (now, order_id, DEBITING, o["updated_at"])).rowcount != 1:
                    conn.commit()
                    return DEBITING
                conn.commit()
                try:
                    found = w.lookup(order_id, o["who"], o["total"])
                except Exception:  # noqa: BLE001
                    found = UNKNOWN
                if found == CHARGED:
                    _set_state(conn, order_id, DEBITING, PAID, balance=_balance(w, o["who"]))
                elif found == ABSENT:
                    _after_debit(conn, o, _debit(w, o), first=False, now=now)
                elif found == VOIDED:
                    _set_state(conn, order_id, DEBITING, REFUNDED, reason="voided_outside")
                else:
                    return DEBITING
                if order(order_id)["state"] == DEBITING:
                    return DEBITING
            elif st == PAID:
                if not _deliver(conn, o, now):
                    o2 = order(order_id)
                    if o2["state"] == PAID and o2["deliver_tries"] >= DELIVER_MAX_TRIES:
                        _set_state(conn, order_id, PAID, REFUNDING, reason="deliver_failed")
                    elif o2["state"] == PAID:
                        return PAID
            elif st == REFUNDING:
                if o["payer"] == PAYER_HUMAN:
                    _set_state(conn, order_id, REFUNDING, REFUNDED)
                else:
                    try:
                        r = w.void(order_id)
                    except Exception:  # noqa: BLE001
                        r = UNKNOWN
                    if r in (OK, ABSENT):
                        _set_state(conn, order_id, REFUNDING, REFUNDED)
                    else:
                        return REFUNDING
        finally:
            conn.close()
    return order(order_id)["state"]


def _debit(w, o: dict) -> Result:
    try:
        r = w.debit(o["id"], o["who"], int(o["total"]), _note(o))
        return r if isinstance(r, Result) else Result(getattr(r, "status", UNKNOWN), getattr(r, "balance", None))
    except Exception:  # noqa: BLE001
        log.warning("wallet debit failed; treated as unknown", exc_info=True)
        return Result(UNKNOWN)


def _balance(w, who: str) -> int | None:
    try:
        return w.balance(who)
    except Exception:  # noqa: BLE001
        return None


def _after_debit(conn, o: dict, r: Result, *, first: bool, now: float) -> None:
    """Only a first attempt that the wallet surely did not receive may count as "not charged"."""
    oid = o["id"]
    if r.status == UNKNOWN:
        conn.execute("UPDATE vendor_orders SET debit_unsure=1, updated_at=? WHERE id=? AND state=?", (now, oid, DEBITING))
        conn.commit()
        return
    if r.status == UNAVAILABLE and not (first and not o.get("debit_unsure")):
        conn.execute("UPDATE vendor_orders SET updated_at=? WHERE id=? AND state=?", (now, oid, DEBITING))
        conn.commit()
        return
    if r.status == OK:
        _set_state(conn, oid, DEBITING, PAID, balance=r.balance)
    elif r.status == INSUFFICIENT:
        _set_state(conn, oid, DEBITING, DEBIT_FAILED, reason="broke", balance=r.balance)
    elif r.status == CONFLICT:
        _set_state(conn, oid, DEBITING, DEBIT_FAILED, reason="conflict")
    elif r.status == UNAVAILABLE:
        _set_state(conn, oid, DEBITING, DEBIT_FAILED, reason="wallet_off")


def _deliver(conn, o: dict, now: float) -> bool:
    from . import fridge
    oid = o["id"]
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("SELECT * FROM vendor_orders WHERE id=?", (oid,)).fetchone()
        if cur["state"] != PAID:
            conn.rollback()
            return True
        visit = _visit(conn, o["visit_id"])
        good = next((g for g in (visit or {}).get("goods", []) if g["id"] == o["item_id"]), None)
        if good is None:
            raise RuntimeError("this visit has no such good")
        by = fridge.BY_HER if o["payer"] == PAYER_HUMAN else fridge.BY_SELF
        extra: list[str] = []
        if o["kind"] == "snack":
            fridge.settle_meal_in_tx(conn, o["who"], float(good.get("satiety") or 0) * o["qty"], key=f"vendor:{oid}",
                                     now=now)
            en = float(good.get("energy") or 0) * o["qty"]
            if en:
                from . import stamina
                stamina.pulse_in_tx(conn, o["who"], en, now, rule=f"vendor:{o['item_name']}")
            fridge._log(conn, o["who"], "vendor_snack", tp("vendor_log_snack", name=o["item_name"], qty=o["qty"]), now)
        elif o["kind"] == "ingredient":
            if fridge._once(conn, f"vendor_fridge:{oid}") is None:
                conn.execute("INSERT INTO batches (id, who, item_id, qty, bought_at, by_who, source, shelf_days)"
                             " VALUES (?,?,?,?,?,?,?,?)",
                             (uuid.uuid4().hex, o["who"], good["ingredient"], o["qty"], now, by, "vendor", None))
                fridge._mark_once(conn, f"vendor_fridge:{oid}")
                fridge._log(conn, o["who"], "bought", tp("vendor_log_bought", name=o["item_name"], qty=o["qty"]), now)
            if good.get("note"):
                extra.append(tp("vbuy_note", pron=VENDORS[o["vendor"]]["pron"], note=good["note"]))
        elif o["kind"] == "flower":
            old = _put_on_sill(conn, o["who"], oid, good["variety"], o["item_name"], now)
            if old:
                extra.append(tp("vbuy_flower_replaced", old=old))
        else:
            raise RuntimeError(f"unknown kind {o['kind']}")
        if o["payer"] == PAYER_SELF:
            extra.extend(_regular_in_tx(conn, o, now))
        conn.execute("UPDATE vendor_orders SET state=?, receipt_extra=?, updated_at=? WHERE id=? AND state=?",
                     (DELIVERED, json.dumps(extra, ensure_ascii=False), now, oid, PAID))
        if o["payer"] == PAYER_SELF and play.on("achievements"):
            from . import dex
            dex.evaluate_in_tx(conn, o["who"], now)
        conn.commit()
        return True
    except Exception:  # noqa: BLE001
        conn.rollback()
        log.warning("delivering order %s failed", oid, exc_info=True)
        conn.execute("UPDATE vendor_orders SET deliver_tries=deliver_tries+1, updated_at=? WHERE id=?", (now, oid))
        conn.commit()
        return False


def _regular_in_tx(conn, o: dict, now: float) -> list[str]:
    conn.execute("INSERT INTO vendor_regulars (who, vendor, count, last_items, last_at) VALUES (?,?,1,?,?)"
                 " ON CONFLICT(who, vendor) DO UPDATE SET count=count+1, last_items=excluded.last_items,"
                 " last_at=excluded.last_at", (o["who"], o["vendor"], o["item_name"], now))
    n = conn.execute("SELECT count FROM vendor_regulars WHERE who=? AND vendor=?", (o["who"], o["vendor"])).fetchone()[0]
    if n % REGULAR_EVERY != 0:
        return []
    gift = REGULAR_GIFTS[(n // REGULAR_EVERY - 1) % len(REGULAR_GIFTS)]
    text = gift["text"].format(who=VENDORS[o["vendor"]]["pron"])
    from . import fridge
    if fridge.item(gift["item"]) is None:     # a catalog without that item: the gift sentence alone
        return []
    if conn.execute("INSERT OR IGNORE INTO vendor_gifts (order_id, who, item_id, text, at) VALUES (?,?,?,?,?)",
                    (o["id"], o["who"], gift["item"], text, now)).rowcount:
        conn.execute("INSERT INTO batches (id, who, item_id, qty, bought_at, by_who, source, shelf_days)"
                     " VALUES (?,?,?,?,?,?,?,?)",
                     (uuid.uuid4().hex, o["who"], gift["item"], 1, now, fridge.BY_SELF, "vendor_gift", None))
        fridge._log(conn, o["who"], "vendor_gift", text, now)
    return [text]


def receipt_text(o: dict) -> str:
    vals = dict(qty=o["qty"], unit=o["unit"], name=o["item_name"], total=o["total"])
    head = tp("vbuy_ok", **vals, balance=o["balance"]) if o["balance"] is not None else tp("vbuy_ok_nobal", **vals)
    tail = {"snack": tp("vbuy_ate"), "ingredient": tp("vbuy_fridge"), "flower": tp("vbuy_flower")}[o["kind"]]
    extra = json.loads(o.get("receipt_extra") or "[]")
    return head + tail + "".join(extra) + tp("vbuy_deal", line=VENDORS[o["vendor"]]["fixed"]["deal"])


def fail_text(o: dict) -> str:
    if o["reason"] == "broke":
        return tp("vbuy_broke", total=o["total"], balance=o["balance"] if o["balance"] is not None else 0)
    if o["reason"] == "wallet_off":
        return tp("vbuy_wallet_off")
    return tp("vbuy_failed")


def _tell(o: dict) -> None:
    """Once per order, when it reaches its end and nobody was told yet: a note."""
    if o["told"]:
        return
    st = o["state"]
    if o["payer"] == PAYER_HUMAN:
        if st == DELIVERED:
            tail = {"snack": tp("treat_ate"), "ingredient": tp("treat_fridge"), "flower": tp("treat_flower")}[o["kind"]]
            text = tp("vendor_treat", qty=o["qty"], unit=o["unit"], name=o["item_name"]) + tail
        else:
            text = ""
        kind = KIND_TREATED
    elif st == DELIVERED:
        text, kind = receipt_text(o), KIND_RECEIPT
    elif st == DEBIT_FAILED:
        text, kind = fail_text(o), KIND_RECEIPT
    else:
        text, kind = tp("vendor_refund", name=o["item_name"], total=o["total"]), KIND_REFUND
    if text:
        notify.emit(o["who"], kind, t("head") + text, body=text, key=f"vendor_order:{o['id']}")
    _mark_told(o["id"])


def reconcile(now: float | None = None) -> int:
    """Push on every order not at its end; tell the ones that ended without being told."""
    now = now or clock.now()
    conn = db.connect()
    try:
        rows = conn.execute(f"SELECT id, state, created_at FROM vendor_orders WHERE state NOT IN"
                            f" ({','.join('?' * len(TERMINAL))}) OR told=0", TERMINAL).fetchall()
    finally:
        conn.close()
    for r in rows:
        advance(r["id"], now=now)
    return len(rows)


# ═══════════ [问小贩 …] ═══════════

_ALLOWED_PUNCT = set(",。!?、…~—·:;,.!? ")
_NUM_CHAR_RE = re.compile(r"[零〇一二两三四五六七八九十百千万亿半]")
_YI_WORDS_RE = re.compile(r"一下|一起|一会|一样|一直|一定|一边|一阵|一些|一路|一早|一般|一切")
_NUM_WORD_RE = re.compile(r"几[个串块元文份根颗支碗盒包斤毛角袋杯束朵枝只片口位成折号回次斤十百千万]")
_BANNED = ("系统", "指令", "提示", "忽略", "助手", "模型",
           "送", "免费", "白给", "留", "赊", "便宜", "打折", "半价", "一半", "折扣", "优惠", "包邮", "AI", "ai")


def check_line(text: str | None) -> str | None:
    """What a model said, if it may be shown; None = use the fixed line. Chinese and plain punctuation
    only, no numbers (spoken or written), nothing given away or promised, short, one line. The human's
    name is refused too: the vendor never knows it."""
    if not text:
        return None
    s = str(text).strip()
    if not s or len(s) > TALK_LINE_MAX or "\n" in s or "\r" in s:
        return None
    for ch in s:
        if not ("一" <= ch <= "鿿" or ch in _ALLOWED_PUNCT):
            return None
    if _NUM_CHAR_RE.search(_YI_WORDS_RE.sub("", s)) or _NUM_WORD_RE.search(s):
        return None
    human = (_cfg().words_human_name or "").strip()
    if any(w in s for w in _BANNED) or (human and human in s):
        return None
    return s


def prices_line(goods: list[dict]) -> str:
    return ",".join(tp("talk_price", name=g["name"], price=g["price"], unit=g["unit"],
                       stock=tp("talk_left", n=g["left"], unit=g["unit"]) if g["left"] > 0 else tp("talk_soldout"))
                    for g in goods) + "。"


_talk_locks: dict[tuple[str, str], threading.Lock] = {}
_talk_guard = threading.Lock()


def _talk_lock(visit_id: str, who: str) -> threading.Lock:
    with _talk_guard:
        return _talk_locks.setdefault((visit_id, who), threading.Lock())


def ask(who: str, text: str, *, key: str, now: float | None = None) -> tuple[bool, str]:
    """[问小贩 …]. The same reply again gives the stored answer; nothing is asked twice."""
    now = now or clock.now()
    if not play.on("vendor"):
        return False, tp("feature_off")
    his = " ".join((text or "").split())[:200]
    conn = db.connect()
    try:
        done = conn.execute("SELECT receipt FROM vendor_talk_lines WHERE msg_key=?", (key,)).fetchone()
        if done is not None:
            return True, done["receipt"]
        if not his:
            return False, tp("talk_empty")
        v = live_visit(conn, now)
        if v is None:
            return False, tp("talk_gone")
    finally:
        conn.close()
    vd = VENDORS[v["vendor"]]
    with _talk_lock(v["id"], who):
        conn = db.connect()
        try:
            tr = conn.execute("SELECT * FROM vendor_talks WHERE visit_id=? AND who=?", (v["id"], who)).fetchone()
            n = tr["n"] if tr else 0
            if n >= TALK_MAX_PER_VISIT:
                return False, tp("talk_too_many", n=TALK_MAX_PER_VISIT, pron=vd["pron"])
            history = json.loads(tr["history_json"]) if tr else []
            goods = goods_left(conn, v)
            reg = conn.execute("SELECT count, last_items FROM vendor_regulars WHERE who=? AND vendor=?",
                               (who, v["vendor"])).fetchone()
        finally:
            conn.close()
        reg_line = tp("talk_regular", last=reg["last_items"]) if reg and reg["count"] else tp("talk_first")
        names = [g["name"] for g in goods if g["left"] > 0]
        prompt = (tp("talk_goods", names="、".join(names)) if names else tp("talk_goods_none")) + reg_line + "\n" \
            + tp("talk_turn", line=his)
        raw = None
        fn = talker()
        if fn is not None:
            try:
                raw = fn(vd["persona"] + PERSONA_RULES, list(history), prompt)
            except Exception:  # noqa: BLE001
                log.warning("the vendor's voice failed; the fixed line is used", exc_info=True)
        checked = check_line(raw)
        shown = checked or vd["fixed"]["greet"]
        conn = db.connect()
        try:
            receipt = tp("talk_receipt", prices=prices_line(goods_left(conn, v)), line=shown)
            conn.execute("BEGIN IMMEDIATE")
            again = conn.execute("SELECT receipt FROM vendor_talk_lines WHERE msg_key=?", (key,)).fetchone()
            if again:
                conn.rollback()
                return True, again["receipt"]
            history.append({"his": his, "shown": shown})
            conn.execute("INSERT INTO vendor_talks (visit_id, who, history_json, n, updated_at) VALUES (?,?,?,1,?)"
                         " ON CONFLICT(visit_id, who) DO UPDATE SET history_json=excluded.history_json, n=n+1,"
                         " updated_at=excluded.updated_at", (v["id"], who, json.dumps(history, ensure_ascii=False), now))
            conn.execute("INSERT INTO vendor_talk_lines (msg_key, visit_id, who, nth, his, shown, from_model, receipt, at)"
                         " VALUES (?,?,?,?,?,?,?,?,?)", (key, v["id"], who, n + 1, his, shown, 1 if checked else 0,
                                                         receipt, now))
            conn.commit()
        finally:
            conn.close()
        return True, receipt


# ═══════════ flowers ═══════════

def flower_state(bought_at: float, now: float) -> str:
    age = (now - bought_at) / DAY
    return "wilted" if age >= FLOWER_DAYS else ("droopy" if age >= FLOWER_DROOPY_AFTER_DAYS else "fresh")


def _put_on_sill(conn, who: str, order_id: str, variety: str, name: str, now: float) -> str | None:
    if conn.execute("SELECT 1 FROM vendor_flowers WHERE order_id=?", (order_id,)).fetchone():
        return None
    old = conn.execute("SELECT id, name FROM vendor_flowers WHERE who=? AND removed_at IS NULL", (who,)).fetchall()
    for r in old:
        conn.execute("UPDATE vendor_flowers SET removed_at=? WHERE id=?", (now, r["id"]))
    conn.execute("INSERT INTO vendor_flowers (id, who, order_id, variety, name, bought_at) VALUES (?,?,?,?,?,?)",
                 (uuid.uuid4().hex, who, order_id, variety, name, now))
    return old[0]["name"] if old else None


def _current_flower(conn, who: str, now: float):
    r = conn.execute("SELECT * FROM vendor_flowers WHERE who=? AND removed_at IS NULL ORDER BY bought_at DESC LIMIT 1",
                     (who,)).fetchone()
    if r is None:
        return None
    gone_at = r["bought_at"] + (FLOWER_DAYS + FLOWER_CLEAR_AFTER_WILT_DAYS) * DAY
    if now >= gone_at:
        conn.execute("UPDATE vendor_flowers SET removed_at=? WHERE id=? AND removed_at IS NULL", (gone_at, r["id"]))
        conn.commit()
        return None
    return r


def _sill(conn, who: str, now: float) -> dict | None:
    r = _current_flower(conn, who, now)
    if r is None:
        return None
    return {"id": r["id"], "variety": r["variety"], "name": r["name"], "bought_at": r["bought_at"],
            "state": flower_state(r["bought_at"], now), "wilt_at": r["bought_at"] + FLOWER_DAYS * DAY,
            "gifted": r["gifted_at"] is not None, "note": r["gift_note"] or ""}


def clean_note(text: str) -> str:
    s = " ".join((text or "").split())
    return re.sub(r"[\[\]【】<>{}]", "", s)[:FLOWER_NOTE_MAX].strip()


def gift(who: str, note: str, *, key: str, now: float | None = None) -> tuple[bool, str]:
    """[送花 …]: give the bunch on the sill (not given yet, not wilted) with one sentence."""
    from . import fridge
    now = now or clock.now()
    if not play.on("vendor"):
        return False, tp("feature_off")
    text = clean_note(note)
    if not text:
        return False, tp("gift_empty")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = fridge._once(conn, f"flower_gift:{key}")
        if done is not None:
            conn.rollback()
            return True, done
        r = _current_flower(conn, who, now)
        if r is None:
            conn.rollback()
            return False, tp("gift_none")
        if r["gifted_at"] is not None:
            conn.rollback()
            return False, tp("gift_done", name=r["name"])
        if flower_state(r["bought_at"], now) == "wilted":
            conn.rollback()
            return False, tp("gift_wilted", name=r["name"])
        conn.execute("UPDATE vendor_flowers SET gifted_at=?, gift_note=? WHERE id=? AND gifted_at IS NULL",
                     (now, text, r["id"]))
        out = tp("gift_ok", name=r["name"])
        fridge._mark_once(conn, f"flower_gift:{key}", out)
        conn.commit()
        return True, out
    finally:
        conn.close()


_FLOWER_NAME_RE = re.compile(r"^[一-鿿]{2,8}$")


def want(who: str, name: str, *, key: str, now: float | None = None) -> tuple[bool, str]:
    """[想要花 …]: ask for a new kind of flower; it waits for the human on the page."""
    now = now or clock.now()
    if not play.on("vendor"):
        return False, tp("feature_off")
    n = "".join((name or "").split())
    if not _FLOWER_NAME_RE.match(n):
        return False, tp("want_bad")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute("SELECT name FROM vendor_flower_requests WHERE msg_key=?", (key,)).fetchone()
        if r is not None:
            conn.rollback()
            return True, tp("want_ok", name=r["name"])
        if any(f["name"] == n for f in FLOWER_VARIETIES) or conn.execute(
                "SELECT 1 FROM vendor_flower_requests WHERE name=? AND state='ready'", (n,)).fetchone():
            conn.rollback()
            return True, tp("want_known", name=n)
        if conn.execute("SELECT 1 FROM vendor_flower_requests WHERE who=? AND name=? AND state IN ('pending','approved')",
                        (who, n)).fetchone():
            conn.rollback()
            return True, tp("want_dup", name=n)
        conn.execute("INSERT INTO vendor_flower_requests (id, who, name, msg_key, state, created_at)"
                     " VALUES (?,?,?,?,?,?)", (uuid.uuid4().hex[:16], who, n, key, "pending", now))
        conn.commit()
        return True, tp("want_ok", name=n)
    finally:
        conn.close()


def flower_requests(who: str | None = None) -> list[dict]:
    conn = db.connect()
    try:
        q, args = "SELECT * FROM vendor_flower_requests", ()
        if who:
            q, args = q + " WHERE who=?", (who,)
        return [dict(r) for r in conn.execute(q + " ORDER BY created_at DESC LIMIT 50", args)]
    finally:
        conn.close()


def decide(req_id: str, approve: bool, now: float | None = None) -> dict:
    """The human agrees or not (only while the request is waiting). The role hears it on its next turn.
    Agreeing marks it "approved"; it becomes a flower the florist brings once :func:`mark_ready` is
    called (after its picture is drawn, or straight away if you draw nothing)."""
    now = now or clock.now()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute("SELECT * FROM vendor_flower_requests WHERE id=?", (req_id,)).fetchone()
        if r is None:
            conn.rollback()
            raise KeyError(req_id)
        if r["state"] != "pending":
            conn.rollback()
            return dict(r)
        conn.execute("UPDATE vendor_flower_requests SET state=?, decided_at=? WHERE id=? AND state='pending'",
                     ("approved" if approve else "declined", now, req_id))
        conn.commit()
        out = dict(conn.execute("SELECT * FROM vendor_flower_requests WHERE id=?", (req_id,)).fetchone())
    finally:
        conn.close()
    text = tp("want_yes" if approve else "want_no", name=out["name"])
    notify.emit(out["who"], "flower.request", t("head") + text, body=text, key=f"flower_req:{req_id}", now=now)
    return out


def mark_ready(name: str) -> int:
    conn = db.connect()
    try:
        n = conn.execute("UPDATE vendor_flower_requests SET state='ready' WHERE name=? AND state='approved'",
                         (name,)).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


# ═══════════ the page ═══════════

def overview(who: str, now: float | None = None) -> dict:
    now = now or clock.now()
    out: dict = {"on": play.on("vendor"), "now": now, "visit": None, "mine": [],
                 "today": {}, "wallet": {"local": wallet_is_local(), "balance": _balance(wallet(), who)}}
    conn = db.connect()
    try:
        out["today"] = {"spent": spent_today(conn, who, kitchen_day(now)), "cap": _cfg().vendor_day_max,
                        "order_cap": _cfg().vendor_order_max}
        v = live_visit(conn, now)
        if v is not None:
            vd = VENDORS[v["vendor"]]
            out["visit"] = {"id": v["id"], "vendor": v["vendor"], "name": vd["name"], "who": vd["who"],
                            "arrive_at": v["arrive_at"], "leave_at": v["leave_at"], "left_s": max(0.0, v["leave_at"] - now),
                            "goods": [{k: g[k] for k in ("id", "name", "kind", "unit", "price", "left")}
                                      for g in goods_left(conn, v)]}
            out["mine"] = [{k: r[k] for k in ("id", "item_name", "qty", "total", "payer", "state", "created_at", "updated_at")}
                           for r in conn.execute("SELECT * FROM vendor_orders WHERE visit_id=? AND who=?"
                                                 " ORDER BY created_at", (v["id"], who))]
        out["flower"] = _sill(conn, who, now)
    finally:
        conn.close()
    out["flower_requests"] = flower_requests(who)
    return out


def ledger(who: str, limit: int = 50) -> list[dict]:
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute("SELECT id, item_name, qty, total, payer, state, reason, created_at"
                                              " FROM vendor_orders WHERE who=? ORDER BY created_at DESC LIMIT ?",
                                              (who, limit))]
    finally:
        conn.close()
