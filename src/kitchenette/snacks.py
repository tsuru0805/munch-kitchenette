"""The snack shelf: a fixed set of snacks with a daily cap each.

- A snack restores a little stamina and a little satiety. A snack with
  variants (coffee by flavour) is eaten by variant; the variants share one cap.
- There are two ways to eat: the human feeds one from the page, or the role
  takes one itself. Both go through :func:`eat` and share the same count for
  the day; past the cap it is refused, and the receipt says how many were
  eaten and when the count resets.
- The snack day rolls over at ``snacks.day_boundary_hour`` local time.
- A worm from a spoiled dish or fruit may be waiting in a snack: that serving
  still counts, but restores no stamina.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from datetime import timedelta

from . import clock, config, db, roles
from .texts import TIER_LABEL, t

log = logging.getLogger(__name__)

BY_HER = "her"
BY_SELF = "self"


def _cfg():
    return config.get()


def _now() -> float:
    return clock.now()


def _hm(ts: float) -> str:
    return clock.hm(ts)


def _conn() -> sqlite3.Connection:
    conn = db.connect()
    conn.isolation_level = None      # explicit transactions: the cap check and the insert are one unit
    return conn


def catalog() -> list[dict]:
    return _cfg().snacks_catalog


def by_id(snack_id: str) -> dict | None:
    return next((s for s in catalog() if s["id"] == snack_id), None)


def known(snack_id: str) -> bool:
    return by_id(snack_id) is not None


# ── pure helpers ────────────────────────────────────────────────────────

def wake_day(epoch: float) -> str:
    """The snack day YYYY-MM-DD: before the boundary hour still counts as the previous day."""
    return (clock.local(epoch) - timedelta(hours=_cfg().snacks_day_boundary_hour)).strftime("%Y-%m-%d")


def next_reset(epoch: float) -> float:
    """When the daily counts next reset."""
    d = clock.local(epoch)
    cut = d.replace(hour=_cfg().snacks_day_boundary_hour, minute=0, second=0, microsecond=0)
    if d >= cut:
        cut += timedelta(days=1)
    return cut.timestamp()


def resolve(snack: str, variant: str | None) -> tuple[dict | None, str]:
    """(snack id, variant id) -> ({snack, variant, name, tier, gain}, error code).
    A snack with variants needs one; a snack without must not be given one."""
    s = by_id((snack or "").strip())
    if s is None:
        return None, "unknown_snack"
    v_id = (variant or "").strip()
    variants = s.get("variants")
    if variants:
        if not v_id:
            return None, "variant_required"
        v = next((x for x in variants if x["id"] == v_id), None)
        if v is None:
            return None, "unknown_variant"
        return {"snack": s["id"], "variant": v["id"], "name": f"{v['name']}{s['name']}",
                "tier": s["tier"], "gain": float(v["gain"])}, ""
    if v_id:
        return None, "variant_not_applicable"
    return {"snack": s["id"], "variant": "", "name": s["name"],
            "tier": s["tier"], "gain": float(s["gain"])}, ""


def _variants_text(s: dict) -> str:
    return "/".join(f"{v['id']}={v['name']}" for v in s.get("variants") or ())


def err_text(err: str, snack: str = "") -> str:
    s = by_id(snack)
    name = s["name"] if s else t("snack_this")
    if err == "unknown_snack":
        return t("snack_unknown", options="、".join(f"{x['id']}={x['name']}" for x in catalog()))
    if err == "variant_required":
        return t("snack_variant_required", name=name, variants=_variants_text(s) if s else "")
    if err == "unknown_variant":
        return t("snack_variant_unknown", name=s["name"] if s else "", variants=_variants_text(s) if s else "")
    if err == "variant_not_applicable":
        return t("snack_variant_not_applicable", name=name)
    if err == "viewer":
        return t("role_bad", got="")
    return err


# ── storage ─────────────────────────────────────────────────────────────

def caps_for_viewer(who: str) -> dict[str, int]:
    conn = _conn()
    try:
        return caps_for(conn, who)
    finally:
        conn.close()


def caps_for(conn: sqlite3.Connection, who: str) -> dict[str, int]:
    out = {s["id"]: int(s["default_cap"]) for s in catalog()}
    for r in conn.execute("SELECT snack, cap FROM snack_caps WHERE who=?", (who,)):
        if r["snack"] in out:
            out[r["snack"]] = int(r["cap"])
    return out


def _counts(conn: sqlite3.Connection, who: str, day: str) -> dict[str, int]:
    out = {s["id"]: 0 for s in catalog()}
    for r in conn.execute(
            "SELECT snack, COUNT(*) AS n FROM snack_log WHERE who=? AND day=? GROUP BY snack", (who, day)):
        if r["snack"] in out:
            out[r["snack"]] = int(r["n"])
    return out


def state(who: str, now: float | None = None, recent_n: int = 8) -> dict:
    """The shelf, today's counts and caps."""
    if not roles.valid(who):
        raise ValueError("viewer")
    now = now or _now()
    day = wake_day(now)
    conn = _conn()
    try:
        caps = caps_for(conn, who)
        counts = _counts(conn, who, day)
        recent = [dict(r) for r in conn.execute(
            "SELECT id, snack, variant, by, gain, energy_delta, ts FROM snack_log"
            " WHERE who=? AND day=? ORDER BY ts DESC LIMIT ?", (who, day, recent_n))]
    finally:
        conn.close()
    shelf = []
    for s in catalog():
        entry = {"id": s["id"], "name": s["name"], "tier": s["tier"],
                 "tier_label": TIER_LABEL[s["tier"]], "default_cap": int(s["default_cap"]),
                 "cap": caps[s["id"]], "eaten": counts[s["id"]]}
        if s.get("variants"):
            entry["variants"] = [{"id": v["id"], "name": v["name"], "gain": v["gain"]} for v in s["variants"]]
            entry["gain"] = None
        else:
            entry["variants"] = []
            entry["gain"] = s["gain"]
        shelf.append(entry)
    for r in recent:
        res, _ = resolve(r["snack"], r["variant"] or None)
        r["name"] = res["name"] if res else r["snack"]
    return {"who": who, "day": day, "resets_at": next_reset(now),
            "energy_enabled": bool(_cfg().stamina_enabled),
            "cap_min": _cfg().snacks_cap_min, "cap_max": _cfg().snacks_cap_max,
            "snacks": shelf, "recent": recent}


def set_caps(who: str, caps: dict, now: float | None = None) -> dict[str, int]:
    """Change daily caps. Everything is validated before anything is written;
    one bad entry rejects the whole request (ValueError with the sentence to show)."""
    if not roles.valid(who):
        raise ValueError(err_text("viewer"))
    if not isinstance(caps, dict) or not caps:
        raise ValueError(t("snack_caps_empty"))
    lo, hi = _cfg().snacks_cap_min, _cfg().snacks_cap_max
    clean: dict[str, int] = {}
    for k, v in caps.items():
        s = by_id(k)
        if s is None:
            raise ValueError(t("snack_caps_unknown", id=k))
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(t("snack_caps_int", name=s["name"]))
        if not (lo <= v <= hi):
            raise ValueError(t("snack_caps_range", name=s["name"], min=lo, max=hi))
        clean[k] = v
    now = now or _now()
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for k, v in clean.items():
            conn.execute(
                "INSERT INTO snack_caps(who,snack,cap,updated_at) VALUES(?,?,?,?)"
                " ON CONFLICT(who,snack) DO UPDATE SET cap=excluded.cap,"
                " updated_at=excluded.updated_at", (who, k, v, now))
        conn.execute("COMMIT")
        return caps_for(conn, who)
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def eat(who: str, snack: str, variant: str | None, by: str,
        now: float | None = None, rid: str | None = None, told: bool = False) -> dict:
    """Eat one serving: check the cap, record it, then add stamina.

    Returns a dict: ok / reason (None | cap | unknown_snack | variant_required | unknown_variant |
    variant_not_applicable | viewer) / snack / variant / name / tier / gain / energy_delta /
    energy (stamina after, or None) / eaten / cap / day / resets_at / id / worm.

    The cap check and the insert share one transaction, so the two ways of eating cannot overshoot
    together. Stamina is added after the commit and written back to the row only if it landed.
    rid, when given, is a stable id for this serving: a second call with the same id returns the
    recorded serving (ok=True, duplicate=True) without counting or adding stamina again.
    told=True: the caller shows the receipt to the role right away (see kitchen.take_worm).
    """
    from . import fridge, kitchen, stamina
    now = now or _now()
    base = {"ok": False, "reason": None, "snack": snack, "variant": variant or "",
            "name": "", "tier": "", "gain": 0.0, "energy_delta": 0.0, "energy": None,
            "eaten": 0, "cap": 0, "day": wake_day(now), "resets_at": next_reset(now), "id": None}
    if not roles.valid(who):
        return {**base, "reason": "viewer"}
    if by not in (BY_HER, BY_SELF):
        raise ValueError(f"unknown by: {by!r}")
    res, err = resolve(snack, variant)
    if res is None:
        return {**base, "reason": err}
    base.update(res)
    day = base["day"]
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if rid:
            old = conn.execute("SELECT energy_delta FROM snack_log WHERE id=?", (rid,)).fetchone()
            if old is not None:
                n_old = conn.execute(
                    "SELECT COUNT(*) FROM snack_log WHERE who=? AND day=? AND snack=?",
                    (who, day, res["snack"])).fetchone()[0]
                conn.execute("ROLLBACK")
                conn.close()
                return {**base, "ok": True, "duplicate": True, "id": rid, "worm": kitchen.worm_of(rid),
                        "eaten": int(n_old), "cap": caps_for_viewer(who)[res["snack"]],
                        "energy_delta": float(old[0])}
        cap = caps_for(conn, who)[res["snack"]]
        n = conn.execute("SELECT COUNT(*) FROM snack_log WHERE who=? AND day=? AND snack=?",
                         (who, day, res["snack"])).fetchone()[0]
        base["cap"] = cap
        if n >= cap:
            conn.execute("ROLLBACK")
            conn.close()
            return {**base, "reason": "cap", "eaten": int(n)}
        rid = rid or uuid.uuid4().hex[:16]
        conn.execute(
            "INSERT INTO snack_log(id,who,snack,variant,day,by,gain,energy_delta,ts)"
            " VALUES(?,?,?,?,?,?,?,0,?)",
            (rid, who, res["snack"], res["variant"], day, by, res["gain"], now))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        raise
    base.update(ok=True, id=rid, eaten=int(n) + 1)
    fridge.on_snack(who, res.get("tier") or "", rid, now=now)
    # A worm in this snack: the serving counts, but it restores no stamina.
    worm = None
    try:
        worm = kitchen.take_worm(who, rid, res["snack"], now=now, told=told)
    except Exception:  # noqa: BLE001
        log.warning("could not check the snack for a worm; treating it as a plain snack", exc_info=True)
    if worm:
        base["worm"] = worm
        conn.close()
        return base
    try:
        gain = min(res["gain"], _cfg().stamina_recharge_cap)
        v = stamina.pulse(who, gain, now=now, rule=f"snack:{res['snack']}")
        if v is not None:
            base["energy_delta"] = gain
            base["energy"] = round(float(v), 4)
            conn.execute("UPDATE snack_log SET energy_delta=? WHERE id=?", (gain, rid))
    except Exception:  # noqa: BLE001
        log.warning("stamina for a snack failed (the serving is recorded, stamina unchanged)", exc_info=True)
        base["energy_delta"] = 0.0
        base["energy"] = None
    finally:
        conn.close()
    return base


# ── eating by name (the role's side) ────────────────────────────────────
# A name is accepted loosely: catalog name, flavour name, flavour + snack name, a listed alias, or
# an id. A bare name of a snack that has flavours is ambiguous: the receipt lists the flavours.

_alias_cache: tuple[int, dict] | None = None


def _aliases() -> dict[str, tuple[str, str]]:
    global _alias_cache
    v = config.version()
    if _alias_cache is None or _alias_cache[0] != v:
        out: dict[str, tuple[str, str]] = {}
        for s in catalog():
            if s.get("variants"):
                for var in s["variants"]:
                    for k in (var["name"], f"{var['name']}{s['name']}", var["id"]):
                        out[k.lower()] = (s["id"], var["id"])
            else:
                out[s["name"].lower()] = (s["id"], "")
                out[s["id"]] = (s["id"], "")
                for a in s.get("aliases", ()):
                    out[a.lower()] = (s["id"], "")
        _alias_cache = (v, out)
    return _alias_cache[1]


_QTY_RE = re.compile(r"^(?:来|吃|喝)?(?:一|1|两|2)?(?:杯|份|块|个|颗|盒|片|口)")


def normalize_name(text: str) -> str:
    """Drop all whitespace, lowercase, and strip a leading measure word ("一杯拿铁" -> "拿铁")."""
    s = re.sub(r"\s+", "", text or "").lower()
    return _QTY_RE.sub("", s, count=1) or s


def resolve_name(text: str) -> tuple[tuple[str, str] | None, str]:
    """A snack name as the role wrote it -> ((snack id, variant id), "") or (None, the reason)."""
    name = normalize_name(text)
    hit = _aliases().get(name)
    if hit:
        return hit, ""
    for s in catalog():
        if s.get("variants") and name in (s["name"].lower(), s["id"]):
            return None, t("snack_flavour_required", name=s["name"],
                           variants="/".join(v["name"] for v in s["variants"]))
    names = "/".join([v["name"] for s in catalog() for v in s.get("variants") or ()]
                     + [s["name"] for s in catalog() if not s.get("variants")])
    return None, t("snack_not_on_shelf", name=(text or "").strip()[:10], names=names)


def receipt_text(r: dict, who: str) -> str:
    """The result of eat() as a receipt for the role: exact numbers, no commentary."""
    reset = t("snack_reset", tz=_cfg().server_timezone_label, hm=_hm(r["resets_at"]))
    if not r["ok"]:
        if r["reason"] == "cap":
            snack_name = by_id(r["snack"])["name"]
            if r["cap"] == 0:
                return t("snack_cap_zero", name=snack_name, reset=reset)
            return t("snack_cap_hit", name=snack_name, eaten=r["eaten"], cap=r["cap"], reset=reset)
        return t("snack_failed", why=err_text(r["reason"] or "", r.get("snack") or ""))
    snack_name = by_id(r["snack"])["name"]
    if r.get("worm"):
        return t("snack_worm", name=r["name"], worm=r["worm"], snack=snack_name,
                 eaten=r["eaten"], cap=r["cap"], reset=reset)
    head = t("snack_head", name=r["name"], tier=TIER_LABEL[r["tier"]])
    if r["energy"] is not None:
        head += t("snack_energy", delta=f"{r['energy_delta']:.2f}", energy=f"{r['energy']:.2f}")
    elif _cfg().stamina_enabled:
        head += t("snack_no_energy")      # stamina is on but the write did not land
    return head + t("snack_tail", snack=snack_name, eaten=r["eaten"], cap=r["cap"], reset=reset)


def fed_payload(r: dict) -> dict:
    """The facts of a serving fed by the human, for the note sent to the role."""
    return {"name": r["name"], "tier": TIER_LABEL[r["tier"]],
            "delta": (f"{r['energy_delta']:.2f}" if r["energy_delta"] > 0 else ""),
            "worm": r.get("worm") or ""}


def fed_text(r: dict) -> str:
    """The sentence telling the role about one serving the human fed it."""
    from . import notify
    return notify.render_snack_fed([fed_payload(r)])
