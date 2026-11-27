"""The upgrade: seventeen switches, recipes, the role's book, proficiency and mishaps, the settled card,
the dish book and achievements, plates, jars and street vendors."""
from __future__ import annotations

import json
import random
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kitchenette import (book, config, db, dex, dishes, fridge, inline, jars, kitchen, menu, notify, play,
                         progress, recipes, service, sleep, stamina, tools, vendor)
from kitchenette.api import create_app
from kitchenette.texts_play import TEXTS, VENDORS

from conftest import A, B, DAY, play_on, set_coupons

TOMATO_EGG = "hc-d9b1068d"      # 西红柿炒鸡蛋: tomato + egg×2, stir-fry, 15 minutes
STEAMED_EGG = "hc-e0a19bc9"     # 蒸水蛋: egg
COLA_WINGS = "hc-3b437fc8"      # 可乐鸡翅: wings + cola (both extra shop items)


def reply(text: str, who: str = A, mid: str | None = None):
    return inline.execute(who, text, mid or uuid.uuid4().hex)


def one(text: str, who: str = A) -> inline.Receipt:
    rs = reply(text, who)
    assert len(rs) == 1, rs
    return rs[0]


def cook(dish: str, ingredients: list[str], minutes: int = 10, who: str = A, **extra):
    res = tools.call("kitchen_cook", {"dish": dish, "minutes": minutes, "ingredients": ingredients, **extra}, who)
    return res.text, res.is_error


def serve(clock, minutes: int = 10, who: str = A) -> None:
    clock["now"] += minutes * 60 + 1
    service.scan_all()


def stock(*ids: str, who: str = A) -> None:
    fridge.buy_her(who, list(ids))


def settle_rows(who: str = A) -> list[dict]:
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM cook_settlements WHERE who=? ORDER BY settled_at", (who,))]
    finally:
        conn.close()


# ── the switches ────────────────────────────────────────────────────────

def test_out_of_the_box_ten_are_on_and_seven_are_off():
    s = config.Settings()
    on = [k for k in play.KEYS if getattr(s, f"play_{k}")]
    off = [k for k in play.KEYS if not getattr(s, f"play_{k}")]
    assert len(play.KEYS) == 17
    assert on == ["recipes_public", "recipes_today", "recipe_cook", "recipe_book", "proficiency", "mishaps",
                  "new_dish_bonus", "settle_card", "dex", "achievements"]
    assert off == ["tasting_notes", "orders", "menus", "recipe_codes", "vendor", "dishwash", "seal_jars"]


def test_a_switch_whose_parent_is_off_does_nothing_and_says_why():
    play_on("mishaps", "orders", "recipe_cook")
    eff = play.effective()
    assert not eff["mishaps"]["on"] and eff["mishaps"]["reason"] == "needs proficiency"
    assert not eff["recipe_cook"]["on"] and eff["recipe_cook"]["reason"] == "needs recipes_public"
    assert not eff["orders"]["on"]
    assert any("mishaps" in line for line in play.startup_lines())


def test_with_everything_off_new_markers_are_plain_text_and_no_tool_is_added(clock):
    text = "好的\n[收藏 西红柿炒鸡蛋]\n[刷盘子]\n[问小贩 多少钱]"
    assert inline.parse(text) == []
    assert inline.strip(text) == text
    names = [s["name"] for s in tools.schemas()]
    assert "kitchen_recipes" not in names
    cook_schema = next(s for s in tools.schemas() if s["name"] == "kitchen_cook")
    assert "recipe" not in cook_schema["input_schema"]["properties"]
    stock("egg")
    assert cook("煮蛋", ["鸡蛋"], recipe=STEAMED_EGG) == (TEXTS["feature_off"], True)


def test_switching_off_deletes_nothing(clock):
    play_on("recipes_public", "recipe_book")
    assert one("[收藏 西红柿炒鸡蛋]").ok
    config.override(play_recipe_book=False)
    assert inline.parse("[收藏 西红柿炒鸡蛋]") == []
    config.override(play_recipe_book=True)
    conn = db.connect()
    assert len(book.my_pages(conn, A)) == 1
    conn.close()


def test_switches_are_settings_written_under_play(tmp_path):
    p = tmp_path / "k.toml"
    p.write_text("[play]\nvendor = true\nrecipes_public = false\n", encoding="utf-8")
    s = config.build(p, env={})
    assert s.play_vendor is True and s.play_recipes_public is False
    assert "[play]" in config.dump(s) and "vendor = true" in config.dump(s)


# ── recipes ─────────────────────────────────────────────────────────────

def test_the_index_has_no_steps_and_names_its_source():
    data = recipes.load()
    assert len(data["list"]) > 300
    assert data["source"]["repo"] == "https://github.com/Anduin2017/HowToCook"
    keys = set().union(*(r.keys() for r in data["list"]))
    assert keys <= {"id", "version", "name", "aliases", "main", "optional", "staples", "method", "minutes", "category",
                    "category_label", "source"}


def test_extra_shop_items_and_seasonings_only_while_the_recipes_are_on(clock):
    assert fridge.resolve("鸡翅") is None and not fridge.is_staple("蚝油")
    play_on("recipes_public")
    assert fridge.resolve("鸡翅") == "wings" and fridge.is_staple("蚝油")
    stock("wings")
    config.override(play_recipes_public=False)
    # bought while on: still recognised, still usable
    assert fridge.item("wings")["name"] == "鸡翅" and fridge.resolve("鸡翅", gone=True) == "wings"
    assert fridge.resolve("鸡翅") is None


def test_browsing_finds_by_ingredient_and_lists_categories(clock):
    play_on("recipes_public")
    text, err = tools.call("kitchen_recipes", {"what": "find", "q": "鸡翅"}, A).text, False
    assert "可乐鸡翅" in text and "· " in text
    cats = tools.call("kitchen_recipes", {"what": "category"}, A).text
    assert cats.startswith("分类:") and "汤" in cats
    res = tools.call("kitchen_recipes", {"what": "today"}, A)
    assert res.is_error and res.text == TEXTS["feature_off"]


def test_today_you_could_try_is_in_the_status_and_stays_the_same_all_day(clock):
    play_on("recipes_public", "recipes_today")
    stock("tomato", "egg")
    def picks():
        text = tools.call("kitchen_status", {}, A).text
        return text[text.index("今天"):]
    first = picks()
    assert first.startswith(("今天可以试试(冰箱里的料够):", "今天料够的只有这一道:"))
    ready = first.split("还差一点就能做:")[0]
    used = re.findall(r"— (.+?) · ", ready)
    assert used and all(set(u.replace("×2", "").split("、")) <= {"番茄", "鸡蛋"} for u in used)
    clock["now"] += 600
    assert picks() == first


def test_a_broken_index_takes_only_its_own_paragraph_down(clock, monkeypatch, tmp_path):
    play_on("recipes_public", "recipes_today")
    bad = tmp_path / "broken.index.json"
    bad.write_text("{", encoding="utf-8")
    monkeypatch.setenv("KITCHENETTE_RECIPES_INDEX", str(bad))
    text = tools.call("kitchen_status", {}, A).text
    assert TEXTS["rec_down"] in text and "冰箱" in text


# ── cooking by a recipe ─────────────────────────────────────────────────

def test_following_a_recipe_and_changing_it(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book")
    stock("tomato", "egg")
    text, err = cook("西红柿炒鸡蛋", ["番茄", "鸡蛋×2"], recipe=TOMATO_EGG)
    assert not err and "改了做法" not in text
    serve(clock, 10)
    text, err = cook("番茄鸡蛋汤", ["番茄"], recipe=TOMATO_EGG)
    assert not err and "记成改了做法" in text and "鸡蛋" in text
    conn = db.connect()
    links = [r["recipe_link"] for r in conn.execute("SELECT recipe_link FROM cook_sessions ORDER BY started_at")]
    conn.close()
    assert links == ["follow", "changed"]


def test_an_unknown_recipe_opens_nothing_and_shortages_name_what_is_missing(clock):
    play_on("recipes_public", "recipe_cook")
    stock("tomato")
    assert cook("x", ["番茄"], recipe="hc-nope") == (TEXTS["cook_no_recipe"], True)
    text, err = cook("西红柿炒鸡蛋", ["番茄", "鸡蛋×2"], recipe=TOMATO_EGG)
    assert err and "照「西红柿炒鸡蛋」还缺:鸡蛋×2" in text


def test_buying_by_recipe_uses_one_coupon_and_skips_the_five_kinds_limit(clock):
    play_on("recipes_public", "recipe_cook")
    set_coupons(A, 1)
    config.override(fridge_buy_max_items=1)
    r = one(f"[买菜 照 {COLA_WINGS}]")
    assert r.ok and "鸡翅×1" in r.text and "可乐×1" in r.text and "还剩 0 张" in r.text
    r2 = one(f"[买菜 照 {COLA_WINGS}]")
    assert r2.ok and r2.text == TEXTS["buy_nothing"].format(name="可乐鸡翅")


def test_buying_by_recipe_without_the_switch_is_ordinary_buying(clock):
    set_coupons(A, 1)
    r = one(f"[买菜 照 {COLA_WINGS}]")
    assert not r.ok


# ── proficiency, mishaps, settlements ───────────────────────────────────

def test_three_good_pots_make_a_practised_hand_and_the_note_says_so(clock):
    play_on("recipes_public", "recipe_cook", "proficiency", "settle_card")
    for i in range(3):
        stock("egg")
        assert not cook("蒸水蛋", ["鸡蛋"], recipe=STEAMED_EGG)[1]
        serve(clock, 10)
    rows = settle_rows()
    assert [r["after_n"] for r in rows] == [1, 2, 3]
    assert rows[-1]["after_tier"] == "拿手" and rows[0]["first_time"] == 1
    sent = [n["text"] for n in notify.pending(A) if n["kind"] == "kitchen.served"]
    assert any("「蒸水蛋」做成 3 次了,现在是拿手。" in s for s in sent)


def test_old_pots_are_never_back_filled(clock):
    stock("egg")
    cook("煮蛋", ["鸡蛋"])
    serve(clock, 10)
    play_on("proficiency")
    service.scan_all()
    assert settle_rows() == []


def test_mishaps_are_decided_once_and_never_change_the_result(clock):
    assert progress.decide_mishap("s1", "fry", "招牌") is None
    picks = {progress.decide_mishap(f"s{i}", "fry", "生疏") for i in range(400)}
    picks.discard(None)
    assert picks and all(re.fullmatch(r"(fry|general)\.\d\d", p) for p in picks)
    assert progress.decide_mishap("s7", "fry", "生疏") == progress.decide_mishap("s7", "fry", "生疏")
    rate = sum(1 for i in range(3000) if progress.decide_mishap(f"x{i}", "boil", "生疏")) / 3000
    assert 0.07 < rate < 0.13


def test_the_settled_card_is_fixed_at_serving(clock):
    play_on("proficiency", "mishaps", "settle_card")
    stock("egg")
    cook("煮蛋", ["鸡蛋"])
    serve(clock, 10)
    sid = settle_rows()[0]["session_id"]
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    card = c.get("/api/kitchen", params={"session_id": sid}).json()["settlement"]
    assert card["has"] and card["proficiency"]["tier"] == "生疏" and card["proficiency"]["to_next"] == 2
    assert card["proficiency"]["next_tier"] == "拿手" and card["proficiency"]["tier_from"] == 0
    assert card["mishap"]["state"] in ("none", "had")
    assert {s["key"] for s in card["stamps"]} == {"first"}
    # later pots do not change this one's card
    for _ in range(3):
        stock("egg")
        cook("煮蛋", ["鸡蛋"])
        serve(clock, 10)
    assert c.get("/api/kitchen", params={"session_id": sid}).json()["settlement"] == card
    # the fourth pot is past the first tier: its bar starts at skilled_at and names the tier after that
    last = settle_rows()[-1]["session_id"]
    pr = c.get("/api/kitchen", params={"session_id": last}).json()["settlement"]["proficiency"]
    assert pr["tier"] == "拿手" and pr["next_tier"] == "招牌" and pr["tier_from"] == 3 and pr["to_next"] == 4


def test_new_dish_bonus_once_per_recipe(clock):
    play_on("recipes_public", "recipe_cook", "new_dish_bonus")
    for i in range(2):
        stock("egg")
        cook("蒸水蛋", ["鸡蛋"], recipe=STEAMED_EGG)
        serve(clock, 10)
        before = stamina.read(A)
        text = menu.eat(A, "蒸水蛋")
        after = stamina.read(A)
        if i == 0:
            assert "体力多回了一点" in text and after > before
        else:
            assert "体力多回了一点" not in text


def test_a_practised_hand_catches_a_bad_egg(clock):
    play_on("proficiency")
    conn = db.connect()
    conn.execute("INSERT INTO dish_counts (who, dish, n) VALUES (?,?,3)", (A, "煎蛋"))
    conn.commit()
    conn.close()
    stock("egg")
    clock["now"] += 40 * DAY          # every egg in the box has gone bad
    stock("egg")                       # a fresh box
    text, err = cook("煎蛋", ["鸡蛋"])
    assert not err and "先打在小碗里看了一眼" in text and "扔掉了,换了好的" in text and "下锅了" in text


def test_a_new_hand_still_ruins_the_pot_with_a_bad_egg(clock):
    play_on("proficiency")
    stock("egg")
    clock["now"] += 40 * DAY
    text, err = cook("煎蛋", ["鸡蛋"])
    assert "小碗" not in text
    conn = db.connect()
    st = conn.execute("SELECT status FROM cook_sessions").fetchone()["status"]
    conn.close()
    assert st == "ruined"


# ── the role's book, notes, menus, codes, orders ────────────────────────

def test_collect_record_adapt_and_note(clock):
    play_on("recipes_public", "recipe_book", "tasting_notes")
    assert one("[收藏 西红柿炒鸡蛋]").text.startswith("收进食谱本了")
    assert one("[收藏 西红柿炒鸡蛋]").text.startswith("已经在你的食谱本里了")
    r = one("[记菜 溏心蛋盖饭 鸡蛋 米饭 煮 10 | 第一次自己想的]")
    assert r.ok and r.text.startswith("记下了:溏心蛋盖饭(p-")
    assert not one("[记菜 只有名字]").ok
    assert "不是冰箱里会有的东西" in one("[记菜 怪菜 月亮 煮 5]").text
    r = one(f"[记菜 我的番茄蛋 番茄 鸡蛋 炒 8 改自 {TOMATO_EGG}]")
    pid = re.search(r"(p-[0-9a-f]+)", r.text).group(1)
    conn = db.connect()
    pages = {p["id"]: p for p in book.my_pages(conn, A)}
    conn.close()
    assert pages[pid]["kind"] == "adapt" and pages[pid]["ref_id"] == TOMATO_EGG
    assert one(f"[札记 {pid} 下次少放点盐]").text == "记下了。"
    mine = tools.call("kitchen_recipes", {"what": "mine"}, A).text
    assert "[自创] 溏心蛋盖饭" in mine and "[改编] 我的番茄蛋" in mine and "[收藏] 西红柿炒鸡蛋" in mine


def test_editing_a_page_adds_a_version_and_keeps_the_old_one(clock):
    play_on("recipe_book")
    a = one("[记菜 拌黄瓜 黄瓜 拌 5]").text
    b = one("[记菜 拌黄瓜 黄瓜 番茄 拌 6]").text
    pid = re.search(r"(p-[0-9a-f]+)", a).group(1)
    assert pid in b
    conn = db.connect()
    assert book.page_version(conn, pid, 1)["minutes"] == 5 and book.page_version(conn, pid)["minutes"] == 6
    conn.close()


def test_a_menu_counts_shared_ingredients_together(clock):
    play_on("recipes_public", "recipe_book", "menus")
    stock("egg")              # 6 eggs, no tomato
    r = one(f"[配一桌 {TOMATO_EGG} {STEAMED_EGG} | 早饭]")
    assert r.ok and "合起来还缺 番茄" in r.text


def test_a_code_carries_the_page_but_not_the_humans_notes(clock):
    play_on("recipe_book", "recipe_codes")
    pid = re.search(r"(p-[0-9a-f]+)", one("[记菜 拌黄瓜 黄瓜 拌 5 | 夏天吃]").text).group(1)
    conn = db.connect()
    conn.execute("INSERT INTO dex_notes (who, page_key, text, at) VALUES (?,?,?,?)", (A, "d:拌黄瓜", "秘密评语", 0))
    conn.commit()
    code = book.export_code(conn, A, pid)
    preview = book.decode_code(code)
    assert preview["name"] == "拌黄瓜" and preview["note"] == "夏天吃"
    assert "秘密评语" not in json.dumps(preview, ensure_ascii=False)
    first = book.import_code(conn, B, code, clock["now"])
    again = book.import_code(conn, B, code, clock["now"])
    conn.commit()
    conn.close()
    assert not first["duplicate"] and again["duplicate"] and first["page_id"] == again["page_id"]
    with pytest.raises(book.BookError):
        book.decode_code(code[:-1] + ("0" if code[-1] != "0" else "1"))
    with pytest.raises(book.BookError):
        book.decode_code("KC1.]]]")


def test_an_order_moves_on_by_itself(clock):
    play_on("recipes_public", "recipe_cook", "orders")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    o = c.post("/api/orders", json={"who": A, "recipe": STEAMED_EGG}).json()
    assert "点了:蒸水蛋" in tools.call("kitchen_status", {}, A).text
    assert one("[接单 蒸水蛋 想加点虾仁]").text.endswith("想换个做法——想加点虾仁。")
    stock("egg")
    cook("蒸水蛋", ["鸡蛋"], recipe=STEAMED_EGG)
    assert c.get("/api/orders", params={"who": A}).json()["orders"][0]["state"] == "cooking"
    tools.call("kitchen_cancel", {}, A)
    assert c.get("/api/orders", params={"who": A}).json()["orders"][0]["state"] == "received"
    stock("egg")
    cook("蒸水蛋", ["鸡蛋"], recipe=STEAMED_EGG)
    serve(clock, 10)
    assert c.get("/api/orders", params={"who": A}).json()["orders"][0]["state"] == "done"
    assert o["state"] == "received"


# ── the dish book and achievements ──────────────────────────────────────

def test_dish_book_pages_silhouettes_and_counts(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    one("[收藏 可乐鸡翅]")
    stock("egg")
    cook("蒸水蛋", ["鸡蛋"], recipe=STEAMED_EGG)
    serve(clock, 10)
    stock("egg")
    cook("我家的蛋", ["鸡蛋"])
    serve(clock, 10)
    stock("egg")
    cook("我家的蛋", ["鸡蛋"])
    tools.call("kitchen_cancel", {}, A)
    conn = db.connect()
    b = dex.build(conn, A)
    conn.close()
    keys = {p["key"]: p for p in b["pages"]}
    assert keys[f"r:{STEAMED_EGG}"]["made"] == 1 and keys["d:我家的蛋"]["made"] == 1
    assert keys["d:我家的蛋"]["pending"] is True
    assert [s["name"] for s in b["silhouettes"]] == ["可乐鸡翅"]
    assert b["backfill"] == {"scanned": 3, "counted": 2, "excluded": 1, "pages": 2, "pending": 1}
    assert b["totals"]["made_public"] == 1 and b["totals"]["art_missing"] == 2


def test_the_role_only_reads_achievements_it_has(clock):
    play_on("dex", "achievements", "recipes_public")
    assert tools.call("kitchen_recipes", {"what": "achievements"}, A).text == TEXTS["ach_none"]
    conn = db.connect()
    conn.execute("INSERT INTO achievements_earned (who, ach, earned_at, why) VALUES (?,?,?,?)",
                 (A, "first_burnt", clock["now"], "「x」糊了。"))
    conn.commit()
    everything = dex.all_for_human(conn, A)
    conn.close()
    text = tools.call("kitchen_recipes", {"what": "achievements"}, A).text
    assert "第一次糊锅" in text and "深夜开火" not in text
    assert any(a["name"] == "深夜开火" and not a["earned"] for a in everything)


def test_an_achievement_is_never_taken_back(clock):
    play_on("dex", "achievements")
    for _ in range(3):
        stock("egg")
        cook("煮蛋", ["鸡蛋"], method="煮")
        serve(clock, 10)
    conn = db.connect()
    assert "one_method" in {r["ach"] for r in conn.execute("SELECT ach FROM achievements_earned")}
    conn.execute("UPDATE cook_sessions SET status='cancelled'")
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    dex.evaluate_in_tx(conn, A)
    conn.commit()
    assert "one_method" in {r["ach"] for r in conn.execute("SELECT ach FROM achievements_earned")}
    conn.close()


def test_dish_pictures_are_drawn_one_at_a_time_and_kept(clock, tmp_path):
    play_on("dex")
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    calls = []
    dex.set_drawer(lambda name, ings, method: calls.append(name) or png)
    stock("egg")
    cook("煮蛋", ["鸡蛋"])
    serve(clock, 10)
    service.scan_all()
    conn = db.connect()
    art = dex.art_index(conn)["d:煮蛋"]
    v2 = dex.request_redraw(conn, "d:煮蛋")
    conn.commit()
    conn.close()
    assert art["state"] == "ready" and art["chosen"] == 1 and calls == ["煮蛋"]
    service.scan_all()
    conn = db.connect()
    art = dex.art_index(conn)["d:煮蛋"]
    assert dex.art_choose(conn, "d:煮蛋", 1)
    conn.commit()
    conn.close()
    assert v2 == 2 and [v["version"] for v in art["versions"]] == [1, 2] and dex.art_file("d:煮蛋", 1).is_file()


# ── plates ──────────────────────────────────────────────────────────────

def _plates(who=A):
    conn = db.connect()
    try:
        return dishes.view(conn, who, 0)["counts"]
    finally:
        conn.close()


def test_plates_go_into_the_dishwasher_unless_the_role_may_wash(clock):
    play_on("dishwash")
    stock("egg")
    cook("煮蛋", ["鸡蛋"])
    serve(clock, 10)
    menu.eat(A, "煮蛋")
    assert _plates()["machine"] == 1
    menu.add("面包", "her", A)          # a dish the human put on the menu: still a meal, still a plate
    menu.eat(A, "面包")
    dishes.set_settings(A, self_wash=True)
    stock("strawberry")
    menu.eat(A, "草莓")                 # straight from the fridge: no plate
    assert _plates()["machine"] == 2 and _plates()["sink"] == 0
    menu.add("饭团", "her", A)
    menu.eat(A, "饭团")
    assert _plates()["sink"] == 1


def test_washing_takes_real_time_and_is_told_next_turn(clock):
    play_on("dishwash")
    dishes.set_settings(A, self_wash=True)
    for i in range(3):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    r = one("[刷盘子]")
    assert r.ok and r.text == "开始刷了:3 只盘子,大概 6 分钟。"
    assert one("[刷盘子]").text.startswith("正在刷:还剩 3 只")
    assert "正在刷盘子" in tools.call("kitchen_status", {}, A).text
    clock["now"] += 3 * 120 + 1
    service.scan_all()
    told = [n for n in notify.pending(A) if n["kind"] == dishes.KIND_DONE]
    assert len(told) == 1 and "3 只盘子刷完了" in told[0]["text"]
    c = _plates()
    assert c["clean"] + c["broken"] == 3 and c["sink"] == 0


def test_turning_self_wash_off_midway_keeps_what_was_washed(clock):
    play_on("dishwash")
    dishes.set_settings(A, self_wash=True, quota=2)
    for i in range(3):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    one("[刷盘子]")
    clock["now"] += 121
    dishes.set_settings(A, self_wash=False)
    c = _plates()
    assert c["clean"] + c["broken"] == 1 and c["machine"] == 2
    service.scan_all()
    assert any("刷了 1 只,剩下的进洗碗机了" in n["text"] for n in notify.pending(A))


def test_the_page_reads_which_plates_break_and_when_plates_went_into_the_dishwasher(clock):
    """What the page's washing-up and dishwasher clips are played from."""
    play_on("dishwash")
    config.override(dishwash_break_rate=1.0)          # every plate breaks: the plan is all of them
    dishes.set_settings(A, self_wash=True)
    for i in range(2):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    one("[刷盘子]")

    def view(at):
        conn = db.connect()
        try:
            return dishes.view(conn, A, at)
        finally:
            conn.close()
    start = clock["now"]
    # a plate's result is only told once its time is up: none before, the first after 120 s, both after 240 s
    assert view(start)["job"]["breaks"] == [] and view(start)["job"]["n"] == 2 and view(start)["machine_at"] is None
    assert view(start + 119)["job"]["breaks"] == []
    assert view(start + 120)["job"]["breaks"] == [0]
    assert view(start + 239)["job"]["breaks"] == [0]
    assert view(start + 240)["job"]["breaks"] == [0, 1]
    config.override(dishwash_break_rate=0.05)
    clock["now"] += 2 * 120 + 1
    dishes.set_settings(A, self_wash=False)            # from now on, plates go straight into the dishwasher
    menu.add("饭2", "her", A)
    menu.eat(A, "饭2")
    conn = db.connect()
    try:
        v = dishes.view(conn, A, clock["now"])
    finally:
        conn.close()
    assert v["counts"]["broken"] == 2 and v["machine_at"] == clock["now"]


def test_a_washing_stopped_midway_tells_only_the_plates_washed_before_it_stopped(clock):
    play_on("dishwash")
    config.override(dishwash_break_rate=1.0)
    dishes.set_settings(A, self_wash=True)
    for i in range(3):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    one("[刷盘子]")
    clock["now"] += 121
    dishes.set_settings(A, self_wash=False)             # stopped after one plate: the other two went into the dishwasher
    conn = db.connect()
    try:
        v = dishes.view(conn, A, clock["now"] + 3600)
    finally:
        conn.close()
    assert v["job"]["state"] == "stopped" and v["job"]["breaks"] == [0]


def test_starting_a_washing_hands_the_chat_a_washing_card(clock):
    play_on("dishwash")
    dishes.set_settings(A, self_wash=True, quota=2)
    for i in range(3):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    mid = uuid.uuid4().hex
    r = reply("[刷盘子]", mid=mid)[0]
    assert r.ok and len(r.attachments) == 1
    card = r.attachments[0]
    assert card["kind"] == "kitchen_washing" and card["who"] == A and card["n"] == 2
    assert card["per_s"] == 120 and card["started_at"] == clock["now"] and card["job_id"]
    # the same reply again: the same card, nothing started twice
    again = reply("[刷盘子]", mid=mid)[0]
    assert again.attachments == [card]
    # already washing: the receipt is that washing's progress, no new card
    busy = one("[刷盘子]")
    assert busy.ok and busy.text.startswith("正在刷") and busy.attachments == []
    # over REST too, in the receipts of POST /api/inline
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    body = client.post("/api/inline", json={"who": A, "text": "[刷盘子]", "message_id": mid}).json()
    assert body["receipts"][0]["attachments"] == [card]


def test_a_marker_that_starts_no_washing_has_no_card(clock):
    play_on("dishwash")
    dishes.set_settings(A, self_wash=True)
    r = one("[刷盘子]")                          # an empty sink
    assert r.text == "水槽里没有盘子。" and r.attachments == []
    dishes.set_settings(A, self_wash=False)
    assert one("[刷盘子]").attachments == []      # plates go into the dishwasher: nothing to wash
    assert one("[吃 不存在的菜]").attachments == []


def test_the_washing_card_reads_one_washing_back(clock):
    """What the card plays from: each plate's result only once its time is up; the end; a stop midway."""
    play_on("dishwash")
    config.override(dishwash_break_rate=1.0)          # every plate breaks
    dishes.set_settings(A, self_wash=True)
    for i in range(3):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    jid = one("[刷盘子]").attachments[0]["job_id"]
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    start = clock["now"]

    def read():
        res = client.get(f"/api/dishes/jobs/{jid}")
        assert res.status_code == 200
        return res.json()
    j = read()
    assert j["state"] == "running" and j["n"] == 3 and j["per_s"] == 120 and j["started_at"] == start
    assert [d["state"] for d in j["dishes"]] == ["washing"] * 3 and "timezone" in j
    clock["now"] = start + 119
    assert read()["counts"]["broken"] == 0           # not told before its time
    clock["now"] = start + 120
    j = read()
    assert [d["state"] for d in j["dishes"]] == ["broken", "washing", "washing"]
    assert j["dishes"][0]["done_at"] == start + 120 and j["counts"] == {"washing": 2, "clean": 0, "broken": 1, "machine": 0}
    clock["now"] = start + 121
    dishes.set_settings(A, self_wash=False)            # stopped: the other two go into the dishwasher
    j = read()
    assert j["state"] == "stopped" and j["ended_at"] == start + 121
    assert j["counts"] == {"washing": 0, "clean": 0, "broken": 1, "machine": 2}
    assert client.get("/api/dishes/jobs/nope").status_code == 404


def test_the_washing_card_reads_a_finished_washing_and_one_stopped_by_the_switch(clock):
    play_on("dishwash")
    dishes.set_settings(A, self_wash=True)
    for i in range(2):
        menu.add(f"饭{i}", "her", A)
        menu.eat(A, f"饭{i}")
    jid = one("[刷盘子]").attachments[0]["job_id"]
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    clock["now"] += 2 * 120 + 5
    j = client.get(f"/api/dishes/jobs/{jid}").json()
    assert j["state"] == "done" and j["ended_at"] == j["started_at"] + 240
    assert j["counts"]["washing"] == 0 and j["counts"]["clean"] + j["counts"]["broken"] == 2
    # a second washing, then the whole feature switched off: the card still reads it, and it was stopped
    menu.add("饭2", "her", A)
    menu.eat(A, "饭2")
    jid2 = one("[刷盘子]").attachments[0]["job_id"]
    config.override(play_dishwash=False)
    clock["now"] += 10
    j = client.get(f"/api/dishes/jobs/{jid2}").json()
    assert j["state"] == "stopped" and j["counts"]["machine"] == 1


def test_the_page_reads_when_an_order_last_changed(clock):
    play_on("vendor")
    _visit(clock, "chestnut", seed=3)
    o = vendor.treat(A, "roast_chestnut", 1, request_id="r1")
    mine = vendor.overview(A)["mine"]
    assert [m["id"] for m in mine] == [o["id"]] and mine[0]["payer"] == "her"
    assert mine[0]["state"] == vendor.DELIVERED and mine[0]["updated_at"] >= mine[0]["created_at"]


def test_the_page_still_reads_a_visit_for_a_short_while_after_it_ends(clock):
    # so it can finish showing an order under way and show the vendor leaving; nothing can be bought from it
    play_on("vendor")
    v = _visit(clock, "chestnut", seed=3)
    o = vendor.treat(A, "roast_chestnut", 1, request_id="r1")
    ov = vendor.overview(A)
    assert ov["ended"] is None and ov["visit"]["id"] == v["id"]
    assert ov["mine"][0]["kind"] == "snack" and ov["mine"][0]["item_id"] == "roast_chestnut"
    clock["now"] = v["leave_at"] + 5
    ov = vendor.overview(A)
    assert ov["visit"] is None and ov["ended"]["id"] == v["id"] and ov["ended"]["vendor"] == "chestnut"
    assert [m["id"] for m in ov["mine"]] == [o["id"]]
    assert {"name", "kind"} <= set(ov["ended"]["goods"][0])
    with pytest.raises(vendor.VendorError):
        vendor.treat(A, "roast_chestnut", 1, request_id="r2")
    clock["now"] = v["leave_at"] + vendor.ENDED_GRACE_S + 1
    ov = vendor.overview(A)
    assert ov["visit"] is None and ov["ended"] is None and ov["mine"] == []


def test_about_one_plate_in_twenty_breaks():
    n = len(dishes.roll_breaks(4000, 0.05))
    assert 140 < n < 260
    assert dishes.roll_breaks(50, 0.0) == [] and dishes.roll_breaks(5, 1.0) == [0, 1, 2, 3, 4]


def _sink(n: int, who: str = A) -> None:
    """n plates in the sink, as n meals would leave them (without eating n meals)."""
    dishes.set_settings(who, self_wash=True)
    conn = db.connect()
    try:
        for i in range(n):
            dishes.produce_in_tx(conn, who, f"eat:test:{uuid.uuid4().hex}", f"饭{i}", clock_now())
        conn.commit()
    finally:
        conn.close()


def clock_now() -> float:
    from kitchenette import clock as clock_mod
    return clock_mod.now()


def _plan(jid: str) -> list[int]:
    conn = db.connect()
    try:
        return json.loads(conn.execute("SELECT break_idx_json FROM wash_jobs WHERE id=?", (jid,)).fetchone()[0])
    finally:
        conn.close()


def test_which_plates_break_cannot_be_worked_out_from_the_washing_id(clock, monkeypatch):
    """The plan is drawn from private randomness when the washing starts and only kept in the database."""
    play_on("dishwash")
    config.override(dishwash_break_rate=0.5)
    draws = iter([0.9, 0.1, 0.9, 0.1, 0.9, 0.1])

    class Fixed:
        def random(self):
            return next(draws)
    monkeypatch.setattr(dishes, "_rng", Fixed())
    _sink(6)
    jid = one("[刷盘子]").attachments[0]["job_id"]
    assert _plan(jid) == [1, 3, 5]                     # whatever the private draw says, nothing else
    monkeypatch.setattr(dishes, "_rng", dishes.secrets.SystemRandom())   # (not undo(): that would take the clock too)
    clock["now"] += 6 * 120 + 1
    service.scan_all()
    _sink(40)
    jid2 = one("[刷盘子]").attachments[0]["job_id"]
    assert _plan(jid2) != [i for i in range(40) if dishes._h(f"break:{jid2}:{i}") < 0.5]   # 1 in 2**40 to collide


def test_a_washing_started_before_keeps_the_plan_it_was_stored_with(clock):
    """A washing already in the database (its plan drawn the old way) is played from what was stored."""
    play_on("dishwash")
    config.override(dishwash_break_rate=0.0)          # nothing would break if it were drawn now
    _sink(2)
    jid = one("[刷盘子]").attachments[0]["job_id"]
    conn = db.connect()
    try:
        conn.execute("UPDATE wash_jobs SET break_idx_json=? WHERE id=?", (json.dumps([0]), jid))
        conn.commit()
    finally:
        conn.close()
    clock["now"] += 2 * 120 + 1
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    j = client.get(f"/api/dishes/jobs/{jid}").json()
    assert [d["state"] for d in j["dishes"]] == ["broken", "clean"]


def test_the_washing_card_reads_only_washings_of_roles_this_server_serves(clock):
    """The readback skips the feature switch, never the role boundary: another role's washing is not there."""
    play_on("dishwash")
    _sink(2, who=B)
    jid = one("[刷盘子]", who=B).attachments[0]["job_id"]
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    assert client.get(f"/api/dishes/jobs/{jid}").status_code == 200
    config.override(roles_allowed=[A])
    clock["now"] += 3 * 120
    assert client.get(f"/api/dishes/jobs/{jid}").status_code == 404
    conn = db.connect()
    try:                                               # and nothing was settled for it on the way
        assert conn.execute("SELECT state FROM wash_jobs WHERE id=?", (jid,)).fetchone()[0] == "running"
        assert conn.execute("SELECT COUNT(*) FROM dishes WHERE job_id=? AND state='washing'", (jid,)).fetchone()[0] == 2
    finally:
        conn.close()


# ── jars ────────────────────────────────────────────────────────────────

def test_sealing_waiting_opening_and_taking(clock):
    play_on("seal_jars")
    stock("apple", "apple", "carrot")
    assert one("[封罐 苹果 冰糖 | 给冬天]").text.startswith("封上了:苹果、冰糖。")
    assert one("[封罐 胡萝卜 盐]").ok
    assert one("[封罐 苹果 蜂蜜]").ok
    assert one("[封罐 苹果 糖]").text.startswith("没封成:三只罐子都用着")
    clock["now"] += 3 * DAY + 60
    service.scan_all()
    opened = [n["text"] for n in notify.pending(A) if n["kind"] == jars.KIND_OPENED]
    assert any("苹果酒泡好了" in s for s in opened) and any("腌胡萝卜" in s for s in opened)
    r = tools.call("snack_eat", {"name": "苹果酒"}, A)
    assert not r.is_error and r.text == "喝了一份苹果酒。封罐时的纸条:「给冬天」"


def test_jar_servings_share_one_daily_cap(clock):
    play_on("seal_jars")
    config.override(jars_daily_cap=1)
    stock("apple")
    one("[封罐 苹果 冰糖]")
    clock["now"] += 3 * DAY + 60
    assert not tools.call("snack_eat", {"name": "苹果酒"}, A).is_error
    r = tools.call("snack_eat", {"name": "苹果酒"}, A)
    assert r.is_error and "到上限了" in r.text


def test_something_spoiled_in_a_jar_comes_out_spoiled(clock):
    play_on("seal_jars")
    stock("apple")
    clock["now"] += 8 * DAY               # spoiled, not yet cleared from the fridge
    assert one("[封罐 苹果 冰糖]").ok
    clock["now"] += 3 * DAY + 60
    service.scan_all()
    assert any("开出来是坏的" in n["text"] for n in notify.pending(A))


def test_anything_in_the_fridge_with_any_seasonings_and_a_name_of_its_own(clock):
    play_on("seal_jars")
    stock("egg", "tofu")
    r = one("[封罐 鸡蛋 酱油、糖、小米辣 = 麻药鸡蛋 | 等周五开]")
    assert r.ok and r.text.startswith("封上了:鸡蛋、酱油、糖、小米辣(开出来叫麻药鸡蛋)。明天") \
        and r.text.endswith("纸条:「等周五开」")
    assert one("[封罐 豆腐 桂花酱]").text.startswith("封上了:豆腐、桂花酱。后天")    # a seasoning it never heard of
    conn = db.connect()
    try:
        assert [j["goods_name"] for j in jars.jars_view(conn, A)][:2] == ["麻药鸡蛋", "桂花酱豆腐"]
    finally:
        conn.close()
    clock["now"] += DAY + 60
    service.scan_all()
    assert any("麻药鸡蛋泡好了" in n["text"] for n in notify.pending(A))
    r = tools.call("snack_eat", {"name": "麻药鸡蛋"}, A)
    assert not r.is_error and r.text == "吃了一份麻药鸡蛋。封罐时的纸条:「等周五开」"
    assert tools.call("snack_eat", {"name": "桂花酱豆腐"}, A).is_error                   # the tofu is not ready yet
    clock["now"] += DAY
    assert not tools.call("snack_eat", {"name": "桂花酱豆腐"}, A).is_error


def test_how_long_a_jar_waits_and_what_comes_out_is_called():
    from kitchenette.texts_play import vendor_id
    days = {iid: jars.jar_days(fridge.item(iid), iid) for iid in ("apple", "lemon", "carrot", "egg", "tofu", "beef",
                                                                 "noodles", vendor_id("山楂"), vendor_id("干桂花"))}
    assert days == {"apple": 3, "lemon": 2, "carrot": 1, "egg": 1, "tofu": 2, "beef": 2, "noodles": 2,
                    vendor_id("山楂"): 2, vendor_id("干桂花"): 1}
    name = jars.auto_name
    assert (name("桃子", "fruit", ["冰糖"]), name("柠檬", "fruit", ["蜂蜜"]), name("白萝卜", "root", ["盐"])) == \
        ("桃子酒", "柠檬蜜", "腌白萝卜")                                               # the three from before
    assert (name("干桂花", "veg", ["糖"]), name("豆腐", "dairy", ["盐"]), name("梨", "fruit", ["蜂蜜", "盐"]),
            name("鸡蛋", "dairy", ["酱油", "糖"]), name("黄瓜", "veg", ["醋"])) == \
        ("糖渍干桂花", "盐渍豆腐", "梨蜜", "酱油鸡蛋", "醋黄瓜")
    assert jars.goods_name("布丁") == "布丁(罐)" and jars.goods_name("麻药鸡蛋") == "麻药鸡蛋"


def test_the_marker_reads_loosely_and_still_says_how_when_it_cannot():
    assert jars.parse("鸡蛋 酱油,糖，小米辣 ＝ 麻药 鸡蛋 ｜ 纸条") == ("鸡蛋", ["酱油", "糖", "小米辣"], "麻药鸡蛋", "纸条")
    assert jars.parse("桃子 冰糖 | 给冬天") == ("桃子", ["冰糖"], "", "给冬天")             # the old way
    assert jars.parse("桃子 糖 糖") == ("桃子", ["糖"], "", "")
    for bad in ("桃子", "", "= 名字 | 纸条"):
        with pytest.raises(jars.JarError) as e:
            jars.parse(bad)
        assert e.value.text == "没封成:写成 [封罐 食材 调料 | 纸条] 这样,如 [封罐 鸡蛋 酱油、糖 = 麻药鸡蛋 | 纸条]。"
    with pytest.raises(jars.JarError):
        jars.parse("桃子 " + "、".join("糖盐醋酒姜蒜葱"))                                    # seven seasonings


def test_a_combination_known_to_go_wrong_is_sealed_and_mostly_comes_out_spoiled(clock, monkeypatch):
    play_on("seal_jars")
    milk, beef, udon = (fridge.item(i) for i in ("milk", "beef", "udon"))
    assert jars.is_odd(milk, ["盐"]) and jars.is_odd(milk, ["醋"]) and not jars.is_odd(milk, ["糖"])
    assert jars.is_odd(beef, ["糖", "蜂蜜"]) and not jars.is_odd(beef, ["酱油", "糖"])
    assert jars.is_odd(udon, ["糖"]) and not jars.is_odd(fridge.item("egg"), ["酱油"])
    stock("milk", "milk")
    monkeypatch.setattr(jars, "JAR_ODD_FAIL_P", 1.0)
    assert one("[封罐 牛奶 盐、醋 | 试试]").ok                     # not refused when sealing
    clock["now"] += 2 * DAY + 60
    service.scan_all()
    assert "窗台上那罐牛奶、盐、醋开出来味道不对,整罐扔了,罐子洗干净空出来了。" in [n["text"] for n in notify.pending(A)
                                                                     if n["kind"] == jars.KIND_OPENED][-1]
    r = tools.call("snack_eat", {"name": "盐渍牛奶"}, A)
    assert r.is_error
    monkeypatch.setattr(jars, "JAR_ODD_FAIL_P", 0.0)               # the other one in five: it came out fine
    assert one("[封罐 牛奶 盐]").ok
    clock["now"] += 2 * DAY + 60
    assert not tools.call("snack_eat", {"name": "盐渍牛奶"}, A).is_error


# ── vendors ─────────────────────────────────────────────────────────────

def _visit(clock, vid="tanghulu", seed=1) -> dict:
    conn = db.connect()
    try:
        now = clock["now"]
        goods = vendor.stock_goods(conn, vid, now, random.Random(seed))
        conn.execute("INSERT INTO vendor_visits (id, day, slot, vendor, arrive_at, leave_at, goods_json, created_at)"
                     " VALUES (?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, vendor.kitchen_day(now), 9, vid, now,
                                                    now + 3600, json.dumps(goods, ensure_ascii=False), now))
        conn.commit()
        return vendor.live_visit(conn, now)
    finally:
        conn.close()


def test_a_day_has_at_most_two_visits_within_hours_and_never_the_same_vendor_twice():
    for seed in range(200):
        plan = vendor.plan_day("2027-01-15", rng=random.Random(seed), rain=False, prev_last="popcorn")
        assert len(plan) <= 2
        assert all(p["vendor"] != "popcorn" for p in plan[:1])
        assert len({p["vendor"] for p in plan}) == len(plan)
        assert all(p["vendor"] != "icecream" for p in plan)           # January
    for seed in range(100):
        plan = vendor.plan_day("2027-07-15", rng=random.Random(seed), rain=True, prev_last=None)
        assert all(p["vendor"] != "icecream" for p in plan)


def test_buying_with_the_built_in_ledger(clock):
    play_on("vendor")
    _visit(clock)
    r = one("[买 山楂糖葫芦 2]")
    assert not r.ok and r.text.startswith("没买成:零花钱不够")
    vendor.LocalWallet().grant(A, 100)
    r = one("[买 山楂糖葫芦 2]")
    assert r.ok and r.text.startswith("买了 2 串山楂糖葫芦,花了 10。零花钱还剩 90。当场吃掉了。")
    assert "小贩说:「好嘞,拿稳了,签子尖。」" in r.text
    r = one("[买 山楂 2]")
    assert r.ok and "放进冰箱了(小贩专供,超市没有卖)" in r.text and "附了一张纸条" in r.text
    assert any(b["name"] == "山楂" for b in fridge.overview(A)["items"])
    config.override(vendor_order_max=8)
    assert one("[买 山楂糖葫芦 2]").text == "没买成:一次最多花 8,这一单要 10。"


def test_the_day_limit_and_the_human_treating_is_free(clock):
    play_on("vendor")
    v = _visit(clock, "chestnut", seed=3)
    vendor.LocalWallet().grant(A, 500)
    config.override(vendor_day_max=10)
    assert one("[买 糖炒栗子 1]").ok
    assert "今天在小贩这儿已经花了 7" in one("[买 糖炒栗子 1]").text
    o = vendor.treat(A, "roast_chestnut", 1, request_id="r1")
    assert o["state"] == vendor.DELIVERED and o["payer"] == "her"
    assert vendor.LocalWallet().balance(A) == 493
    assert v["goods"]


def test_what_a_model_says_is_checked_before_the_role_sees_it(clock):
    play_on("vendor")
    _visit(clock)
    vendor.set_talker(lambda system, history, line: "便宜卖你,三块钱一串")
    r = one("[问小贩 多少钱]")
    assert r.ok and "小贩说:「刚蘸的,糖壳还脆着呢。」" in r.text and "山楂糖葫芦 5 一串" in r.text
    vendor.set_talker(lambda system, history, line: "刚出锅的,快尝尝。")
    assert "小贩说:「刚出锅的,快尝尝。」" in one("[问小贩 甜不甜]").text
    assert vendor.check_line(config.get().words_human_name + "好") is None
    for _ in range(4):
        one("[问小贩 还有吗]")
    assert one("[问小贩 再问一句]").text.startswith("没问成:这一趟已经问了 6 句")


def test_no_model_means_the_fixed_line(clock):
    play_on("vendor")
    _visit(clock)
    assert "小贩说:「刚蘸的,糖壳还脆着呢。」" in one("[问小贩 你好]").text


def test_flowers_on_the_sill_and_asking_for_a_new_kind(clock):
    play_on("vendor")
    _visit(clock, "florist", seed=5)
    vendor.LocalWallet().grant(A, 100)
    goods = [g for g in vendor.overview(A)["visit"]["goods"] if g["kind"] == "flower"]
    r = one(f"[买 {goods[0]['name']} 1]")
    assert r.ok and "插在窗台的花瓶里了" in r.text
    assert f"窗台上插着一束{goods[0]['name']}" in tools.call("kitchen_status", {}, A).text
    assert one("[送花 今天的花给你]").text.startswith("花送给")
    assert "已经送过了" in one("[送花 再送一次]").text
    assert "递给" in one("[想要花 风信子]").text
    req = vendor.flower_requests(A)[0]
    vendor.decide(req["id"], True)
    assert any("同意了你想要的「风信子」" in n["text"] for n in notify.pending(A))


def test_vendors_never_leave_a_note_for_a_sleeping_role(clock):
    play_on("vendor")
    config.override(notify_respect_sleep=True)
    fridge.buy_her(A, ["egg"])
    fridge.buy_her(B, ["egg"])
    sleep.set_asleep_hook(lambda who, now: who == B)
    _visit(clock)
    service.scan_all()
    assert [n for n in notify.pending(A) if n["kind"] == vendor.KIND_ARRIVED]
    assert not [n for n in notify.pending(B) if n["kind"] == vendor.KIND_ARRIVED]


def test_vendors_off_means_no_visit_but_an_order_under_way_is_finished(clock):
    play_on("vendor")
    _visit(clock)

    class Slow(vendor.LocalWallet):
        calls = 0

        def debit(self, *a):
            Slow.calls += 1
            return vendor.Result(vendor.UNKNOWN) if Slow.calls == 1 else super().debit(*a)
    vendor.set_wallet(Slow())
    Slow().grant(A, 100)
    r = one("[买 山楂糖葫芦 1]")
    assert r.ok and r.text == TEXTS["vbuy_pending"]
    config.override(play_vendor=False)
    clock["now"] += 120
    service.scan_all()
    assert any("买了 1 串山楂糖葫芦" in n["text"] for n in notify.pending(A))
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM wallet_local WHERE kind='vendor'").fetchone()[0] == 1
    conn.close()


# ── the page's view, and what is never in the package ──────────────────

def test_features_endpoint_and_switched_off_endpoints_say_so(clock):
    play_on("recipes_public", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    feats = {f["key"]: f for f in c.get("/api/features").json()["features"]}
    assert feats["recipes_public"]["on"] and not feats["vendor"]["on"]
    assert c.get("/api/vendor", params={"who": A}).status_code == 409
    assert c.get("/api/recipes", params={"q": "鸡蛋"}).json()["total"] > 300
    assert c.get("/api/dex", params={"who": A}).status_code == 200
    assert c.get("/api/about").json()["features"]["dex"] is True


def test_with_markers_off_the_new_wording_names_no_marker(clock):
    config.override(inline_enabled=False)
    play_on(everything=True)
    cook_desc = next(s for s in tools.schemas() if s["name"] == "kitchen_cook")["description"]
    assert "[" not in cook_desc
    stock("tomato")
    text = tools.call("kitchen_cook", {"dish": "番茄汤", "minutes": 5, "ingredients": ["番茄"],
                                       "recipe": TOMATO_EGG}, A).text
    assert "[" not in text


def test_with_markers_on_the_cooking_tool_teaches_what_is_on(clock):
    config.override(inline_enabled=True)
    play_on("recipes_public", "recipe_book", "dishwash")
    desc = next(s for s in tools.schemas() if s["name"] == "kitchen_cook")["description"]
    assert "[收藏 菜名或编号]" in desc and "[刷盘子]" in desc and "[封罐" not in desc


def test_every_vendor_price_is_within_the_agreed_ranges():
    for v in VENDORS.values():
        for g in v["goods"]:
            lo, hi = (3, 8) if g["kind"] == "snack" else (8, 15)
            assert lo <= g["price"] <= hi


def test_a_fresh_install_with_the_defaults_walks_through(clock):
    defaults = config.Settings()
    config.override(**{f"play_{k}": getattr(defaults, f"play_{k}") for k in play.KEYS}, inline_enabled=True)
    names = [s["name"] for s in tools.schemas()]
    assert "kitchen_recipes" in names
    stock("tomato", "egg")
    status = tools.call("kitchen_status", {}, A).text
    assert "今天" in status
    assert one("[收藏 西红柿炒鸡蛋]").ok
    text, err = cook("西红柿炒鸡蛋", ["番茄", "鸡蛋×2"], recipe=TOMATO_EGG)
    assert not err
    serve(clock, 15)
    assert "体力多回了一点" in menu.eat(A, "西红柿炒鸡蛋")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    d = c.get("/api/dex", params={"who": A}).json()
    assert d["pages"][0]["key"] == f"r:{TOMATO_EGG}" and d["achievements"]
    assert c.get("/api/dishes", params={"who": A}).status_code == 409      # plates are off by default
    assert inline.parse("[刷盘子]") == []


def test_the_example_file_lists_the_defaults():
    s = config.build(Path(__file__).resolve().parents[1] / "examples" / "play.toml", env={})
    d = config.Settings()
    assert all(getattr(s, f"play_{k}") == getattr(d, f"play_{k}") for k in play.KEYS)
    assert (s.recipes_skilled_at, s.recipes_signature_at, s.jars_daily_cap, s.vendor_order_max, s.vendor_day_max) == \
           (3, 8, 3, 30, 60)


def test_recipe_ingredients_outside_the_catalog_are_sold_but_vendor_only_things_are_not(clock):
    set_coupons(A, 2)
    assert not one("[买菜 午餐肉]").ok                    # public recipes off: not sold
    play_on("recipes_public")
    r = one("[买菜 午餐肉]")
    assert r.ok and "午餐肉" in r.text
    assert recipes.item_sold(fridge.resolve("午餐肉")) and not recipes.item_sold(fridge.resolve("山药", gone=True))
    assert not one("[买菜 山药]").ok                      # only a vendor brings yams
    assert fridge.resolve("山药") is None and fridge.resolve("山药", gone=True) is not None


def test_a_kind_the_human_added_and_a_recipe_ingredient_of_the_same_name_are_one_thing(clock):
    play_on("recipes_public", "recipe_cook")
    kid = fridge.add_kind("午餐肉", "meat")["id"]
    vid = recipes.vendor_resolve("午餐肉")
    assert fridge.canon(vid) == kid
    stock(kid)
    conn = db.connect()
    have = recipes.fridge_snapshot(fridge._batches(conn, A, clock["now"]))
    conn.close()
    assert recipes.feasibility([[{"item": vid, "qty": 1}]], have)["ok"]
    used = fridge.take_for_cooking(A, [("午餐肉", 1)])
    assert used[0]["item_id"] == kid


def test_the_settled_card_names_the_dish_picture():
    assert progress.dish_icon("番茄炒蛋") == "stirfry"
    assert progress.dish_icon("面包") == "bake" and progress.dish_icon("汤圆") == "dessert"
    assert progress.dish_icon("一个谁都不认得的名字") == "bowl"


def test_money_and_feeding_happen_once_per_key(clock):
    play_on("vendor", "seal_jars")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.post("/api/wallet/grant", json={"who": A, "amount": 50}).status_code == 400      # no key
    for _ in range(2):
        r = c.post("/api/wallet/grant", json={"who": A, "amount": 50, "key": "g1"})
        assert r.status_code == 200 and r.json()["balance"] == 50
    assert c.post("/api/wallet/grant", json={"who": A, "amount": 70, "key": "g1"}).status_code == 409
    stock("apple")
    one("[封罐 苹果 冰糖]")
    clock["now"] += 3 * DAY + 60
    assert c.post("/api/jars/feed", json={"who": A, "name": "苹果酒"}).status_code == 400      # no key
    first = c.post("/api/jars/feed", json={"who": A, "name": "苹果酒", "key": "f1"}).json()
    again = c.post("/api/jars/feed", json={"who": A, "name": "苹果酒", "key": "f1"}).json()
    assert again.get("duplicate") and again["text"] == first["text"]


def test_a_voided_charge_is_never_charged_again_and_an_order_id_keeps_its_good(clock):
    play_on("vendor")
    w = vendor.LocalWallet()
    w.grant(A, 100)
    assert w.debit("o1", A, 10, "x").status == vendor.OK
    assert w.void("o1") == vendor.OK
    assert w.debit("o1", A, 10, "x").status == vendor.CONFLICT
    _visit(clock)
    vendor._create(A, order_id="o2", item_name="山楂糖葫芦", item_id=None, qty=1, payer="self", now=clock["now"])
    with pytest.raises(vendor.VendorError):
        vendor._create(A, order_id="o2", item_name="草莓糖葫芦", item_id=None, qty=1, payer="self", now=clock["now"])


def test_switched_off_and_bad_input_answers(clock):
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.get("/api/prefs", params={"who": A}).status_code == 409
    play_on("dex")
    assert c.put("/api/dex/art/choice", json={"page_key": "d:x", "version": "abc"}).status_code == 400


def test_the_built_in_ledger_starts_at_zero_and_the_role_hears_of_pocket_money(clock):
    play_on("vendor")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.get("/api/wallet", params={"who": A}).json() == {"local": True, "balance": 0}
    service.scan_all()
    assert c.get("/api/wallet", params={"who": A}).json()["balance"] == 0          # nothing is paid by itself
    for _ in range(2):                                                              # a retry of the same grant
        assert c.post("/api/wallet/grant", json={"who": A, "amount": 25, "key": "k1"}).json() == {"balance": 25}
    told = [n["text"] for n in notify.pending(A) if n["kind"] == "pocket.given"]
    assert len(told) == 1 and told[0].endswith("给了你 25 零花钱,现在有 25。")


class _PocketServer:
    """A pocket-money system of someone's own, speaking the contract in docs/UPGRADE.md."""

    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        rows: dict = {}
        bal = {"aster": 20}
        seen = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                seen.append(self.headers.get("Authorization"))
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                mode = outer.mode
                if mode == "401":
                    return self._send(401, {})
                if mode == "sleep":
                    import time
                    time.sleep(1.0)
                    return self._send(201, {"balance": 0})
                if mode == "redirect":
                    self.send_response(307)
                    self.send_header("Location", "http://127.0.0.1:9/elsewhere")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                if self.path == "/debit":
                    r = rows.get(body["order_id"])
                    if r:
                        return self._send(200 if (r["who"], r["amount"]) == (body["who"], body["amount"]) else 409,
                                          {"balance": bal[body["who"]]})
                    if bal.get(body["who"], 0) < body["amount"]:
                        return self._send(402, {"balance": bal.get(body["who"], 0)})
                    rows[body["order_id"]] = {**body, "status": "active"}
                    bal[body["who"]] -= body["amount"]
                    if mode == "500":           # charged, but the answer is lost in an error
                        return self._send(500, {})
                    return self._send(201, {"balance": bal[body["who"]]})
                oid = self.path.split("/")[2]
                if oid not in rows:
                    return self._send(404, {})
                if rows[oid]["status"] == "active":
                    rows[oid]["status"] = "voided"
                    bal[rows[oid]["who"]] += rows[oid]["amount"]
                return self._send(200, {})

            def do_GET(self):
                if self.path.startswith("/balance"):
                    return self._send(200, {"balance": bal.get(self.path.split("=")[1], 0)})
                oid = self.path.split("/")[2]
                r = rows.get(oid)
                return self._send(200, {"found": bool(r), **({"status": r["status"]} if r else {})})

        outer = self
        self.mode = "ok"
        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.seen = seen
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def test_your_own_wallet_over_http_is_charged_and_the_ledger_is_not_used(clock):
    srv = _PocketServer()
    try:
        play_on("vendor")
        config.override(vendor_wallet_url=srv.url, vendor_wallet_token="tok")
        assert not vendor.wallet_is_local()
        _visit(clock)
        r = one("[买 山楂糖葫芦 2]")
        assert r.ok and "零花钱还剩 10" in r.text
        assert not one("[买 山楂糖葫芦 3]").ok                     # 15 > 10: not enough
        assert srv.seen and srv.seen[0] == "Bearer tok"
        c = TestClient(create_app(scheduler=False, with_mcp=False))
        assert c.post("/api/wallet/grant", json={"who": A, "amount": 5, "key": "x"}).status_code == 409
        w = vendor.wallet()
        assert w.debit("z1", A, 3, "n").status == vendor.OK and w.debit("z1", A, 4, "n").status == vendor.CONFLICT
        assert w.lookup("z1", A, 3) == vendor.CHARGED and w.void("z1") == vendor.OK and w.lookup("z1", A, 3) == vendor.VOIDED
        assert w.void("nope") == vendor.ABSENT and w.balance(A) == 10
    finally:
        srv.close()
    config.override(vendor_wallet_url="http://127.0.0.1:9")                # nothing listens there
    assert vendor.wallet().debit("q", A, 1, "n").status == vendor.UNAVAILABLE


def test_no_smooth_line_on_a_burnt_or_spoiled_card(clock):
    play_on("proficiency", "mishaps", "settle_card")
    conn = db.connect()
    for sid, oc in (("s-burnt", "burnt"), ("s-good", "great")):
        conn.execute("INSERT INTO cook_sessions (id, who, dish, duration_seconds, started_at, status, created_at, outcome,"
                     " served_at) VALUES (?,?,?,?,?,?,?,?,?)", (sid, A, "煎蛋", 60, 0, "served", 0, oc, 60))
        conn.execute("INSERT INTO cook_settlements (session_id, who, dish, outcome, link, book, before_n, after_n,"
                     " before_tier, after_tier, mishap_id, mishap_ver, started_at, settled_at) VALUES"
                     " (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (sid, A, "煎蛋", oc, "free", "dish", 0, 1, "生疏", "生疏",
                                                       None, 1, 0, 60))
    conn.commit()
    assert progress.card(conn, "s-burnt")["mishap"] is None
    assert progress.card(conn, "s-good")["mishap"] == {"state": "none", "text": TEXTS["card_smooth"]}
    conn.close()


def test_your_own_wallet_answers_it_cannot_tell_and_the_order_is_settled_by_looking_it_up(clock):
    srv = _PocketServer()
    try:
        play_on("vendor")
        config.override(vendor_wallet_url=srv.url)
        _visit(clock)
        srv.mode = "500"                                   # charged, but the answer was an error
        r = one("[买 山楂糖葫芦 1]")
        assert r.ok and r.text == TEXTS["vbuy_pending"]
        (oid,) = _order_ids()
        assert vendor.order(oid)["state"] == vendor.DEBITING
        srv.mode = "ok"
        clock["now"] += vendor.DEBIT_SETTLE_S + 1
        assert vendor.advance(oid) == vendor.DELIVERED     # looked up by its id: charged, so paid and delivered
        assert vendor.HttpWallet(srv.url).balance(A) == 15                 # charged once
        srv.mode = "sleep"
        assert vendor.HttpWallet(srv.url, timeout=0.3).debit("t1", A, 1, "n").status == vendor.UNKNOWN
        srv.mode = "redirect"
        assert vendor.HttpWallet(srv.url).debit("t2", A, 1, "n").status == vendor.UNKNOWN
        srv.mode = "401"
        assert vendor.HttpWallet(srv.url).debit("t3", A, 1, "n").status == vendor.UNAVAILABLE
    finally:
        srv.close()


def _order_ids():
    conn = db.connect()
    try:
        return [r["id"] for r in conn.execute("SELECT id FROM vendor_orders")]
    finally:
        conn.close()


def test_a_wrong_wallet_address_is_not_echoed_whole(tmp_path):
    p = tmp_path / "k.toml"
    p.write_text('[vendor]\nwallet_url = "ftp://pocket.example/secret-key-123"\n', encoding="utf-8")
    with pytest.raises(config.ConfigError) as e:
        config.build(p, env={})
    assert "secret-key-123" not in " ".join(e.value.lines())
