"""Cooking: opening pots, settling on read, turning the heat off, role isolation,
and the after-serving steps (menu + telling the role) with every external part faked."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from kitchenette import config, db, fridge, kitchen, notify, service, tools
from kitchenette.api import create_app
from kitchenette.texts import t

from conftest import A, B, notes


def _cook(dish="番茄炒蛋", minutes=10, note="", collector=None, who=A):
    fridge.buy_her(who, ["egg"])
    return kitchen._exec_cook(collector, {"dish": dish, "minutes": minutes, "note": note,
                                          "ingredients": ["鸡蛋"]}, who)


def _status(who=A):
    return kitchen._exec_status({}, who)


def _cancel(args=None, who=A):
    return kitchen._exec_cancel(args or {}, who)


def _rows():
    conn = kitchen._conn()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cook_sessions ORDER BY started_at, created_at")]
    finally:
        conn.close()


def test_cook_ok_receipt_and_card(clock):
    col: list = []
    text, err = _cook(minutes=25, note="少放盐", collector=col)
    assert not err
    assert "『番茄炒蛋』下锅了" in text and "做 25 分钟" in text
    assert "挂" not in text
    assert len(col) == 1
    att = col[0]
    assert att == {
        "kind": "kitchen_cooking", "session_id": att["session_id"], "who": A,
        "dish": "番茄炒蛋", "note": "少放盐",
        "duration_seconds": 1500, "started_at": clock["now"],
        "method": "stirfry",
    }
    assert _rows()[0]["status"] == "cooking"


def test_cook_without_collector_still_cooks(clock):
    text, err = _cook(collector=None)
    assert not err and "下锅了" in text
    assert _rows()[0]["status"] == "cooking"


@pytest.mark.parametrize("args,needle", [
    ({"dish": "", "minutes": 5}, "菜名是空的"),
    ({"dish": "   ", "minutes": 5}, "菜名是空的"),
    ({"dish": "汤", "minutes": 0}, "1–1440"),
    ({"dish": "汤", "minutes": 1441}, "1–1440"),
    ({"dish": "汤", "minutes": -3}, "1–1440"),
    ({"dish": "汤"}, "整数分钟"),
    ({"dish": "汤", "minutes": "十"}, "整数分钟"),
    ({"dish": "汤", "minutes": 2.5}, "整数分钟"),
    ({"dish": "汤", "minutes": True}, "整数分钟"),
    ({"dish": "汤" * 61, "minutes": 5}, "菜名太长"),
    ({"dish": "汤", "minutes": 5, "note": "x" * 201}, "备注太长"),
])
def test_cook_rejects_with_visible_reason(clock, args, needle):
    col: list = []
    text, err = kitchen._exec_cook(col, {**args, "ingredients": ["鸡蛋"]}, A)
    assert err and text.startswith("没开成") and needle in text
    assert col == [] and _rows() == []


def test_same_dish_on_fire_is_idempotent_and_reattaches_card(clock):
    assert not _cook(minutes=10)[1]
    clock["now"] += 60
    col: list = []
    text, err = _cook(minutes=30, collector=col)
    assert not err and "已经在火上了" in text and "还剩 9 分钟" in text
    assert "没有另开一锅" in text
    assert len(_rows()) == 1 and _rows()[0]["duration_seconds"] == 600
    assert len(col) == 1 and col[0]["session_id"] == _rows()[0]["id"]
    assert col[0]["started_at"] == clock["now"] - 60
    clock["now"] += 600
    assert not _cook(minutes=10)[1]
    assert [r["status"] for r in _rows()] == ["served", "cooking"]


def test_parallel_pots_each_own_clock(clock):
    _cook("汤", 30)
    clock["now"] += 300
    text, err = _cook("饭", 10)
    assert not err and "火上一共 2 锅" in text
    clock["now"] += 600
    st, _ = _status()
    assert "火上 1 锅" in st and "汤" in st and "还剩 15 分钟" in st
    assert "最近出锅" in st and "饭" in st


def test_settle_uses_true_due_time_not_read_time(clock):
    t0 = clock["now"]
    _cook(minutes=10)
    clock["now"] = t0 + 599
    _status()
    assert _rows()[0]["status"] == "cooking"
    clock["now"] = t0 + 5000
    _status()
    r = _rows()[0]
    assert r["status"] == "served" and r["served_at"] == t0 + 600


def test_status_empty_kitchen(clock):
    text, err = _status()
    assert not err and text.splitlines()[0] == "火上没有锅。"


def test_cancel_single_pot_without_name(clock):
    _cook("汤", 30)
    text, err = _cancel()
    assert not err and "『汤』关火了" in text
    r = _rows()[0]
    assert r["status"] == "cancelled" and r["cancelled_at"] == clock["now"]
    assert kitchen.due_work(A) == []


def test_cancel_failures_are_visible(clock):
    text, err = _cancel()
    assert err and "火上没有锅" in text
    _cook("汤", 30)
    _cook("饭", 10)
    text, err = _cancel()
    assert err and "说一下关哪一锅" in text and "『汤』" in text and "『饭』" in text
    text, err = _cancel({"dish": "面"})
    assert err and "火上没有『面』" in text
    clock["now"] += 601
    text, err = _cancel({"dish": "饭"})
    assert err and "火上没有『饭』" in text
    assert not _cancel({"dish": "汤"})[1]


def test_cancelled_pot_never_served(clock):
    _cook("汤", 5)
    _cancel()
    clock["now"] += 999
    _status()
    assert _rows()[0]["status"] == "cancelled"


def test_foreign_viewer_rows_invisible(clock):
    conn = kitchen._conn()
    conn.execute(
        "INSERT INTO cook_sessions (id, who, dish, duration_seconds, started_at,"
        " status, created_at) VALUES ('x',?,'骨头汤',60,?, 'cooking', ?)",
        (B, clock["now"], clock["now"]))
    conn.commit()
    conn.close()
    clock["now"] += 120
    assert _status()[0].splitlines()[0] == "火上没有锅。"
    assert kitchen.due_work(A) == []
    assert _rows()[0]["status"] == "cooking"


class _Ext:
    def __init__(self):
        self.menu: dict[str, str] = {}
        self.posts = 0
        self.wakes: list[str] = []
        self.add_raises = False
        self.add_lands_then_raises = False
        self.wake_result = kitchen.WAKE_SENT
        self.is_busy = False
        self.floats: list[tuple[str, bool]] = []
        self.float_raises = False

    def find(self, s):
        return self.menu.get(s["dish"])

    def add(self, s):
        self.posts += 1
        if self.add_raises:
            raise RuntimeError("menu down")
        self.menu[s["dish"]] = f"row-{self.posts}"
        if self.add_lands_then_raises:
            raise TimeoutError("read timeout")
        return self.menu[s["dish"]]

    def wake(self, msg):
        self.wakes.append(msg)
        return self.wake_result

    def float_event(self, s, menu_ok):
        if self.float_raises:
            raise RuntimeError("queue down")
        self.floats.append((s["dish"], menu_ok))

    def run(self, quiet=False):
        return kitchen.process_due(find_menu=self.find, add_menu=self.add, wake=self.wake,
                                   float_event=self.float_event,
                                   in_quiet=quiet, busy=lambda: self.is_busy, who=A)


def test_due_happy_path_then_idempotent(clock):
    _cook("汤", 10, note="少盐")
    ext = _Ext()
    assert ext.run() == {"menu_added": 0, "menu_failed": 0, "woke": 0,
                         "floated": 0, "deferred": ""}
    clock["now"] += 600
    out = ext.run()
    assert out["menu_added"] == 1 and out["woke"] == 1
    assert ext.posts == 1 and len(ext.wakes) == 1
    r = _rows()[0]
    assert r["menu_row_id"] == "row-1" and r["menu_added_at"] and r["woke_at"]
    for _ in range(3):
        ext.run()
    assert ext.posts == 1 and len(ext.wakes) == 1


def test_wake_message_wording(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.run()
    msg = ext.wakes[0]
    assert msg.startswith("【厨房·非用户发言】你 ")
    assert "下锅的『汤』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。" in msg


def test_menu_post_timeout_reads_back_no_double_post(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.add_lands_then_raises = True
    out = ext.run()
    assert out["menu_failed"] == 1 and ext.posts == 1 and ext.wakes == []
    clock["now"] += 60
    out = ext.run()
    assert out["menu_added"] == 1 and ext.posts == 1 and len(ext.wakes) == 1


def test_menu_down_gives_up_after_10min_and_says_so(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.add_raises = True
    ext.run()
    assert ext.wakes == []
    clock["now"] += 599
    ext.run()
    assert ext.wakes == []
    clock["now"] += 2
    ext.run()
    assert len(ext.wakes) == 1 and ext.wakes[0].endswith("菜单这次没挂上。")
    ext.add_raises = False
    clock["now"] += 60
    out = ext.run()
    assert out["menu_added"] == 1 and len(ext.wakes) == 1


def test_quiet_window_defers_wake_but_not_menu(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    out = ext.run(quiet=True)
    assert out["menu_added"] == 1 and out["deferred"] == "quiet" and ext.wakes == []
    clock["now"] += 3 * 3600
    out = ext.run(quiet=False)
    assert out["woke"] == 1 and len(ext.wakes) == 1


def test_busy_floats_event_instead_of_interrupting(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.is_busy = True
    out = ext.run()
    assert out["floated"] == 1 and out["woke"] == 0
    assert ext.floats == [("汤", True)] and ext.wakes == []
    assert _rows()[0]["woke_at"] is not None
    ext.is_busy = False
    ext.run()
    assert ext.wakes == [] and len(ext.floats) == 1


def test_busy_beats_quiet_window(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.is_busy = True
    assert ext.run(quiet=True)["floated"] == 1 and ext.wakes == []


def test_float_failure_retries_next_minute(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.is_busy = True
    ext.float_raises = True
    assert ext.run()["floated"] == 0 and _rows()[0]["woke_at"] is None
    ext.float_raises = False
    assert ext.run()["floated"] == 1


def test_menu_retry_stops_after_a_day(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.add_raises = True
    clock["now"] += 601
    ext.run()
    assert len(ext.wakes) == 1
    posts = ext.posts
    clock["now"] += 86400
    assert kitchen.due_work(A) == []
    ext.run()
    assert ext.posts == posts


def test_wake_not_sent_retries_unknown_never_retries(clock):
    _cook("汤", 10)
    clock["now"] += 600
    ext = _Ext()
    ext.wake_result = kitchen.WAKE_NOT_SENT
    ext.run()
    ext.run()
    assert len(ext.wakes) == 2 and _rows()[0]["woke_at"] is None
    ext.wake_result = kitchen.WAKE_UNKNOWN
    ext.run()
    assert len(ext.wakes) == 3 and _rows()[0]["woke_at"] is not None
    ext.run()
    assert len(ext.wakes) == 3


def test_same_minute_pots_merge_into_one_wake(clock):
    _cook("汤", 10)
    _cook("饭", 10)
    clock["now"] += 600
    ext = _Ext()
    out = ext.run()
    assert out["woke"] == 2 and len(ext.wakes) == 1
    assert "『汤』" in ext.wakes[0] and "『饭』" in ext.wakes[0]


def test_db_is_wal(clock):
    _cook("汤", 1)
    conn = sqlite3.connect(db.path())
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()




def test_tools_fail_closed_for_roles_outside_the_allowlist(clock):
    names = [s["name"] for s in kitchen.tool_schemas()]
    assert names == ["kitchen_cook", "kitchen_status", "kitchen_cancel", "kitchen_toss"]
    assert set(kitchen.local_tools(None, A)) == set(names)
    assert kitchen.local_tools(None, "") == {} and kitchen.local_tools(None, None) == {}
    config.override(roles_allowed=[A])
    assert kitchen.local_tools(None, B) == {}
    text, err = kitchen._exec_cook(None, {"dish": "汤", "minutes": 5, "ingredients": ["鸡蛋"]}, B)
    assert err and text == "没开成:不认识的人格。"
    res = tools.call("kitchen_status", {}, B)
    assert res.is_error and "who" in res.text


def test_every_role_gets_the_same_tool_face():
    names = {s["name"] for s in tools.schemas()}
    assert {"kitchen_cook", "kitchen_status", "kitchen_cancel", "kitchen_toss",
            "kitchen_buy", "eat", "read_menu", "snack_eat", "kitchen_notes"} == names
    assert all("who" in s["input_schema"]["properties"] for s in tools.schemas())
    assert all("who" not in s["input_schema"].get("required", []) for s in tools.schemas())


def test_kitchen_tools_count_as_one_kind_of_work():
    for n in ("kitchen_cook", "kitchen_status", "kitchen_cancel", "kitchen_toss"):
        assert config.get().stamina_work[n] == "kitchen"


def test_served_note_shares_wording_with_the_wake_message(clock):
    _cook("汤", 10)
    clock["now"] += 600
    s1 = kitchen.due_work(A)[0]
    p = kitchen.served_event_payload(s1, True)
    assert set(p) == {"dish", "started_hm", "minutes", "menu_ok", "outcome"}
    assert all(isinstance(v, str) for v in p.values())
    core = kitchen.build_wake_message([s1]).removeprefix(t("head"))
    assert core == kitchen.served_body([s1])
    assert core == f"你 {p['started_hm']} 下锅的『汤』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。"
    assert kitchen.served_body([s1], False).endswith("菜单这次没挂上。")
    assert "\n" not in kitchen.served_body([s1, s1], sep="")


def test_scan_writes_one_served_note_per_pot_and_never_repeats(clock):
    _cook("汤", 10)
    clock["now"] += 600
    service.scan(A)
    service.scan(A)
    got = notes(A, notify.KIND_SERVED)
    assert len(got) == 1
    assert got[0]["text"].startswith("【厨房·非用户发言】你 ") and "『汤』出锅了" in got[0]["text"]
    assert got[0]["body"] == got[0]["text"].removeprefix(t("head"))
    assert got[0]["payload"]["session_id"] == _rows()[0]["id"]
    assert notes(B) == []
    sid = _rows()[0]["id"]
    assert notify.emit(A, notify.KIND_SERVED, "again", key=f"kitchen.served:{sid}") is None


def test_tool_retry_returns_the_same_pot_with_its_card(clock):
    fridge.buy_her(B, ["egg"])
    r = tools.call("kitchen_cook", {"dish": "骨头汤", "minutes": 5, "ingredients": ["鸡蛋"]}, B)
    assert not r.is_error and [x["who"] for x in _rows()] == [B]
    fridge.buy_her(A, ["egg"])
    first = tools.call("kitchen_cook", {"dish": "汤", "minutes": 5, "ingredients": ["鸡蛋"]}, A)
    again = tools.call("kitchen_cook", {"dish": "汤", "minutes": 5, "ingredients": ["鸡蛋"]}, A)
    assert not first.is_error and not again.is_error and "没有另开一锅" in again.text
    assert len(first.attachments) == 1 and first.attachments[0]["kind"] == "kitchen_cooking"
    assert again.attachments[0]["session_id"] == first.attachments[0]["session_id"]
    assert len(_rows()) == 2


def test_rest_overview_shape(clock):
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook("汤", 30)
    _cook("饭", 10)
    _cancel({"dish": "饭"})
    clock["now"] += 60
    body = client.get("/api/kitchen", params={"who": A}).json()
    assert body["now"] == clock["now"]
    assert [c["dish"] for c in body["cooking"]] == ["汤"]
    assert body["cooking"][0]["remaining_seconds"] == 29 * 60
    assert [(r["dish"], r["status"]) for r in body["recent"]] == [("饭", "cancelled")]
    wanted = {"id", "dish", "note", "duration_seconds", "started_at", "status", "served_at", "cancelled_at",
              "remaining_seconds", "outcome", "ingredients", "method"}
    assert wanted <= set(body["cooking"][0]) and wanted <= set(body["recent"][0])
    sid = body["recent"][0]["id"]
    one = client.get("/api/kitchen", params={"session_id": sid}).json()
    assert one["session"]["status"] == "cancelled" and one["session"]["dish"] == "饭"
    assert client.get("/api/kitchen", params={"session_id": "nope"}).json()["session"] is None
    assert client.get("/api/kitchen", params={"viewer": B}).json()["cooking"] == []
