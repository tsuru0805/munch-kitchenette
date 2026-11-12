"""Cooking method: the role may pick one of seven; otherwise it is guessed from the dish name."""
from __future__ import annotations

import pytest

from kitchenette import fridge, kitchen

from conftest import B, T0



def _cook(dish, who=B, **kw):
    fridge.buy_her(who, ["egg"])
    col: list = []
    text, err = kitchen._exec_cook(col, {"dish": dish, "minutes": 10, "ingredients": ["鸡蛋"], **kw}, who)
    return text, err, col


@pytest.mark.parametrize("dish,want", [
    ("番茄炒蛋", "stirfry"), ("爆炒腰花", "stirfry"), ("炒面", "stirfry"),
    ("煎饺", "fry"), ("锅贴", "fry"), ("葱油烙饼", "fry"),
    ("炸鸡", "deepfry"), ("酥炸鱿鱼", "deepfry"),
    ("鸡蛋豆腐汤", "boil"), ("红烧肉", "boil"), ("炸酱面", "boil"), ("皮蛋瘦肉粥", "boil"), ("卤肉饭", "boil"), ("火锅", "boil"),
    ("清蒸鲈鱼", "steam"), ("蒸蛋羹", "steam"),
    ("烤鸡翅", "bake"), ("芝士焗饭", "bake"), ("烧烤拼盘", "bake"),
    ("凉拌黄瓜", "mix"), ("水果沙拉", "mix"),
    ("烧麦", "steam"), ("叉烧包", "steam"), ("小笼包", "steam"), ("叉烧", "bake"), ("炸馒头", "deepfry"), ("烤包子", "bake"),
    ("牛排", "fry"), ("荷包蛋", "fry"), ("寿司", "mix"), ("三明治", "mix"), ("草莓蛋糕", "bake"),
    ("宫保鸡丁", "stirfry"), ("咖喱饭", "stirfry"), ("", "stirfry"),
])
def test_guess_from_dish_name(dish, want):
    assert kitchen.guess_method(dish) == want


def test_he_picks_a_method_and_it_wins_over_the_name(clock):
    text, err, col = _cook("番茄炒蛋", method="蒸")
    assert not err and col[0]["method"] == "steam"
    row = kitchen._conn().execute("SELECT method FROM cook_sessions").fetchone()
    assert row["method"] == "steam"
    assert kitchen.resolve_method("bake", "x") == "bake" and kitchen.resolve_method(" 拌 ", "炒饭") == "mix"


def test_no_method_is_guessed_and_stored(clock):
    _t, err, col = _cook("鸡蛋豆腐汤")
    assert not err and col[0]["method"] == "boil"
    assert kitchen._conn().execute("SELECT method FROM cook_sessions").fetchone()["method"] == "boil"


def test_unknown_method_is_refused_with_the_seven_choices(clock):
    text, err, col = _cook("番茄炒蛋", method="微波")
    assert err and col == []
    assert text == "没开成:做法只能是 炒 / 煎 / 炸 / 煮 / 蒸 / 烤 / 拌 里的一个,收到的是「微波」。不写也行,会按菜名猜。"
    assert kitchen._conn().execute("SELECT COUNT(*) FROM cook_sessions").fetchone()[0] == 0
    assert sum(b["qty"] for b in fridge.overview(B)["items"]) == 6


def test_old_pot_without_method_reads_as_guess_and_rest_carries_it(clock):
    _cook("清蒸鲈鱼")
    conn = kitchen._conn()
    conn.execute("UPDATE cook_sessions SET method=NULL")
    conn.commit()
    r = conn.execute("SELECT * FROM cook_sessions").fetchone()
    assert kitchen._card_entry(r)["method"] == "steam" and kitchen._row_dict(r, T0)["method"] == "steam"
    conn.close()


def test_tool_schema_offers_method_as_optional_enum():
    cook = next(t for t in kitchen.tool_schemas() if t["name"] == kitchen.TOOL_COOK)
    prop = cook["input_schema"]["properties"]["method"]
    assert prop["enum"] == ["炒", "煎", "炸", "煮", "蒸", "烤", "拌"]
    assert prop["description"] == "做法(可省):炒 / 煎 / 炸 / 煮 / 蒸 / 烤 / 拌,不写就按菜名猜"
    assert "method" not in cook["input_schema"]["required"]
