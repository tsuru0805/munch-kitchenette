"""The fridge: batches and freshness, coupons, cooking from stock, eating and what it does
to satiety, stamina and dizziness. Every failure path asserts the sentence that is shown."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kitchenette import config, fridge, inline, kitchen, snacks, stamina, tools
from kitchenette.api import create_app
from kitchenette.texts import t

from conftest import A, B, DAY, T0, earn_rules, notes, receipts, run_reply
from conftest import qty as _qty, set_coupons as _set_coupons


def test_db_path_isolated_by_conftest(tmp_path):
    assert fridge._db_path() == str(tmp_path / "kitchen.db")


def test_catalog_has_her_33_items_with_art_ids():
    ids = [c["id"] for c in fridge.catalog()]
    assert len(ids) == 33 and len(set(ids)) == 33
    names = {c["name"] for c in fridge.catalog()}
    assert {"茼蒿", "乌冬面", "茄子"} <= names
    assert fridge.resolve("西红柿") == "tomato" and fridge.resolve("牛腩") == "beef"
    assert fridge.resolve("龙虾") is None
    assert {"面条", "味噌", "白萝卜", "西蓝花", "豆芽", "猪肉薄切"} <= names
    assert fridge.resolve("萝卜") == "daikon" and fridge.resolve("胡萝卜") == "carrot"
    assert fridge.resolve("猪肉片") == "pork_slice" and fridge.resolve("猪肉") == "pork"
    assert fridge.resolve("乌冬") == "udon" and fridge.resolve("拉面") == "noodles"
    assert fridge.resolve("西兰花") == "broccoli" and fridge.resolve("味增") == "miso"
    assert fridge.resolve("鸡肉") == "chicken" and fridge.resolve("虾仁") == "shrimp"
    sd = {c["id"]: c["shelf_days"] for c in fridge.catalog()}
    assert sd["miso"] == 30 and sd["beansprout"] == 2 and sd["broccoli"] == 5


def test_unknown_viewer_rejected(clock):
    config.override(roles_allowed=[A, B])
    with pytest.raises(ValueError):
        fridge.overview("stranger")
    with pytest.raises(ValueError):
        fridge.buy_her("", ["egg"])


def test_freshness_three_tiers_by_category(clock):
    assert fridge.freshness("spinach", T0, T0 + 0.9 * DAY) == fridge.FRESH
    assert fridge.freshness("spinach", T0, T0 + 1.5 * DAY) == fridge.MEH
    assert fridge.freshness("spinach", T0, T0 + 2.0 * DAY) == fridge.MEH
    assert fridge.freshness("spinach", T0, T0 + 2.1 * DAY) == fridge.BAD
    assert fridge.freshness("potato", T0, T0 + 3 * DAY) == fridge.FRESH
    assert fridge.freshness("potato", T0, T0 + 8 * DAY) == fridge.BAD


def test_overview_sorted_by_urgency(clock):
    fridge.buy_her(A, ["potato"])
    clock["now"] += 1.5 * DAY
    fridge.buy_her(A, ["spinach", "egg"])
    clock["now"] += 1.2 * DAY
    items = fridge.overview(A)["items"]
    assert items[0]["item_id"] == "spinach" and items[0]["freshness"] == fridge.MEH
    assert [b["freshness"] for b in items[1:]] == [fridge.FRESH, fridge.FRESH]


def test_spoiled_cleared_after_three_days_with_log(clock):
    fridge.buy_her(A, ["lettuce"])
    clock["now"] += 4 * DAY
    assert _qty(A, "lettuce") == 1
    clock["now"] += 1.5 * DAY
    ov = fridge.overview(A)
    assert _qty(A, "lettuce") == 0
    assert any(l["kind"] == "cleared" and "生菜" in l["text"] for l in ov["log"])


def test_viewers_have_separate_fridges(clock):
    fridge.buy_her(A, ["egg"])
    assert _qty(A, "egg") == 6 and _qty(B, "egg") == 0


def test_buy_self_spends_one_coupon(clock):
    _set_coupons(B, 2)
    text = fridge.buy_self(B, "番茄 鸡蛋、牛奶", key="k1")
    assert "买好了" in text and "还剩 1 张" in text and "原本还有" not in text
    assert _qty(B, "tomato") == 3 and _qty(B, "egg") == 6 and _qty(B, "milk") == 1


def test_buy_self_is_idempotent_per_key(clock):
    _set_coupons(A, 2)
    a = fridge.buy_self(A, "土豆", key="same")
    b = fridge.buy_self(A, "土豆", key="same")
    assert a == b and _qty(A, "potato") == 2
    assert fridge.overview(A)["coupons"]["count"] == 1


@pytest.mark.parametrize("text,needle,code", [
    ("", "没写买什么", "empty"),
    ("龙虾 番茄", "龙虾 不在能买的单子上", "unknown_item"),
    ("番茄 黄瓜 菠菜 茼蒿 生菜 土豆", "最多买 5 样", "too_many"),
    ("米 酱油", "常备品", "only_staples"),
])
def test_buy_self_failures_are_visible(clock, text, needle, code):
    _set_coupons(A, 1)
    with pytest.raises(fridge.FridgeError) as ei:
        fridge.buy_self(A, text, key="x")
    assert needle in ei.value.text and ei.value.code == code
    assert fridge.overview(A)["coupons"]["count"] == 1


def test_buy_self_without_coupon_tells_how_to_get_one(clock):
    earn_rules()
    with pytest.raises(fridge.FridgeError) as ei:
        fridge.buy_self(A, "番茄", key="x")
    assert "0 张" in ei.value.text and "日记、书摘或游记" in ei.value.text


def test_buy_self_staples_skipped_not_counted(clock):
    _set_coupons(A, 1)
    fridge.buy_self(A, "米 番茄 黄瓜 菠菜 茼蒿 生菜", key="k")
    assert _qty(A, "lettuce") == 1


def test_coupon_sources_and_moment_does_not_count():
    assert fridge.coupon_source_for_tool("srv__write_diary") is None      # nothing earns one out of the box
    earn_rules()
    assert fridge.coupon_source_for_tool("srv__write_diary") == "日记"
    assert fridge.coupon_source_for_tool("srv__write_travelogue") == "游记"
    assert fridge.coupon_source_for_tool("srv__write_moment") is None
    assert fridge.coupon_source_for_tool("srv__eat") is None


def test_coupon_caps_at_three_and_same_piece_once(clock):
    assert fridge.grant_coupon(A, "日记", "d1") == 1
    assert fridge.grant_coupon(A, "日记", "d1") is None
    assert fridge.grant_coupon(A, "书摘", "e1") == 2
    assert fridge.grant_coupon(A, "游记", "r1") == 3
    assert fridge.grant_coupon(A, "日记", "d2") is None
    log = fridge.overview(A)["log"]
    assert log[0]["kind"] == "coupon_full"


def test_her_coupon_respects_cap(clock):
    fridge.grant_coupon_by_her(B)
    fridge.grant_coupon_by_her(B)
    assert fridge.grant_coupon_by_her(B) == 3
    with pytest.raises(fridge.FridgeError) as ei:
        fridge.grant_coupon_by_her(B)
    assert "满 3 张" in ei.value.text


def test_round_tools_grant_coupon_and_count_meal(clock):
    earn_rules()
    kitchen.on_round_tools(B, [
        {"id": "t1", "name": "srv__write_diary", "input": {}},
        {"id": "t2", "name": "srv__write_travelogue", "input": {}, "is_error": True},
        {"id": "t3", "name": "srv__eat", "input": {"meal": "饭团"}},
    ])
    assert fridge.overview(B)["coupons"]["count"] == 1
    assert fridge.overview(B)["satiety"]["value"] == pytest.approx(100.0)


def test_take_uses_non_spoiled_oldest_first(clock):
    fridge.buy_her(A, ["milk"])
    clock["now"] += 6 * DAY
    fridge.buy_her(A, ["milk"])
    used = fridge.take_for_cooking(A, [("牛奶", 1)])
    assert [u["freshness"] for u in used] == [fridge.FRESH]
    used = fridge.take_for_cooking(A, [("牛奶", 1)])
    assert [u["freshness"] for u in used] == [fridge.BAD]
    fridge.buy_her(A, ["egg"])
    clock["now"] += 6 * DAY
    fridge.buy_her(A, ["egg"])
    used = fridge.take_for_cooking(A, [("鸡蛋", 2)])
    assert [u["freshness"] for u in used] == [fridge.BAD]


def test_take_short_is_atomic_and_visible(clock):
    fridge.buy_her(A, ["tomato"])
    with pytest.raises(fridge.FridgeError) as ei:
        fridge.take_for_cooking(A, [("番茄", 2), ("鸡蛋", 1)])
    assert "鸡蛋(要 1,有 0)" in ei.value.text and "买菜券现在 0 张" in ei.value.text
    assert _qty(A, "tomato") == 3


def test_take_needs_at_least_one_fridge_item(clock):
    with pytest.raises(fridge.FridgeError) as ei:
        fridge.take_for_cooking(A, [("盐", 1), ("酱油", 1)])
    assert ei.value.code == "no_ingredients"


def test_put_back_restores(clock):
    fridge.buy_her(A, ["milk"])
    used = fridge.take_for_cooking(A, [("牛奶", 1)])
    assert _qty(A, "milk") == 0
    fridge.put_back(A, used)
    assert _qty(A, "milk") == 1


def test_outcome_rules():
    assert fridge.decide_outcome("a", [{"freshness": "fresh"}]) == fridge.GREAT
    assert fridge.decide_outcome("a", [{"freshness": "fresh"}, {"freshness": "bad"}]) == fridge.SPOILED
    assert fridge.decide_outcome("a", []) == fridge.OK
    meh = [{"freshness": "meh"}]
    outs = [fridge.decide_outcome(f"s{i}", meh) for i in range(2000)]
    assert set(outs) == {fridge.OK, fridge.BURNT}
    assert 0.15 < outs.count(fridge.BURNT) / len(outs) < 0.25
    assert fridge.decide_outcome("s7", meh) == fridge.decide_outcome("s7", meh)


def _cook(who, dish, ingredients, minutes=10):
    return kitchen._exec_cook([], {"dish": dish, "minutes": minutes, "ingredients": ingredients}, who)


def test_cook_empty_fridge_cannot_cook(clock):
    text, err = _cook(B, "番茄炒蛋", ["番茄", "鸡蛋×2"])
    assert err and text.startswith("没开成") and "冰箱里不够" in text
    conn = kitchen._conn()
    assert conn.execute("SELECT COUNT(*) FROM cook_sessions").fetchone()[0] == 0
    conn.close()


def test_cook_missing_ingredients_param_rejected(clock):
    fridge.buy_her(A, ["egg"])
    text, err = kitchen._exec_cook([], {"dish": "蛋", "minutes": 5}, A)
    assert err and "ingredients" in text


def test_cook_consumes_and_retry_does_not_double(clock):
    fridge.buy_her(A, ["tomato", "egg"])
    text, err = _cook(A, "番茄炒蛋", ["番茄", "鸡蛋×2"])
    assert not err and "用了番茄×1、鸡蛋×2" in text
    text, err = _cook(A, "番茄炒蛋", ["番茄", "鸡蛋×2"])
    assert not err and "已经在火上" in text
    assert _qty(A, "tomato") == 2 and _qty(A, "egg") == 4


def test_outcome_fixed_at_serve_and_shown(clock):
    fridge.buy_her(A, ["spinach"])
    clock["now"] += 3 * DAY
    fridge.buy_her(A, ["egg"])
    _cook(A, "菠菜炒蛋", ["菠菜", "鸡蛋"])
    clock["now"] += 601
    s = kitchen.due_work(A)[0]
    assert s["outcome"] == fridge.SPOILED
    msg = kitchen.build_wake_message([s])
    assert "用了坏掉的食材,吃了会晕。" in msg
    assert kitchen.menu_note(s) == "坏了"
    st, _ = kitchen._exec_status({}, A)
    assert "菠菜炒蛋" in st and "坏了" in st and "买菜券 0/3 张" in st


def test_two_roles_have_separate_kitchens(clock):
    fridge.buy_her(B, ["egg"])
    assert not _cook(B, "蛋饼", ["鸡蛋"])[1]
    assert kitchen._exec_status({}, A)[0].splitlines()[0] == "火上没有锅。"
    assert "蛋饼" in kitchen._exec_status({}, B)[0]


def _serve(clock, who, dish, items, ingredients):
    fridge.buy_her(who, items)
    _cook(who, dish, ingredients)
    clock["now"] += 601
    kitchen.due_work(who)


def test_eat_great_dish_fills_and_marks_eaten(clock):
    _serve(clock, B, "煎蛋", ["egg"], ["鸡蛋"])
    assert kitchen.on_eat(B, "煎蛋", key="m1") == fridge.GREAT
    assert fridge.overview(B)["satiety"]["value"] == pytest.approx(100.0)
    assert kitchen.on_eat(B, "煎蛋", key="m1") is None
    assert kitchen.on_eat(B, "煎蛋", key="m2") == "her"


def test_satiety_decays_and_both_feel_hungry_with_fridge_list(clock):
    assert fridge.turn_lines(B) is None
    assert fridge.turn_lines(A) is None
    fridge.buy_her(B, ["tomato", "egg"])
    clock["now"] += 4 * 3600
    line = fridge.turn_lines(B)
    assert "有点饿了" in line and "冰箱里有:" in line and "番茄×3" in line and "鸡蛋×6" in line
    assert "有点饿了" in fridge.turn_lines(A) and "冰箱空了" in fridge.turn_lines(A)
    fridge.fill(B, 40.0)
    assert fridge.turn_lines(B) is None


def test_spoiled_dish_makes_dizzy_then_recovers_once(clock):

    fridge.buy_her(A, ["lettuce"])
    clock["now"] += 3 * DAY
    _cook(A, "生菜汤", ["生菜"])
    clock["now"] += 601
    kitchen.due_work(A)
    assert kitchen.on_eat(A, "生菜汤", key="x") == fridge.SPOILED
    fridge.fill(A, 100.0)
    line = fridge.turn_lines(A)
    assert "晕乎乎" in line and "『生菜汤』" in line
    assert fridge.turn_lines(A) == line
    clock["now"] += 2.5 * 3600 + 1
    fridge.fill(A, 100.0)
    assert fridge.turn_lines(A) == "【厨房·非用户发言】晕乎乎的劲过去了。"
    assert fridge.turn_lines(A) is None
    assert fridge.overview(A)["dizzy"] is None


def test_marker_without_coupon_fails_visibly(marker_env):
    run_reply("[买菜 番茄]\n")
    fail = receipts(False)
    assert fail and fail[-1]["marker"] == "买菜" and "0 张" in fail[-1]["hint"]
    assert _qty(A, "tomato") == 0


def test_concurrent_same_dish_opens_one_pot(clock):
    import threading
    fridge.buy_her(A, ["egg"])
    out = []
    ts = [threading.Thread(target=lambda: out.append(_cook(A, "蛋羹", ["鸡蛋"]))) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    conn = kitchen._conn()
    n = conn.execute("SELECT COUNT(*) FROM cook_sessions WHERE dish='蛋羹'").fetchone()[0]
    conn.close()
    assert n == 1 and _qty(A, "egg") == 5


def test_take_failure_leaves_no_pot(clock, monkeypatch):
    fridge.buy_her(A, ["egg"])

    def boom(*a, **k):
        raise RuntimeError("disk")
    monkeypatch.setattr(fridge, "take_in_tx", boom)
    text, err = _cook(A, "蛋", ["鸡蛋"])
    assert err and "写不进去" in text
    conn = kitchen._conn()
    assert conn.execute("SELECT COUNT(*) FROM cook_sessions").fetchone()[0] == 0
    conn.close()


def test_pot_insert_failure_rolls_back_ingredients(clock, monkeypatch):
    fridge.buy_her(A, ["egg"])
    real = fridge.take_in_tx

    def take_then_break(conn, *a, **k):
        used = real(conn, *a, **k)
        conn.execute("DROP TABLE cook_sessions")
        return used
    monkeypatch.setattr(fridge, "take_in_tx", take_then_break)
    text, err = _cook(A, "蛋", ["鸡蛋"])
    assert err and _qty(A, "egg") == 6


def test_eat_partial_failure_commits_nothing_and_retry_works(clock, monkeypatch):
    fridge.buy_her(B, ["lettuce"])
    clock["now"] += 3 * DAY
    _cook(B, "生菜汤", ["生菜"])
    clock["now"] += 601
    kitchen.due_work(B)
    real = fridge.settle_meal_in_tx
    calls = {"n": 0}

    def flaky(conn, *a, **k):
        v = real(conn, *a, **k)
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk")
        return v
    monkeypatch.setattr(fridge, "settle_meal_in_tx", flaky)
    with pytest.raises(RuntimeError):
        kitchen.on_eat(B, "生菜汤", key="k")
    assert fridge.overview(B)["dizzy"] is None
    assert kitchen.on_eat(B, "生菜汤", key="k") == fridge.SPOILED
    assert fridge.overview(B)["dizzy"]["dish"] == "生菜汤"


def test_meal_settles_satiety_and_dizzy_together(clock):
    assert fridge.settle_meal(B, 10, key="k", dizzy_dish="坏汤") is not None
    ov = fridge.overview(B)
    assert ov["dizzy"]["dish"] == "坏汤" and ov["satiety"]["value"] == pytest.approx(70)
    assert fridge.settle_meal(B, 10, key="k", dizzy_dish="坏汤") is None


def test_eat_raw_spoiled_makes_dizzy_and_meh_is_raw_meh(clock):
    fridge.buy_her(A, ["strawberry"])
    clock["now"] += 2 * DAY
    assert kitchen.on_eat(A, "草莓", key="a") == "raw_meh"
    fridge.buy_her(B, ["cucumber"])
    clock["now"] += 6 * DAY
    assert kitchen.on_eat(B, "黄瓜", key="b") == fridge.SPOILED
    assert fridge.overview(B)["dizzy"]["dish"] == "黄瓜"


def test_raw_rules_lemon_empty_fridge_and_her_feed(clock):
    fridge.buy_her(A, ["lemon", "apple"])
    assert kitchen.on_eat(A, "柠檬", key="l") == "her"
    assert _qty(A, "lemon") == 1
    assert kitchen.on_eat(B, "苹果", key="e") == "her"
    assert kitchen.on_eat(A, "苹果", key="f", by_her=True) == "her"
    assert _qty(A, "apple") == 2


def test_buy_self_receipt_lists_what_was_already_there(clock):
    _set_coupons(A, 2)
    fridge.buy_her(A, ["spinach"])
    clock["now"] += 1.5 * DAY
    fridge.buy_her(A, ["tomato"])
    text = fridge.buy_self(A, "土豆", key="k")
    assert "冰箱里原本还有:菠菜×1(不太新鲜)、番茄×3。" in text


def test_fridge_brief_caps_length():
    items = [{"name": f"菜{i}", "qty": 1, "freshness": fridge.FRESH, "item_id": "tomato",
              "bought_at": 0.0} for i in range(12)]
    out = fridge._fridge_brief(items)
    assert out.count("、") == fridge.FRIDGE_LIST_MAX - 1 and out.endswith("等 12 样")


def test_status_text_lists_buyable_catalog(clock):
    t = fridge.status_text(B)
    assert "能买的:" in t
    for it in config.get().fridge_ingredients:
        assert it["name"] in t.split("能买的:", 1)[1]
    assert "肉和海鲜 牛肉/" in t


def test_toss_bad_ones_keeps_good(clock):
    fridge.buy_her(A, ["spinach", "egg"])
    clock["now"] += 3 * DAY
    fridge.buy_her(A, ["tomato"])
    t = fridge.toss_self(A, "坏了的", key="k1")
    assert t == "扔掉了:菠菜×1(坏了)。"
    assert _qty(A, "spinach") == 0 and _qty(A, "egg") == 6 and _qty(A, "tomato") == 3
    assert fridge.toss_self(A, "坏了的", key="k1") == t
    with pytest.raises(fridge.FridgeError) as e:
        fridge.toss_self(A, "坏的", key="k2")
    assert e.value.code == "nothing_bad"


def test_toss_by_name_and_failures(clock):
    fridge.buy_her(B, ["egg"])
    fridge.buy_her(B, ["egg"])
    md = fridge.bought_md(clock["now"])
    assert fridge.toss_self(B, "鸡蛋", key="a") == f"扔掉了:鸡蛋×6({md}买的)、鸡蛋×6({md}买的)。"
    assert _qty(B, "egg") == 0
    for text, code in (("", "empty"), ("恐龙蛋", "unknown_item"), ("番茄", "not_in_fridge")):
        with pytest.raises(fridge.FridgeError) as e:
            fridge.toss_self(B, text, key=f"x{code}")
        assert e.value.code == code


def test_toss_marker_registered_and_receipt(marker_env):
    assert inline.MARKERS["扔掉"] == (tools.TOOL_TOSS, "what")
    fridge.buy_her(B, ["tomato"])
    run_reply("这番茄不要了。\n[扔掉 番茄]\n", who=B)
    assert _qty(B, "tomato") == 0
    rec = receipts(True)
    assert rec and rec[-1]["marker"] == "扔掉" and "扔掉了:番茄×3" in rec[-1]["hint"]
    run_reply("[扔掉 坏了的]\n", who=B)
    fail = receipts(False)
    assert fail and fail[-1]["marker"] == "扔掉" and "没有坏掉" in fail[-1]["hint"]


def _md(ts):
    return fridge.bought_md(ts)


def test_egg_shows_date_not_freshness_for_him(clock):
    t0 = clock["now"]
    fridge.buy_her(A, ["egg"])
    clock["now"] += 4 * DAY
    fridge.buy_her(A, ["spinach"])
    clock["now"] += 2.5 * DAY
    txt = fridge.status_text(A)
    assert f"鸡蛋×6({_md(t0)}买的)" in txt and "菠菜×1(坏了)" in txt
    assert "鸡蛋×6(坏了)" not in txt
    assert fridge.overview(A)["items"][0]["freshness"]


def test_bad_eggs_never_vanish_by_themselves(clock):
    fridge.buy_her(B, ["egg"])
    clock["now"] += 30 * DAY
    assert _qty(B, "egg") == 6


def test_cooking_grabs_oldest_box_and_bad_egg_ruins_pot_at_once(clock):
    old = clock["now"]
    fridge.buy_her(A, ["egg", "tomato"])
    clock["now"] += 6 * DAY
    fridge.buy_her(A, ["egg"])
    text, err = _cook(A, "番茄炒蛋", ["番茄", "鸡蛋×2"])
    assert not err
    assert "流出来的是一股黑汤,直接流进了锅里" in text and f"是 {_md(old)} 买的那盒" in text
    assert "整锅菜毁了" in text and f"那盒鸡蛋还剩 4 个:可以用 kitchen_toss 写「鸡蛋 {_md(old)}」" in text
    c = kitchen._conn()
    st = c.execute("SELECT status, outcome FROM cook_sessions").fetchone()
    c.close()
    assert tuple(st) == ("ruined", "ruined")
    assert _qty(A, "egg") == 10 and _qty(A, "tomato") == 2
    clock["now"] += 3600
    assert kitchen.due_work(A) == []
    log = [l["text"] for l in fridge.overview(A)["log"]]
    assert any("打到坏鸡蛋,整锅毁了" in t for t in log)


def test_toss_eggs_by_box_date_and_bad_words_skip_eggs(clock):
    old = clock["now"]
    fridge.buy_her(A, ["egg"])
    clock["now"] += 6 * DAY
    fridge.buy_her(A, ["egg", "spinach"])
    clock["now"] += 3 * DAY
    t = fridge.toss_self(A, "坏了的", key="a")
    assert "菠菜" in t and "鸡蛋" not in t
    t = fridge.toss_self(A, f"鸡蛋 {_md(old)}", key="b")
    assert t == f"扔掉了:鸡蛋×6({_md(old)}买的)。" and _qty(A, "egg") == 6
    with pytest.raises(fridge.FridgeError) as e:
        fridge.toss_self(A, f"鸡蛋 {_md(old)}", key="c")
    assert e.value.code == "not_in_fridge" and f"{_md(old)} 买的" in e.value.text


def _toss(who, what):
    return kitchen.local_tools(None, who)[kitchen.TOOL_TOSS]({"what": what})


@pytest.mark.parametrize("who", [A, B])
def test_toss_tool_takes_effect_before_next_pot(clock, who):
    old = clock["now"]
    fridge.buy_her(who, ["egg", "tomato"])
    clock["now"] += 6 * DAY
    fridge.buy_her(who, ["egg", "tomato"])
    text, err = _cook(who, "第一锅", ["鸡蛋×2"])
    assert not err and "kitchen_toss" in text and "[扔掉" not in text
    text, err = _toss(who, f"鸡蛋 {_md(old)}")
    assert not err and text.startswith("扔掉了:鸡蛋×4")
    text, err = _cook(who, "第二锅", ["鸡蛋×2"])
    assert not err and "下锅了" in text and "黑汤" not in text


def test_toss_tool_failure_says_why(clock):
    text, err = _toss(A, "番茄")
    assert err and "没有" in text
    text, err = _toss(A, "")
    assert err and "没写扔什么" in text
    assert kitchen.TOOL_TOSS in kitchen.tool_schemas()[-1]["name"]


def test_toss_box_used_up_receipt(marker_env, clock):
    old = clock["now"]
    fridge.buy_her(A, ["egg"])
    clock["now"] += 6 * DAY
    assert "黑汤" in _cook(A, "炒蛋", ["鸡蛋×6"])[0]
    run_reply(f"[扔掉 鸡蛋 {_md(old)}]\n", who=A)
    fail = receipts(False)
    assert fail[-1]["hint"] == f"没扔:{_md(old)} 买的鸡蛋那盒已经用完了,不用扔。"
    with pytest.raises(fridge.FridgeError) as e:
        fridge.toss_self(A, "鸡蛋 1-01", key="z")
    assert e.value.code == "not_in_fridge"


def test_egg_position_does_not_reveal_it_is_bad(clock):
    fridge.buy_her(A, ["strawberry", "apple", "egg"])
    fresh = fridge._fridge_brief(fridge.overview(A)["items"])
    assert fresh.startswith("鸡蛋×6(")
    clock["now"] += 5.5 * DAY
    bad = fridge.overview(A)["items"]
    assert {b["item_id"] for b in bad if b["freshness"] == fridge.BAD} == {"egg", "strawberry"}
    brief = fridge._fridge_brief(bad)
    assert brief.startswith("鸡蛋×6(") and "草莓×1(坏了)" in brief
    assert fridge.status_text(A).startswith("冰箱:鸡蛋×6(")
    assert "坏了" not in brief.split("、")[0]
    assert [b["item_id"] for b in fridge.overview(A)["items"]][0] in {"egg", "strawberry"}


def test_toss_receipt_order_does_not_reveal_egg(clock):
    fridge.buy_her(A, ["egg", "tomato"])
    clock["now"] += 6 * DAY
    fridge.buy_her(A, ["egg"])
    text = fridge.toss_self(A, "鸡蛋 番茄", key="order")
    assert text.index("番茄") > text.rindex("鸡蛋")


def test_writing_coupon_receipt_reaches_him(clock):
    first = kitchen.grant_writing_coupon(A, "日记", "tool:abc")
    again = kitchen.grant_writing_coupon(A, "日记", "tool:abc")
    assert first == {"ok": True, "text": "得了一张买菜券(现在 1/3)。"} and again is None


def test_coupon_failure_is_visible(clock, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("locked")
    monkeypatch.setattr(fridge, "grant_coupon_ex", boom)
    res = kitchen.grant_writing_coupon(A, "日记", "tool:z")
    assert res == {"ok": False, "text": "这篇日记的买菜券没发上(冰箱的账本写不进去)"}


def test_stamina_delta_by_outcome(clock, monkeypatch):
    got = []
    monkeypatch.setattr(stamina, "pulse", lambda who, delta, **kw: got.append((who, delta, kw.get("rule"))) or 0.5)
    fridge.buy_her(A, ["egg"])
    _cook(A, "蛋", ["鸡蛋"])
    clock["now"] += 601
    kitchen.due_work(A)
    kitchen.on_eat(A, "蛋", key="e1")
    assert got == [(A, config.get().stamina_outcome_delta[fridge.GREAT], "kitchen:great")]
    got.clear()
    kitchen.on_eat(B, "随便", key="e2")
    kitchen.on_eat(A, "别人挂的饭", key="e3")
    assert got == []


def test_snack_fills_satiety(clock):
    snacks.eat(B, "jelly", None, snacks.BY_SELF, rid="r1")
    assert fridge.overview(B)["satiety"]["value"] == pytest.approx(60 + config.get().satiety_snack_gain["high"])


def test_buy_marker_is_registered_and_parsed():
    assert inline.MARKERS["买菜"] == (tools.TOOL_BUY, "items")
    acts = inline.parse("家里没菜了。\n[买菜 番茄 鸡蛋]\n说完了 [买菜 不算] 行内的不算\n")
    assert [(a.marker, a.args) for a in acts] == [("买菜", "番茄 鸡蛋")]
    assert inline.strip("家里没菜了。\n[买菜 番茄 鸡蛋]\n好。") == "家里没菜了。\n好。"


def test_marker_buys_with_coupon_and_receipt(marker_env):
    _set_coupons(B, 1)
    mid = run_reply("家里没菜了。\n[买菜 番茄 鸡蛋]\n", who=B)
    assert _qty(B, "tomato") == 3 and _qty(B, "egg") == 6
    rec = receipts(True)
    assert rec and rec[-1]["marker"] == "买菜" and "还剩 0 张" in rec[-1]["hint"]
    run_reply("家里没菜了。\n[买菜 番茄 鸡蛋]\n", who=B, message_id=mid)
    assert _qty(B, "tomato") == 3


def test_rest_buy_coupon_overview(clock):
    config.override(roles_allowed=[A, B])
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert len(c.get("/api/fridge/catalog").json()) == 33
    r = c.post("/api/fridge/buy", json={"who": B, "items": ["egg", "udon"]})
    assert r.status_code == 200 and "鸡蛋×6" in r.json()["text"]
    assert c.post("/api/fridge/buy", json={"who": B, "items": ["lobster"]}).status_code == 400
    assert c.post("/api/fridge/buy", json={"who": "stranger", "items": ["egg"]}).status_code == 400
    for n in (1, 2, 3):
        assert c.post("/api/fridge/coupon", json={"viewer": B}).json()["count"] == n
    assert c.post("/api/fridge/coupon", json={"who": B}).status_code == 409
    ov = c.get("/api/fridge", params={"who": B}).json()
    assert ov["coupons"] == {"count": 3, "max": 3} and ov["staples"] == ["米", "油", "盐", "酱油"]
    assert {b["item_id"] for b in ov["items"]} == {"egg", "udon"}
    # what piled up before the role heard of it is told once per kind
    kinds = [n["kind"] for n in notes(B)]
    assert kinds.count("fridge.bought") == 1 and kinds.count("fridge.coupon") == 1
    assert notes(B, "fridge.bought")[0]["text"] == "用户给你买了菜,放进冰箱了:鸡蛋×6、乌冬面×1。"
    assert notes(B, "fridge.coupon")[0]["text"] == "用户给了你一张买菜券(现在 3 张)。"
    assert len(notes(B, "fridge.coupon")[0]["payload"]["events"]) == 3


def test_notes_wording_for_groceries_and_served():
    assert t("note_bought", items="鸡蛋×6") == "用户给你买了菜,放进冰箱了:鸡蛋×6。"
    s = {"dish": "汤", "started_at": T0, "duration_seconds": 600, "outcome": "burnt"}
    assert "出锅了(共 10 分钟)。糊了。已挂到" in kitchen.served_body([s])


def test_human_name_is_a_setting():
    config.override(words_human_name="小满")
    assert t("head") == "【厨房·非小满发言】"
    assert t("note_coupon", n=2) == "小满给了你一张买菜券(现在 2 张)。"


def test_eat_raw_from_fridge_without_cooking(clock):
    fridge.buy_her(B, ["apple"])
    d = kitchen.eat_detail(B, "苹果", key="r1")
    assert d["outcome"] == "raw"
    assert _qty(B, "apple") == 1
    assert fridge.overview(B)["satiety"]["value"] == pytest.approx(60 + config.get().satiety_gain["raw"])
    assert kitchen.on_eat(B, "苹果", key="r1") is None
    assert _qty(B, "apple") == 1
    assert "从冰箱拿了苹果直接吃了(还剩 1 个)" in d["raw_receipt"]
    assert any(l["kind"] == "ate_raw" for l in fridge.overview(B)["log"])
