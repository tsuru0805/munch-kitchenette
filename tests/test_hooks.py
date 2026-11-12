"""The plug-in points: notifications (queue and webhook), sleep, round settlement, coupons,
the rest/work tables, settings, and the REST surface a page uses."""
from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kitchenette import clock as clock_mod, config, fridge, kitchen, menu, notify, service, sleep, stamina, tools
from kitchenette.api import create_app
from kitchenette.texts import t

from conftest import A, B, DAY, T0, notes

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _example(name: str):
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _client() -> TestClient:
    return TestClient(create_app(scheduler=False, with_mcp=False))


class Recorder:
    """A Notifier that remembers what it was asked to deliver."""

    def __init__(self, result=notify.SENT):
        self.result, self.calls = result, []

    def deliver(self, who, batch):
        self.calls.append((who, [n["text"] for n in batch]))
        return self.result


# ── queue ───────────────────────────────────────────────────────────────

def test_queue_hands_each_note_over_once(clock):
    notify.emit(A, notify.KIND_HUNGRY, "一", key="k1")
    notify.emit(A, notify.KIND_WORM, "二")
    assert notify.emit(A, notify.KIND_HUNGRY, "一 again", key="k1") is None      # same key: dropped
    assert [n["text"] for n in notify.pending(A)] == ["一", "二"]
    assert [n["text"] for n in notify.take(A)] == ["一", "二"]
    assert notify.take(A) == [] and notify.pending(B) == []


def test_notes_tool_and_rest_take_the_same_queue(clock):
    c = _client()
    notify.emit(A, notify.KIND_COUPON, payload={"count": "1"})
    assert c.get("/api/notes", params={"who": A}).json()["notes"][0]["kind"] == "fridge.coupon"
    assert t("note_coupon", n=1) == "用户给了你一张买菜券(现在 1 张)。"
    assert tools.call("kitchen_notes", {}, A).text == "用户给了你一张买菜券(现在 1 张)。"
    assert c.post("/api/notes/take", json={"who": A}).json() == {"notes": [], "text": ""}
    assert tools.call("kitchen_notes", {}, A).text == "没有新的话。"


def test_mode_none_records_nothing(clock):
    config.override(notify_mode="none")
    assert notify.emit(A, notify.KIND_HUNGRY, "x") is None and notify.pending(A) == []
    fridge.buy_her(A, ["egg"])
    kitchen._exec_cook(None, {"dish": "煎蛋", "minutes": 5, "ingredients": ["鸡蛋"]}, A)
    clock["now"] += 400
    service.scan(A)
    assert notify.pending(A) == [] and kitchen.due_work(A) == []          # served and settled, silently


# ── push ────────────────────────────────────────────────────────────────

def test_push_delivers_once_per_role_and_only_retries_what_was_not_sent(clock):
    rec = Recorder(notify.NOT_SENT)
    notify.set_notifier(rec)
    notify.emit(A, notify.KIND_HUNGRY, "一")
    notify.emit(A, notify.KIND_WORM, "二")
    notify.emit(B, notify.KIND_WORM, "三")
    assert notify.flush() == {"pushed": 0, "deferred": 0, "failed": 3}
    rec.result = notify.SENT
    assert notify.flush()["pushed"] == 3
    assert rec.calls[-2:] == [(A, ["一", "二"]), (B, ["三"])]
    assert notify.flush() == {"pushed": 0, "deferred": 0, "failed": 0}      # nothing is sent twice
    rec.result = notify.UNKNOWN
    notify.emit(A, notify.KIND_WORM, "四")
    assert notify.flush()["pushed"] == 1 and notify.flush()["pushed"] == 0  # unclear = not repeated


def test_quiet_hours_hold_the_push_until_they_end(clock):
    rec = Recorder()
    notify.set_notifier(rec)
    config.override(notify_quiet_hours=["02:00-06:30", "23:30-00:30"])
    midnight = T0 - (T0 % DAY) + 15 * 3600                    # 00:00 in Asia/Tokyo
    for hour, quiet in ((0.2, True), (1.0, False), (3.0, True), (6.4, True), (6.6, False), (23.6, True)):
        assert notify.in_quiet_hours(midnight + hour * 3600) is quiet
    clock["now"] = midnight + 3 * 3600
    notify.emit(A, notify.KIND_HUNGRY, "出锅了")
    assert notify.flush() == {"pushed": 0, "deferred": 1, "failed": 0} and rec.calls == []
    clock["now"] = midnight + 7 * 3600
    assert notify.flush()["pushed"] == 1 and rec.calls == [(A, ["出锅了"])]


def test_no_quiet_hours_means_told_at_once_even_at_night(clock):
    rec = Recorder()
    notify.set_notifier(rec)
    clock["now"] = T0 - (T0 % DAY) + 18 * 3600                # 03:00 in Asia/Tokyo
    notify.emit(A, notify.KIND_HUNGRY, "出锅了")
    assert notify.flush()["pushed"] == 1


def test_sleeping_role_is_not_pushed_until_it_wakes(clock):
    rec = Recorder()
    notify.set_notifier(rec)
    notify.emit(A, notify.KIND_HUNGRY, "出锅了")
    sleep.report(A, asleep=True)
    assert notify.flush()["pushed"] == 1                      # respect_sleep is off by default
    config.override(notify_respect_sleep=True)
    notify.emit(A, notify.KIND_HUNGRY, "又一锅")
    notify.emit(B, notify.KIND_HUNGRY, "别人的")
    out = notify.flush()
    assert out == {"pushed": 1, "deferred": 1, "failed": 0} and rec.calls[-1] == (B, ["别人的"])
    sleep.report(A, asleep=False)
    assert notify.flush()["pushed"] == 1 and rec.calls[-1] == (A, ["又一锅"])
    # asleep "until" a time ends by itself; a hook, when set, has the last word
    sleep.report(A, asleep=True, until=clock["now"] + 3600)
    assert sleep.is_asleep(A) and not sleep.is_asleep(A, clock["now"] + 3601)
    sleep.set_asleep_hook(lambda who, now: who == B)
    assert sleep.is_asleep(B) and not sleep.is_asleep(A)
    sleep.set_asleep_hook(lambda who, now: 1 / 0)
    assert sleep.is_asleep(A) is False                        # unreadable = awake


def test_webhook_notifier_posts_to_the_example_receiver(clock):
    receiver = _example("notify_webhook_receiver")
    got = []
    receiver.deliver = lambda who, text, batch: got.append((who, text, [n["kind"] for n in batch]))
    server = HTTPServer(("127.0.0.1", 0), receiver.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/kitchen"
        config.override(notify_mode="both", notify_webhook_url=url)
        c = _client()
        assert c.post("/api/fridge/buy", json={"who": A, "items": ["egg"]}).status_code == 200
        assert got == [(A, "用户给你买了菜,放进冰箱了:鸡蛋×6。", ["fridge.bought"])]
        assert notify.pending(A) == []                        # pushed = handed over: not offered again
    finally:
        server.shutdown()
    config.override(notify_webhook_url="http://127.0.0.1:9/nowhere")
    notify.emit(A, notify.KIND_WORM, "x")
    assert notify.flush()["failed"] == 1                      # unreachable: kept for the next scan


def test_webhook_carries_its_bearer_token(clock):
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["auth"] = self.headers.get("Authorization")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(500 if seen.get("fail") else 200)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        n = notify.WebhookNotifier(f"http://127.0.0.1:{server.server_address[1]}/", "tok")
        assert n.deliver(A, [{"id": 1, "kind": "hungry", "text": "饿了"}]) == notify.SENT
        assert seen["auth"] == "Bearer tok" and seen["body"]["who"] == A and seen["body"]["text"] == "饿了"
        seen["fail"] = True
        assert n.deliver(A, [{"id": 1, "kind": "hungry", "text": "饿了"}]) == notify.NOT_SENT
    finally:
        server.shutdown()


# ── hunger ──────────────────────────────────────────────────────────────

def test_hungry_note_is_sent_once_and_rearmed_after_eating(clock):
    fridge.buy_her(A, ["apple"])
    service.scan(A)
    assert notes(A, notify.KIND_HUNGRY) == []
    clock["now"] += 4 * 3600
    service.scan(A)
    service.scan(A)
    got = notes(A, notify.KIND_HUNGRY)
    assert len(got) == 1 and got[0]["text"] == "【厨房·非用户发言】你有点饿了(饱食度低于 30%)。冰箱里有:苹果×2。"
    assert fridge.turn_lines(A) == got[0]["text"]             # the per-turn line says the same
    fridge.fill(A, 60)
    service.scan(A)
    clock["now"] += 7 * 3600
    service.scan(A)
    assert len(notes(A, notify.KIND_HUNGRY)) == 2


# ── sleep debt ──────────────────────────────────────────────────────────

def test_sleep_debt_is_off_until_switched_on(clock):
    config.override(stamina_schedule=[0.8] * 24)
    sleep.report(A, factor=0.5)
    stamina.pulse(A, 0.0)
    stamina.pulse(B, 0.0)
    assert stamina.read(A, clock["now"] + 30 * 3600) == pytest.approx(0.8, abs=0.01)     # ignored
    config.override(stamina_sleep_debt=True)
    assert stamina.read(A, clock["now"] + 30 * 3600) == pytest.approx(0.4, abs=0.01)     # 0.8 x 0.5
    assert stamina.read(B, clock["now"] + 30 * 3600) == pytest.approx(0.8, abs=0.01)     # only who slept badly
    sleep.set_factor_hook(lambda who, now: 0.75)
    assert stamina.read(A, clock["now"] + 30 * 3600) == pytest.approx(0.6, abs=0.01)     # a hook wins
    for broken in (lambda who, now: float("nan"), lambda who, now: 1 / 0):
        sleep.set_factor_hook(broken)
        assert sleep.factor(A) == 1.0                                                   # never breaks stamina
    sleep.set_factor_hook(lambda who, now: 7)
    assert sleep.factor(A) == 1.0
    with pytest.raises(ValueError):
        sleep.report(A, factor=1.5)


def test_sleep_debt_example_formula_and_rest_endpoint(clock):
    ex = _example("sleep_debt")
    assert ex.factor_from(None, 0) == 1.0 and ex.factor_from(100, 0) == 1.0
    assert ex.factor_from(0, 0) == 0.8 and ex.factor_from(None, 10) == 0.85 and ex.factor_from(None, 99) == 0.85
    assert ex.factor_from(0, 10) == pytest.approx(0.68)
    c = _client()
    assert c.put("/api/sleep", json={"who": A, "factor": ex.factor_from(55, 4), "asleep": True}).json() == {
        "who": A, "asleep": True, "until": None, "factor": 0.8554}
    assert c.get("/api/sleep", params={"who": B}).json()["factor"] == 1.0
    assert c.put("/api/sleep", json={"who": A, "factor": 2}).status_code == 400


# ── rounds: rest, work, coupons ─────────────────────────────────────────

def test_round_costs_work_once_per_kind_and_rest_restores(clock):
    config.override(stamina_schedule=[0.5] * 24, stamina_init=0.5,
                    stamina_work={"send_email": "errand", "file_report": "errand", "web_search": "research"},
                    stamina_rest={"eat": 0.10, "take_bath": 0.08, "nap": 0.30})
    assert stamina.round_delta([]) == (0.0, "")
    assert stamina.round_delta(["just_talking"]) == (0.0, "")
    assert stamina.round_delta(["send_email"]) == (pytest.approx(-0.06), "work")
    assert stamina.round_delta(["send_email", "file_report"])[0] == pytest.approx(-0.06)       # same kind
    assert stamina.round_delta(["send_email", "web_search"])[0] == pytest.approx(-0.10)        # two kinds
    assert stamina.round_delta(["srv__eat", "take_bath"]) == (pytest.approx(0.18), "rest")
    assert stamina.round_delta(["eat", "take_bath", "nap"])[0] == pytest.approx(0.25)          # capped
    assert stamina.round_delta(["send_email", "eat"]) == (pytest.approx(0.04), "work+rest")
    config.override(stamina_work={f"t{i}": f"k{i}" for i in range(9)})
    assert stamina.round_delta([f"t{i}" for i in range(9)])[0] == pytest.approx(-0.20)         # capped


def test_settle_round_is_idempotent_and_grants_configured_coupons(clock):
    config.override(stamina_schedule=[0.5] * 24, stamina_init=0.5,
                    stamina_work={"web_search": "research"}, coupons_earn={"write_diary": "日记"})
    out = service.settle_round(A, ["web_search", "notes__write_diary", "write_poem"], round_id="r1")
    assert out["stamina"] == pytest.approx(0.44, abs=0.005) and not out["duplicate"]
    assert out["receipts"] == [{"kind": "coupon", "ok": True, "text": "得了一张买菜券(现在 1/3)。"}]
    again = service.settle_round(A, ["web_search", "notes__write_diary"], round_id="r1")
    assert again["duplicate"] and again["receipts"] == [] and again["stamina"] == pytest.approx(0.44, abs=0.005)
    assert fridge.overview(A)["coupons"]["count"] == 1
    assert any(l["text"] == "写了一篇日记,得一张买菜券" for l in fridge.overview(A)["log"])
    failed = service.settle_round(A, [{"name": "write_diary", "is_error": True}], round_id="r2")
    assert failed["receipts"] == [] and fridge.overview(A)["coupons"]["count"] == 1


def test_coupon_hint_follows_the_setting(clock):
    config.override(coupons_earn_hint="写成一篇日记")
    assert tools.call("kitchen_buy", {"items": ["番茄"]}, A).text == "没买成:买菜券用完了(现在 0 张)。写成一篇日记就得一张。"
    config.override(coupons_earn_hint="")
    assert tools.call("kitchen_buy", {"items": ["番茄"]}, A).text == "没买成:买菜券用完了(现在 0 张)。买菜券由用户给。"
    fridge.buy_her(A, ["tomato"])
    short = tools.call("kitchen_cook", {"dish": "炒蛋", "minutes": 5, "ingredients": ["鸡蛋"]}, A).text
    assert short == "没开成:冰箱里不够——鸡蛋(要 1,有 0)。买菜券现在 0 张。买菜券由用户给。"
    config.override(coupons_earn={"write_diary": "日记"})          # something earns one, nothing to hint
    assert tools.call("kitchen_buy", {"items": ["番茄"]}, A).text == "没买成:买菜券用完了(现在 0 张)。"


def test_own_tools_settle_as_they_are_called_one_round_at_a_time(clock):
    config.override(stamina_schedule=[0.5] * 24, stamina_init=0.5)
    fridge.buy_her(A, ["egg"])
    for _ in range(3):
        tools.call("kitchen_status", {}, A)
    tools.call("kitchen_cook", {"dish": "煎蛋", "minutes": 5, "ingredients": ["鸡蛋"]}, A)
    assert stamina.read(A) == pytest.approx(0.44, abs=0.005)       # four kitchen calls, one round
    clock["now"] += 600
    tools.call("kitchen_status", {}, A)
    assert stamina.read(A) == pytest.approx(0.385, abs=0.01)       # a later call is a new round
    # reporting the same tools through the round endpoint does not charge them twice
    before = stamina.read(A)
    assert service.settle_round(A, ["kitchen_cook", "kitchen_status"])["stamina"] == pytest.approx(before, abs=0.001)
    # with auto-accounting off, tool calls are free until a round is reported
    config.override(stamina_auto_account=False)
    clock["now"] += 600
    before = stamina.read(A)
    tools.call("kitchen_status", {}, A)
    assert stamina.read(A) == pytest.approx(before, abs=0.001)
    assert service.settle_round(A, ["kitchen_status"])["stamina"] == pytest.approx(before - 0.06, abs=0.005)


# ── settings ────────────────────────────────────────────────────────────

def test_settings_layer_defaults_file_then_environment(tmp_path):
    f = tmp_path / "k.toml"
    f.write_text('[server]\nport = 9001\ntimezone = "Europe/Paris"\n\n[fridge]\ncoupon_max = 5\n\n'
                 '[stamina.rest]\nnap = 0.2\n', encoding="utf-8")
    s = config.build(f, env={"KITCHENETTE_SERVER_PORT": "9002", "KITCHENETTE_SATIETY_ENABLED": "false",
                             "KITCHENETTE_ROLES_ALLOWED": '["a", "b"]'})
    assert (s.server_port, s.server_timezone, s.fridge_coupon_max) == (9002, "Europe/Paris", 5)
    assert s.stamina_rest["nap"] == 0.2 and s.stamina_rest["eat"] == 0.10      # tables merge key by key
    assert s.satiety_enabled is False and s.roles_allowed == ["a", "b"]
    assert config.build(None, env={}).fridge_coupon_max == 3
    for bad, needle in (('[fridge]\ncoupon_maxx = 1\n', "unknown config key"),
                        ('[nope]\nx = 1\n', "unknown config section"),
                        ('[stamina]\nschedule = [0.5, 0.5]\n', "24 values"),
                        ('[notify]\nmode = "webhook"\n', "webhook_url")):
        f.write_text(bad, encoding="utf-8")
        with pytest.raises(ValueError, match=needle):
            config.build(f, env={})


def test_every_example_settings_file_loads():
    files = sorted(EXAMPLES.glob("*.toml")) + sorted((EXAMPLES / "schedules").glob("*.toml"))
    assert len(files) >= 9
    for f in files:
        config.build(f, env={})
    quiet = config.build(EXAMPLES / "worms-and-quiet.toml", env={})
    assert quiet.notify_quiet_hours == ["02:00-06:30"] and quiet.notify_respect_sleep is True
    assert set(config.build(EXAMPLES / "coupons.toml", env={}).coupons_earn) == {
        "write_diary", "write_excerpt", "write_travelogue"}
    off = config.build(EXAMPLES / "switches.toml", env={})
    assert off.stamina_enabled is False and off.satiety_enabled is False


def test_numbers_can_be_changed_in_one_place(clock):
    config.override(fridge_coupon_max=1, fridge_buy_max_items=2, satiety_dizzy_hours=1.0, kitchen_minutes_max=30)
    fridge.grant_coupon_by_her(A)
    with pytest.raises(fridge.FridgeError) as e:
        fridge.grant_coupon_by_her(A)
    assert e.value.text == "券已经满 1 张了。"
    assert "一张券一次最多买 2 样" in tools.call("kitchen_buy", {"items": ["番茄", "鸡蛋", "牛奶"]}, A).text
    assert "minutes 要在 1–30 之间" in tools.call("kitchen_cook", {"dish": "汤", "minutes": 31, "ingredients": ["鸡蛋"]}, A).text
    assert fridge.make_dizzy(A, "坏汤") == clock["now"] + 3600


def test_timezone_setting_moves_the_clock_times_in_receipts(clock):
    config.override(server_timezone="UTC", server_timezone_label="UTC ")
    assert clock_mod.hm(T0) == "08:00"
    r = tools.call("snack_eat", {"name": "布丁"}, A).text
    assert r.endswith("今日布丁 1/3 份,UTC 04:00 重置。")
    config.override(server_timezone="Asia/Tokyo", server_timezone_label="")
    assert clock_mod.hm(T0) == "17:00"


# ── REST for the page ───────────────────────────────────────────────────

def test_menu_rest_post_patch_feed_delete(clock):
    c = _client()
    assert c.post("/api/menu", json={"dish": "", "by": "human", "for_who": A}).status_code == 400
    row = c.post("/api/menu", json={"dish": "三鲜水饺", "by": "human", "for_who": A, "note": "趁热"})
    assert row.status_code == 201
    rid = row.json()["id"]
    assert notes(A, notify.KIND_MENU_POSTED)[0]["text"] == "用户刚在菜单上挂了一道『三鲜水饺』(备注:趁热)"
    assert [r["dish"] for r in c.get("/api/menu", params={"pending": "1", "for_who": A}).json()] == ["三鲜水饺"]
    assert c.get("/api/menu", params={"pending": "1", "for_who": B}).json() == []
    assert c.patch(f"/api/menu/{rid}", json={"dish": "三鲜水饺🥟", "note": "慢慢吃"}).json()["note"] == "慢慢吃"
    assert c.patch(f"/api/menu/{rid}", json={}).status_code == 400
    assert c.patch("/api/menu/nope", json={"note": "x"}).status_code == 404
    sat = fridge.satiety(A)
    fed = c.post(f"/api/menu/{rid}/feed")
    assert fed.status_code == 200 and fed.json()["outcome"] == "her"
    assert notes(A, notify.KIND_MENU_FED)[0]["text"] == "用户刚把菜单上那道『三鲜水饺🥟』喂给你吃了(备注:慢慢吃)"
    assert fridge.satiety(A) == pytest.approx(sat + 40) and c.post(f"/api/menu/{rid}/feed").status_code == 409
    assert c.patch(f"/api/menu/{rid}", json={"eaten_at": None, "if_pending": True}).status_code == 409
    assert c.delete(f"/api/menu/{rid}").json() == {"deleted": rid} and c.delete(f"/api/menu/{rid}").status_code == 404
    own = menu.add("煎蛋", A, A)                                   # the role's own dish: nothing to announce
    assert own["by"] == A and len(notes(A, notify.KIND_MENU_POSTED)) == 1


def test_snack_rest_feed_caps_and_note(clock):
    c = _client()
    shelf = c.get("/api/snacks", params={"who": A}).json()
    assert [s["id"] for s in shelf["snacks"]] == ["coffee", "jelly", "pudding", "chocolate", "cookie"]
    fed = c.post("/api/snacks/eat", json={"who": A, "snack": "coffee", "variant": "latte"}).json()
    assert fed["result"]["name"] == "拿铁咖啡" and fed["notified"] is True and fed["result"]["energy_delta"] == 0.05
    assert notes(A, notify.KIND_SNACK_FED)[0]["text"] == "用户刚从常驻零食里喂你吃了一份『拿铁咖啡』(中档,体力 +0.05)"
    assert c.post("/api/snacks/eat", json={"who": A, "snack": "coffee"}).status_code == 400
    assert c.put("/api/snacks/caps", json={"who": A, "caps": {"coffee": 1}}).json()["snacks"][0]["cap"] == 1
    over = c.post("/api/snacks/eat", json={"who": A, "snack": "coffee", "variant": "mocha"})
    assert over.status_code == 409 and over.json()["detail"]["message"].startswith("今天的咖啡已经 1/1 份了")
    assert tools.call("snack_eat", {"name": "拿铁"}, A).text.startswith("没吃成:今日咖啡已吃 1/1 份(含用户在 App 喂的)")
    assert c.put("/api/snacks/caps", json={"who": A, "caps": {"coffee": 99}}).status_code == 400
    assert tools.call("snack_eat", {"name": "咖啡"}, A).text == "咖啡要写口味:浓缩/美式/拿铁/摩卡"
    assert "常驻零食里没有「辣条」" in tools.call("snack_eat", {"name": "辣条"}, A).text


def test_turn_lines_stamina_inline_and_dev_clock_endpoints(clock):
    c = _client()
    lines = c.get("/api/turn-lines", params={"who": A}).json()
    assert lines["kitchen"] is None and lines["body"] == "[你的身体 17:00 | 体力 0.70]"
    assert c.get("/api/stamina", params={"who": A}).json()["energy"] == 0.7
    fridge.grant_coupon_by_her(A)
    got = c.post("/api/inline", json={"who": A, "text": "去买菜。\n[买菜 番茄]\n回来了。", "message_id": "m1"}).json()
    assert got["stripped"] == "去买菜。\n回来了。" and got["receipts"][0]["ok"] is True
    assert got["receipts"][0]["rendered"].startswith("刚才正文里那条『买菜』:买好了:番茄×3")
    assert c.post("/api/dev/clock", json={"advance_seconds": 60}).status_code == 404       # off by default
    assert c.post("/api/scan").status_code == 200
    assert c.get("/api/roles").json() == {"default": "companion", "roles": [A, "companion"]}
    earned = c.post("/api/coupons/earn", json={"who": A, "source": "日记", "key": "d1"}).json()
    assert earned["granted"] is True and earned["text"] == "得了一张买菜券(现在 1/3)。"
    assert c.post("/api/coupons/earn", json={"who": A, "source": "日记", "key": "d1"}).json()["granted"] is False


def test_dev_clock_walks_time_when_switched_on(frozen):
    config.override(server_dev_clock=True)
    c = _client()
    fridge.buy_her(A, ["egg"])
    tools.call("kitchen_cook", {"dish": "煎蛋", "minutes": 5, "ingredients": ["鸡蛋"]}, A)
    out = c.post("/api/dev/clock", json={"advance_seconds": 36 * 3600}).json()
    assert out["offset"] == 36 * 3600
    assert menu.list_rows(A, pending=True)[0]["note"].endswith("长虫了")     # served, put up, left overnight
    assert c.post("/api/dev/clock", json={"reset": True}).json()["offset"] == 0


# ── wording ─────────────────────────────────────────────────────────────

def test_example_art_provider_draws_three_pngs():
    from kitchenette import art
    ex = _example("art_provider")
    k = fridge.add_kind("柿子", "fruit")
    art.set_provider(ex.draw)
    assert art.run(k["id"]) == "ready"
    assert fridge.kind(k["id"])["art"]["sizes"] == {s: [ex.SIZE, ex.SIZE] for s in art.STATES}
    config.override(art_provider="examples.art_provider:draw")
    assert art.enabled()
