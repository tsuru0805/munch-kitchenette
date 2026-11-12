"""Worms: a dish left out overnight or fruit gone bad grows one, it hides in a snack,
and the role finds it there."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from kitchenette import fridge, inline, kitchen, notify, service, snacks, tools

from conftest import A, B, DAY, notes, receipts, run_reply

JST = ZoneInfo("Asia/Tokyo")
REAL_WORM_SNACK = kitchen._worm_snack


@pytest.fixture(autouse=True)
def worm_into_pudding(monkeypatch):
    monkeypatch.setattr(kitchen, "_worm_snack", lambda who: "pudding")


def ts(mo, d, h, mi=0):
    return datetime(2026, mo, d, h, mi, tzinfo=JST).timestamp()


def serve(who, dish, at, row="r1", note=""):
    c = kitchen._conn()
    c.execute("UPDATE once_keys SET at=0 WHERE key='worm_since'")
    c.execute("INSERT INTO cook_sessions (id,who,dish,note,duration_seconds,started_at,status,created_at,"
              "served_at,outcome,menu_added_at,menu_row_id,woke_at) VALUES (?,?,?,?,600,?,'served',?,?,'great',?,?,?)",
              (f"s-{row}", who, dish, note, at - 600, at - 600, at, at, row, at))
    c.commit()
    c.close()


class Menu:
    def __init__(self, rows=("r1",)):
        self.rows, self.notes, self.removed, self.fetched, self.fail = set(rows), {}, [], 0, False

    def run(self, who=B, now=None):
        def table():
            self.fetched += 1
            if self.fail:
                raise RuntimeError("menu down")
            return self.rows

        def note(row, text):
            if self.fail:
                raise RuntimeError("menu down")
            self.notes[row] = text

        return kitchen.process_worms(list_table=table, set_note=note, remove_row=self.removed.append,
                                     who=who, now=now)


def test_overnight_line():
    assert kitchen.worm_due_at(ts(11, 2, 19, 12)) == ts(11, 3, 4)
    assert kitchen.worm_due_at(ts(11, 2, 2)) == ts(11, 2, 8)
    assert kitchen.worm_due_at(ts(11, 2, 4)) == ts(11, 3, 4)


@pytest.mark.parametrize("who", [B, A])
def test_grows_worm_only_after_overnight_and_still_on_table(who):
    serve(who, "虾仁炒蛋", ts(11, 2, 19, 12), note="晚饭")
    m = Menu()
    assert m.run(who, ts(11, 3, 3, 59)) == {"wormed": 0, "skipped": 0, "noted": 0, "removed": 0}
    assert m.fetched == 0 and m.run(who, ts(11, 3, 4))["wormed"] == 1
    assert m.notes == {"r1": "晚饭 · 长虫了"}
    assert m.run(who, ts(11, 3, 5))["wormed"] == 0
    assert "长虫了" in kitchen._exec_status({}, who)[0]


def test_not_on_table_never_grows_and_stops_asking():
    serve(B, "蛋花汤", ts(11, 2, 12))
    m = Menu(rows=())
    assert m.run(now=ts(11, 3, 5))["skipped"] == 1
    m.run(now=ts(11, 3, 6))
    assert m.fetched == 1 and kitchen.take_worm(B, "x", "pudding") is None


def test_dish_before_loading_does_not_grow():
    serve(B, "虾仁炒蛋", ts(11, 1, 19))
    c = kitchen._conn()
    c.execute("UPDATE once_keys SET at=? WHERE key='worm_since'", (ts(11, 2, 1),))
    c.commit()
    c.close()
    m = Menu()
    assert m.run(now=ts(11, 3, 5))["wormed"] == 0 and m.fetched == 0


def test_menu_down_decides_nothing_then_retries_note():
    serve(B, "虾仁炒蛋", ts(11, 2, 19))
    m = Menu()
    m.fail = True
    assert m.run(now=ts(11, 3, 5))["wormed"] == 0
    m.fail = False
    calls = []

    def bad_note(row, text):
        calls.append(row)
        raise RuntimeError("patch failed")

    kitchen.process_worms(list_table=lambda: {"r1"}, set_note=bad_note, remove_row=print, who=B,
                          now=ts(11, 3, 5))
    assert calls == ["r1"] and m.run(now=ts(11, 3, 5, 1))["noted"] == 1


def test_pudding_has_worm_once_no_energy_no_stack(clock):
    serve(B, "虾仁炒蛋", ts(11, 1, 19, 12), row="r1")
    serve(B, "白菜汤", ts(11, 1, 20), row="r2")
    Menu(rows=("r1", "r2")).run(now=ts(11, 2, 5))
    assert snacks.eat(B, "cookie", None, snacks.BY_SELF).get("worm") is None
    r = snacks.eat(B, "pudding", None, snacks.BY_SELF, rid="p1")
    assert r["ok"] and r["eaten"] == 1 and r["energy_delta"] == 0.0
    want = ("吃了一份布丁。挖到第二口,里面有条虫子在动——是从桌上那盘 11 月 1 日 19 点 12 分"
            "做的『虾仁炒蛋』里爬过来的,可能是放太久坏掉了。这份没回体力。今日布丁 1/3 份")
    assert snacks.receipt_text(r, B).startswith(want)
    dup = snacks.eat(B, "pudding", None, snacks.BY_SELF, rid="p1")
    assert dup["duplicate"] and snacks.receipt_text(dup, B).startswith(want)
    assert snacks.eat(B, "pudding", None, snacks.BY_SELF, rid="p2").get("worm") is None
    assert any("吃到了虫子" in l["text"] for l in fridge.overview(B)["log"])


def test_eating_wormed_dish_counts_as_spoiled(clock):
    now = clock["now"]
    serve(B, "虾仁炒蛋", now - 86400)
    Menu().run(now=now)
    assert kitchen.on_eat(B, "虾仁炒蛋", key="k1") == fridge.SPOILED
    assert fridge.overview(B)["dizzy"]["dish"] == "虾仁炒蛋"


def test_eaten_between_table_look_and_lock_does_not_grow():
    serve(B, "虾仁炒蛋", ts(11, 2, 19))

    def table():
        c = kitchen._conn()
        c.execute("UPDATE cook_sessions SET eaten_at=1")
        c.commit()
        c.close()
        return {"r1"}

    res = kitchen.process_worms(list_table=table, set_note=lambda *_: None, remove_row=print, who=B,
                                now=ts(11, 3, 5))
    assert res["wormed"] == 0 and kitchen.take_worm(B, "x", "pudding") is None


def test_toss_retry_after_fridge_branch_does_not_toss_dish_too():
    fridge.buy_her(B, ["spinach"])
    serve(B, "菠菜", ts(11, 1, 19))
    assert kitchen.toss_wormed_dish(B, "菠菜", key="k") is None
    first = fridge.toss_self(B, "菠菜", key="k")
    Menu().run(now=ts(11, 2, 5))
    assert kitchen.toss_wormed_dish(B, "菠菜", key="k") == first
    c = kitchen._conn()
    assert c.execute("SELECT worm_state FROM cook_sessions").fetchone()[0] == "noted"
    c.close()


def _since(key, at=0):
    c = kitchen._conn()
    c.execute("UPDATE once_keys SET at=? WHERE key=?", (at, key))
    c.commit()
    c.close()


def test_random_pick_never_coffee_and_skips_cap_zero():
    assert set(kitchen.WORM_SNACK_HEAD) == {"pudding", "jelly", "chocolate", "cookie"}
    assert {REAL_WORM_SNACK(B) for _ in range(200)} == set(kitchen.WORM_SNACK_HEAD)
    snacks.set_caps(B, {"cookie": 0})
    assert "cookie" not in {REAL_WORM_SNACK(B) for _ in range(200)}
    snacks.set_caps(B, {"pudding": 0, "jelly": 0, "chocolate": 0})
    assert REAL_WORM_SNACK(B) is None


def test_all_snacks_off_dish_still_grows_but_no_worm_taken(monkeypatch):
    monkeypatch.setattr(kitchen, "_worm_snack", REAL_WORM_SNACK)
    snacks.set_caps(B, {"pudding": 0, "jelly": 0, "chocolate": 0, "cookie": 0})
    serve(B, "虾仁炒蛋", ts(11, 2, 19))
    m = Menu()
    assert m.run(now=ts(11, 3, 5))["wormed"] == 1 and m.notes["r1"] == "长虫了"
    assert all(kitchen.take_worm(B, f"x{s}", s) is None for s in kitchen.WORM_SNACK_HEAD)


@pytest.mark.parametrize("snack,head", list(kitchen.WORM_SNACK_HEAD.items()))
def test_worm_only_in_chosen_snack_with_its_words(clock, monkeypatch, snack, head):
    monkeypatch.setattr(kitchen, "_worm_snack", lambda who: snack)
    serve(B, "虾仁炒蛋", ts(11, 1, 19, 12))
    Menu().run(now=ts(11, 2, 5))
    other = next(s for s in kitchen.WORM_SNACK_HEAD if s != snack)
    assert snacks.eat(B, other, None, snacks.BY_SELF).get("worm") is None
    assert snacks.eat(B, "coffee", "latte", snacks.BY_SELF).get("worm") is None
    r = snacks.eat(B, snack, None, snacks.BY_SELF)
    assert r["worm"].startswith(head + "——是从桌上那盘 11 月 1 日 19 点 12 分做的『虾仁炒蛋』")
    assert r["energy_delta"] == 0.0
    assert kitchen.take_worm(B, "again", snack) is None


def test_fruit_bad_grows_worm_and_tag(clock):
    fridge.buy_her(B, ["strawberry"])
    _since("fruit_worm_since")
    bought = clock["now"]
    m = Menu(rows=())
    assert m.run(now=clock["now"])["wormed"] == 0
    clock["now"] += 3.5 * DAY
    assert m.run(now=clock["now"])["wormed"] == 1
    assert m.fetched == 0
    assert "草莓×1(长虫了)" in fridge.status_text(B)
    assert fridge.overview(B)["items"][0]["freshness"] == fridge.BAD
    assert m.run(now=clock["now"])["wormed"] == 0
    d = datetime.fromtimestamp(bought, JST)
    r = snacks.eat(B, "pudding", None, snacks.BY_SELF)
    assert f"——是从冰箱里那个 {d.month} 月 {d.day} 日买的『草莓』里爬过来的,可能是放太久坏掉了。" in r["worm"]


def test_fruit_already_bad_at_load_and_non_fruit_do_not_grow(clock):
    fridge.buy_her(B, ["strawberry", "spinach"])
    clock["now"] += 3.5 * DAY
    _since("fruit_worm_since", clock["now"])
    assert Menu(rows=()).run(now=clock["now"])["wormed"] == 0
    _since("fruit_worm_since")
    res = Menu(rows=()).run(now=clock["now"])
    assert res["wormed"] == 1
    assert "菠菜×1(坏了)" in fridge.status_text(B)


def test_fruit_second_worm_does_not_stack(clock):
    fridge.buy_her(B, ["strawberry", "apple"])
    _since("fruit_worm_since")
    clock["now"] += 3.5 * DAY
    Menu(rows=()).run(now=clock["now"])
    clock["now"] += 4 * DAY
    Menu(rows=()).run(now=clock["now"])
    assert "苹果×2(长虫了)" in fridge.status_text(B)
    assert snacks.eat(B, "pudding", None, snacks.BY_SELF, rid="a")["worm"]
    assert snacks.eat(B, "pudding", None, snacks.BY_SELF, rid="b").get("worm") is None


def test_wormed_fruit_tossed_and_eating_it_still_dizzy(clock):
    fridge.buy_her(B, ["apple"])
    _since("fruit_worm_since")
    clock["now"] += 7.5 * DAY
    Menu(rows=()).run(now=clock["now"])
    assert kitchen.on_eat(B, "苹果", key="k") == fridge.SPOILED
    assert fridge.toss_self(B, "苹果", key="t") == "扔掉了:苹果×1(长虫了)。"


class Waker:
    def __init__(self, result=kitchen.WAKE_SENT, busy=False, state=kitchen.RECEIPT_WAITING, quiet=False):
        self.result, self.is_busy, self.state, self.quiet, self.sent = result, busy, state, quiet, []

    def run(self, who=B):
        def wake(m):
            self.sent.append(m)
            return self.result

        return kitchen.process_worm_wakes(who=who, wake=wake, busy=lambda: self.is_busy,
                                          receipt=lambda at: self.state, in_quiet=self.quiet)


def _eat_worm(rid="w1"):
    serve(B, "虾仁炒蛋", ts(11, 1, 19), row=f"r{rid}")
    Menu(rows=(f"r{rid}",)).run(now=ts(11, 2, 5))
    assert snacks.eat(B, "pudding", None, snacks.BY_SELF, rid=rid)["worm"]


def test_worm_wakes_him_once_with_no_duplicate_sentence(clock):
    _eat_worm()
    w = Waker()
    assert w.run()["woke"] == 1 and w.sent == [kitchen.worm_wake_text()] and "虫" not in w.sent[0]
    assert w.run()["woke"] == 0 and len(w.sent) == 1
    assert snacks.eat(B, "pudding", None, snacks.BY_SELF, rid="w1")["duplicate"]
    assert w.run()["woke"] == 0


def test_plain_snack_does_not_wake(clock):
    snacks.eat(B, "pudding", None, snacks.BY_SELF)
    w = Waker()
    assert w.run()["woke"] == 0 and w.sent == []


@pytest.mark.parametrize("kw,reason", [({"busy": True}, "busy"), ({"quiet": True}, "quiet"),
                                       ({"result": kitchen.WAKE_NOT_SENT}, "not_sent")])
def test_wake_deferred_then_sent(clock, kw, reason):
    _eat_worm()
    w = Waker(**kw)
    assert w.run()["deferred"] == reason
    w2 = Waker()
    assert w2.run()["woke"] == 1


def test_wake_unknown_result_not_resent(clock):
    _eat_worm()
    assert Waker(result=kitchen.WAKE_UNKNOWN).run()["woke"] == 1
    w = Waker()
    assert w.run()["woke"] == 0 and w.sent == []


def test_already_had_a_round_no_wake_even_if_quiet(clock):
    _eat_worm()
    w = Waker(state=kitchen.RECEIPT_SEEN, quiet=True)
    assert w.run()["seen"] == 1 and w.sent == []
    assert Waker().run()["woke"] == 0


def test_two_worms_waiting_merge_into_one_wake(clock):
    _eat_worm("a")
    _eat_worm("b")
    w = Waker()
    assert w.run()["woke"] == 2 and len(w.sent) == 1


def test_receipt_gone_puts_sentence_in_wake(clock):
    _eat_worm()
    w = Waker(state=kitchen.RECEIPT_GONE)
    assert w.run()["woke"] == 1
    assert w.sent[0].startswith(kitchen.worm_wake_text()) and "虫子在动" in w.sent[0] and "虾仁炒蛋" in w.sent[0]




def test_worm_reaches_him_through_marker(marker_env):
    serve(B, "虾仁炒蛋", ts(11, 1, 19, 12))
    Menu().run(now=ts(11, 2, 5))
    run_reply("[零食 布丁]\n", who=B)
    rec = receipts(True)
    assert rec[-1]["marker"] == "零食" and "虾仁炒蛋" in rec[-1]["hint"]
    assert "可能是放太久坏掉了。这份没回体力。" in rec[-1]["hint"] and rec[-1]["hint"].endswith("重置。")
    rendered = inline.render("零食", True, rec[-1]["hint"])
    assert rendered.startswith("刚才正文里那条『零食』:") and rendered.endswith("重置。")


def test_her_feeding_pudding_tells_him_worm():
    serve(B, "虾仁炒蛋", ts(11, 1, 19, 12))
    Menu().run(now=ts(11, 2, 5))
    r = snacks.eat(B, "pudding", None, snacks.BY_HER)
    assert snacks.fed_payload(r)["worm"] == r["worm"]
    text = snacks.fed_text(r)
    assert text.startswith("用户刚从常驻零食里喂你吃了一份『布丁』") and "虫子在动" in text and "虾仁炒蛋" in text


def test_toss_wormed_dish_marker(marker_env):
    serve(B, "虾仁炒蛋", ts(11, 1, 19))
    m = Menu()
    m.run(now=ts(11, 2, 5))
    run_reply("[扔掉 虾仁炒蛋]\n", who=B)
    assert "长虫的『虾仁炒蛋』" in receipts(True)[-1]["hint"]
    assert m.run(now=ts(11, 2, 5, 1))["removed"] == 1 and m.removed == ["r1"]
    assert kitchen.on_eat(B, "虾仁炒蛋", key="k2") == "her"


def test_toss_fresh_dish_still_says_why(marker_env):
    serve(B, "虾仁炒蛋", ts(11, 1, 19))
    run_reply("[扔掉 虾仁炒蛋]\n", who=B)
    assert "没扔" in receipts(False)[-1]["hint"]


def test_worm_found_through_a_marker_is_also_sent_as_a_note_once(clock):
    serve(B, "虾仁炒蛋", clock["now"] - DAY)
    Menu().run(now=clock["now"])
    assert "虫子在动" in inline.execute(B, "[零食 布丁]", "m1")[0].text
    service.scan(B)
    service.scan(B)
    got = notes(B, notify.KIND_WORM)
    assert len(got) == 1 and got[0]["text"].startswith("【厨房·非用户发言】刚才那口零食不对劲。")
    assert "虾仁炒蛋" in got[0]["text"]


def test_worm_found_through_a_tool_call_needs_no_second_notice(clock):
    serve(B, "虾仁炒蛋", clock["now"] - DAY)
    Menu().run(now=clock["now"])
    res = tools.call("snack_eat", {"name": "布丁"}, B)
    assert not res.is_error and "虫子在动" in res.text and "这份没回体力" in res.text
    service.scan(B)
    assert notes(B, notify.KIND_WORM) == []


def test_worms_can_be_switched_off(clock):
    from kitchenette import config
    config.override(kitchen_worm_enabled=False)
    serve(B, "虾仁炒蛋", clock["now"] - 2 * DAY)
    assert Menu().run(now=clock["now"]) == {"wormed": 0, "skipped": 0, "noted": 0, "removed": 0}


def test_worm_hour_and_minimum_age_follow_the_settings():
    from kitchenette import config
    config.override(kitchen_worm_day_hour=9, kitchen_worm_min_age_hours=1.0)
    assert kitchen.worm_due_at(ts(11, 2, 19, 12)) == ts(11, 3, 9)
    assert kitchen.worm_due_at(ts(11, 2, 8, 30)) == ts(11, 2, 9, 30)
