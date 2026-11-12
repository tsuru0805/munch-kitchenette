"""Take the notes waiting for a role: "what to carry into its next turn".
取走等着某个角色的话——也就是「下一轮带给他的话」。

With `notify.mode = "queue"` (the default) nothing is pushed anywhere. Notes
wait on the server until the role's side asks for them, typically right
before each turn of the model:

    python examples/notify_queue.py                 # take once and print
    python examples/notify_queue.py --watch 5       # poll every 5 seconds

Taking marks the notes as handed over, so each is returned exactly once.
`GET /api/notes?who=...` looks without taking. The model can also take them
itself through the `kitchen_notes` tool.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request


def take(base: str, who: str | None, token: str) -> dict:
    req = urllib.request.Request(f"{base}/api/notes/take", method="POST",
                                 data=json.dumps({"who": who}).encode(),
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def as_turn_prefix(taken: dict) -> str:
    """One way to hand the notes to the model: a block placed before the human's message."""
    return taken["text"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8765")
    p.add_argument("--who", default=None)
    p.add_argument("--token", default="")
    p.add_argument("--watch", type=float, default=0.0, help="poll every N seconds")
    a = p.parse_args()
    while True:
        got = take(a.base, a.who, a.token)
        if got["notes"]:
            print(as_turn_prefix(got), flush=True)
        elif not a.watch:
            print("(nothing waiting)")
        if not a.watch:
            break
        time.sleep(a.watch)
