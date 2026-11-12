"""Things found by someone installing from the documents alone: each one a regression test."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kitchenette import config, fridge, inline, kitchen, menu, notify, potion, service, stamina, tools
from kitchenette.api import create_app
from kitchenette.texts import t

from conftest import A, B, DAY, earn_rules, notes

ROOT = Path(__file__).resolve().parent.parent


def _client() -> TestClient:
    return TestClient(create_app(scheduler=False, with_mcp=False))


def _serve(clock, who, dish):
    fridge.buy_her(who, ["egg"])
    assert not tools.call("kitchen_cook", {"dish": dish, "minutes": 5, "ingredients": ["鸡蛋"]}, who).is_error
    clock["now"] += 301


# ── 1: a tossed dish is really gone ─────────────────────────────────────

def test_tossed_wormy_dish_leaves_the_menu_at_once_and_cannot_be_eaten(clock):
    _serve(clock, A, "煎蛋")
    service.scan(A)
    clock["now"] += 2 * DAY
    service.scan(A)
    assert menu.list_rows(A, pending=True)[0]["note"].endswith("长虫了")
    assert tools.call("kitchen_toss", {"what": "煎蛋"}, A).text == "扔掉了:桌上长虫的『煎蛋』。"
    assert menu.list_rows(A, pending=True) == []                       # no scan in between
    assert "煎蛋" not in tools.call("read_menu", {}, A).text.split("🍪")[0]
    sat = fridge.satiety(A)
    res = tools.call("eat", {"meal": "煎蛋"}, A)
    assert res.is_error and res.text == "没吃成:桌上没有煎蛋,想吃得先做。"
    assert fridge.satiety(A) == pytest.approx(sat) and fridge.overview(A)["dizzy"] is None
    conn = kitchen._conn()
    assert conn.execute("SELECT worm_state FROM cook_sessions").fetchone()[0] == "gone"
    conn.close()
    assert tools.call("kitchen_toss", {"what": "煎蛋"}, A).is_error      # nothing left to toss


# ── 2: a pushed note is not handed over a second time ───────────────────

def test_pushed_note_is_not_offered_again_by_the_notes_tool(clock):
    class Sent:
        calls = []

        def deliver(self, who, batch):
            self.calls.append([n["text"] for n in batch])
            return notify.SENT
    config.override(notify_mode="webhook", notify_webhook_url="http://127.0.0.1:9/unused")
    notify.set_notifier(Sent())
    _serve(clock, A, "煎蛋")
    service.scan_all()
    assert len(Sent.calls) == 1 and "『煎蛋』出锅了" in Sent.calls[0][0]
    assert tools.call("kitchen_notes", {}, A).text == t("notes_empty")
    assert notify.take(A) == [] and notify.pending(A) == []
    service.scan_all()
    assert len(Sent.calls) == 1


def test_in_both_mode_whichever_comes_first_hands_the_note_over(clock):
    class Down:
        def deliver(self, who, batch):
            return notify.NOT_SENT
    config.override(notify_mode="both", notify_webhook_url="http://127.0.0.1:9/unused")
    notify.set_notifier(Down())
    notify.emit(A, notify.KIND_HUNGRY, "饿了")
    assert notify.flush()["failed"] == 1
    assert [n["text"] for n in notify.take(A)] == ["饿了"]             # the queue got there first
    assert notify.flush() == {"pushed": 0, "deferred": 0, "failed": 0}


# ── 3: a potion amount needs a real potion row ──────────────────────────

def test_registering_a_potion_for_a_row_that_is_not_there_is_refused(clock):
    c = _client()
    bad = c.post("/api/potions", json={"who": A, "menu_row_id": "ghost", "pct": 30})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_row"
    assert bad.json()["detail"]["message"] == "菜单上没有这一行,或者它不是还挂着的精力补充药剂。"
    assert potion.pending(A) == []
    dish = menu.add("番茄炒蛋", "human", A)
    other = menu.add("精力补充药剂", "human", B)
    eaten = menu.add("精力补充药剂", "human", A)
    menu.mark_eaten(eaten["id"])
    for rid in (dish["id"], other["id"], eaten["id"]):                 # not a potion / not this role's / gone
        with pytest.raises(potion.PotionError) as e:
            potion.register_potion(A, rid, 30)
        assert e.value.code == "bad_row"
    assert potion.pending(A) == [] and potion.pending(B) == []


def test_hanging_a_potion_in_one_step_is_all_or_nothing(clock):
    c = _client()
    got = c.post("/api/potions/hang", json={"who": A, "pct": 30, "memo": "慢慢喝"}).json()
    assert got["ok"] and got["row"]["dish"] == "精力补充药剂" and got["row"]["note"] == "回 30% 体力 · 慢慢喝"
    assert got["potion"]["menu_row_id"] == got["row"]["id"] and got["potion"]["pct"] == 30
    assert notes(A, notify.KIND_MENU_POSTED)[0]["text"] == "用户刚在菜单上挂了一道『精力补充药剂』(备注:回 30% 体力 · 慢慢喝)"
    drunk = tools.call("eat", {"meal": "精力补充药剂"}, A)
    assert not drunk.is_error and drunk.text.startswith("喝了精力补充药剂。体力 +30%")
    bad = c.post("/api/potions/hang", json={"who": A, "pct": 0})
    assert bad.status_code == 400 and menu.list_rows(A, pending=True) == []     # refused: no row left behind
    config.override(stamina_enabled=False)
    assert c.post("/api/potions/hang", json={"who": A, "pct": 30}).status_code == 409
    assert menu.list_rows(A, pending=True) == []


# ── 4: the note is there the moment the pot is seen as served ───────────

def test_served_note_and_menu_row_exist_as_soon_as_the_role_looks(clock):
    _serve(clock, A, "煎蛋")
    status = tools.call("kitchen_status", {}, A).text                  # no scan has run
    assert "最近出锅" in status and "煎蛋" in status
    assert [r["dish"] for r in menu.list_rows(A, pending=True)] == ["煎蛋"]
    got = tools.call("kitchen_notes", {}, A).text
    assert "『煎蛋』出锅了(共 5 分钟)。火候刚好。已挂到你的菜单上。" in got
    service.scan(A)
    assert notify.pending(A) == []                                     # and the scan adds no second one


@pytest.mark.parametrize("path", ["/api/notes", "/api/kitchen", "/api/menu"])
def test_served_note_is_written_when_a_page_reads_first(clock, path):
    _serve(clock, A, "煎蛋")
    c = _client()
    params = {"for_who": A, "pending": "1"} if path == "/api/menu" else {"who": A}
    assert c.get(path, params=params).status_code == 200
    assert len(notes(A, notify.KIND_SERVED)) == 1 and len(menu.list_rows(A, pending=True)) == 1


def test_notes_tool_alone_brings_the_served_note(clock):
    _serve(clock, A, "煎蛋")
    assert "『煎蛋』出锅了" in tools.call("kitchen_notes", {}, A).text


# ── 5: every refusal is an error ────────────────────────────────────────

def test_snack_refusals_are_errors_like_every_other_refusal(clock):
    from kitchenette import snacks
    snacks.set_caps(A, {"pudding": 1})
    assert not tools.call("snack_eat", {"name": "布丁"}, A).is_error
    capped = tools.call("snack_eat", {"name": "布丁"}, A)
    assert capped.is_error and capped.text.startswith("没吃成:今日布丁已吃 1/1 份")
    assert tools.call("snack_eat", {"name": "辣条"}, A).is_error
    assert tools.call("snack_eat", {"name": "咖啡"}, A).is_error
    rec = inline.execute(A, "[零食 布丁]", "m1")[0]
    assert rec.ok is False and rec.rendered.startswith("刚才正文里那条『零食』没有执行成功(没吃成:今日布丁已吃 1/1 份")


# ── 6: a settings file lying around is not read by the tests ────────────

def test_tests_ignore_a_settings_file_in_the_current_directory(tmp_path, monkeypatch):
    (tmp_path / "kitchenette.toml").write_text('[fridge]\ncoupon_max = 9\n[roles]\ndefault = "someone"\n',
                                               encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert config.build(None, env={}).fridge_coupon_max == 3
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", "kitchenette.toml")      # what the server does
    assert config.build(None, env={}).fridge_coupon_max == 9


# ── 7: why no coupon was granted ────────────────────────────────────────

def test_coupon_earn_endpoint_says_why_nothing_was_granted(clock):
    c = _client()
    body = {"who": A, "source": "日记"}
    first = c.post("/api/coupons/earn", json={**body, "key": "d1"}).json()
    assert first == {"ok": True, "granted": True, "text": "得了一张买菜券(现在 1/3)。", "reason": ""}
    again = c.post("/api/coupons/earn", json={**body, "key": "d1"}).json()
    assert again == {"ok": False, "granted": False, "text": "", "reason": "duplicate"}
    c.post("/api/coupons/earn", json={**body, "key": "d2"})
    c.post("/api/coupons/earn", json={**body, "key": "d3"})
    full = c.post("/api/coupons/earn", json={**body, "key": "d4"}).json()
    assert full == {"ok": False, "granted": False, "text": "", "reason": "full"}


# ── 8, 9: wrong values are caught when the settings are read ────────────

BAD = [
    ('[fridge]\ncoupon_max = "五"\n', "[fridge] coupon_max", "expected a whole number", "要填一个整数"),
    ('[fridge]\ncoupon_max = -1\n', "[fridge] coupon_max", "must be 0 or more", "不能小于 0"),
    ('[fridge]\ncoupon_max = 2.5\n', "[fridge] coupon_max", "expected a whole number", "要填一个整数"),
    ('[server]\ntimezone = "Asia/Tokio"\n', "[server] timezone", "not a known time zone name", "不认识这个时区名"),
    ('[satiety]\nenabled = "no"\n', "[satiety] enabled", "expected true or false", "只能填 true 或 false"),
    ('[satiety]\ndecay_per_hour = -3\n', "[satiety] decay_per_hour", "must be 0 or more", "不能小于 0"),
    ('[server]\nport = 99999\n', "[server] port", "must be between 1 and 65535", "要在 1 到 65535 之间"),
    ('[kitchen]\nworm_day_hour = 24\n', "[kitchen] worm_day_hour", "must be between 0 and 23", "要在 0 到 23 之间"),
    ('[stamina]\ninit = 70\n', "[stamina] init", "must be between 0 and 1", "要在 0 到 1 之间"),
    ('[stamina]\nschedule = "night"\n', "[stamina] schedule", '"night-owl"', "只能填"),
    ('[stamina]\nschedule = [0.5, 0.5]\n', "[stamina] schedule", "24 values", "24 个数"),
    ('[stamina.rest]\neat = "多"\n', "[stamina] rest.eat", "expected a number", "要填一个数"),
    ('[fridge.category_days]\nleafy = 0\n', "[fridge] category_days.leafy", "must be 0.01 or more", "不能小于 0.01"),
    ('[fridge.shelf_days]\nlobster = 3\n', "[fridge.shelf_days] lobster", "not an ingredient", "不是清单里的食材"),
    ('[notify]\nquiet_hours = ["2点到6点"]\n', "[notify] quiet_hours", "HH:MM-HH:MM", "时:分-时:分"),
    ('[notify]\nmode = "push"\n', "[notify] mode", '"queue"', "只能填"),
    ('[inline]\nenabled = "maybe"\n', "[inline] enabled", '"auto"', '"auto"'),
    ('[words]\nhuman_name = 7\n', "[words] human_name", "expected text", "要填文字"),
    ('[roles]\nallowed = "mika"\n', "[roles] allowed", "expected a list", "要填一个列表"),
    ('[stamina]\nenabled = true\n[stamina]\ninit = 0.5\n', "", "written twice", "写了两次"),
    ('[fridge]\ncoupon_max = \n', "", "is not valid TOML", "不是合法的 TOML"),
]


@pytest.mark.parametrize("text,where,en,zh", BAD)
def test_wrong_values_are_refused_with_the_place_and_what_to_write(tmp_path, text, where, en, zh):
    f = tmp_path / "bad.toml"
    f.write_text(text, encoding="utf-8")
    with pytest.raises(config.ConfigError) as e:
        config.build(f, env={})
    first, second = e.value.lines()
    assert first.startswith(str(f)) and second.startswith(str(f))
    assert where in first and en in first and where in second and zh in second


def test_wrong_environment_values_are_refused_too():
    for name, raw in (("KITCHENETTE_SATIETY_ENABLED", "nope"), ("KITCHENETTE_FRIDGE_COUPON_MAX", "five"),
                      ("KITCHENETTE_SERVER_TIMEZONE", "Mars/Olympus"), ("KITCHENETTE_FRIDGE_COUPON_MAX", "-2")):
        with pytest.raises(config.ConfigError) as e:
            config.build(None, env={name: raw})
        assert name in e.value.lines()[0]


@pytest.mark.parametrize("command", ["check", "serve"])
def test_command_line_reports_a_settings_mistake_in_two_lines_without_a_traceback(tmp_path, command):
    f = tmp_path / "kitchenette.toml"
    f.write_text('[fridge]\ncoupon_max = "五"\n', encoding="utf-8")
    run = subprocess.run([sys.executable, "-m", "kitchenette", command, "--config", str(f)],
                         capture_output=True, text=True, timeout=60, cwd=tmp_path)
    assert run.returncode == 2 and "Traceback" not in run.stderr and run.stdout == ""
    lines = run.stderr.strip().splitlines()
    assert len(lines) == 2
    assert lines[0] == f'{f}: [fridge] coupon_max = "五": expected a whole number (no quotes)'
    assert lines[1] == f'{f}：[fridge] coupon_max 填的是 "五"：要填一个整数，不加引号'


# ── 10: schedule by name or by 24 numbers ───────────────────────────────

@pytest.mark.parametrize("name", ["night-owl", "early-bird", "no-sleep"])
def test_schedule_can_be_named_and_matches_the_example_file(tmp_path, name):
    f = tmp_path / "k.toml"
    f.write_text(f'[stamina]\nenabled = true\nschedule = "{name}"\n', encoding="utf-8")
    named = config.build(f, env={}).stamina_schedule
    written_out = config.build(ROOT / "examples" / "schedules" / f"{name}.toml", env={}).stamina_schedule
    assert named == written_out and len(named) == 24
    assert config.build(None, env={"KITCHENETTE_STAMINA_SCHEDULE": name}).stamina_schedule == named
    config.override(stamina_schedule=name)
    assert config.get().stamina_schedule == named


# ── 11: tables merge; shelf life per item ───────────────────────────────

def test_changing_one_entry_of_a_table_keeps_the_others(tmp_path, clock):
    f = tmp_path / "k.toml"
    f.write_text('[fridge.category_days]\nleafy = 4\n\n[fridge.shelf_days]\negg = 10\n"番茄" = 9\n\n'
                 '[stamina.work]\nweb_search = "research"\nkitchen_status = ""\n\n[satiety.gain]\ngreat = 50\n',
                 encoding="utf-8")
    s = config.build(f, env={})
    assert s.fridge_category_days == {"leafy": 4, "meat": 3, "dairy": 5, "root": 7, "fruit": 7, "veg": 5,
                                      "staple_food": 5}
    assert s.stamina_work["web_search"] == "research" and s.stamina_work["kitchen_cook"] == "kitchen"
    assert s.satiety_gain["great"] == 50 and s.satiety_gain["ok"] == 40
    s.server_db_path = config.get().server_db_path
    s.server_timezone = "Asia/Tokyo"
    config.use(s)
    by_id = {c["id"]: c["shelf_days"] for c in fridge.catalog()}
    assert (by_id["spinach"], by_id["egg"], by_id["tomato"], by_id["milk"]) == (4, 10, 9, 5)
    fridge.buy_her(A, ["spinach", "egg"])
    assert fridge.freshness("spinach", clock["now"], clock["now"] + 1.9 * DAY) == fridge.FRESH
    assert stamina.round_delta(["kitchen_status"]) == (0.0, "")        # emptied: no longer work


# ── 12: categories by their Chinese name ────────────────────────────────

def test_new_ingredient_category_may_be_given_by_its_label(clock):
    c = _client()
    ok = c.post("/api/fridge/kinds", json={"name": "年糕", "category": "主食"})
    assert ok.status_code == 200 and ok.json()["kind"]["category"] == "staple_food"
    assert c.post("/api/fridge/kinds", json={"name": "柿子", "category": "fruit"}).status_code == 200
    bad = c.post("/api/fridge/kinds", json={"name": "糖果", "category": "零嘴"})
    assert bad.status_code == 400
    assert bad.json()["detail"] == ("没选是哪一类。可选:叶菜(leafy)、肉和海鲜(meat)、蛋奶豆(dairy)、根茎(root)、"
                                    "水果(fruit)、蔬菜(veg)、主食(staple_food)。")


# ── 13, 14, 15: the example file, check output, coupons off by default ──

def test_example_settings_do_not_pin_a_time_zone():
    s = config.build(ROOT / "examples" / "kitchenette.toml", env={})
    assert s.server_timezone == "" and s.server_timezone_label == ""
    assert s.coupons_earn == {} and s.coupons_earn_hint == ""


def test_check_prints_settings_the_way_the_file_is_written(tmp_path):
    out = config.dump(config.Settings())
    assert "[fridge]\ncoupon_max = 3\n" in out and "[fridge.category_days]\nleafy = 2\n" in out
    assert 'schedule = "night-owl"' in out and "fridge_coupon_max" not in out
    f = tmp_path / "again.toml"
    f.write_text(out, encoding="utf-8")                        # what it prints can be read back
    again = config.build(f, env={})
    assert config.dump(again) == out
    secret = config.Settings()
    secret.server_token = "hunter2"
    assert "hunter2" not in config.dump(secret) and 'token = "***"' in config.dump(secret)


def test_nothing_earns_a_coupon_until_it_is_configured(clock):
    assert config.get().coupons_earn == {} and config.get().coupons_earn_hint == ""
    assert tools.call("kitchen_buy", {"items": ["番茄"]}, A).text == "没买成:买菜券用完了(现在 0 张)。买菜券由用户给。"
    assert service.settle_round(A, ["write_diary"])["receipts"] == []
    earn_rules()
    assert service.settle_round(A, ["write_diary"])["receipts"][0]["text"] == "得了一张买菜券(现在 1/3)。"
    example = config.build(ROOT / "examples" / "coupons.toml", env={})
    assert example.coupons_earn == {"write_diary": "日记", "write_excerpt": "书摘", "write_travelogue": "游记"}
    assert example.coupons_earn_hint == "写成一篇日记、书摘或游记"


# ── 18: inline.enabled = "auto" ─────────────────────────────────────────

def test_auto_speaks_of_tools_until_a_reply_really_arrives(clock):
    config.override(inline_enabled="auto")
    assert t("menu_how") == "吃完哪道，用 eat 写上菜名，就会自动划掉。"
    assert "[吃 菜名]" not in kitchen.tool_schemas()[0]["description"]
    c = _client()
    menu.add("粥", "human", A)
    got = c.post("/api/inline", json={"who": A, "text": "好。\n[吃 粥]", "message_id": "m1"})
    assert got.status_code == 200 and got.json()["receipts"][0]["ok"] is True       # usable from the start
    assert t("menu_how") == "吃完哪道，回复里单独一行写 [吃 菜名]，就会自动划掉。"
    assert "(之后照常用 [吃 菜名] 吃掉)" in kitchen.tool_schemas()[0]["description"]


def test_auto_remembers_across_a_restart_and_is_per_database(clock, tmp_path):
    from kitchenette import db
    config.override(inline_enabled="auto")
    inline.execute(A, "没有方括号的一句话", "m1")
    db.forget()                                               # a new process: only the file remembers
    assert t("menu_how").startswith("吃完哪道，回复里单独一行写 [吃 菜名]")
    config.override(server_db_path=str(tmp_path / "other.db"))
    assert t("menu_how") == "吃完哪道，用 eat 写上菜名，就会自动划掉。"
    config.override(inline_enabled=True)
    assert t("menu_how").startswith("吃完哪道，回复里单独一行写 [吃 菜名]")
    config.override(inline_enabled=False)
    assert _client().post("/api/inline", json={"who": A, "text": "[吃 粥]"}).status_code == 409


# ── 19, 20: wording that follows a switch ───────────────────────────────

def test_snack_receipt_says_nothing_about_stamina_when_it_is_off(clock, monkeypatch):
    config.override(stamina_enabled=False)
    assert tools.call("snack_eat", {"name": "布丁"}, A).text == "吃了一份布丁(低档)。今日布丁 1/3 份,04:00 重置。"
    config.override(stamina_enabled=True)
    monkeypatch.setattr(stamina, "pulse", lambda *a, **k: None)          # on, but the write fails
    assert "这次体力没有变化(体力系统未生效或写入失败)" in tools.call("snack_eat", {"name": "曲奇"}, A).text


def test_cook_description_follows_how_notes_are_delivered():
    config.override(inline_enabled=True)

    def desc():
        return kitchen.tool_schemas()[0]["description"]
    assert config.get().notify_mode == "queue"
    assert "(之后照常用 [吃 菜名] 吃掉),到点会留一句话等你来取。开锅成功时" in desc()
    for mode in ("webhook", "both"):
        config.override(notify_mode=mode, notify_webhook_url="http://127.0.0.1:9/x")
        assert "(之后照常用 [吃 菜名] 吃掉),到点会叫醒你一次。开锅成功时" in desc()
    config.override(notify_mode="none")
    assert "(之后照常用 [吃 菜名] 吃掉)。开锅成功时" in desc()


# ── 24, 26: what a page gets back ───────────────────────────────────────

def test_rest_refusals_are_sentences_a_page_can_show(clock):
    config.override(roles_allowed=[A, B], server_token="tok")
    c = _client()
    assert c.get("/api/fridge", params={"who": A}).json() == {"detail": "口令不对,或者没带口令。"}
    h = {"Authorization": "Bearer tok"}
    assert c.get("/api/fridge", params={"who": "stranger"}, headers=h).json() == {"detail": "who 要填一个角色名。"}
    assert c.patch("/api/menu/nope", json={"note": "x"}, headers=h).json() == {"detail": "没有这一行。"}
    assert c.delete("/api/menu/nope", headers=h).json() == {"detail": "没有这一行。"}
    row = c.post("/api/menu", json={"dish": "粥", "by": "human", "for_who": A}, headers=h).json()
    c.post(f"/api/menu/{row['id']}/feed", headers=h)
    assert c.post(f"/api/menu/{row['id']}/feed", headers=h).json() == {"detail": "这道菜已经吃掉了。"}
    assert c.post("/api/menu", json={"dish": " ", "by": "human", "for_who": A}, headers=h).json() == {
        "detail": "dish(菜名)、by(谁挂的)、for_who(挂给谁)都要填。"}
    kind = c.post("/api/fridge/kinds", json={"name": "柿子", "category": "水果"}, headers=h).json()["kind"]
    assert c.post(f"/api/fridge/kinds/{kind['id']}/redraw", headers=h).json() == {"detail": "没有接画图,这里画不了。"}
    assert c.post("/api/dev/clock", json={}, headers=h).json() == {"detail": "快进钟没开(server.dev_clock)。"}
    assert c.put("/api/sleep", json={"who": A, "factor": 2}, headers=h).json() == {"detail": "factor 要在 0 到 1 之间。"}


def test_kitchen_overview_carries_the_configured_time_zone(clock):
    c = _client()
    assert c.get("/api/kitchen", params={"who": A}).json()["timezone"] == "Asia/Tokyo"
    assert c.get("/api/kitchen", params={"session_id": "nope"}).json() == {
        "now": clock["now"], "timezone": "Asia/Tokyo", "session": None}
    config.override(server_timezone="")
    assert c.get("/api/kitchen", params={"who": A}).json()["timezone"] == ""


# ── never point at a dead end when out of coupons ───────────────────────

SHORT = "没开成:冰箱里不够——鸡蛋(要 1,有 0)。买菜券现在 {n} 张{how}。"


def _short(who=A) -> str:
    return tools.call("kitchen_cook", {"dish": "炒蛋", "minutes": 5, "ingredients": ["鸡蛋"]}, who).text


@pytest.mark.parametrize("markers,go", [(True, "[买菜 …] 去买"), (False, "用 kitchen_buy 去买"), ("auto", "用 kitchen_buy 去买")])
def test_short_of_ingredients_only_suggests_what_can_be_done(clock, markers, go):
    config.override(inline_enabled=markers)
    # no coupon, nothing earns one: the bracket is left out altogether, and where coupons come from is said
    assert _short() == SHORT.format(n=0, how="") + "买菜券由用户给。"
    assert tools.call("kitchen_buy", {"items": ["鸡蛋"]}, A).text == "没买成:买菜券用完了(现在 0 张)。买菜券由用户给。"
    # no coupon, but something earns one: how to earn it, and no "go and buy"
    earn_rules()
    assert _short() == SHORT.format(n=0, how="(写成一篇日记、书摘或游记得一张)")
    # a coupon in hand: the original sentence, both halves
    fridge.grant_coupon_by_her(A)
    assert _short() == SHORT.format(n=1, how=f"(写成一篇日记、书摘或游记得一张;{go})")
    # a coupon in hand and nothing earns one: only "go and buy"
    config.override(coupons_earn={}, coupons_earn_hint="")
    assert _short() == SHORT.format(n=1, how=f"({go})")


def test_being_out_of_coupons_says_where_they_come_from_until_earning_is_configured(clock):
    assert tools.call("kitchen_buy", {"items": ["鸡蛋"]}, A).text == "没买成:买菜券用完了(现在 0 张)。买菜券由用户给。"
    assert _short() == "没开成:冰箱里不够——鸡蛋(要 1,有 0)。买菜券现在 0 张。买菜券由用户给。"
    config.override(words_human_name="阿青")
    assert _short().endswith("买菜券现在 0 张。买菜券由阿青给。")
    fridge.grant_coupon_by_her(A)                                   # with a coupon in hand it is not said
    assert _short() == "没开成:冰箱里不够——鸡蛋(要 1,有 0)。买菜券现在 1 张(用 kitchen_buy 去买)。"
    earn_rules()                                                   # nor once something earns one
    conn = fridge._conn()
    conn.execute("UPDATE coupons SET count=0")
    conn.commit()
    conn.close()
    assert tools.call("kitchen_buy", {"items": ["鸡蛋"]}, A).text == "没买成:买菜券用完了(现在 0 张)。写成一篇日记、书摘或游记就得一张。"
    assert _short() == "没开成:冰箱里不够——鸡蛋(要 1,有 0)。买菜券现在 0 张(写成一篇日记、书摘或游记得一张)。"


# ── what check prints can always be pasted back ─────────────────────────

def test_check_output_with_quoted_keys_reads_back(tmp_path):
    f = tmp_path / "k.toml"
    f.write_text('[fridge.shelf_days]\n"番茄" = 1\negg = 10\n\n[coupons.earn]\n"写 日记" = "日记"\nwrite_diary = "日记"\n'
                 '\n[stamina.work]\n"notes.search" = "research"\n', encoding="utf-8")
    out = config.dump(config.build(f, env={}))
    assert '[fridge.shelf_days]\n"番茄" = 1\negg = 10\n' in out
    assert '"写 日记" = "日记"\nwrite_diary = "日记"\n' in out and '"notes.search" = "research"' in out
    again = tmp_path / "again.toml"
    again.write_text(out, encoding="utf-8")
    back = config.build(again, env={})
    assert config.dump(back) == out and back.fridge_shelf_days == {"番茄": 1, "egg": 10}


# ── two more slips that used to pass unnoticed ──────────────────────────

def test_unknown_category_in_the_shelf_life_table_is_refused(tmp_path):
    f = tmp_path / "k.toml"
    f.write_text("[fridge.category_days]\nleafyy = 4\n", encoding="utf-8")
    with pytest.raises(config.ConfigError) as e:
        config.build(f, env={})
    en, zh = e.value.lines()
    assert en == (f"{f}: [fridge.category_days] leafyy is not a category (did you mean leafy?); the categories are: "
                  "leafy, meat, dairy, root, fruit, veg, staple_food")
    assert zh == (f"{f}：[fridge.category_days] leafyy 不是一个类别（是不是想写 leafy？）；类别只有这几个："
                  "leafy、meat、dairy、root、fruit、veg、staple_food")
    # a category of your own is fine once an ingredient of your catalog uses it
    f.write_text('[fridge.category_days]\nfrozen = 30\n\n[[fridge.ingredients]]\nid = "peas"\nname = "豌豆"\n'
                 'category = "frozen"\npack_qty = 1\n', encoding="utf-8")
    assert config.build(f, env={}).fridge_category_days["frozen"] == 30


def test_misspelt_environment_variable_is_pointed_out_but_does_not_stop_anything(tmp_path):
    env = {"KITCHENETTE_FRIDGE_COUPONMAX": "3", "KITCHENETTE_SERVER_PORT": "9001", "KITCHENETTE_CONFIG": "x",
           "KITCHENETTE_ZZZ": "1", "PATH": "/usr/bin"}
    assert config.unknown_env(env) == [
        "KITCHENETTE_FRIDGE_COUPONMAX is not a setting and was ignored; did you mean KITCHENETTE_FRIDGE_COUPON_MAX? "
        "/ 不认识这个变量，已忽略；是不是想写 KITCHENETTE_FRIDGE_COUPON_MAX？",
        "KITCHENETTE_ZZZ is not a setting and was ignored / 不认识这个变量，已忽略",
    ]
    assert config.build(None, env={"KITCHENETTE_FRIDGE_COUPONMAX": "3"}).fridge_coupon_max == 3      # the default
    import os
    run = subprocess.run([sys.executable, "-m", "kitchenette", "check"], capture_output=True, text=True, timeout=60,
                         cwd=tmp_path, env={**os.environ, "KITCHENETTE_FRIDGE_COUPONMAX": "5"})
    assert run.returncode == 0 and "coupon_max = 3" in run.stdout
    assert run.stderr.strip().splitlines() == [
        "KITCHENETTE_FRIDGE_COUPONMAX is not a setting and was ignored; did you mean KITCHENETTE_FRIDGE_COUPON_MAX? "
        "/ 不认识这个变量，已忽略；是不是想写 KITCHENETTE_FRIDGE_COUPON_MAX？"]
