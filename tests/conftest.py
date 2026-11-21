"""Shared fixtures: every test gets its own database file, default settings and a fake clock."""
from __future__ import annotations

import os

import pytest

from kitchenette import art, clock as clock_mod, config, db, dex, fridge, notify, play, recipes, sleep, vendor

T0 = 1_800_000_000.0     # 2027-01-15 17:00 in Asia/Tokyo
DAY = 86400.0
A = "aster"              # two role ids used throughout
B = "birch"


HOME_EARN = {"write_diary": "日记", "write_excerpt": "书摘", "write_travelogue": "游记"}
HOME_EARN_HINT = "写成一篇日记、书摘或游记"


def earn_rules() -> None:
    """Switch on an example of "what earns a coupon" (none is configured out of the box)."""
    config.override(coupons_earn=dict(HOME_EARN), coupons_earn_hint=HOME_EARN_HINT)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Fresh settings pointing at a database under tmp_path; nothing leaks between tests, and
    nothing leaks in: a kitchenette.toml in the directory pytest was started from, or
    KITCHENETTE_* variables in the shell, are not read."""
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", str(tmp_path / "no-such-kitchenette.toml"))
    for name in [n for n in os.environ if n.startswith(config.ENV_PREFIX)]:
        monkeypatch.delenv(name)
    s = config.Settings()
    s.server_db_path = str(tmp_path / "kitchen.db")
    s.server_timezone = "Asia/Tokyo"       # receipts quote clock times; pin the zone
    s.art_dir = str(tmp_path / "art")
    # The tests written before the upgrade check the kitchen word for word as it was: there every
    # upgrade switch is off. Tests of the upgrade switch on what they need (play_on below);
    # test_play_defaults checks the out-of-the-box defaults.
    for key in play.KEYS:
        setattr(s, f"play_{key}", False)
    config.use(s)
    db.forget()
    fridge._kinds_cache.clear()
    clock_mod.reset()
    notify.set_notifier(None)
    sleep.set_asleep_hook(None)
    sleep.set_factor_hook(None)
    art.set_provider(None)
    dex.set_drawer(None)
    recipes.set_weather_provider(None)
    vendor.set_wallet(None)
    vendor.set_talker(None)
    yield
    clock_mod.reset()


@pytest.fixture()
def clock(monkeypatch):
    """A clock the test moves by hand: clock["now"] += seconds."""
    state = {"now": T0}
    monkeypatch.setattr(clock_mod, "now", lambda: state["now"])
    return state


@pytest.fixture()
def frozen(monkeypatch):
    """Wall time pinned at T0; the clock then only moves through clock.advance / fast_forward."""
    monkeypatch.setattr(clock_mod.time, "time", lambda: T0)
    return clock_mod


def set_coupons(who: str, n: int) -> None:
    conn = fridge._conn()
    conn.execute("INSERT INTO coupons (who, count) VALUES (?,?)"
                 " ON CONFLICT(who) DO UPDATE SET count=excluded.count", (who, n))
    conn.commit()
    conn.close()


def qty(who: str, item_id: str) -> int:
    return sum(b["qty"] for b in fridge.overview(who)["items"] if b["item_id"] == item_id)


def notes(who: str, kind: str | None = None) -> list[dict]:
    return [n for n in notify.pending(who) if kind is None or n["kind"] == kind]


# ── bracket markers: run a reply through the executor and look at the receipts ──

_receipts: list = []


@pytest.fixture()
def marker_env(clock):
    _receipts.clear()
    yield None
    _receipts.clear()


def run_reply(text: str, who: str = A, message_id: str | None = None) -> str:
    """Execute the markers in one reply; returns the message id (pass it again to replay)."""
    import uuid

    from kitchenette import inline
    message_id = message_id or uuid.uuid4().hex
    _receipts.extend(inline.execute(who, text, message_id))
    return message_id


def receipts(ok: bool) -> list[dict]:
    return [{"marker": r.marker, "hint": r.text} for r in _receipts if r.ok == ok]


def play_on(*keys: str, everything: bool = False) -> None:
    """Switch upgrade features on (with everything=True: all seventeen)."""
    config.override(**{f"play_{k}": True for k in (play.KEYS if everything else keys)})
