"""Let a short night lower the next day's stamina. Off unless you switch it on.
让「没睡好」拉低第二天的体力。默认关着，要你自己打开。

The server keeps no sleep record. If you track the role's sleep somewhere,
turn the hook on and report one number, a factor between 0 and 1 that scales
the whole stamina schedule (1 = well rested):

    # kitchenette.toml
    [stamina]
    sleep_debt = true

    python examples/sleep_debt.py --score 55 --debt-hours 4     # reports 0.857

`factor_from` below is one way to get the number: last night's quality
(0-100) takes off up to 20%, and accumulated sleep debt (capped at 10 hours)
up to another 15%. Use your own formula if you like; only the factor is sent.

The same endpoint also takes "asleep", for `notify.respect_sleep`:

    python examples/sleep_debt.py --asleep            # goodnight: hold webhook calls
    python examples/sleep_debt.py --awake             # good morning: release them

Embedding the server in your own Python program? Register functions instead:

    from kitchenette import sleep
    sleep.set_factor_hook(lambda who, now: my_factor(who))
    sleep.set_asleep_hook(lambda who, now: my_tracker.is_asleep(who))
"""
from __future__ import annotations

import argparse
import json
import urllib.request

ACUTE_MAX = 0.20        # a night scored 0 scales the day by 0.80
CHRONIC_MAX = 0.15      # sleep debt at or above the reference scales it by a further 0.85
DEBT_REF_HOURS = 10.0


def factor_from(last_night_score: float | None, debt_hours: float) -> float:
    f = 1.0 - CHRONIC_MAX * min(max(debt_hours, 0.0), DEBT_REF_HOURS) / DEBT_REF_HOURS
    if last_night_score is not None:
        f *= 1.0 - ACUTE_MAX * (1.0 - min(max(last_night_score, 0.0), 100.0) / 100.0)
    return round(min(1.0, max(0.0, f)), 4)


def report(base: str, token: str, body: dict) -> dict:
    req = urllib.request.Request(f"{base}/api/sleep", method="PUT", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8765")
    p.add_argument("--token", default="")
    p.add_argument("--who", default=None)
    p.add_argument("--score", type=float, default=None, help="last night's sleep quality, 0-100")
    p.add_argument("--debt-hours", type=float, default=0.0)
    p.add_argument("--asleep", action="store_true")
    p.add_argument("--awake", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print the factor without contacting the server")
    a = p.parse_args()
    body: dict = {"who": a.who}
    if a.asleep or a.awake:
        body["asleep"] = bool(a.asleep)
    if a.score is not None or a.debt_hours:
        body["factor"] = factor_from(a.score, a.debt_hours)
    print("reporting", body)
    if not a.dry_run:
        print(report(a.base, a.token, body))
