"""A webhook receiver for kitchen notifications. Run it, then point the server at it:
接收厨房通知的一个小程序。先把它跑起来，再让服务把通知发给它：

    python examples/notify_webhook_receiver.py            # listens on 127.0.0.1:9000

    # kitchenette.toml
    [notify]
    mode = "webhook"
    webhook_url = "http://127.0.0.1:9000/kitchen"

Each delivery is one POST with a JSON body:

    {"who": "companion",
     "text": "<every note's sentence, one per line>",
     "notes": [{"id": 1, "kind": "kitchen.served", "text": "...", "body": "...", "payload": {...}}]}

Answer 2xx once the notes are safely on their way to the role. Any other
status (or no answer) makes the server try again on its next scan. This
receiver also skips note ids it has already handled, in case one comes again.

What you do in `deliver` is the part that is yours: start a turn for the
model with `text` as input, push a message into a chat, write to a file.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def deliver(who: str, text: str, notes: list[dict]) -> None:
    print(f"--- for {who} ({', '.join(n['kind'] for n in notes)})")
    print(text, flush=True)


_seen: set[int] = set()       # note ids already handled (kept in memory: a real receiver would store them)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        fresh = [n for n in body.get("notes", []) if n.get("id") not in _seen]
        if fresh:
            deliver(body.get("who", ""), "\n".join(n.get("text", "") for n in fresh), fresh)
            _seen.update(n.get("id") for n in fresh)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    print(f"listening on http://127.0.0.1:{port}/kitchen")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
