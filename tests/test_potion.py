"""The stamina potion: a reserved menu name that restores exactly the amount the human set,
is never a meal, and is granted once no matter who gets to the bottle first."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from kitchenette import config, fridge, inline, kitchen, menu, notify, potion, service, stamina, tools
from kitchenette.api import create_app

from conftest import A, B, notes

T = datetime(2026, 11, 11, 13, 0, tzinfo=ZoneInfo("Asia/Tokyo")).timestamp()
EAT = "srv__eat"


@pytest.fixture(autouse=True)
def _at_t(clock):
    clock["now"] = T
    return clock


@pytest.fixture(autouse=True)
def _rows(_at_t):
    """Potion rows on the menu, with the ids the tests below register amounts for."""
    conn = fridge._conn()
    for who, ids in ((A, ("row1", "m1", "m2", "m4", "big", "tiny", "a", "b", "r")), (B, ("n1", "m3"))):
        for rid in ids:
            conn.execute("INSERT INTO menu (id, dish, note, by, for_who, eaten_at, created_at, updated_at)"
                         " VALUES (?,?,NULL,'human',?,NULL,?,?)", (rid, potion.NAME, who, T, T))
    conn.commit()
    conn.close()


def _seed(who, energy):
    conn = fridge._conn()
    conn.execute("INSERT INTO stamina (who, value, updated_at) VALUES (?,?,?)"
                 " ON CONFLICT(who) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                 (who, energy, T))
    conn.commit()
    conn.close()


def _energy(who, now=T):
    return stamina.read(who, now)


def _satiety(who):
    return fridge.overview(who, now=T)["satiety"]["value"]


def _meals():
    conn = fridge._conn()
    try:
        return [r["meal"] for r in conn.execute("SELECT meal FROM meals ORDER BY at")]
    finally:
        conn.close()


def _call(meal, tid="t1", name=EAT):
    return {"name": name, "id": tid, "input": {"meal": meal}}


def _native_round(who, calls, now=T + 1):
    """A finished round of tool calls made outside this server: stamina, then coupons and bites."""
    names = [c["name"] for c in calls
             if not c.get("is_error") and not potion.is_potion_call(c.get("name"), c.get("input"))]
    stamina.settle(who, names, now=now)
    kitchen.on_round_tools(who, calls)


@pytest.mark.parametrize("meal,yes", [
    ("精力补充药剂", True), (" 精力补充药剂 ", True), ("精力 补充药剂", True), ("精力　补充药剂\n", True),
    ("精力\u0085补充药剂", False), ("﻿精力补充药剂", False),
    ("药剂", False), ("番茄炒蛋和精力补充药剂", False), ("精力补充药剂!", False), ("", False),
])
def test_only_the_exact_reserved_name_is_a_potion(meal, yes):
    assert potion.is_potion_meal(meal) is yes
    assert potion.is_potion_call(EAT, {"meal": meal}) is yes
    assert potion.is_potion_call("eat", {"meal": meal}) is yes
    assert potion.is_potion_call("srv__read_menu", {"meal": meal}) is False
    assert potion.is_potion_call("srv__cheat", {"meal": meal}) is False


def test_register_lists_with_the_note_he_sees_and_no_upper_limit():
    p = potion.register_potion(A, "row1", 30)
    assert p["pct"] == 30 and p["note"] == "回 30% 体力"
    assert [x["menu_row_id"] for x in potion.pending(A)] == ["row1"] and potion.pending(B) == []
    assert potion.register_potion(A, "row1", 250)["note"] == "回 250% 体力"
    assert potion.remove_potion("row1") is True and potion.pending(A) == []
    assert potion.remove_potion("row1") is False


def test_her_memo_rides_after_the_number_and_survives_a_number_only_change():
    p = potion.register_potion(A, "m1", 30, "  慢慢喝\n别一口闷  ")
    assert p["memo"] == "慢慢喝 别一口闷" and p["note"] == "回 30% 体力 · 慢慢喝 别一口闷"
    assert potion.register_potion(A, "m1", 50)["note"] == "回 50% 体力 · 慢慢喝 别一口闷"
    assert potion.register_potion(A, "m1", 50, "")["note"] == "回 50% 体力"
    assert len(potion.register_potion(A, "m1", 50, "字" * 200)["memo"]) == potion.MEMO_MAX
    assert potion.pending(A)[0]["memo"] == "字" * potion.MEMO_MAX
    assert potion.note_for(30) == "回 30% 体力" and potion.note_for(30, "  ") == "回 30% 体力"
    assert potion.clean_memo("饭后\u0085喝 别\x1c急　 \t的") == "饭后 喝 别 急 的"
    assert potion.clean_memo("﻿饭后") == "﻿饭后"


@pytest.mark.parametrize("who,row,pct,needle", [
    ("stranger", "r", 30, "who 必须是配置里允许的角色"),
    (A, "", 30, "没有这一行"),
    (A, "r", 0, "大于 0 的整数"),
    (A, "r", -5, "大于 0 的整数"),
    (A, "r", "多", "要填一个数"),
])
def test_bad_potion_is_refused_with_words(who, row, pct, needle):
    config.override(roles_allowed=[A, B])
    with pytest.raises(potion.PotionError) as e:
        potion.register_potion(who, row, pct)
    assert needle in e.value.text


def test_round_nets_exactly_her_number_and_is_not_a_meal():
    _seed(A, 0.40)
    sat = _satiety(A)
    potion.register_potion(A, "row1", 30)
    r = potion.drink(A, ["row1"])
    assert r["drunk"] == ["row1"] and r["text"] == "喝了精力补充药剂。体力 +30%,现在 70%。"
    _native_round(A, [_call("精力补充药剂")])
    assert _energy(A, T + 1) == pytest.approx(0.70, abs=0.005)
    assert _satiety(A) == pytest.approx(sat, abs=0.05) and _meals() == []
    assert potion.pending(A) == []


def test_full_bar_stays_full_and_tiny_potion_stays_tiny():
    _seed(A, 0.20)
    potion.register_potion(A, "big", 500)
    assert "现在 100%" in potion.drink(A, ["big"])["text"]
    _native_round(A, [_call("精力补充药剂")])
    assert _energy(A, T + 1) == pytest.approx(1.0, abs=0.005)
    _seed(A, 0.01)
    potion.register_potion(A, "tiny", 1)
    potion.drink(A, ["tiny"])
    _native_round(A, [_call("精力补充药剂", "t2")])
    assert _energy(A, T + 1) == pytest.approx(0.02, abs=0.005)


def test_same_round_real_dish_keeps_its_own_meal_and_recharge():
    _seed(A, 0.40)
    sat = _satiety(A)
    potion.register_potion(A, "row1", 30)
    potion.drink(A, ["row1"])
    _native_round(A, [_call("番茄炒蛋", "a"), _call("精力补充药剂", "b")])
    assert _energy(A, T + 1) == pytest.approx(0.80, abs=0.005)       # +30% potion, +10% for the meal
    assert _satiety(A) > sat
    again = _satiety(A)
    kitchen.on_round_tools(A, [_call("番茄炒蛋", "a"), _call("精力补充药剂", "b")])
    assert _satiety(A) == pytest.approx(again, abs=0.05)             # the same call id settles once


def test_each_role_has_its_own_bottles_and_stamina():
    _seed(A, 0.40)
    before = _energy(B)
    potion.register_potion(B, "n1", 20)
    r = potion.drink(B, ["n1"])
    after = min(1.0, before + 0.20)
    assert r["text"] == f"喝了精力补充药剂。体力 +20%,现在 {round(after * 100)}%。"
    _native_round(B, [_call("精力补充药剂")], now=T)
    assert _energy(B) == pytest.approx(after, abs=0.005) and _energy(A) == pytest.approx(0.40, abs=0.005)
    assert _meals() == []
    with pytest.raises(potion.PotionError) as e:
        potion.drink(A, ["n1"])
    assert e.value.code == "unregistered"


def _empty_menu():
    conn = fridge._conn()
    conn.execute("DELETE FROM menu")
    conn.commit()
    conn.close()


def test_marker_and_tool_both_drink_without_counting_a_meal():
    _empty_menu()
    _seed(A, 0.40)
    sat = _satiety(A)
    row = menu.add("精力补充药剂", "human", A, potion.note_for(30))
    potion.register_potion(A, row["id"], 30)
    rec = inline.execute(A, "[吃 精力补充药剂]", "m1")[0]
    assert rec.ok and rec.text.startswith("喝了精力补充药剂。体力 +30%,现在 70%。")
    assert _energy(A) == pytest.approx(0.70, abs=0.005)              # no extra +10% for "eating"
    assert _satiety(A) == pytest.approx(sat, abs=0.05) and _meals() == []
    assert menu.get(row["id"])["eaten_at"] is not None
    row2 = menu.add("精力补充药剂", "human", A)
    potion.register_potion(A, row2["id"], 10)
    res = tools.call("eat", {"meal": "精力补充药剂"}, A)
    assert not res.is_error and "体力 +10%,现在 80%" in res.text and _meals() == []
    none_left = tools.call("eat", {"meal": "精力补充药剂"}, A)
    assert none_left.is_error and none_left.text == "没喝成:菜单上没有精力补充药剂。"


def test_potion_row_is_never_food_and_shows_its_amount_on_the_menu():
    config.override(inline_enabled=True)
    _empty_menu()
    _seed(A, 0.40)
    row = menu.add("精力补充药剂", "human", A, "回 5% 体力")
    potion.register_potion(A, row["id"], 30, "慢慢喝")
    menu.add("番茄炒蛋", "human", A)
    assert "· 精力补充药剂（回 30% 体力 · 慢慢喝）" in menu.read_menu(A)
    res = tools.call("eat", {"meal": "番茄炒蛋和精力补充药剂"}, A)
    assert not res.is_error and "菜单划掉：番茄炒蛋 ✓" in res.text
    assert "精力补充药剂没喝:它要单独喝,[吃 精力补充药剂] 单独成一行。" in res.text
    assert menu.get(row["id"])["eaten_at"] is None and potion.pending(A)


def test_one_bottle_per_drink_oldest_first():
    _seed(A, 0.10)
    potion.register_potion(A, "a", 30, now=T - 10)
    potion.register_potion(A, "b", 25, now=T - 5)
    r = potion.drink(A, ["b", "a", "not-a-potion"])
    assert r["drunk"] == ["a"] and r["text"] == "喝了精力补充药剂。体力 +30%,现在 40%。"
    assert [p["menu_row_id"] for p in potion.pending(A)] == ["b"]
    assert potion.drink(A, ["b", "a"])["drunk"] == ["b"]
    with pytest.raises(potion.PotionError) as e:
        potion.drink(A, ["a", "b"])
    assert e.value.code == "gone" and "已经喝过了" in e.value.text and sorted(e.value.rows) == ["a", "b"]
    assert _energy(A) == pytest.approx(0.65, abs=0.005)


def test_unregistered_row_is_never_food_and_says_why():
    with pytest.raises(potion.PotionError) as e:
        potion.drink(A, ["ghost"])
    assert e.value.code == "unregistered" and "还没登记好回多少" in e.value.text
    assert "要用户撤掉重挂" in e.value.text


def test_energy_not_landing_puts_the_bottle_back(monkeypatch):
    _seed(A, 0.40)
    potion.register_potion(A, "row1", 30)
    with monkeypatch.context() as m:
        m.setattr(stamina, "pulse", lambda *a, **k: None)
        with pytest.raises(potion.PotionError) as e:
            potion.drink(A, ["row1"])
        assert e.value.code == "energy" and "还挂在菜单上" in e.value.text
        assert [p["menu_row_id"] for p in potion.pending(A)] == ["row1"]
    with monkeypatch.context() as m:
        def boom(*a, **k):
            raise RuntimeError("disk")
        m.setattr(stamina, "pulse", boom)
        with pytest.raises(potion.PotionError) as e:
            potion.drink(A, ["row1"])
        assert e.value.code == "energy" and [p["menu_row_id"] for p in potion.pending(A)] == ["row1"]
    assert potion.drink(A, ["row1"])["drunk"] == ["row1"] and _energy(A) == pytest.approx(0.70, abs=0.005)


def test_bottle_stuck_mid_drink_counts_as_drunk_after_a_minute():
    _seed(A, 0.40)
    potion.register_potion(A, "row1", 30)
    conn = potion._conn()
    conn.execute("UPDATE potions SET state='taking', taken_at=? WHERE menu_row_id='row1'", (T - 5,))
    conn.commit()
    conn.close()
    with pytest.raises(potion.PotionError) as e:
        potion.drink(A, ["row1"])
    assert e.value.code == "busy" and "稍等一下" in e.value.text
    with pytest.raises(potion.PotionError) as e:
        potion.drink(A, ["row1"], now=T + 100)
    assert e.value.code == "gone" and e.value.rows == ["row1"] and _energy(A) == pytest.approx(0.40, abs=0.005)


def test_potion_call_is_left_out_of_round_settlement():
    calls = [_call("精力补充药剂", "a"), _call("番茄炒蛋", "b"), {"name": "srv__take_bath", "id": "c", "input": {}}]
    kept = [c["name"] for c in calls if not potion.is_potion_call(c.get("name"), c.get("input"))]
    assert kept == [EAT, "srv__take_bath"]
    config.override(stamina_auto_account=False)
    _seed(A, 0.40)
    out = service.settle_round(A, [_call("精力补充药剂", "a")], round_id="r1")
    assert out["stamina"] == pytest.approx(0.40, abs=0.005)          # drinking is neither a meal nor work
    out = service.settle_round(A, [_call("番茄炒蛋", "b")], round_id="r2")
    assert out["stamina"] == pytest.approx(0.50, abs=0.005)


def test_she_feeds_full_number_and_he_is_told():
    _seed(A, 0.40)
    sat = _satiety(A)
    potion.register_potion(A, "row1", 45)
    r = potion.feed(A, "row1")
    assert r["text"] == "喂好了。体力 +45%,现在 85%。" and _energy(A) == pytest.approx(0.85, abs=0.005)
    assert _satiety(A) == pytest.approx(sat, abs=0.05) and _meals() == []
    assert r["note"] == "用户喂你喝了一瓶精力补充药剂。体力 +45%,现在 85%。"
    with pytest.raises(potion.PotionError) as e:
        potion.feed(A, "row1")
    assert e.value.text == "这一瓶已经喝掉了。" and e.value.rows == ["row1"] and _energy(A) == pytest.approx(0.85, abs=0.005)
    with pytest.raises(potion.PotionError) as e:
        potion.feed(A, "ghost")
    assert "没登记上回多少" in e.value.text
    assert kitchen.on_eat(A, "精力补充药剂", key="fed:1", by_her=True) == "potion" and _meals() == []


def test_she_feeds_and_he_drinks_the_same_bottle_only_one_wins():
    _seed(A, 0.10)
    potion.register_potion(A, "row1", 30)
    potion.feed(A, "row1")
    with pytest.raises(potion.PotionError) as e:
        potion.drink(A, ["row1"])
    assert e.value.code == "gone" and _energy(A) == pytest.approx(0.40, abs=0.005)


def test_potions_need_stamina_switched_on():
    config.override(stamina_enabled=False)
    with pytest.raises(potion.PotionError) as e:
        potion.register_potion(A, "row1", 30)
    assert e.value.code == "stamina_off"


def test_rest_round_trip():
    config.override(roles_allowed=[A, B])
    _seed(A, 0.30)
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.post("/api/potions", json={"who": A, "menu_row_id": "m1", "pct": 40}).json()["potion"]["note"] == "回 40% 体力"
    bad = c.post("/api/potions", json={"who": A, "menu_row_id": "m2", "pct": 0})
    assert bad.status_code == 400 and "大于 0 的整数" in bad.json()["detail"]["message"]
    assert c.patch("/api/potions/m1", json={"who": A, "pct": 60}).json()["potion"]["pct"] == 60
    lst = c.get("/api/potions", params={"who": A}).json()
    assert lst["name"] == "精力补充药剂" and lst["note_fmt"] == "回 {pct}% 体力" and "pct_max" not in lst
    assert lst["memo_sep"] == " · " and lst["memo_max"] == 60
    assert c.patch("/api/potions/m1", json={"who": A, "pct": 60, "memo": "饭后"}).json()["potion"]["note"] == "回 60% 体力 · 饭后"
    assert c.get("/api/potions", params={"who": A}).json()["items"][0]["memo"] == "饭后"
    assert [i["menu_row_id"] for i in lst["items"]] == ["m1"]
    d = c.post("/api/potions/drink", json={"who": A, "menu_row_ids": ["m1"]}).json()
    assert d["drunk"] == ["m1"] and "体力 +60%,现在 90%" in d["text"]
    again = c.post("/api/potions/drink", json={"who": A, "menu_row_ids": ["m1"]})
    assert again.status_code == 409 and again.json()["detail"] == {
        "message": "没喝成:这瓶精力补充药剂已经喝过了。", "code": "gone", "rows": ["m1"]}
    assert c.patch("/api/potions/m1", json={"who": A, "pct": 10}).status_code == 409
    c.post("/api/potions", json={"who": B, "menu_row_id": "m3", "pct": 15})
    f = c.post("/api/potions/m3/feed", json={"who": B})
    assert f.status_code == 200 and f.json()["text"].startswith("喂好了。体力 +15%")
    assert notes(B, notify.KIND_POTION_FED)[0]["text"].startswith("用户喂你喝了一瓶精力补充药剂。体力 +15%")
    assert c.post("/api/potions/m3/feed", json={"who": B}).json()["detail"]["code"] == "gone"
    c.post("/api/potions", json={"who": A, "menu_row_id": "m4", "pct": 15})
    assert c.delete("/api/potions/m4").json()["removed"] is True
    assert c.get("/api/potions", params={"who": "stranger"}).status_code == 400
