"""Pushing notes: a flush takes the notes it sends (so two flushes at once never send the same one, and
nothing is merged into a note on its way). A sure "not sent" lets them go to be offered again; a result
that cannot be told (or a delivery that raised) counts as delivered, as HOOKS.md promises: a duplicate is
worse than a miss."""
from __future__ import annotations

import threading

from kitchenette import config, db, notify

from conftest import A, B


class Gate:
    """A notifier whose first delivery waits until the test lets it finish."""

    def __init__(self, results=None):
        self.calls: list[tuple[str, list[int], list[str]]] = []
        self.inside = threading.Event()
        self.go = threading.Event()
        self.results = list(results or [])

    def deliver(self, who, batch):
        self.calls.append((who, [n["id"] for n in batch], [n["text"] for n in batch]))
        if len(self.calls) == 1:
            self.inside.set()
            assert self.go.wait(10)
        r = self.results.pop(0) if self.results else notify.SENT
        if isinstance(r, Exception):
            raise r
        return r


def _on(n) -> None:
    config.override(notify_mode="webhook", notify_webhook_url="http://127.0.0.1:9/unused")
    notify.set_notifier(n)


def _rows():
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute("SELECT id, text, pushed_at, claim_token FROM notes ORDER BY id")]
    finally:
        conn.close()


def _flush_in_thread():
    out = {}
    t = threading.Thread(target=lambda: out.update(notify.flush()), daemon=True)
    t.start()
    return t, out


def test_two_flushes_at_once_send_a_note_once(clock):
    g = Gate()
    _on(g)
    notify.emit(A, notify.KIND_HUNGRY, "饿了")
    t, first = _flush_in_thread()
    assert g.inside.wait(10)                      # the first flush is sending
    assert notify.flush() == {"pushed": 0, "deferred": 0, "failed": 0}   # the second finds nothing to take
    assert notify.take(A) == []                   # nor does the queue: the note is on its way
    g.go.set()
    t.join(10)
    assert first["pushed"] == 1 and len(g.calls) == 1
    assert _rows()[0]["pushed_at"] is not None and _rows()[0]["claim_token"] is None


def test_something_told_while_a_note_is_being_sent_gets_a_note_of_its_own(clock):
    g = Gate()
    _on(g)
    notify.emit(A, notify.KIND_BOUGHT, payload={"items": "番茄×1"})          # a kind that merges
    t, _ = _flush_in_thread()
    assert g.inside.wait(10)
    notify.emit(A, notify.KIND_BOUGHT, payload={"items": "鸡蛋×2"})          # while the first is on its way
    g.go.set()
    t.join(10)
    rows = _rows()
    assert len(rows) == 2                                                     # not merged into the one being sent
    assert rows[0]["pushed_at"] is not None and "鸡蛋" not in rows[0]["text"]
    assert rows[1]["pushed_at"] is None and "鸡蛋" in rows[1]["text"]
    assert notify.flush()["pushed"] == 1 and "鸡蛋" in g.calls[-1][2][0]     # and it goes out next


def test_not_sent_is_offered_again_but_unclear_or_raised_counts_as_delivered(clock):
    g = Gate([notify.NOT_SENT, notify.NOT_SENT, notify.SENT])
    g.go.set()
    _on(g)
    nid = notify.emit(A, notify.KIND_HUNGRY, "饿了")
    for _ in range(2):
        assert notify.flush()["failed"] == 1
        assert _rows()[0]["pushed_at"] is None and _rows()[0]["claim_token"] is None   # let go each time
    assert notify.flush()["pushed"] == 1
    assert [c[1] for c in g.calls] == [[nid]] * 3

    # unclear, or the delivery raised (a connection broken half-way): delivered, never sent again
    g.results = [notify.UNKNOWN, RuntimeError("connection reset")]
    u = notify.emit(A, notify.KIND_HUNGRY, "又饿了")
    assert notify.flush()["pushed"] == 1 and notify.flush()["pushed"] == 0
    r = notify.emit(A, notify.KIND_HUNGRY, "还饿")
    assert notify.flush()["pushed"] == 1 and notify.flush()["pushed"] == 0
    conn = db.connect()
    try:
        states = {row["id"]: (row["push_state"], row["pushed_at"] is not None, row["claim_token"])
                  for row in conn.execute("SELECT id, push_state, pushed_at, claim_token FROM notes")}
    finally:
        conn.close()
    assert states[u] == ("unknown", True, None) and states[r] == ("raised", True, None)
    assert [c[1] for c in g.calls[3:]] == [[u], [r]]


def test_notes_taken_by_a_flush_that_died_are_taken_again_after_a_while(clock):
    rec = Gate()
    rec.go.set()
    _on(rec)
    notify.emit(A, notify.KIND_HUNGRY, "饿了")
    token, taken = notify._claim(clock["now"], A)                  # a flush took it, then its process stopped
    assert taken and notify.flush() == {"pushed": 0, "deferred": 0, "failed": 0}
    clock["now"] += notify.CLAIM_S + 1
    assert notify.flush()["pushed"] == 1
    notify._settle(token, [taken[0]["id"]], clock["now"], True, notify.SENT)       # the dead one's late word
    assert len(rec.calls) == 1 and _rows()[0]["pushed_at"] is not None


def test_a_batch_slower_than_the_claim_never_lets_another_flush_send_its_later_roles_again(clock):
    """One flush sends to A, which takes longer than a claim lasts; while it then turns to B, another flush
    runs. Taken role by role, right before sending, B is this flush's fresh claim: the other one sends
    nothing, and the sequence is A, B (taking everything up front gave A, B, B)."""
    calls: list[str] = []

    class Slow:
        nested = False

        def deliver(self, who, batch):
            calls.append(who)
            if who == A:
                clock["now"] += notify.CLAIM_S + 1          # a very slow delivery
            elif not Slow.nested:
                Slow.nested = True
                assert notify.flush() == {"pushed": 0, "deferred": 0, "failed": 0}   # the other flush, meanwhile
            return notify.SENT
    _on(Slow())
    notify.emit(A, notify.KIND_HUNGRY, "饿了")
    notify.emit(B, notify.KIND_HUNGRY, "也饿了")
    assert notify.flush()["pushed"] == 2
    assert calls == [A, B]
    assert all(r["pushed_at"] is not None for r in _rows())
