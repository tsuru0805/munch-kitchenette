"""Three jars on the window sill.

- [封罐 <ingredient> <sugar|honey|salt> | <a slip>]: in one transaction, find an empty jar (two at once
  cannot both win), take one portion of that ingredient from the fridge (picked the way cooking picks)
  and seal it. Sugar, honey and salt are always at hand. Fruit with sugar or honey waits three days
  (sour fruit like lemon two); vegetables with salt one day; nothing else goes together.
- What went in stays as it was: the jar remembers how fresh it was when sealed. Something already
  spoiled makes a spoiled jar: on the day it is opened, thrown away, the jar emptied.
- Jars open themselves when due (settled on read, at the due moment): the result goes on the snack
  shelf and the role hears it on its next turn.
- The result is named after what went in (桃子 + sugar = 桃子酒, 柠檬 + honey = 柠檬蜜, 白萝卜 + salt =
  腌白萝卜), with "(罐)" added if that name is already a snack.
- Taking one goes through the existing [零食 <name>]: the fixed snacks first, then the jars. All jar
  servings share one daily cap (``[jars] daily_cap``, per role; the human feeding one counts too) that
  resets with the snack day. Each serving gives what the lowest snack gives. Jar treats never get worms.
"""
from __future__ import annotations

import hashlib
import re
from datetime import timedelta

from . import clock, config, db, notify, play
from .texts import t
from .texts_play import (JAR_COUNT, JAR_DAYS_FRUIT, JAR_DAYS_SOUR_FRUIT, JAR_DAYS_VEG, JAR_PORTIONS_MAX,
                         JAR_PORTIONS_MIN, JAR_SALT_WORDS, JAR_SUFFIX, JAR_SWEET_WORDS, SOUR_FRUITS, TAG_NAME_MAX,
                         TAG_NOTE_MAX, tp)

DAY = 86400.0
BY_SELF, BY_HUMAN = "self", "her"
KIND_OPENED = "jar.opened"


class JarError(Exception):
    def __init__(self, text: str, code: str = "jar_error"):
        super().__init__(text)
        self.text = text
        self.code = code


def _h(seed: str) -> float:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _ensure(conn, who: str) -> None:
    for i in range(1, JAR_COUNT + 1):
        conn.execute("INSERT OR IGNORE INTO jars (who, slot, state) VALUES (?,?, 'empty')", (who, i))


def lowest_snack() -> tuple[float, float]:
    """(stamina, satiety) of the lowest snack on the shelf."""
    from . import snacks
    gains = []
    for s in snacks.catalog():
        if "gain" in s:
            gains.append(float(s["gain"]))
        for v in s.get("variants") or ():
            gains.append(float(v["gain"]))
    sat = config.get().satiety_snack_gain
    return (min(gains) if gains else 0.0), (min(sat.values()) if sat else 0.0)


def parse(line: str) -> tuple[str, str, str]:
    body, _, note = (line or "").partition("|")
    toks = body.split()
    if len(toks) != 2:
        raise JarError(tp("jar_bad_format"), "bad_format")
    note = note.strip()
    if len(note) > TAG_NOTE_MAX or len(toks[0]) > TAG_NAME_MAX:
        raise JarError(tp("tag_too_long"), "too_long")
    return toks[0], toks[1], re.sub(r"[\[\]【】\r\n]", "", note)


def _how(word: str) -> str | None:
    if word in ("蜂蜜", "蜜"):
        return "honey"
    if word in JAR_SWEET_WORDS:
        return "sugar"
    if word in JAR_SALT_WORDS:
        return "salt"
    return None


def goods_name(item_name: str, how: str) -> str:
    from . import snacks
    base = {"sugar": f"{item_name}酒", "honey": f"{item_name}蜜", "salt": f"腌{item_name}"}[how]
    if snacks.resolve_name(base)[0] is not None or base in {s["name"] for s in snacks.catalog()}:
        return base + JAR_SUFFIX
    return base


def _fmt_left(sec: float) -> str:
    sec = max(0, int(sec))
    d, rem = divmod(sec, 86400)
    h = rem // 3600
    if d:
        return tp("jar_days_hours", d=d, h=h) if h else tp("jar_days", d=d)
    return tp("jar_hours", h=h) if h else tp("jar_under_hour")


def _ready_when(due: float, now: float) -> str:
    dd = clock.local(due)
    days = (dd.date() - clock.local(now).date()).days
    part = tp("jar_morning") if dd.hour < 11 else tp("jar_noon") if dd.hour < 14 else (
        tp("jar_afternoon") if dd.hour < 18 else tp("jar_evening"))
    word = {0: tp("jar_today"), 1: tp("jar_tomorrow"), 2: tp("jar_after")}.get(days) or tp("jar_date", m=dd.month, d=dd.day)
    return f"{word}{part}"


def seal(who: str, line: str, *, key: str, now: float | None = None) -> str:
    from . import fridge
    now = now or clock.now()
    if not play.on("seal_jars"):
        return tp("feature_off")
    name, word, note = parse(line)
    how = _how(word)
    iid = fridge.resolve(name, gone=True)
    if iid is None:
        raise JarError(tp("jar_unknown", name=name), "unknown_item")
    it = fridge.item(iid) or {}
    cat = it.get("category")
    fruit = cat == "fruit"
    veg = cat in ("veg", "leafy", "root")
    if how is None or (fruit and how == "salt") or (veg and how != "salt") or not (fruit or veg):
        raise JarError(tp("jar_bad_combo", name=it.get("name", name), how=word), "bad_combo")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        done = fridge._once(conn, f"jar_seal:{key}")
        if done is not None:
            conn.rollback()
            return done
        settle_in_tx(conn, who, now)
        _ensure(conn, who)
        empty = conn.execute("SELECT slot FROM jars WHERE who=? AND state='empty' ORDER BY slot LIMIT 1",
                             (who,)).fetchone()
        if empty is None:
            soonest = conn.execute("SELECT MIN(due_at) FROM jars WHERE who=? AND state='sealed'", (who,)).fetchone()[0]
            conn.rollback()
            raise JarError(tp("jar_full", when=_ready_when(soonest, now) if soonest else tp("jar_full_later")), "full")
        try:
            used = fridge.take_in_tx(conn, who, [(it["name"], 1)], now)
        except fridge.FridgeError:
            conn.rollback()
            raise JarError(tp("jar_no_item", name=it["name"]), "no_item") from None
        u = used[0]
        days = (JAR_DAYS_SOUR_FRUIT if any(w in it["name"] for w in SOUR_FRUITS) else JAR_DAYS_FRUIT) if fruit \
            else JAR_DAYS_VEG
        due = now + days * DAY
        conn.execute("UPDATE jars SET state='sealed', item_id=?, item_name=?, freshness=?, how=?, how_word=?, note=?,"
                     " sealed_at=?, due_at=?, seal_key=? WHERE who=? AND slot=? AND state='empty'",
                     (iid, it["name"], u["freshness"], how, word, note, now, due, key, who, empty["slot"]))
        receipt = tp("jar_sealed", what=f"{it['name']}、{word}", ready=_ready_when(due, now),
                     note=tp("jar_sealed_note", note=note) if note else "")
        fridge._log(conn, who, "jar_sealed", tp("jar_log", name=it["name"]), now)
        fridge._mark_once(conn, f"jar_seal:{key}", receipt)
        conn.commit()
        return receipt
    finally:
        conn.close()


def settle_in_tx(conn, who: str, now: float) -> list[str]:
    """Open every jar that is due (at its due moment). Returns the ids of what came out."""
    out = []
    for j in conn.execute("SELECT * FROM jars WHERE who=? AND state='sealed' AND due_at<=? ORDER BY due_at",
                          (who, now)).fetchall():
        ok = j["freshness"] != "bad"
        gid = "g-" + hashlib.sha1(f"{who}:{j['slot']}:{j['sealed_at']}".encode()).hexdigest()[:10]
        n = JAR_PORTIONS_MIN + int(_h(gid) * (JAR_PORTIONS_MAX - JAR_PORTIONS_MIN + 1)) if ok else 0
        conn.execute("INSERT OR IGNORE INTO jar_goods (id, who, name, item_name, ok, total, left_n, note, opened_at)"
                     " VALUES (?,?,?,?,?,?,?,?,?)",
                     (gid, who, goods_name(j["item_name"], j["how"]) if ok else j["item_name"], j["item_name"],
                      1 if ok else 0, n, n, j["note"] or "", j["due_at"]))
        conn.execute("UPDATE jars SET state='empty', item_id=NULL, item_name=NULL, freshness=NULL, how=NULL,"
                     " how_word=NULL, note='', sealed_at=NULL, due_at=NULL, seal_key=NULL"
                     " WHERE who=? AND slot=? AND sealed_at=?", (who, j["slot"], j["sealed_at"]))
        out.append(gid)
    if out and play.on("achievements"):
        from . import dex
        dex.evaluate_in_tx(conn, who, now)
    return out


def status_text(conn, who: str, now: float) -> str:
    _ensure(conn, who)
    lines = [tp("jars_head")]
    for j in conn.execute("SELECT * FROM jars WHERE who=? ORDER BY slot", (who,)).fetchall():
        if j["state"] != "sealed":
            lines.append(tp("jar_line_empty"))
            continue
        lines.append(tp("jar_line", what=f"{j['item_name']}、{j['how_word']}", left=_fmt_left(j["due_at"] - now),
                        note=tp("jar_note", note=j["note"]) if j["note"] else ""))
    return "\n".join(lines)


def tick(who: str, now: float) -> int:
    """Periodic scan: open what is due and leave a note for each jar opened."""
    if not play.on("seal_jars"):
        return 0
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settle_in_tx(conn, who, now)
        todo = [(g["id"], tp("jar_opened", goods=g["name"], n=g["total"]) if g["ok"]
                 else tp("jar_failed", name=g["item_name"]))
                for g in conn.execute("SELECT * FROM jar_goods WHERE who=? AND told=0 ORDER BY opened_at",
                                      (who,)).fetchall()]
        conn.commit()
    finally:
        conn.close()
    for gid, text in todo:
        notify.emit(who, KIND_OPENED, t("head") + text, body=text, key=f"jar:{gid}", now=now)
        conn = db.connect()
        try:
            conn.execute("UPDATE jar_goods SET told=1 WHERE id=?", (gid,))
            conn.commit()
        finally:
            conn.close()
    return len(todo)


def cap_for(conn, who: str) -> int:
    r = conn.execute("SELECT cap FROM jar_caps WHERE who=?", (who,)).fetchone()
    return int(r["cap"]) if r else int(config.get().jars_daily_cap)


def set_cap(who: str, cap: int) -> int:
    cap = max(0, min(20, int(cap)))
    conn = db.connect()
    try:
        conn.execute("INSERT INTO jar_caps (who, cap) VALUES (?,?) ON CONFLICT(who) DO UPDATE SET cap=excluded.cap",
                     (who, cap))
        conn.commit()
    finally:
        conn.close()
    return cap


def _snack_day(ts: float) -> str:
    return (clock.local(ts) - timedelta(hours=config.get().snacks_day_boundary_hour)).strftime("%Y-%m-%d")


def has_goods(who: str, name: str, now: float | None = None) -> bool:
    if not play.on("seal_jars"):
        return False
    now = now or clock.now()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settle_in_tx(conn, who, now)
        hit = conn.execute("SELECT 1 FROM jar_goods WHERE who=? AND name=? AND ok=1 AND left_n>0 LIMIT 1",
                           (who, (name or "").strip())).fetchone()
        conn.commit()
        return hit is not None
    finally:
        conn.close()


def take(who: str, name: str, *, key: str, by: str = BY_SELF, now: float | None = None) -> dict:
    """One serving (the role's [零食 name], or the human feeding). The earliest jar of that name first,
    with its slip. Same key again = the same result. Returns {ok, text, code?, duplicate?}."""
    from . import fridge, stamina
    now = now or clock.now()
    name = (name or "").strip()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old = conn.execute("SELECT receipt FROM jar_takes WHERE take_key=?", (key,)).fetchone()
        if old is not None:
            conn.rollback()
            return {"ok": True, "text": old["receipt"], "duplicate": True}
        settle_in_tx(conn, who, now)
        g = conn.execute("SELECT * FROM jar_goods WHERE who=? AND name=? AND ok=1 AND left_n>0"
                         " ORDER BY opened_at LIMIT 1", (who, name)).fetchone()
        if g is None:
            conn.rollback()
            return {"ok": False, "text": tp("jar_none", name=name), "code": "none"}
        day = _snack_day(now)
        n = conn.execute("SELECT COUNT(*) FROM jar_takes WHERE who=? AND day=?", (who, day)).fetchone()[0]
        if n >= cap_for(conn, who):
            conn.rollback()
            return {"ok": False, "text": tp("jar_cap", n=n), "code": "cap"}
        conn.execute("UPDATE jar_goods SET left_n=left_n-1 WHERE id=? AND left_n>0", (g["id"],))
        if by == BY_HUMAN:
            text = tp("jar_fed", goods=g["name"]) + (tp("jar_fed_note", note=g["note"]) if g["note"] else "")
        else:
            verb = "喝" if g["name"].endswith("酒") else "吃"
            text = (tp("jar_take", verb=verb, goods=g["name"], note=g["note"]) if g["note"]
                    else tp("jar_take_no_note", verb=verb, goods=g["name"]))
        conn.execute("INSERT INTO jar_takes (take_key, who, goods_id, day, by_who, receipt, at) VALUES (?,?,?,?,?,?,?)",
                     (key, who, g["id"], day, by, text, now))
        energy, satiety = lowest_snack()
        fridge.settle_meal_in_tx(conn, who, satiety, key=f"jar:{key}", now=now)
        stamina.pulse_in_tx(conn, who, energy, now, rule="jar")
        conn.commit()
        return {"ok": True, "text": text}
    finally:
        conn.close()


def jars_view(conn, who: str) -> list[dict]:
    _ensure(conn, who)
    return [dict(r) for r in conn.execute("SELECT * FROM jars WHERE who=? ORDER BY slot", (who,)).fetchall()]


def goods_view(conn, who: str) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM jar_goods WHERE who=? ORDER BY opened_at DESC LIMIT 30",
                                          (who,)).fetchall()]
