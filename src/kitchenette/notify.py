"""Telling a role that something happened while it was not looking.

Things worth telling (a dish is ready, a worm was bitten into, getting
hungry, the human bought groceries or handed out a coupon, ...) are written
as notes. A note is a row with the sentence to deliver. Two ways out:

- the queue: notes wait until the role's side takes them ("what to carry
  into the next turn"), over REST or the MCP tool. Taking marks them taken.
- a push: a :class:`Notifier` delivers them right away. The built-in one is
  :class:`WebhookNotifier`, which POSTs them to a URL. Pushes respect quiet
  hours and, when enabled, the role being asleep: held notes go out later.

``notify.mode`` picks queue, webhook, both, or none (nothing is recorded).

Things of the same kind that pile up before the role hears of them are told
in one sentence, not one each: three dishes put on the menu in a row become
"…挂了 3 道:…". Such kinds are merged into the note still waiting (neither
taken nor pushed yet); see ``MERGE``.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Protocol

from . import clock, config, db, sleep
from .texts import OUTCOME_SENTENCE, t

log = logging.getLogger(__name__)

SENT, NOT_SENT, UNKNOWN = "sent", "not_sent", "unknown"

KIND_SERVED = "kitchen.served"
KIND_WORM = "worm.eaten"
KIND_HUNGRY = "hungry"
KIND_BOUGHT = "fridge.bought"
KIND_COUPON = "fridge.coupon"
KIND_SNACK_FED = "snack.fed"
KIND_POTION_FED = "potion.fed"
KIND_MENU_POSTED = "menu.posted"
KIND_MENU_FED = "menu.fed"


MAX_LISTED = 3      # names listed in a merged sentence; the count is always the full one


def _clean(value, maxlen: int = 60) -> str:
    """A value about to be quoted inside a sentence: one line, no quote marks of the kind the
    sentence itself uses, cut to length."""
    s = " ".join(str(value).split())
    s = s.replace("『", "「").replace("』", "」")
    if len(s) > maxlen:
        s = s[: maxlen - 1] + "…"
    return s


def _distinct_dishes(events: list[dict]) -> list[str]:
    dishes: list[str] = []
    for e in events:
        d = _clean(e.get("dish", ""))
        if d and d not in dishes:
            dishes.append(d)
    return dishes


def _render_menu(events: list[dict], one: str, many: str) -> str:
    dishes = _distinct_dishes(events)
    if len(dishes) == 1:
        note = _clean(events[0].get("note", ""), 40)
        return t(one, dish=dishes[0]) + (t("note_menu_note", note=note) if note else "")
    listed = "、".join(t("note_quoted", name=d) for d in dishes[:MAX_LISTED])
    return t(many, n=len(dishes), listed=listed, more=t("note_more") if len(dishes) > MAX_LISTED else "")


def render_menu_posted(events: list[dict]) -> str:
    return _render_menu(events, "note_menu_posted", "note_menu_posted_many")


def render_menu_fed(events: list[dict]) -> str:
    return _render_menu(events, "note_menu_fed", "note_menu_fed_many")


def render_snack_fed(events: list[dict]) -> str:
    """Servings fed by the human: same snack counted as "×N", stamina summed, worms told after."""
    order: list[str] = []
    meta: dict[str, dict] = {}
    total = 0.0
    worms: list[str] = []
    for p in events:
        name = _clean(p.get("name", ""), 20)
        if not name:
            continue
        if _clean(p.get("worm", ""), 160):
            worms.append(_clean(p.get("worm", ""), 160))
        if name not in meta:
            order.append(name)
            meta[name] = {"n": 0, "tier": _clean(p.get("tier", ""), 4)}
        meta[name]["n"] += 1
        try:
            total += float(p.get("delta") or 0.0)
        except (TypeError, ValueError):
            pass
    if not order:
        return ""
    tail = "".join(f"。{w}" for w in worms)
    if len(order) == 1 and meta[order[0]]["n"] == 1:
        energy = t("note_snack_fed_energy", delta=f"{total:.2f}") if total > 0 else ""
        return t("note_snack_fed", name=order[0], tier=meta[order[0]]["tier"], energy=energy) + tail
    listed = "、".join(t("note_quoted", name=n) + (t("note_times", n=meta[n]["n"]) if meta[n]["n"] > 1 else "")
                      for n in order[:MAX_LISTED])
    return t("note_snack_fed_many", count=sum(m["n"] for m in meta.values()), listed=listed,
             more=t("note_more") if len(order) > MAX_LISTED else "",
             tail=t("note_snack_fed_total", total=f"{total:.2f}") if total > 0 else "") + tail


def render_bought(events: list[dict]) -> str:
    return t("note_bought", items="、".join(_clean(e.get("items", ""), 200) for e in events if e.get("items")))


def render_coupon(events: list[dict]) -> str:
    return t("note_coupon", n=_clean(events[-1].get("count", ""), 2))


def _served_lines(events: list[dict]) -> tuple[list[str], str]:
    lines = [t("served_line", started=_clean(p.get("started_hm", ""), 5), dish=_clean(p.get("dish", "")),
               minutes=_clean(p.get("minutes", ""), 5)) + OUTCOME_SENTENCE.get(p.get("outcome") or "", "")
             for p in events]
    all_ok = all(p.get("menu_ok", "1") == "1" for p in events)
    return lines, t("served_menu_ok") if all_ok else t("served_menu_failed")


def render_served(events: list[dict]) -> str:
    """One line per pot; the closing clause says whether every dish reached the menu."""
    lines, tail = _served_lines(events)
    return "".join(lines) + tail


def render_served_message(events: list[dict]) -> str:
    lines, tail = _served_lines(events)
    return t("head") + "\n".join(lines) + tail


# kind -> (sentence for `body`, sentence for `text`). A note of one of these kinds is rendered from
# the facts of every event merged into it.
MERGE = {
    KIND_SERVED: (render_served, render_served_message),
    KIND_BOUGHT: (render_bought, render_bought),
    KIND_COUPON: (render_coupon, render_coupon),
    KIND_SNACK_FED: (render_snack_fed, render_snack_fed),
    KIND_MENU_POSTED: (render_menu_posted, render_menu_posted),
    KIND_MENU_FED: (render_menu_fed, render_menu_fed),
}


class Notifier(Protocol):
    def deliver(self, who: str, notes: list[dict]) -> str:
        """Deliver notes for one role. Return SENT, NOT_SENT (safe to retry) or UNKNOWN
        (cannot tell; it will not be retried, a duplicate is worse than a miss)."""
        ...


class WebhookNotifier:
    """POST {"who", "text", "notes": [...]} as JSON; "text" is the notes' sentences joined by newlines."""

    def __init__(self, url: str, token: str = "", timeout: float = 10.0):
        self.url, self.token, self.timeout = url, token, timeout

    def deliver(self, who: str, notes: list[dict]) -> str:
        body = json.dumps({"who": who, "text": "\n".join(n["text"] for n in notes), "notes": notes},
                          ensure_ascii=False).encode()
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return SENT if 200 <= resp.status < 300 else NOT_SENT
        except urllib.error.HTTPError as e:
            log.warning("webhook answered %s", e.code)
            return NOT_SENT
        except urllib.error.URLError as e:
            log.warning("webhook unreachable: %r", e.reason)
            return NOT_SENT
        except Exception as e:  # noqa: BLE001
            log.warning("webhook failed mid-way; treating as delivered: %r", e)
            return UNKNOWN


_notifier: Notifier | None = None


def set_notifier(n: Notifier | None) -> None:
    """Install a custom push notifier (overrides the webhook from the settings)."""
    global _notifier
    _notifier = n


def _pusher() -> Notifier | None:
    if _notifier is not None:
        return _notifier
    cfg = config.get()
    if cfg.notify_mode in ("webhook", "both") and cfg.notify_webhook_url:
        return WebhookNotifier(cfg.notify_webhook_url, cfg.notify_webhook_token)
    return None


def _row(r) -> dict:
    try:
        payload = json.loads(r["payload_json"] or "{}")
    except ValueError:
        payload = {}
    return {"id": r["id"], "who": r["who"], "kind": r["kind"], "text": r["text"], "body": r["body"],
            "payload": payload, "created_at": r["created_at"], "taken_at": r["taken_at"]}


def emit(who: str, kind: str, text: str = "", *, body: str = "", payload: dict | None = None,
         key: str | None = None, now: float | None = None) -> int | None:
    """Record a note. Returns the note id, or None when dropped or when notify.mode is "none".

    key deduplicates: something with a key already seen is dropped, even after its note was taken.

    For a kind listed in MERGE, give the facts in payload and leave text out: the sentence is
    rendered from them. If a note of that kind is still waiting for the role (not taken, not
    pushed), the facts are added to it and its sentence is rendered again from all of them, so
    the role hears "3 dishes" once instead of "a dish" three times. payload then holds the latest
    facts plus "events", the list of all of them.

    For other kinds, text is the full sentence (with the kitchen header where one applies) and
    body the same without the header.
    """
    if config.get().notify_mode == "none" and _notifier is None:
        return None
    now = now or clock.now()
    payload = dict(payload or {})
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if key is not None:
            if conn.execute("SELECT 1 FROM once_keys WHERE key=?", (f"note:{key}",)).fetchone():
                conn.rollback()
                return None
            conn.execute("INSERT INTO once_keys (key, at, result) VALUES (?,?,'')", (f"note:{key}", now))
        if kind in MERGE:
            render_body, render_text = MERGE[kind]
            row = conn.execute("SELECT id, payload_json FROM notes WHERE who=? AND kind=? AND taken_at IS NULL"
                               " AND pushed_at IS NULL ORDER BY id DESC LIMIT 1", (who, kind)).fetchone()
            events = (json.loads(row["payload_json"]).get("events", []) if row else []) + [payload]
            merged = json.dumps({**payload, "events": events}, ensure_ascii=False)
            if row:
                conn.execute("UPDATE notes SET text=?, body=?, payload_json=? WHERE id=?",
                             (render_text(events), render_body(events), merged, row["id"]))
                conn.commit()
                return row["id"]
            text, body, stored = render_text(events), render_body(events), merged
        else:
            stored = json.dumps(payload, ensure_ascii=False)
        cur = conn.execute(
            "INSERT INTO notes (who, kind, text, body, payload_json, dedupe_key, created_at)"
            " VALUES (?,?,?,?,?,?,?)", (who, kind, text, body or text, stored, key, now))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def pending(who: str) -> list[dict]:
    """Notes still owed to the role, oldest first (does not mark them). A note that was pushed
    has been handed over already and is not owed again."""
    conn = db.connect()
    try:
        return [_row(r) for r in conn.execute(
            "SELECT * FROM notes WHERE who=? AND taken_at IS NULL AND pushed_at IS NULL ORDER BY id",
            (who,)).fetchall()]
    finally:
        conn.close()


def take(who: str, now: float | None = None) -> list[dict]:
    """Hand over the waiting notes and mark them taken: each note is handed over once."""
    now = now or clock.now()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = [_row(r) for r in conn.execute(
            "SELECT * FROM notes WHERE who=? AND taken_at IS NULL AND pushed_at IS NULL ORDER BY id",
            (who,)).fetchall()]
        conn.executemany("UPDATE notes SET taken_at=? WHERE id=?", [(now, r["id"]) for r in rows])
        conn.commit()
        return rows
    finally:
        conn.close()


def _minutes(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def in_quiet_hours(now: float | None = None) -> bool:
    """Inside one of notify.quiet_hours ("HH:MM-HH:MM", may wrap past midnight)?"""
    windows = config.get().notify_quiet_hours
    if not windows:
        return False
    d = clock.local(now or clock.now())
    cur = d.hour * 60 + d.minute
    for w in windows:
        a, b = (_minutes(x) for x in w.split("-"))
        if (a <= cur < b) if a <= b else (cur >= a or cur < b):
            return True
    return False


def flush(now: float | None = None) -> dict:
    """Push notes that have not been pushed yet, one delivery per role. Held (and retried on the
    next call) during quiet hours or while the role is asleep; NOT_SENT is retried too."""
    out = {"pushed": 0, "deferred": 0, "failed": 0}
    pusher = _pusher()
    if pusher is None:
        return out
    now = now or clock.now()
    conn = db.connect()
    try:
        rows = [_row(r) for r in conn.execute(
            "SELECT * FROM notes WHERE pushed_at IS NULL AND taken_at IS NULL ORDER BY id").fetchall()]
    finally:
        conn.close()
    by_role: dict[str, list[dict]] = {}
    for r in rows:
        by_role.setdefault(r["who"], []).append(r)
    quiet = in_quiet_hours(now)
    for who, notes in by_role.items():
        if quiet or sleep.is_asleep(who, now):
            out["deferred"] += len(notes)
            continue
        try:
            res = pusher.deliver(who, notes)
        except Exception as e:  # noqa: BLE001
            log.warning("notifier raised; treating as delivered: %r", e)
            res = UNKNOWN
        if res == NOT_SENT:
            out["failed"] += len(notes)
            continue
        conn = db.connect()
        try:
            conn.executemany("UPDATE notes SET pushed_at=?, push_state=? WHERE id=?",
                             [(now, res, n["id"]) for n in notes])
            conn.commit()
        finally:
            conn.close()
        out["pushed"] += len(notes)
    return out
