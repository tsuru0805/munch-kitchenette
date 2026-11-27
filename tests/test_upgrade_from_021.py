"""Upgrading from 0.2.1: the database 0.2.1 left behind (tests/fixtures/kitchenette-0.2.1.sql, made by
running 0.2.1 itself) is opened by this version with nothing done by hand. It gains the four columns the
freer jars need and keeps everything it had; opening it again changes nothing; jars sealed under 0.2.1 open
under the name the old rule gave them, slips and all; what was already on the shelf is still there; and the
new way of sealing works on the old database. No network: the REST calls go through the test client."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kitchenette import config, db, fridge, inline, jars, notify, service, tools
from kitchenette.api import create_app

from conftest import play_on

FIXTURE = Path(__file__).parent / "fixtures" / "kitchenette-0.2.1.sql"
W = "companion"                              # the role the 0.2.1 kitchen was used with
AFTER = 1796700770.0                         # a moment after the last thing done in 0.2.1
LEMON_DUE, APPLE_DUE, SPOILED_DUE = 1796873551.184224, 1796959951.167592, 1796959965.322038
NEW_COLUMNS = {"jars": {"goods_name", "odd"}, "jar_goods": {"why", "how_word"}}


@pytest.fixture()
def old_db(clock):
    """The 0.2.1 database at this test's database path, nothing of this version having touched it yet."""
    path = config.get().server_db_path
    raw = sqlite3.connect(path)
    raw.executescript(FIXTURE.read_text(encoding="utf-8"))
    raw.close()
    db.forget()
    clock["now"] = AFTER
    play_on("seal_jars")               # 0.2.1 was used with the jars on
    return path


def _shape(path: str) -> tuple[list, dict]:
    raw = sqlite3.connect(path)
    try:
        schema = sorted((n, s or "") for n, s in raw.execute("SELECT name, sql FROM sqlite_master"))
        counts = {n: raw.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
                  for n, s in schema if s.startswith("CREATE TABLE")}
        return schema, counts
    finally:
        raw.close()


def _cols(path: str, table: str) -> set[str]:
    raw = sqlite3.connect(path)
    try:
        return {r[1] for r in raw.execute(f"PRAGMA table_info({table})")}
    finally:
        raw.close()


def test_it_opens_adds_only_four_columns_and_a_second_open_changes_nothing(old_db):
    before_schema, before_counts = _shape(old_db)
    before_cols = {t: _cols(old_db, t) for t in NEW_COLUMNS}
    assert all(not (before_cols[t] & c) for t, c in NEW_COLUMNS.items())   # 0.2.1 had none of them
    db.connect().close()
    schema, counts = _shape(old_db)
    assert {n for n, _ in schema} == {n for n, _ in before_schema}           # no table added
    for t, c in NEW_COLUMNS.items():
        assert _cols(old_db, t) == before_cols[t] | c                        # just these columns
    assert counts == before_counts                                           # every row is still there
    for _ in range(2):                                                       # a restart, twice: nothing more
        db.forget()
        db.connect().close()
        assert _shape(old_db) == (schema, counts)
    service.scan_all()                                                       # the minute's work runs on it


def test_jars_sealed_under_0_2_1_open_under_the_old_rules_name_with_their_slip(old_db, clock):
    clock["now"] = LEMON_DUE + 60
    service.scan_all()
    clock["now"] = SPOILED_DUE + 60
    service.scan_all()
    opened = [n["text"] for n in notify.pending(W) if n["kind"] == jars.KIND_OPENED]
    assert any("窗台上的柠檬蜜泡好了" in s for s in opened) and any("窗台上的苹果酒泡好了" in s for s in opened)
    assert any(s.endswith("窗台上那罐苹果开出来是坏的(封进去的时候就坏了),整罐扔了,罐子洗干净空出来了。")
               for s in opened)                                    # the spoiled one sealed under 0.2.1
    r = tools.call("snack_eat", {"name": "苹果酒"}, W)
    assert not r.is_error and r.text == "喝了一份苹果酒。封罐时的纸条:「冬天吃」"
    assert not tools.call("snack_eat", {"name": "柠檬蜜"}, W).is_error
    conn = db.connect()
    try:
        assert all(j["state"] == "empty" and j["goods_name"] is None for j in jars.jars_view(conn, W))
        rows = jars.goods_view(conn, W)
    finally:
        conn.close()
    goods = {g["name"]: g for g in rows if g["ok"]}
    assert goods["苹果酒"]["how_word"] == "冰糖" and goods["苹果酒"]["why"] == ""
    spoiled = [g for g in rows if not g["ok"] and g["opened_at"] == SPOILED_DUE]
    assert len(spoiled) == 1 and (spoiled[0]["name"], spoiled[0]["why"], spoiled[0]["how_word"]) == ("苹果", "bad", "蜂蜜")


def test_what_was_on_the_shelf_and_the_spoiled_jar_read_as_before(old_db):
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    got = c.get("/api/jars", params={"who": W}).json()
    goods = {g["id"]: g for g in got["goods"]}
    pickles, spoiled = goods["g-3f1a6d91d7"], goods["g-336820a453"]
    assert (pickles["name"], pickles["ok"], pickles["left_n"], pickles["note"]) == ("腌胡萝卜", 1, 2, "配粥")
    assert (spoiled["ok"], spoiled["why"], spoiled["how_word"]) == (0, "", "")
    assert [j["state"] for j in got["jars"]] == ["sealed", "sealed", "sealed"]
    r = tools.call("snack_eat", {"name": "腌胡萝卜"}, W)
    assert not r.is_error and r.text == "吃了一份腌胡萝卜。封罐时的纸条:「配粥」"


def test_the_new_way_of_sealing_works_on_the_old_database(old_db, clock):
    clock["now"] = LEMON_DUE + 60                   # the lemon opens: one jar free (all three were sealed)
    fridge.buy_her(W, ["egg"])
    rs = inline.execute(W, "[封罐 鸡蛋 酱油、糖、小米辣 = 麻药鸡蛋 | 等周五开]", "m-upgrade")
    assert rs[0].ok and "(开出来叫麻药鸡蛋)" in rs[0].text
    clock["now"] = LEMON_DUE + 60 + jars.DAY + 60
    assert tools.call("snack_eat", {"name": "麻药鸡蛋"}, W).text == "吃了一份麻药鸡蛋。封罐时的纸条:「等周五开」"
