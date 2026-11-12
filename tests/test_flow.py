"""End to end, on a fake clock: the whole chain a role goes through, each refusal on the way,
the same chain with stamina and satiety switched off, and two roles side by side."""
from __future__ import annotations

from pathlib import Path

import pytest

from kitchenette import config, fridge, kitchen, menu, notify, potion, service, snacks, stamina, tools

from conftest import A, B, DAY, earn_rules, notes, qty

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def call(tool: str, who: str = A, /, **args):
    return tools.call(tool, args, who)


def ok(tool: str, who: str = A, /, **args) -> str:
    res = call(tool, who, **args)
    assert not res.is_error, res.text
    return res.text


def refused(tool: str, who: str = A, /, **args) -> str:
    res = call(tool, who, **args)
    assert res.is_error, res.text
    return res.text


def test_full_chain_with_every_refusal_on_the_way(frozen):
    # no coupon: buying is refused; how to earn one is only said once that is configured
    assert refused("kitchen_buy", items=["番茄"]) == "没买成:买菜券用完了(现在 0 张)。买菜券由用户给。"
    earn_rules()
    assert refused("kitchen_buy", items=["番茄"]) == "没买成:买菜券用完了(现在 0 张)。写成一篇日记、书摘或游记就得一张。"
    fridge.grant_coupon_by_her(A)
    fridge.buy_her(A, ["egg", "spinach"])
    # unknown name: refused, coupon kept
    assert "龙虾 不在能买的单子上" in refused("kitchen_buy", items=["龙虾"])
    assert fridge.overview(A)["coupons"]["count"] == 1
    bought = ok("kitchen_buy", items=["番茄", "苹果"])
    assert bought.startswith("买好了:番茄×3、苹果×2,放进冰箱了。用掉一张买菜券(还剩 0 张)。")

    # missing and unknown ingredients: refused, nothing taken
    assert "冰箱里不够——土豆(要 1,有 0)、牛肉(要 1,有 0)" in refused(
        "kitchen_cook", dish="土豆炖牛肉", minutes=30, ingredients=["土豆", "牛肉"])
    assert refused("kitchen_cook", dish="龙虾汤", minutes=30, ingredients=["龙虾"]).startswith(
        "没开成:龙虾 冰箱里没有这一样(也不在能买的单子上)。")
    assert qty(A, "tomato") == 3 and qty(A, "egg") == 6

    cooked = call("kitchen_cook", dish="番茄炒蛋", minutes=10, ingredients=["番茄", "鸡蛋×2"])
    assert not cooked.is_error and "『番茄炒蛋』下锅了" in cooked.text and "做 10 分钟" in cooked.text
    assert cooked.attachments[0]["duration_seconds"] == 600 and cooked.attachments[0]["method"] == "stirfry"
    assert qty(A, "tomato") == 2 and qty(A, "egg") == 4

    # not ready yet, and never cooked: both refused
    assert "还在火上" in refused("eat", meal="番茄炒蛋")
    assert refused("eat", meal="红烧肉") == "没吃成:桌上没有红烧肉,想吃得先做。"

    # it comes due: served, on the menu, one note waiting
    service.fast_forward(660)
    served = notes(A, notify.KIND_SERVED)
    assert len(served) == 1 and "『番茄炒蛋』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。" in served[0]["text"]
    row = menu.list_rows(A, pending=True)[0]
    assert (row["dish"], row["by"], row["note"]) == ("番茄炒蛋", A, "火候刚好")
    assert "· 番茄炒蛋（火候刚好）" in ok("read_menu")
    assert "【厨房·非用户发言】" in ok("kitchen_notes") and notes(A) == []

    # eat: the menu row is crossed off, satiety and stamina rise
    sat0, sta0 = fridge.satiety(A), stamina.read(A)
    receipt = ok("eat", meal="番茄炒蛋")
    assert receipt.splitlines()[0] == "🍚 吃好了：番茄炒蛋。距上次：这是第一餐 / 今日第 1 餐 / 本周 1 餐"
    assert f"饱食度：{round(sat0)}% → 100%" in receipt and "菜单划掉：番茄炒蛋 ✓" in receipt
    assert fridge.satiety(A) == pytest.approx(100.0)
    assert stamina.read(A) == pytest.approx(sta0 + 0.10 + 0.02, abs=0.005)    # the meal, plus "great"
    assert menu.list_rows(A, pending=True) == []
    assert refused("eat", meal="番茄炒蛋") == "没吃成:桌上没有番茄炒蛋,想吃得先做。"

    # a second dish is left on the table overnight: worms
    ok("kitchen_cook", dish="煎蛋", minutes=5, ingredients=["鸡蛋"])
    service.fast_forward(36 * 3600)
    status = ok("kitchen_status")
    assert "· 煎蛋 — " in status and "长虫了" in status
    assert menu.list_rows(A, pending=True)[0]["note"] == "火候刚好 · 长虫了" or \
        menu.list_rows(A, pending=True)[0]["note"].endswith("长虫了")

    # days pass: the spinach spoils, the role is told once that it is hungry
    service.fast_forward(3 * DAY)
    assert "菠菜×1(坏了)" in ok("kitchen_status")
    hungry = notes(A, notify.KIND_HUNGRY)
    assert len(hungry) == 1 and hungry[0]["text"].startswith("【厨房·非用户发言】你有点饿了(饱食度低于 30%)。冰箱里有:")

    # toss the wormy dish and the spoiled food; the menu row goes with the next scan
    assert ok("kitchen_toss", what="煎蛋") == "扔掉了:桌上长虫的『煎蛋』。"
    assert ok("kitchen_toss", what="坏了的") == "扔掉了:菠菜×1(坏了)。"
    assert refused("kitchen_toss", what="坏了的") == "没扔:冰箱里没有坏掉的东西。"
    service.fast_forward(60)
    assert menu.list_rows(A, pending=True) == [] and qty(A, "spinach") == 0

    # the worm went into exactly one snack
    texts = [ok("snack_eat", name=n) for n in ("布丁", "果冻", "黑巧克力", "曲奇")]
    wormy = [x for x in texts if "虫子在动" in x]
    assert len(wormy) == 1 and "『煎蛋』里爬过来的" in wormy[0] and "这份没回体力。" in wormy[0]


@pytest.mark.parametrize("stamina_on,satiety_on", [(False, True), (True, False), (False, False)])
def test_chain_still_works_with_switches_off(frozen, stamina_on, satiety_on):
    config.override(stamina_enabled=stamina_on, satiety_enabled=satiety_on)
    fridge.grant_coupon_by_her(A)
    ok("kitchen_buy", items=["鸡蛋", "生菜"])
    ok("kitchen_cook", dish="煎蛋", minutes=5, ingredients=["鸡蛋"])
    service.fast_forward(400)
    assert len(notes(A, notify.KIND_SERVED)) == 1
    receipt = ok("eat", meal="煎蛋")
    assert ("饱食度" in receipt) is satiety_on
    status = ok("kitchen_status")
    assert ("饱食度" in status) is satiety_on
    snack = ok("snack_eat", name="布丁")
    assert ("体力 +0.04" in snack) is stamina_on
    assert "这次体力没有变化" not in snack                 # a switched-off part simply does not appear
    if not stamina_on:
        assert snack.startswith("吃了一份布丁(低档)。今日布丁 1/3 份,")
    assert (stamina.read(A) is not None) is stamina_on
    assert (stamina.body_line(A) is not None) is stamina_on
    # a spoiled dish still makes the role dizzy whatever is switched off
    service.fast_forward(3 * DAY)
    ok("kitchen_cook", dish="生菜汤", minutes=5, ingredients=["生菜"])
    service.fast_forward(400)
    ok("eat", meal="生菜汤")
    assert fridge.overview(A)["dizzy"]["dish"] == "生菜汤"
    assert "晕乎乎" in fridge.turn_lines(A)
    # hunger only exists while satiety is on
    assert bool(notes(A, notify.KIND_HUNGRY)) is satiety_on
    # leftovers, worms and tossing do not depend on either switch
    ok("kitchen_cook", dish="炒蛋", minutes=5, ingredients=["鸡蛋"])
    service.fast_forward(2 * DAY)
    assert ok("kitchen_toss", what="炒蛋") == "扔掉了:桌上长虫的『炒蛋』。"


def test_potions_are_the_only_thing_that_needs_stamina(frozen):
    config.override(stamina_enabled=False, satiety_enabled=False)
    with pytest.raises(potion.PotionError):
        potion.register_potion(A, "row", 30)
    assert "· " not in ok("read_menu").split("🍪")[0]          # nothing on the menu, and no crash


def test_two_roles_never_see_each_other(frozen):
    fridge.grant_coupon_by_her(A)
    fridge.buy_her(A, ["egg", "apple"])
    ok("kitchen_cook", A, dish="蛋羹", minutes=5, ingredients=["鸡蛋"])
    menu.add("三鲜水饺", "human", A, "趁热")
    ok("snack_eat", A, name="布丁")
    stamina.pulse(A, -0.3)

    # B starts from nothing
    ov = fridge.overview(B)
    assert ov["items"] == [] and ov["coupons"]["count"] == 0 and ov["log"] == []
    assert ok("kitchen_status", B).splitlines()[0] == "火上没有锅。"
    assert "冰箱空了" in ok("kitchen_status", B)
    assert "三鲜水饺" not in ok("read_menu", B) and "布丁（低档）0/3" in ok("read_menu", B)
    assert "冰箱里不够" in refused("kitchen_cook", B, dish="蛋羹", minutes=5, ingredients=["鸡蛋"])
    assert refused("eat", B, meal="三鲜水饺") == "没吃成:桌上没有三鲜水饺,想吃得先做。"
    assert refused("eat", B, meal="苹果") == "没吃成:桌上没有苹果,想吃得先做。"
    assert refused("kitchen_cancel", B, dish="蛋羹").startswith("没关成:火上没有锅")
    assert "没买成:买菜券用完了" in refused("kitchen_buy", B, items=["番茄"])
    # B looked at its own kitchen (one round of kitchen work); A's snack and pulse are not B's
    assert stamina.read(B) == pytest.approx(config.get().stamina_init - 0.06, abs=0.01)
    assert stamina.read(A) < stamina.read(B)

    service.fast_forward(400)
    assert len(notes(A, notify.KIND_SERVED)) == 1 and notes(B) == []
    assert kitchen.overview(B) == {"now": kitchen.overview(B)["now"], "timezone": "Asia/Tokyo",
                                   "cooking": [], "recent": []}
    assert [r["dish"] for r in menu.list_rows(B)] == []
    assert sorted(r["dish"] for r in menu.list_rows(A, pending=True)) == ["三鲜水饺", "蛋羹"]

    # B gets its own things and A's are untouched by them
    fridge.grant_coupon_by_her(B)
    ok("kitchen_buy", B, items=["番茄"])
    assert qty(B, "tomato") == 3 and qty(A, "tomato") == 0 and qty(A, "egg") == 5
    ok("eat", A, meal="蛋羹")
    assert fridge.satiety(A) > fridge.satiety(B)
    assert snacks.state(A)["snacks"][2]["eaten"] == 1 and snacks.state(B)["snacks"][2]["eaten"] == 0


def test_default_role_is_used_when_who_is_left_out(frozen):
    config.override(roles_default="moss")
    fridge.buy_her("moss", ["egg"])
    assert "下锅了" in tools.call("kitchen_cook", {"dish": "煎蛋", "minutes": 5, "ingredients": ["鸡蛋"]}).text
    assert "火上 1 锅" in tools.call("kitchen_status").text
    assert tools.call("kitchen_status", {"who": B}).text.splitlines()[0] == "火上没有锅。"


@pytest.mark.parametrize("name", ["night-owl", "early-bird", "no-sleep", "blank"])
def test_each_example_schedule_runs_the_chain(frozen, name):
    built = config.build(EXAMPLES / "schedules" / f"{name}.toml", env={})
    built.server_db_path = config.get().server_db_path
    built.server_timezone = "Asia/Tokyo"
    config.use(built)
    assert len(config.get().stamina_schedule) == 24

    fridge.buy_her(A, ["egg"])
    ok("kitchen_cook", dish="煎蛋", minutes=5, ingredients=["鸡蛋"])
    service.fast_forward(400)
    before = stamina.read(A)
    ok("eat", meal="煎蛋")
    assert stamina.read(A) == pytest.approx(min(1.0, before + 0.12), abs=0.005)

    # two days with nothing happening: stamina follows the schedule and stays inside 0-1
    seen = {}
    for _ in range(48):
        service.fast_forward(3600)
        v = stamina.read(A)
        assert 0.0 <= v <= 1.0
        seen[frozen.local(frozen.now()).hour] = v
    if name == "no-sleep":
        assert all(v == pytest.approx(0.80, abs=0.01) for v in seen.values())
    elif name == "blank":
        assert all(v == pytest.approx(0.70, abs=0.01) for v in seen.values())
    elif name == "night-owl":
        assert seen[8] > 0.9 and seen[1] < 0.7 and seen[8] > seen[22]
    else:
        assert seen[8] > 0.9 and seen[23] < 0.7 and seen[1] > seen[23]


def test_built_in_schedule_is_the_night_owl_example():
    assert config.build(EXAMPLES / "schedules" / "night-owl.toml", env={}).stamina_schedule == list(config.DEFAULT_SCHEDULE)
