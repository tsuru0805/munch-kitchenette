"""Bracket markers: actions a role writes inline in its reply. Optional.

Some setups let the model act by writing a line of its own such as::

    [买菜 番茄 鸡蛋]
    [吃 番茄炒蛋]
    [零食 拿铁]
    [扔掉 坏了的]

:func:`parse` finds these lines, :func:`strip` removes them from the text
shown to the human, and :func:`execute` runs them and returns one receipt per
marker. A setup that only uses tools never needs this module.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field

from . import db, roles, tools
from .texts import MARKER_BUY, MARKER_EAT, MARKER_SNACK, MARKER_TOSS, t

# marker -> (tool, argument name)
MARKERS = {
    MARKER_BUY: (tools.TOOL_BUY, "items"),
    MARKER_EAT: (tools.TOOL_EAT, "meal"),
    MARKER_SNACK: (tools.TOOL_SNACK, "name"),
    MARKER_TOSS: (tools.TOOL_TOSS, "what"),
}

# A marker must be alone on its line: "[name args]". The upgrade's markers (play.MARKERS) are only
# recognised while the thing they belong to is switched on; otherwise they stay plain text.


def _line_re(names) -> re.Pattern:
    alts = "|".join(map(re.escape, sorted(names, key=len, reverse=True)))
    return re.compile(r"^[ \t　]*\[(" + alts + r")(?:[ \t　]+([^\[\]\n]*?))?[ \t　]*\][ \t　]*$", re.M)


def _active_re() -> re.Pattern:
    from . import play
    return _line_re(list(MARKERS) + list(play.enabled_markers()))


@dataclass
class Action:
    marker: str
    args: str
    index: int
    start: int
    end: int


@dataclass
class Receipt:
    marker: str
    args: str
    ok: bool
    text: str          # the bare outcome
    rendered: str      # the outcome phrased as "that marker in your reply ..." for the next turn
    attachments: list[dict] = field(default_factory=list)   # e.g. the washing card of a [刷盘子] that started


def parse(text: str) -> list[Action]:
    return [Action(m.group(1), (m.group(2) or "").strip(), i, m.start(), m.end())
            for i, m in enumerate(_active_re().finditer(text or ""))]


def strip(text: str) -> str:
    """The text without its marker lines (a marker line takes its line break with it)."""
    out, pos = [], 0
    for a in parse(text):
        out.append(text[pos:a.start])
        pos = a.end + (1 if text[a.end:a.end + 1] == "\n" else 0)
    out.append(text[pos:])
    return "".join(out)


def render(marker: str, ok: bool, hint: str) -> str:
    if ok:
        return t("inline_ok", marker=marker, hint=hint) if hint else t("inline_ok_bare", marker=marker)
    return t("inline_failed", marker=marker, hint=hint) if hint else t("inline_failed_bare", marker=marker)


def _stored(key: str) -> Receipt | None:
    conn = db.connect()
    try:
        r = conn.execute("SELECT result FROM once_keys WHERE key=?", (f"inline:{key}",)).fetchone()
    finally:
        conn.close()
    return Receipt(**json.loads(r["result"])) if r else None


def _store(key: str, receipt: Receipt) -> None:
    from . import clock
    conn = db.connect()
    try:
        conn.execute("INSERT OR IGNORE INTO once_keys (key, at, result) VALUES (?,?,?)",
                     (f"inline:{key}", clock.now(), json.dumps(asdict(receipt), ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def execute(who: str | None, text: str, message_id: str | None = None, *, told: bool = False) -> list[Receipt]:
    """Run every marker in a reply, in order.

    message_id identifies the reply. Given one, running the same reply again returns the same
    receipts without acting twice. told=True means the receipts are shown to the role at once
    (otherwise a worm found in a snack is also sent as a note, in case the receipt arrives late).
    """
    who = roles.resolve(who)
    db.set_flag("inline_seen")      # with inline.enabled = "auto", the wording now speaks of markers
    out: list[Receipt] = []
    for a in parse(text):
        tool, arg = MARKERS.get(a.marker, ("play", ""))
        key = (hashlib.sha1(f"{tool}:{a.marker}:{message_id}:{a.index}".encode()).hexdigest()[:16]
               if message_id and tool == "play" else
               hashlib.sha1(f"{tool}:{message_id}:{a.index}".encode()).hexdigest()[:16] if message_id else None)
        if key:
            done = _stored(key)
            if done is not None:
                out.append(done)
                continue
        if tool == "play":
            from . import playkit, service
            service.serve_due(who)
            run_key = key or uuid.uuid4().hex
            ok, text_ = playkit.run_marker(who, a.marker, a.args, key=run_key)
            cards = playkit.marker_attachments(a.marker, run_key) if ok else []
            receipt = Receipt(a.marker, a.args, ok, text_, render(a.marker, ok, text_), cards)
            if key:
                _store(key, receipt)
            out.append(receipt)
            continue
        res = tools.call(tool, {arg: a.args}, who, key=key, told=told)
        receipt = Receipt(a.marker, a.args, not res.is_error, res.text, render(a.marker, not res.is_error, res.text),
                          list(res.attachments))
        if key:
            _store(key, receipt)
        out.append(receipt)
    return out
