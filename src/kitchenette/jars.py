"""Three jars on the window sill.

- [封罐 <ingredient> <seasoning>、<seasoning>… = <a name> | <a slip>]: anything in the fridge can go in, with
  any seasonings (they are always at hand: nothing is looked up or taken for them); the name and the slip
  are both optional, and the older [封罐 桃子 冰糖 | 纸条] still reads. In one transaction: find an empty
  jar (two at once cannot both win), take one portion of that ingredient from the fridge (picked the way
  cooking picks) and seal it. How long it waits goes by the ingredient: fruit three days (sour fruit like
  lemon two), vegetables one, eggs one, anything else two.
- Nothing is refused for going badly together. A combination known to go wrong (``JAR_ODD_COMBOS``: milk
  with salt or vinegar, raw meat in sugar only, noodles or rice) is sealed all the same, and on the day
  it opens mostly comes out tasting wrong: thrown away, the jar emptied.
- What went in stays as it was: the jar remembers how fresh it was when sealed. Something already
  spoiled makes a spoiled jar: on the day it is opened, thrown away, the jar emptied.
- Jars open themselves when due (settled on read, at the due moment): the result goes on the snack
  shelf and the role hears it on its next turn.
- The result's name is fixed when the jar is sealed: the role's own if it gave one, else from what went
  in, by the first seasoning (fruit + sugar = 桃子酒, fruit + honey = 柠檬蜜, vegetable + salt = 腌白萝卜;
  anything else 糖渍X / 蜜渍X / 盐渍X, or the seasoning put before it: 酱油鸡蛋), with "(罐)" added if
  that name is already a snack. A jar sealed before names were stored is named by the old rule when it opens.
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
from .texts_play import (JAR_COUNT, JAR_DAYS_EGG, JAR_DAYS_FRUIT, JAR_DAYS_OTHER, JAR_DAYS_SOUR_FRUIT,
                         JAR_DAYS_VEG, JAR_HONEY_KEYS, JAR_ODD_COMBOS, JAR_ODD_FAIL_P, JAR_PORTIONS_MAX,
                         JAR_PORTIONS_MIN, JAR_SALT_KEYS, JAR_SALTY_KEYS, JAR_SEASONINGS_MAX, JAR_SOUR_KEYS,
                         JAR_SUFFIX, JAR_SWEET_KEYS, SOUR_FRUITS, TAG_NAME_MAX, TAG_NOTE_MAX, tp)

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


_SEP = re.compile(r"[\s、,，+＋/／;；]+")
_DIRTY = re.compile(r"[\[\]【】\r\n]")
_VEG = ("veg", "leafy", "root")
_OLD_NAMES = {"sugar": "{x}酒", "honey": "{x}蜜", "salt": "腌{x}"}     # the only three before 0.2.2


def parse(line: str) -> tuple[str, list[str], str, str]:
    """-> (ingredient, seasonings, the name the role gave or "", slip). Seasonings may be split by spaces,
    、 or commas; full-width ＝ and ｜ read as = and |."""
    text = (line or "").replace("｜", "|").replace("＝", "=")
    body, _, note = text.partition("|")
    body, _, named = body.partition("=")
    toks = [w for w in _SEP.split(_DIRTY.sub("", body)) if w]
    if len(toks) < 2:
        raise JarError(tp("jar_bad_format"), "bad_format")
    item, seas = toks[0], list(dict.fromkeys(toks[1:]))
    named = re.sub(r"\s+", "", _DIRTY.sub("", named))
    note = note.strip()
    if (len(note) > TAG_NOTE_MAX or len(item) > TAG_NAME_MAX or len(named) > TAG_NAME_MAX
            or len(seas) > JAR_SEASONINGS_MAX or any(len(w) > TAG_NAME_MAX for w in seas)):
        raise JarError(tp("tag_too_long"), "too_long")
    return item, seas, named, _DIRTY.sub("", note)


def _has(word: str, keys: tuple[str, ...]) -> bool:
    return any(k in word for k in keys)


def _how(word: str) -> str:
    """What kind of seasoning (the first one decides the name and the jar's look): honey | sugar | salt | other."""
    if _has(word, JAR_HONEY_KEYS):
        return "honey"
    if _has(word, JAR_SWEET_KEYS):
        return "sugar"
    if _has(word, JAR_SALT_KEYS):
        return "salt"
    return "other"


def jar_days(it: dict, iid: str | None) -> int:
    cat, name = it.get("category"), it.get("name") or ""
    if cat == "fruit":
        return JAR_DAYS_SOUR_FRUIT if any(w in name for w in SOUR_FRUITS) else JAR_DAYS_FRUIT
    if cat in _VEG:
        return JAR_DAYS_VEG
    if iid == "egg" or "蛋" in name:
        return JAR_DAYS_EGG
    return JAR_DAYS_OTHER


def is_odd(it: dict, seas: list[str]) -> bool:
    """A combination known to go wrong (JAR_ODD_COMBOS): sealed all the same, mostly spoiled when opened."""
    cat, name = it.get("category"), it.get("name") or ""
    salty_sour = any(_has(w, JAR_SALTY_KEYS) or _has(w, JAR_SOUR_KEYS) for w in seas)
    only_sweet = all(_has(w, JAR_SWEET_KEYS) for w in seas)
    for rule in JAR_ODD_COMBOS:
        if name not in rule["names"] and cat not in rule["cats"]:
            continue
        when = rule["when"]
        if when == "any" or (when == "salty_or_sour" and salty_sour) or (when == "only_sweet" and only_sweet):
            return True
    return False


def auto_name(item_name: str, category: str | None, seas: list[str]) -> str:
    """The result's name when the role gave none (before the "(罐)" a clash adds)."""
    first = seas[0] if seas else ""
    how = _how(first)
    if category == "fruit" and how in ("sugar", "honey"):
        return _OLD_NAMES[how].format(x=item_name)
    if category in _VEG and how == "salt":
        return _OLD_NAMES["salt"].format(x=item_name)
    return {"honey": "蜜渍", "sugar": "糖渍", "salt": "盐渍"}.get(how, first) + item_name


def goods_name(base: str) -> str:
    """The name on the shelf: "(罐)" added if a snack is already called that."""
    from . import snacks
    if snacks.resolve_name(base)[0] is not None or base in {s["name"] for s in snacks.catalog()}:
        return base + JAR_SUFFIX
    return base


def _name_when_opened(j) -> str:
    if j["goods_name"]:
        return j["goods_name"]
    old = _OLD_NAMES.get(j["how"] or "")         # sealed before 0.2.2: named by the rule it was sealed under
    if old:
        return goods_name(old.format(x=j["item_name"]))
    from . import fridge
    cat = (fridge.item(j["item_id"]) or {}).get("category") if j["item_id"] else None
    return goods_name(auto_name(j["item_name"], cat, [w for w in _SEP.split(j["how_word"] or "") if w]))


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
    name, seas, named, note = parse(line)
    iid = fridge.resolve(name, gone=True)
    if iid is None:
        raise JarError(tp("jar_unknown", name=name), "unknown_item")
    it = fridge.item(iid) or {}
    word = "、".join(seas)
    how = _how(seas[0])
    odd = is_odd(it, seas)
    gname = goods_name(named or auto_name(it.get("name", name), it.get("category"), seas))
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
        due = now + jar_days(it, iid) * DAY
        conn.execute("UPDATE jars SET state='sealed', item_id=?, item_name=?, freshness=?, how=?, how_word=?, note=?,"
                     " sealed_at=?, due_at=?, seal_key=?, goods_name=?, odd=? WHERE who=? AND slot=? AND state='empty'",
                     (iid, it["name"], u["freshness"], how, word, note, now, due, key, gname, 1 if odd else 0,
                      who, empty["slot"]))
        what = f"{it['name']}、{word}"
        if named:
            what = tp("jar_sealed_named", what=what, name=gname)
        receipt = tp("jar_sealed", what=what, ready=_ready_when(due, now),
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
        gid = "g-" + hashlib.sha1(f"{who}:{j['slot']}:{j['sealed_at']}".encode()).hexdigest()[:10]
        why = ("bad" if j["freshness"] == "bad"
               else "odd" if j["odd"] and _h(gid + ":odd") < JAR_ODD_FAIL_P else "")
        ok = not why
        n = JAR_PORTIONS_MIN + int(_h(gid) * (JAR_PORTIONS_MAX - JAR_PORTIONS_MIN + 1)) if ok else 0
        conn.execute("INSERT OR IGNORE INTO jar_goods (id, who, name, item_name, ok, total, left_n, note, opened_at,"
                     " why, how_word) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (gid, who, _name_when_opened(j) if ok else j["item_name"], j["item_name"],
                      1 if ok else 0, n, n, j["note"] or "", j["due_at"], why, j["how_word"] or ""))
        conn.execute("UPDATE jars SET state='empty', item_id=NULL, item_name=NULL, freshness=NULL, how=NULL,"
                     " how_word=NULL, note='', sealed_at=NULL, due_at=NULL, seal_key=NULL, goods_name=NULL, odd=0"
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


def _opened_text(g) -> str:
    if g["ok"]:
        return tp("jar_opened", goods=g["name"], n=g["total"])
    if g["why"] == "odd":
        return tp("jar_failed_odd", what=f"{g['item_name']}、{g['how_word']}" if g["how_word"] else g["item_name"])
    return tp("jar_failed", name=g["item_name"])


def tick(who: str, now: float) -> int:
    """Periodic scan: open what is due and leave a note for each jar opened."""
    if not play.on("seal_jars"):
        return 0
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settle_in_tx(conn, who, now)
        todo = [(g["id"], _opened_text(g))
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
