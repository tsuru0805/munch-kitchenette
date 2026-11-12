"""Wording that depends on how much piled up or on a setting: merged sentences, the
bracket-marker switch, and the configurable words."""
from __future__ import annotations

import re

from pathlib import Path

from fastapi.testclient import TestClient

from kitchenette import config, fridge, inline, kitchen, menu, notify, service, snacks, tools
from kitchenette.api import create_app
from kitchenette.texts import QUEUE_MODE, TEXTS, TOOLS_ONLY, pending_wording, t

from conftest import A, B, notes

MARKER = re.compile(r"\[(吃|零食|买菜|扔掉)")


def _client() -> TestClient:
    return TestClient(create_app(scheduler=False, with_mcp=False))


# ── several of a kind become one sentence ───────────────────────────────

def test_dishes_put_up_in_a_row_are_told_in_one_sentence(clock):
    c = _client()
    c.post("/api/menu", json={"dish": "三鲜水饺", "by": "human", "for_who": A, "note": "趁热"})
    assert [n["text"] for n in notes(A)] == ["用户刚在菜单上挂了一道『三鲜水饺』(备注:趁热)"]
    c.post("/api/menu", json={"dish": "番茄炒蛋", "by": "human", "for_who": A})
    c.post("/api/menu", json={"dish": "三鲜水饺", "by": "human", "for_who": A})      # same name: counted once
    assert [n["text"] for n in notes(A)] == ["用户刚在菜单上挂了 2 道:『三鲜水饺』、『番茄炒蛋』"]
    c.post("/api/menu", json={"dish": "蛋花汤", "by": "human", "for_who": A})
    c.post("/api/menu", json={"dish": "凉拌黄瓜", "by": "human", "for_who": A})
    got = notes(A)
    assert len(got) == 1 and got[0]["kind"] == "menu.posted"
    assert got[0]["text"] == "用户刚在菜单上挂了 4 道:『三鲜水饺』、『番茄炒蛋』、『蛋花汤』等"
    assert got[0]["body"] == got[0]["text"] and len(got[0]["payload"]["events"]) == 5
    assert notes(B) == []


def test_a_new_batch_starts_once_the_note_was_taken_or_pushed(clock):
    notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "粥"})
    notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "面"})
    assert [n["text"] for n in notify.take(A)] == ["用户刚在菜单上挂了 2 道:『粥』、『面』"]
    notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "汤"})
    assert [n["text"] for n in notes(A)] == ["用户刚在菜单上挂了一道『汤』"]

    class Sent:
        def deliver(self, who, batch):
            return notify.SENT
    notify.set_notifier(Sent())
    notify.flush()                                   # pushed: what comes next is news again
    notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "饭"})
    assert [n["text"] for n in notes(A)] == ["用户刚在菜单上挂了一道『饭』"]
    # the same event reported twice is dropped, also after its note was taken
    assert notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "粥"}, key="k") is not None
    notify.take(A)
    assert notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "粥"}, key="k") is None


def test_dishes_fed_in_a_row_are_told_in_one_sentence(clock):
    c = _client()
    ids = [menu.add(d, "human", A, note)["id"] for d, note in
           (("三鲜水饺", "慢慢吃"), ("番茄炒蛋", None), ("蛋花汤", None), ("凉拌黄瓜", None))]
    notify.take(A)
    c.post(f"/api/menu/{ids[0]}/feed")
    assert [n["text"] for n in notes(A)] == ["用户刚把菜单上那道『三鲜水饺』喂给你吃了(备注:慢慢吃)"]
    c.post(f"/api/menu/{ids[1]}/feed")
    assert [n["text"] for n in notes(A)] == ["用户刚把菜单上的 2 道菜喂给你吃了:『三鲜水饺』、『番茄炒蛋』"]
    c.post(f"/api/menu/{ids[2]}/feed")
    c.post(f"/api/menu/{ids[3]}/feed")
    assert [n["text"] for n in notes(A)] == ["用户刚把菜单上的 4 道菜喂给你吃了:『三鲜水饺』、『番茄炒蛋』、『蛋花汤』等"]


def test_snacks_fed_in_a_row_are_told_in_one_sentence(clock):
    c = _client()
    c.post("/api/snacks/eat", json={"who": A, "snack": "coffee", "variant": "latte"})
    assert [n["text"] for n in notes(A)] == ["用户刚从常驻零食里喂你吃了一份『拿铁咖啡』(中档,体力 +0.05)"]
    c.post("/api/snacks/eat", json={"who": A, "snack": "coffee", "variant": "latte"})
    c.post("/api/snacks/eat", json={"who": A, "snack": "pudding"})
    assert [n["text"] for n in notes(A)] == [
        "用户刚从常驻零食里喂你吃了 3 份:『拿铁咖啡』×2、『布丁』(合计体力 +0.14)"]
    c.post("/api/snacks/eat", json={"who": A, "snack": "cookie"})
    c.post("/api/snacks/eat", json={"who": A, "snack": "chocolate"})
    assert [n["text"] for n in notes(A)] == [
        "用户刚从常驻零食里喂你吃了 5 份:『拿铁咖啡』×2、『布丁』、『曲奇』等(合计体力 +0.19)"]


def test_merged_snack_sentence_without_stamina_and_with_a_worm():
    plain = {"name": "布丁", "tier": "低档", "delta": "", "worm": ""}
    assert notify.render_snack_fed([plain]) == "用户刚从常驻零食里喂你吃了一份『布丁』(低档)"
    assert notify.render_snack_fed([plain, plain]) == "用户刚从常驻零食里喂你吃了 2 份:『布丁』×2"
    wormy = {"name": "曲奇", "tier": "低档", "delta": "", "worm": "咬开一半,夹层里有条虫子在动——是从…爬过来的。"}
    assert notify.render_snack_fed([plain, wormy]) == (
        "用户刚从常驻零食里喂你吃了 2 份:『布丁』、『曲奇』。咬开一半,夹层里有条虫子在动——是从…爬过来的。")
    assert notify.render_snack_fed([{"name": "", "tier": ""}]) == ""
    assert snacks.fed_text({"name": "布丁", "tier": "low", "energy_delta": 0.04}) == \
        "用户刚从常驻零食里喂你吃了一份『布丁』(低档,体力 +0.04)"


def test_quoted_values_are_flattened_and_cut(clock):
    notify.emit(A, notify.KIND_MENU_POSTED, payload={"dish": "红烧『肉』\n加辣", "note": "备" * 50})
    text = notes(A)[0]["text"]
    assert text.startswith("用户刚在菜单上挂了一道『红烧「肉」 加辣』(备注:") and text.endswith("备…)")
    assert text.count("备") == 40                       # the label's own 备, plus 39 of the note


def test_groceries_and_coupons_that_piled_up_are_told_once(clock):
    fridge_client = _client()
    fridge_client.post("/api/fridge/buy", json={"who": A, "items": ["egg"]})
    fridge_client.post("/api/fridge/buy", json={"who": A, "items": ["tomato", "milk"]})
    fridge_client.post("/api/fridge/coupon", json={"who": A})
    fridge_client.post("/api/fridge/coupon", json={"who": A})
    assert [n["text"] for n in notes(A)] == ["用户给你买了菜,放进冰箱了:鸡蛋×6、番茄×3、牛奶×1。",
                                            "用户给了你一张买菜券(现在 2 张)。"]


def test_pots_served_together_are_told_in_one_note(clock):
    fridge.buy_her(A, ["egg"])
    for dish in ("汤", "饭"):
        kitchen._exec_cook(None, {"dish": dish, "minutes": 10, "ingredients": ["鸡蛋"]}, A)
    clock["now"] += 600
    service.scan(A)
    service.scan(A)
    got = notes(A, notify.KIND_SERVED)
    assert len(got) == 1 and len(got[0]["payload"]["events"]) == 2
    hm = got[0]["payload"]["started_hm"]
    line = "你 {hm} 下锅的『{d}』出锅了(共 10 分钟)。火候刚好。"
    assert got[0]["text"] == ("【厨房·非用户发言】" + line.format(hm=hm, d="汤") + "\n"
                              + line.format(hm=hm, d="饭") + "已挂到你的菜单上。")
    assert got[0]["body"] == line.format(hm=hm, d="汤") + line.format(hm=hm, d="饭") + "已挂到你的菜单上。"
    one_failed = [{"dish": "汤", "started_hm": "17:00", "minutes": "10", "menu_ok": "1", "outcome": ""},
                  {"dish": "饭", "started_hm": "17:00", "minutes": "10", "menu_ok": "0", "outcome": "burnt"}]
    assert notify.render_served(one_failed) == (
        "你 17:00 下锅的『汤』出锅了(共 10 分钟)。你 17:00 下锅的『饭』出锅了(共 10 分钟)。糊了。菜单这次没挂上。")


# ── bracket markers on or off ───────────────────────────────────────────

ORIGINAL = {
    "buy_empty": "没买成:没写买什么。写成 [买菜 番茄 鸡蛋] 这样,一样一个名字。",
    "toss_empty": "没扔:没写扔什么。写成 [扔掉 菠菜],或 [扔掉 坏了的] 把坏掉的都扔掉。",
    "menu_how": "吃完哪道，回复里单独一行写 [吃 菜名]，就会自动划掉。",
    "menu_snacks_how": "吃一份：回复里单独一行写 [零食 名字]（咖啡写口味，如 [零食 拿铁]）。",
}


def test_marker_switch_is_auto_out_of_the_box(clock):
    assert config.get().inline_enabled == "auto"
    assert t("menu_how") == "吃完哪道，用 eat 写上菜名，就会自动划掉。"         # nothing has arrived yet
    assert not MARKER.search(tools.call("read_menu", {}, A).text)
    assert not any(MARKER.search(s["description"]) for s in tools.schemas())
    inline.execute(A, "嗯。", "m1")                                            # the host is wired up
    assert t("menu_how") == "吃完哪道，回复里单独一行写 [吃 菜名]，就会自动划掉。"
    assert MARKER.search(tools.call("read_menu", {}, A).text)


def test_with_markers_on_the_wording_is_the_original():
    config.override(inline_enabled=True)
    for key, text in ORIGINAL.items():
        assert t(key) == text
    assert "出锅后这道菜会挂到你的菜单上(之后照常用 [吃 菜名] 吃掉)," in kitchen.tool_schemas()[0]["description"]
    assert t("tool_menu").endswith("A line [吃 菜名] alone in your reply crosses a dish off after eating.")
    assert t("take_short_go") == "[买菜 …] 去买" and t("take_short_hint", hint="写成一篇日记") == "写成一篇日记得一张"
    assert t("eat_fuzzy", dish="三鲜水饺", why="报的像是简称").endswith("确实是它就把菜名带全再写一次 [吃 菜名]）")
    assert t("eat_potion_aside", potion="精力补充药剂") == \
        "精力补充药剂没喝:它要单独喝,[吃 精力补充药剂] 单独成一行。"


def test_no_wording_is_left_pending_anywhere():
    assert pending_wording() == {}
    word = "PLACE" + "HOLDER"                                 # spelt in two halves so this file passes too
    root = Path(__file__).resolve().parent.parent
    files = [p for d in ("src", "tests", "examples", "docs") for p in (root / d).rglob("*")
             if p.is_file() and p.suffix in (".py", ".md", ".toml") and "animation" not in p.parts
             and p.name != "ANIMATION.md"]
    assert len(files) > 40
    assert [str(p.relative_to(root)) for p in files if word in p.read_text(encoding="utf-8")] == []


def test_the_sentences_that_were_settled_last(clock):
    by_name = {s["name"]: s for s in tools.schemas()}
    assert by_name["kitchen_buy"]["description"] == "用一张买菜券买一次菜，最多 5 样，买的放进冰箱。最多攒 3 张。"
    assert by_name["kitchen_buy"]["input_schema"]["properties"]["items"]["description"] == \
        "要买的食材名，一样一个名字，例如 番茄、鸡蛋。"
    assert by_name["snack_eat"]["description"] == "从常驻零食里吃一份。每款每天有份数上限，超出则不吃。"
    assert by_name["snack_eat"]["input_schema"]["properties"]["name"]["description"] == \
        "零食的名字；咖啡写口味（浓缩/美式/拿铁/摩卡）。"
    assert by_name["kitchen_notes"]["description"] == "取走厨房留给你的话（出锅了、给你买了菜这类）。每条只给一次。"
    assert tools.call("kitchen_notes", {}, A).text == "没有新的话。"
    assert t("potion_stamina_off", potion="精力补充药剂") == "体力关着，精力补充药剂用不了。"
    # the numbers and flavours come from the settings
    config.override(fridge_buy_max_items=2, fridge_coupon_max=9, snacks_catalog=[
        {"id": "tea", "name": "茶", "tier": "low", "default_cap": 3,
         "variants": [{"id": "green", "name": "绿", "gain": 0.01}, {"id": "black", "name": "红", "gain": 0.01}]},
        {"id": "cookie", "name": "曲奇", "tier": "low", "gain": 0.02, "default_cap": 5}])
    by_name = {s["name"]: s for s in tools.schemas()}
    assert by_name["kitchen_buy"]["description"] == "用一张买菜券买一次菜，最多 2 样，买的放进冰箱。最多攒 9 张。"
    assert by_name["snack_eat"]["input_schema"]["properties"]["name"]["description"] == "零食的名字；茶写口味（绿/红）。"
    config.override(snacks_catalog=[{"id": "cookie", "name": "曲奇", "tier": "low", "gain": 0.02, "default_cap": 5}])
    assert tools.schemas()[7]["input_schema"]["properties"]["name"]["description"] == "零食的名字。"


def test_marker_sentences_each_have_a_tool_version():
    assert set(QUEUE_MODE) <= set(TEXTS)
    # every sentence that names a marker has a tool-only counterpart, and no other sentence does
    assert {k for k, v in TEXTS.items() if MARKER.search(v)} == set(TOOLS_ONLY)
    assert not any(MARKER.search(v) for v in TOOLS_ONLY.values())


def test_with_markers_off_nothing_the_role_reads_names_a_marker(clock):
    config.override(inline_enabled=False)
    assert t("menu_how") == "吃完哪道，用 eat 写上菜名，就会自动划掉。"
    assert t("menu_snacks_how") == "吃一份：用 snack_eat 写上名字（咖啡写口味，如「拿铁」）。"
    assert t("buy_empty") == "没买成:没写买什么。在 kitchen_buy 的 items 里写成 [\"番茄\", \"鸡蛋\"] 这样,一样一个名字。"
    assert t("toss_empty") == "没扔:没写扔什么。用 kitchen_toss 写「菠菜」,或写「坏了的」把坏掉的都扔掉。"
    assert "出锅后这道菜会挂到你的菜单上(之后照常用 eat 吃掉)," in kitchen.tool_schemas()[0]["description"]
    assert t("eat_potion_aside", potion="精力补充药剂") == "精力补充药剂没喝:它要单独喝,用 eat 单独吃一次「精力补充药剂」。"

    seen = [s["description"] for s in tools.schemas()]
    fridge.buy_her(A, ["tomato"])
    fridge.grant_coupon_by_her(A)
    menu.add("三鲜水饺", "human", A)
    menu.add("精力补充药剂", "human", A)
    for name, args in (("read_menu", {}), ("kitchen_status", {}), ("kitchen_buy", {"items": []}),
                       ("kitchen_toss", {"what": ""}), ("eat", {"meal": "水饺"}),
                       ("kitchen_cook", {"dish": "炒蛋", "minutes": 5, "ingredients": ["鸡蛋"]}),
                       ("eat", {"meal": "三鲜水饺和精力补充药剂"}), ("snack_eat", {"name": "咖啡"})):
        seen.append(tools.call(name, args, A).text)
    assert not [s for s in seen if MARKER.search(s)]
    assert any("用 kitchen_buy 去买" in s for s in seen) and any("用 eat 写上菜名" in s for s in seen)

    c = _client()
    assert c.post("/api/inline", json={"who": A, "text": "[吃 三鲜水饺]"}).status_code == 409


def test_with_markers_on_the_same_calls_do_name_them(clock):
    config.override(inline_enabled=True)
    fridge.buy_her(A, ["tomato"])
    fridge.grant_coupon_by_her(A)
    menu.add("三鲜水饺", "human", A)
    assert MARKER.search(tools.call("read_menu", {}, A).text)
    assert "[买菜 …] 去买" in tools.call("kitchen_cook", {"dish": "炒蛋", "minutes": 5, "ingredients": ["鸡蛋"]}, A).text


# ── configurable words ──────────────────────────────────────────────────

def test_app_word_is_a_setting_and_app_by_default(clock):
    snacks.set_caps(A, {"pudding": 0, "cookie": 1})
    assert tools.call("snack_eat", {"name": "布丁"}, A).text.startswith("没吃成:布丁今日上限为 0 份(用户在 App 设的),")
    tools.call("snack_eat", {"name": "曲奇"}, A)
    assert tools.call("snack_eat", {"name": "曲奇"}, A).text.startswith("没吃成:今日曲奇已吃 1/1 份(含用户在 App 喂的),")
    config.override(words_app_name="厨房页", words_human_name="阿青")
    assert tools.call("snack_eat", {"name": "布丁"}, A).text.startswith("没吃成:布丁今日上限为 0 份(阿青在 厨房页 设的),")
    assert tools.call("snack_eat", {"name": "曲奇"}, A).text.startswith("没吃成:今日曲奇已吃 1/1 份(含阿青在 厨房页 喂的),")
