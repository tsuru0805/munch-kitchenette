"""Upgrading from 0.2.0: the database 0.2.0 left behind (tests/fixtures/kitchenette-0.2.0.sql, made by
running 0.2.0 itself) is opened by this version with nothing done by hand. It gains what it lacks and keeps
everything it had; opening it again changes nothing; and what was made before the upgrade reads back the way
it was made — a pot by the recipe it followed then, a deleted page by the version that pot used, a washing by
the plan it was stored with, an ingredient bought under a name the index no longer uses, dislikes, the notes
nobody had taken yet. No network: the webhook is a fake, the REST calls go through the test client."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kitchenette
from kitchenette import book, config, db, dishes, fridge, notify, progress, recipes, service, tools
from kitchenette.api import create_app
from kitchenette.texts_play import vendor_id

from conftest import play_on

FIXTURE = Path(__file__).parent / "fixtures" / "kitchenette-0.2.0.sql"
W = "companion"                              # the role the 0.2.0 kitchen was used with
AFTER = 1795321200.0                         # a moment after the last thing done in 0.2.0

POT_PRAWNS = "a7128ce95eb5436ebb15716b67179f6b"     # 油焖大虾 by hc-0fd53334, version 1 (scallion)
POT_NOODLES = "f73f2ee0bd5541e29d39d8752527c95b"    # 西红柿鸡蛋挂面 by hc-27764b15, version 1, "changed"
POT_PAGE = "7f95c38866c04350ad448ebf329a7e98"       # 葱香炒蛋 by its own page p-f10194d1, deleted afterwards
POT_FREE = "7668e994743545ef9ed7cd7dd40aa97e"       # 番茄炒蛋, no recipe
POT_SWITCHED_OFF = "5f8202f2be2243169d920060cd4a199f"   # 土豆煎蛋, cooked while every switch was off
ALL_POTS = (POT_SWITCHED_OFF, POT_PRAWNS, POT_FREE, POT_NOODLES, POT_PAGE)
PRAWNS, NOODLES, SOUP = "hc-0fd53334", "hc-27764b15", "hc-581cccda"
DELETED_PAGE, FAV_PAGE = "p-f10194d1", "p-c76d9ad6"
JOB_DONE, JOB_RUNNING = "783cd57e1106", "c231296afa55"   # the running one was stored with plate 2 to break


@pytest.fixture()
def old_db(clock):
    """The 0.2.0 database at this test's database path, nothing of this version having touched it yet."""
    path = config.get().server_db_path
    raw = sqlite3.connect(path)
    raw.executescript(FIXTURE.read_text(encoding="utf-8"))
    raw.close()
    db.forget()
    clock["now"] = AFTER
    play_on(everything=True)           # 0.2.0 was used with all seventeen on
    recipes.load()
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


def _conn():
    return db.connect()


def test_it_opens_adds_only_what_is_new_and_a_second_open_changes_nothing(old_db):
    before_schema, before_counts = _shape(old_db)
    db.connect().close()
    schema, counts = _shape(old_db)
    added = {n for n, _ in schema} - {n for n, _ in before_schema}
    assert added == set()                                    # 0.2.1 adds no table on open
    cols = {r[1] for r in sqlite3.connect(old_db).execute("PRAGMA table_info(notes)")}
    assert {"claim_token", "claim_at"} <= cols               # ...and two columns to notes
    assert counts == before_counts                           # every row is still there
    for _ in range(2):                                       # a restart, twice: nothing more happens
        db.forget()
        db.connect().close()
        assert _shape(old_db) == (schema, counts)
    service.scan_all()                                       # the minute's work runs on it


def test_pots_from_before_keep_the_recipe_version_they_followed_and_new_ones_take_the_new(old_db):
    conn = _conn()
    try:
        prawns = book.resolve_ref(conn, W, PRAWNS, version=1)
        noodles = book.resolve_ref(conn, W, NOODLES, version=1)
        assert [e["item"] for e in prawns["main"]] == ["scallion"]
        assert [e["item"] for e in noodles["main"]] == ["noodles", "egg", "pepper"]
        assert [e["item"] for e in book.resolve_ref(conn, W, PRAWNS)["main"]] == ["shrimp"]   # the index now
        assert conn.execute("SELECT recipe_version FROM cook_sessions WHERE id=?", (POT_PRAWNS,)).fetchone()[0] == 1
    finally:
        conn.close()
    fridge.buy_her(W, ["shrimp"])
    res = tools.call("kitchen_cook", {"dish": "油焖大虾", "minutes": 10, "ingredients": ["虾"], "recipe": PRAWNS}, W)
    assert not res.is_error, res.text
    conn = _conn()
    try:
        rows = conn.execute("SELECT recipe_version, recipe_link FROM cook_sessions WHERE recipe_id=? ORDER BY started_at",
                            (PRAWNS,)).fetchall()
    finally:
        conn.close()
    assert [tuple(r) for r in rows] == [(1, "follow"), (2, "follow")]


def test_settled_cards_of_old_pots_read_back_with_the_new_fields(old_db):
    conn = _conn()
    try:
        cards = {sid: progress.card(conn, sid) for sid in ALL_POTS}
    finally:
        conn.close()
    assert all(c["has"] for c in cards.values())
    for c in cards.values():
        assert c["proficiency"]["next_tier"] == "拿手" and c["proficiency"]["tier_from"] == 0
    assert cards[POT_PRAWNS]["icon"] == "fish" and [s["key"] for s in cards[POT_PRAWNS]["stamps"]] == ["first", "follow"]
    assert [s["key"] for s in cards[POT_NOODLES]["stamps"]] == ["first", "changed"]
    assert cards[POT_PAGE]["mishap"]["state"] == "had"


def test_a_pot_served_before_the_upgrade_was_first_used_still_shows_the_legacy_card(old_db):
    """0.2.0 never settled pots served before its own first use; 0.2.1 shows those the same way."""
    conn = _conn()
    try:
        since = conn.execute("SELECT at FROM once_keys WHERE key='play_since'").fetchone()[0]
        conn.execute("INSERT INTO cook_sessions (id, who, dish, note, duration_seconds, started_at, status, served_at,"
                     " created_at, outcome, method, ingredients_json) SELECT 'older-pot', who, '煎蛋', '', 60, ?, 'served',"
                     " ?, ?, 'great', 'fry', ingredients_json FROM cook_sessions WHERE id=?",
                     (since - 3660, since - 3600, since - 3660, POT_SWITCHED_OFF))
        conn.commit()
        progress.settle_due(conn, W, AFTER)
        assert progress.card(conn, "older-pot") == {"has": False, "why": "legacy", "legacy_outcome": "great"}
    finally:
        conn.close()


def test_a_page_deleted_in_0_2_0_still_answers_for_its_pot_and_a_collection_shows_the_recipe_now(old_db):
    conn = _conn()
    try:
        assert book.resolve_ref(conn, W, DELETED_PAGE) is None
        old = book.resolve_ref(conn, W, DELETED_PAGE, version=1)
        assert old["name"] == "葱香炒蛋" and [e["item"] for e in old["main"]] == ["egg", "scallion"]
        # a public recipe collected in 0.2.0 kept a copy of version 1; cooking by it follows the entry now,
        # and so does the page
        fav = {p["id"]: p for p in book.my_pages(conn, W)}[FAV_PAGE]
        assert [e["item"] for e in fav["main"]] == ["shrimp"] and fav["main"][0]["name"] == "虾"
        assert [e["item"] for e in book.resolve_ref(conn, W, FAV_PAGE)["main"]] == ["shrimp"]
        assert "name" not in recipes.get(PRAWNS)["main"][0]           # the index itself is left alone
        config.override(play_recipes_public=False)
        fav = {p["id"]: p for p in book.my_pages(conn, W)}[FAV_PAGE]
        assert [e["item"] for e in fav["main"]] == ["scallion"]       # public recipes off: the copy
    finally:
        conn.close()


def test_an_ingredient_bought_under_its_old_name_counts_for_the_recipe_now(old_db, clock):
    old_id, new_id = vendor_id("泡好的粉丝"), vendor_id("粉丝")
    assert [b["item_id"] for b in fridge.overview(W)["items"] if b["item_id"].startswith("v_")].count(old_id) == 1
    assert fridge.canon(old_id) == fridge.canon(new_id)
    soup = recipes.get(SOUP)
    assert new_id in [e["item"] for e in soup["main"]]
    have = recipes.fridge_snapshot(fridge._batches(fridge._conn(), W, clock["now"]))
    assert recipes.feasibility([soup["main"]], have)["short"] == {}


def test_washings_from_before_read_back_and_the_running_one_keeps_its_stored_breakage(old_db, clock):
    conn = _conn()
    try:
        done = dishes.job_detail(conn, JOB_DONE, clock["now"])
        assert (done["state"], done["counts"]["clean"]) == ("done", 3)
        conn.execute("BEGIN IMMEDIATE")
        dishes.settle_in_tx(conn, W, AFTER + 600)
        conn.commit()
        run = dishes.job_detail(conn, JOB_RUNNING, AFTER + 600)
    finally:
        conn.close()
    assert run["state"] == "done" and [d["state"] for d in run["dishes"]] == ["clean", "broken"]
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.get(f"/api/dishes/jobs/{JOB_DONE}").status_code == 200


def test_dislikes_set_with_the_whole_list_put_are_kept_and_both_ways_of_editing_work(old_db):
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    got = c.get("/api/prefs", params={"who": W}).json()
    assert got["dislike"] == ["celery", "eggplant"] and got["version"]
    put = c.put("/api/prefs", json={"who": W, "dislike": ["celery", "eggplant", "cucumber"]})       # 0.2.0's way
    assert put.status_code == 200 and put.json()["dislike"] == ["celery", "eggplant", "cucumber"]
    assert c.post("/api/prefs/dislike", json={"who": W, "item": "tofu"}).status_code == 200
    assert c.delete("/api/prefs/dislike/cucumber", params={"who": W}).json()["dislike"] == ["celery", "eggplant", "tofu"]
    assert c.put("/api/prefs", json={"who": W, "dislike": [], "version": "stale"}).status_code == 409


def test_notes_nobody_took_in_0_2_0_go_out_once(old_db):
    sent: list[list[int]] = []

    class Hook:
        def deliver(self, who, notes):
            sent.append([n["id"] for n in notes])
            return notify.SENT

    config.override(notify_mode="webhook", notify_webhook_url="http://127.0.0.1:9/unused")
    notify.set_notifier(Hook())
    assert [n["id"] for n in notify.pending(W)] == [1, 2, 3, 4, 5, 6]
    assert notify.flush(AFTER)["pushed"] == 6
    assert notify.flush(AFTER + 60)["pushed"] == 0
    assert sent == [[1, 2, 3, 4, 5, 6]] and notify.pending(W) == []


def test_the_page_and_its_reads_answer(old_db):
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.get("/page/").status_code == 200
    assert c.get("/api/about").json()["version"] == kitchenette.__version__
    for path in ("/api/dex", "/api/book", "/api/dishes", "/api/jars", "/api/vendor", "/api/vendor/ledger",
                 "/api/fridge", "/api/kitchen", "/api/recipes/today", "/api/wallet"):
        assert c.get(path, params={"who": W}).status_code == 200, path
    for sid in ALL_POTS:
        assert c.get("/api/kitchen", params={"session_id": sid}).json()["settlement"]["has"] is True
    mine = c.get("/api/vendor/ledger", params={"who": W}).json()["orders"]
    assert sorted(o["state"] for o in mine) == ["debit_failed", "delivered"]
    # buying what a recipe lacks now wants an op_id (a retry of the same buying sends the same one)
    assert c.post("/api/recipes/buy_missing", json={"who": W, "recipe": SOUP}).status_code == 400
    assert c.post("/api/recipes/buy_missing", json={"who": W, "recipe": SOUP, "op_id": "o1"}).status_code == 200


def test_a_reply_sent_again_after_the_upgrade_gets_its_0_2_0_receipts(old_db):
    from kitchenette import inline
    got = inline.execute(W, "[刷盘子]", "m6")             # the reply that started the first washing in 0.2.0
    assert [(r.marker, r.ok, r.text) for r in got] == [("刷盘子", True, "开始刷了:3 只盘子,大概 6 分钟。")]
    assert got[0].attachments == []                      # stored before receipts carried cards
    conn = _conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM wash_jobs").fetchone()[0] == 2     # nothing started again
    finally:
        conn.close()
