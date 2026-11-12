"""Artwork for ingredient kinds added from the page. Off by default.

With no provider configured a new kind is a text card (``art.state`` is
``"none"``) and the page shows its name. With ``art.provider`` set to
``"package.module:callable"``, each new kind is drawn in the background:

    def draw(name: str, category: str) -> dict[str, bytes]:
        '''Return PNG bytes for the three looks: {"fresh": ..., "meh": ..., "bad": ...}.'''

Drawing runs one kind at a time. A failure is recorded on the kind
(``art.state = "failed"`` with the reason) and can be retried from the page.
Files are written once per version and never rewritten, so a URL that
carries the version can be cached forever.
"""
from __future__ import annotations

import importlib
import logging
import os
import shutil
import struct
import sys
import threading
from pathlib import Path
from typing import Callable

from . import config, fridge

log = logging.getLogger(__name__)

STATES = ("fresh", "meh", "bad")
_PNG_SIG = b"\x89PNG\r\n\x1a\n"

_provider: Callable[[str, str], dict] | None = None
_lock = threading.Lock()          # one drawing at a time
_running: set[str] = set()


def set_provider(fn: Callable[[str, str], dict] | None) -> None:
    """Install a provider directly (overrides art.provider from the settings)."""
    global _provider
    _provider = fn


def provider() -> Callable[[str, str], dict] | None:
    if _provider is not None:
        return _provider
    spec = config.get().art_provider
    if not spec:
        return None
    mod, _, attr = spec.partition(":")
    if os.getcwd() not in sys.path:          # a provider module next to where the server was started
        sys.path.insert(0, os.getcwd())
    return getattr(importlib.import_module(mod), attr or "draw")


def enabled() -> bool:
    return _provider is not None or bool(config.get().art_provider)


def art_dir() -> Path:
    return Path(config.get().art_dir)


def art_path(kind_id: str, state: str, v: int) -> Path:
    return art_dir() / kind_id / f"v{int(v)}" / f"{state}.png"


def _png_size(data: bytes) -> list[int]:
    if len(data) < 24 or data[:8] != _PNG_SIG:
        raise ValueError("not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    return [w, h]


def run(kind_id: str) -> str:
    """Draw one kind now. Returns the resulting art state."""
    k = fridge.kind(kind_id)
    if k is None or k["removed"]:
        return fridge.ART_FAILED
    req = k["art_req"]
    try:
        draw = provider()
        if draw is None:
            raise RuntimeError("no art provider configured")
        images = draw(k["name"], k["category"])
        v = k["art"]["v"] + 1
        sizes = {}
        for state in STATES:
            data = images[state]
            sizes[state] = _png_size(data)
            p = art_path(kind_id, state, v)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        if not fridge.set_art(kind_id, fridge.ART_READY, sizes=sizes, v=v, req=req):
            # a redraw was requested while this one was being drawn: this result does not count
            shutil.rmtree(art_path(kind_id, STATES[0], v).parent, ignore_errors=True)
            return fridge.ART_PENDING
        for old in (art_dir() / kind_id).glob("v*"):
            if old.name != f"v{v}":
                shutil.rmtree(old, ignore_errors=True)
        return fridge.ART_READY
    except Exception as e:  # noqa: BLE001
        log.warning("drawing %s failed: %r", kind_id, e)
        fridge.set_art(kind_id, fridge.ART_FAILED, err=f"{type(e).__name__}: {e}", req=req)
        return fridge.ART_FAILED


MAX_ROUNDS = 5      # passes in one go when redraws keep arriving mid-drawing; a guard, not a rule


def run_queued(kind_id: str) -> str:
    """Draw until a result lands. If redraws keep superseding it, end as a visible failure
    rather than a kind stuck on "pending" forever."""
    state = fridge.ART_PENDING
    for _ in range(MAX_ROUNDS):
        state = run(kind_id)
        if state != fridge.ART_PENDING:
            return state
    fridge.set_art(kind_id, fridge.ART_FAILED, err="superseded by redraw requests too many times; ask for a redraw again")
    return fridge.ART_FAILED


def _worker(kind_id: str) -> None:
    try:
        with _lock:
            run_queued(kind_id)
    finally:
        _running.discard(kind_id)


def start(kind_id: str) -> bool:
    """Queue a drawing in the background. False when art is off or this kind is already queued."""
    if not enabled() or kind_id in _running:
        return False
    _running.add(kind_id)
    threading.Thread(target=_worker, args=(kind_id,), name=f"art-{kind_id}", daemon=True).start()
    return True


def resume_pending() -> int:
    """Restart drawings that were still pending when the server stopped."""
    if not enabled():
        return 0
    return sum(1 for k in fridge.kinds()
               if not k["removed"] and k["art"]["state"] == fridge.ART_PENDING and start(k["id"]))
