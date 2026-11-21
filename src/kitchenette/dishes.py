"""Plates: a dishwasher, or the role washes them.

- One meal leaves one plate (eating straight from the fridge, snacks and potions leave none).
- Two switches. ``[play] dishwash`` off: no plates at all, the sink stays empty. On, with the human's
  "let the role wash" off (per role, from the page): every plate goes into the dishwasher. Both on:
  plates wait in the sink until the role writes [刷盘子].
- Washing is real time, ``[dishwash] seconds_per_plate`` each. How many to wash is the human's call
  (none set = everything in the sink). About one plate in twenty breaks (``break_rate``): one
  sentence, one plate fewer. It costs no stamina, and a new pot can be opened meanwhile.
- When washing starts, how many, how long each and which one breaks are all fixed; reading it later,
  restarting the server, nothing draws again. Turning "let the role wash" off midway: plates already
  washed count, the rest go into the dishwasher. The role hears it is done on its next turn (a note).
"""
from __future__ import annotations

import hashlib
import json
import uuid

from . import clock, config, db, notify, play
from .texts import t
from .texts_play import WASH_BREAK_LINES, tp

SINK, WASHING, CLEAN, BROKEN, MACHINE = "sink", "washing", "clean", "broken", "machine"
KIND_DONE = "dishwash.done"


def _h(seed: str) -> float:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def settings(conn, who: str) -> dict:
    r = conn.execute("SELECT * FROM wash_settings WHERE who=?", (who,)).fetchone()
    return {"self_wash": bool(r["self_wash"]) if r else False, "quota": (r["quota"] if r else None)}


def produce_in_tx(conn, who: str, eat_key: str, dish: str, now: float) -> None:
    """One plate for one meal, inside the eating transaction (the same bite never makes two)."""
    if not play.on("dishwash"):
        return
    state = SINK if settings(conn, who)["self_wash"] else MACHINE
    conn.execute("INSERT OR IGNORE INTO dishes (id, who, eat_key, dish, state, created_at) VALUES (?,?,?,?,?,?)",
                 (uuid.uuid4().hex[:12], who, eat_key, (dish or "")[:40], state, now))


def _fmt_left(sec: float) -> str:
    m = (max(0, int(sec)) + 59) // 60
    return tp("wash_minutes", m=m) if m < 60 else tp("wash_hours", h=m // 60, m=m % 60)


def _stop_job(conn, job, now: float) -> None:
    conn.execute("UPDATE dishes SET state=?, done_at=? WHERE job_id=? AND state=?", (MACHINE, now, job["id"], WASHING))
    conn.execute("UPDATE wash_jobs SET state='stopped', ended_at=? WHERE id=? AND state='running'", (now, job["id"]))


def settle_in_tx(conn, who: str, now: float) -> None:
    """Bring washing up to now; with the feature or "let the role wash" off, tidy up into the dishwasher."""
    on = play.on("dishwash")
    self_wash = settings(conn, who)["self_wash"]
    for job in conn.execute("SELECT * FROM wash_jobs WHERE who=? AND state='running'", (who,)).fetchall():
        ids = json.loads(job["dish_ids_json"])
        brk = set(json.loads(job["break_idx_json"] or "[]"))
        for i, did in enumerate(ids):
            at = job["started_at"] + (i + 1) * job["per_s"]
            if at <= now:
                conn.execute("UPDATE dishes SET state=?, done_at=? WHERE id=? AND state=?",
                             (BROKEN if i in brk else CLEAN, at, did, WASHING))
        last = job["started_at"] + len(ids) * job["per_s"]
        if last <= now:
            conn.execute("UPDATE wash_jobs SET state='done', ended_at=? WHERE id=? AND state='running'", (last, job["id"]))
        elif not on or not self_wash:
            _stop_job(conn, job, now)
    if not self_wash or not on:
        conn.execute("UPDATE dishes SET state=?, done_at=? WHERE who=? AND state=?", (MACHINE, now, who, SINK))


def set_settings(who: str, *, self_wash: bool | None = None, quota: int | None = None,
                 clear_quota: bool = False, now: float | None = None) -> dict:
    now = now or clock.now()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settle_in_tx(conn, who, now)              # up to now under the old setting (washed ones count)
        cur = settings(conn, who)
        sw = cur["self_wash"] if self_wash is None else bool(self_wash)
        q = None if clear_quota else (cur["quota"] if quota is None else max(0, int(quota)))
        conn.execute("INSERT INTO wash_settings (who, self_wash, quota, updated_at) VALUES (?,?,?,?)"
                     " ON CONFLICT(who) DO UPDATE SET self_wash=excluded.self_wash, quota=excluded.quota,"
                     " updated_at=excluded.updated_at", (who, 1 if sw else 0, q, now))
        settle_in_tx(conn, who, now)              # turned off: the rest goes into the dishwasher now
        conn.commit()
        return settings(conn, who)
    finally:
        conn.close()


def start(who: str, *, key: str, now: float | None = None) -> str:
    """[刷盘子]. Already washing: says how far it is. The same reply again: the same washing."""
    now = now or clock.now()
    if not play.on("dishwash"):
        return tp("feature_off")
    cfg = config.get()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settle_in_tx(conn, who, now)
        again = conn.execute("SELECT * FROM wash_jobs WHERE key=?", (key,)).fetchone()
        if again is not None and again["state"] != "running":
            n = len(json.loads(again["dish_ids_json"]))
            conn.commit()
            return tp("wash_start", n=n, minutes=round(n * again["per_s"] / 60))
        run = conn.execute("SELECT * FROM wash_jobs WHERE who=? AND state='running'", (who,)).fetchone()
        if run is not None:
            left = run["started_at"] + len(json.loads(run["dish_ids_json"])) * run["per_s"] - now
            n_left = conn.execute("SELECT COUNT(*) FROM dishes WHERE job_id=? AND state=?", (run["id"], WASHING)).fetchone()[0]
            conn.commit()
            return tp("wash_already", n=n_left, left=_fmt_left(left))
        st = settings(conn, who)
        if not st["self_wash"]:
            conn.commit()
            return tp("wash_self_off")
        sink = [r["id"] for r in conn.execute("SELECT id FROM dishes WHERE who=? AND state=? ORDER BY created_at",
                                              (who, SINK)).fetchall()]
        n = len(sink) if st["quota"] is None else min(st["quota"], len(sink))
        if n <= 0:
            conn.commit()
            return tp("wash_empty")
        ids = sink[:n]
        jid = uuid.uuid4().hex[:12]
        brk = [i for i in range(n) if _h(f"break:{jid}:{i}") < cfg.dishwash_break_rate]
        per = float(cfg.dishwash_seconds_per_plate)
        conn.execute("INSERT INTO wash_jobs (id, who, key, dish_ids_json, per_s, break_idx_json, started_at, state)"
                     " VALUES (?,?,?,?,?,?,?,?)", (jid, who, key, json.dumps(ids), per, json.dumps(brk), now, "running"))
        conn.executemany("UPDATE dishes SET state=?, job_id=? WHERE id=? AND state=?",
                         [(WASHING, jid, d, SINK) for d in ids])
        conn.commit()
        return tp("wash_start", n=n, minutes=round(n * per / 60))
    finally:
        conn.close()


def view(conn, who: str, now: float) -> dict:
    counts = {s: 0 for s in (SINK, WASHING, CLEAN, BROKEN, MACHINE)}
    for r in conn.execute("SELECT state, COUNT(*) n FROM dishes WHERE who=? GROUP BY state", (who,)).fetchall():
        counts[r["state"]] = r["n"]
    job = conn.execute("SELECT * FROM wash_jobs WHERE who=? ORDER BY started_at DESC LIMIT 1", (who,)).fetchone()
    j = None
    if job:
        # breaks: which of the plates already washed broke (0-based, in washing order). Which ones will break
        # is fixed when the washing starts, but a plate's result is only told once its time is up: a plate
        # still to come is never in this list. The page plays the dropped plate when it reads one here.
        # machine_at: when a plate last went into the dishwasher (null = never), for the loading-the-dishwasher clip.
        last = min(now, job["ended_at"]) if job["ended_at"] is not None else now
        j = {"id": job["id"], "state": job["state"], "started_at": job["started_at"], "per_s": job["per_s"],
             "n": len(json.loads(job["dish_ids_json"])), "ended_at": job["ended_at"],
             "breaks": sorted(i for i in json.loads(job["break_idx_json"] or "[]")
                              if job["started_at"] + (i + 1) * job["per_s"] <= last)}
    m = conn.execute("SELECT MAX(COALESCE(done_at, created_at)) FROM dishes WHERE who=? AND state=?", (who, MACHINE)).fetchone()[0]
    return {"now": now, "on": play.on("dishwash"), **settings(conn, who), "counts": counts, "job": j, "machine_at": m}


def status_line(conn, who: str, now: float) -> str:
    run = conn.execute("SELECT * FROM wash_jobs WHERE who=? AND state='running'", (who,)).fetchone()
    if run:
        n_left = conn.execute("SELECT COUNT(*) FROM dishes WHERE job_id=? AND state=?", (run["id"], WASHING)).fetchone()[0]
        left = run["started_at"] + len(json.loads(run["dish_ids_json"])) * run["per_s"] - now
        return tp("sink_washing", n=n_left, left=_fmt_left(left))
    n = conn.execute("SELECT COUNT(*) FROM dishes WHERE who=? AND state=?", (who, SINK)).fetchone()[0]
    return tp("sink_line", n=n) if n else ""


def pending_notices(conn, who: str) -> list[tuple[str, str]]:
    out = []
    for job in conn.execute("SELECT * FROM wash_jobs WHERE who=? AND state IN ('done','stopped') AND told=0"
                            " ORDER BY ended_at", (who,)).fetchall():
        clean = conn.execute("SELECT COUNT(*) FROM dishes WHERE job_id=? AND state=?", (job["id"], CLEAN)).fetchone()[0]
        broken = conn.execute("SELECT COUNT(*) FROM dishes WHERE job_id=? AND state=?", (job["id"], BROKEN)).fetchone()[0]
        if job["state"] == "stopped":
            text = tp("wash_stopped", done=clean + broken)
        elif broken:
            line = WASH_BREAK_LINES[int(_h(f"breakline:{job['id']}") * len(WASH_BREAK_LINES)) % len(WASH_BREAK_LINES)]
            text = tp("wash_done_broken", n=clean + broken, broke=line)
        else:
            text = tp("wash_done", n=clean)
        out.append((job["id"], text))
    return out


def tick(who: str, now: float) -> int:
    """Periodic scan: bring washing up to now and leave a note for each one that finished."""
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settle_in_tx(conn, who, now)
        todo = pending_notices(conn, who) if play.on("dishwash") else []
        conn.commit()
    finally:
        conn.close()
    for jid, text in todo:
        notify.emit(who, KIND_DONE, t("head") + text, body=text, key=f"dishwash:{jid}", now=now)
        conn = db.connect()
        try:
            conn.execute("UPDATE wash_jobs SET told=1 WHERE id=?", (jid,))
            conn.commit()
        finally:
            conn.close()
    return len(todo)
