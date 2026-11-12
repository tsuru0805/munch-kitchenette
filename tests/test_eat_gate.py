"""What can be eaten: only what is on the menu, a pot just served, or something edible
straight from the fridge. Anything else is refused with the reason."""
from __future__ import annotations

import pytest

from kitchenette import fridge, kitchen, menu, tools

from conftest import A, B, receipts, run_reply


def _serve(who, dish, at, state=None, eaten=None, hung=None):
    c = kitchen._conn()
    c.execute("INSERT INTO cook_sessions (id,who,dish,note,duration_seconds,started_at,status,created_at,"
              "served_at,outcome,worm_state,eaten_at,menu_added_at) VALUES (?,?,?,'',60,?,'served',?,?,'great',?,?,?)",
              (f"s-{dish}", who, dish, at - 60, at - 60, at, state, eaten, hung))
    c.commit()
    c.close()


@pytest.mark.parametrize("who", [A, B])
def test_nothing_on_table_cannot_eat(clock, who):
    r = kitchen.can_eat(who, "鸡蛋豆腐汤")
    assert r == {"ok": False, "why": "none", "text": "没吃成:桌上没有鸡蛋豆腐汤,想吃得先做。"}


def test_fridge_ingredients_are_not_a_dish(clock):
    fridge.buy_her(A, ["egg", "tofu"])
    assert kitchen.can_eat(A, "鸡蛋豆腐汤")["ok"] is False
    assert kitchen.can_eat(A, "鸡蛋")["ok"] is False


def test_just_served_pot_can_eat_before_menu_hung(clock):
    _serve(A, "番茄炒蛋", clock["now"])
    assert kitchen.can_eat(A, "番茄炒蛋")["why"] == "pot"
    assert kitchen.can_eat(A, "番茄炒蛋和粥")["ok"] is False
    assert kitchen.can_eat(B, "番茄炒蛋")["ok"] is False


def test_old_pot_with_empty_eaten_at_is_not_a_free_meal(clock):
    _serve(A, "老菜", clock["now"] - 3 * 86400)
    _serve(A, "挂过的", clock["now"], hung=clock["now"])
    assert kitchen.can_eat(A, "老菜")["ok"] is False
    assert kitchen.can_eat(A, "挂过的")["ok"] is False


def test_cooking_or_eaten_pot_cannot_eat(clock):
    _serve(A, "吃过的", clock["now"], eaten=clock["now"])
    assert kitchen.can_eat(A, "吃过的")["ok"] is False
    c = kitchen._conn()
    c.execute("INSERT INTO cook_sessions (id,who,dish,note,duration_seconds,started_at,status,created_at)"
              " VALUES ('fire','aster','火上的','',600,?,'cooking',?)", (clock["now"], clock["now"]))
    c.commit()
    c.close()
    assert kitchen.can_eat(A, "火上的")["ok"] is False


def test_raw_edible_only_when_in_fridge(clock):
    assert kitchen.can_eat(B, "苹果")["ok"] is False
    fridge.buy_her(B, ["apple"])
    assert kitchen.can_eat(B, "苹果")["why"] == "raw"


def test_eaten_before_hung_is_not_hung_later(clock):
    _serve(A, "番茄炒蛋", clock["now"], eaten=clock["now"])
    added, woke = [], []
    res = kitchen.process_due(find_menu=lambda s: None, add_menu=lambda s: added.append(s) or "r1",
                              wake=lambda m: woke.append(m) or kitchen.WAKE_SENT,
                              float_event=lambda s, ok: None, in_quiet=False, busy=lambda: False, who=A)
    assert added == [] and woke == [] and res["menu_added"] == 0
    assert kitchen.due_work(A) == []
    assert kitchen.can_eat(A, "番茄炒蛋")["ok"] is False


def test_cooking_pot_says_still_on_fire(clock):
    c = kitchen._conn()
    c.execute("INSERT INTO cook_sessions (id,who,dish,note,duration_seconds,started_at,status,created_at)"
              " VALUES ('soup','aster','豆腐蛋花汤','',480,?,'cooking',?)", (clock["now"] - 60, clock["now"] - 60))
    c.commit()
    c.close()
    r = kitchen.can_eat(A, "豆腐蛋花汤")
    assert r["ok"] is False and r["why"] == "cooking"
    assert r["text"] == f"没吃成:『豆腐蛋花汤』还在火上,{kitchen._hm(clock['now'] + 420)} 出锅。"
    assert "先做" not in r["text"]
    assert kitchen.can_eat(B, "豆腐蛋花汤")["why"] == "none"


def _due(clock, **kw):
    _serve(A, "豆腐蛋花汤", clock["now"])
    woke, floated = [], []
    res = kitchen.process_due(find_menu=lambda s: "r1", add_menu=lambda s: "r1",
                              wake=lambda m: woke.append(m) or kitchen.WAKE_SENT,
                              float_event=lambda s, ok: floated.append(s["dish"]),
                              in_quiet=False, who=A, **kw)
    return res, woke, floated


def test_his_own_round_running_defers_wake_not_float(clock):
    res, woke, floated = _due(clock, busy=lambda: False, round_running=lambda: True)
    assert res["deferred"] == "round" and woke == [] and floated == []
    res, woke, floated = (kitchen.process_due(find_menu=lambda s: "r1", add_menu=lambda s: "r1",
                                              wake=lambda m: [m] and kitchen.WAKE_SENT,
                                              float_event=lambda s, ok: None, in_quiet=False,
                                              busy=lambda: False, who=A), None, None)
    assert res["woke"] == 1


def test_her_talking_still_floats(clock):
    res, woke, floated = _due(clock, busy=lambda: True, round_running=lambda: True)
    assert floated == ["豆腐蛋花汤"] and woke == []




def test_refused_marker_tells_him_why_and_gives_nothing(marker_env):
    sat0 = fridge.overview(A)["satiety"]["value"]
    run_reply("[吃 鸡蛋豆腐汤]")
    fail = receipts(False)
    assert fail[-1]["marker"] == "吃" and fail[-1]["hint"] == "没吃成:桌上没有鸡蛋豆腐汤,想吃得先做。"
    assert fridge.overview(A)["satiety"]["value"] <= sat0
    c = kitchen._conn()
    assert c.execute("SELECT COUNT(*) FROM meals").fetchone()[0] == 0
    c.close()


def test_eat_tool_refusal_is_an_error_and_gives_no_stamina(clock):
    from kitchenette import stamina
    before = stamina.read(A)
    res = tools.call("eat", {"meal": "鸡蛋豆腐汤"}, A)
    assert res.is_error and res.text == "没吃成:桌上没有鸡蛋豆腐汤,想吃得先做。"
    assert stamina.read(A) == before
    assert tools.call("eat", {"meal": "  "}, A).is_error


def test_abbreviation_of_a_menu_dish_is_refused_with_a_hint(clock):
    menu.add("三鲜水饺", "human", A)
    res = tools.call("eat", {"meal": "水饺"}, A)
    assert res.is_error and res.text == "没吃成:桌上没有水饺。有道像它的:三鲜水饺,把菜名写全再吃一次。"
    ok = tools.call("eat", {"meal": "三鲜水饺"}, A)
    assert not ok.is_error and "菜单划掉：三鲜水饺 ✓" in ok.text
