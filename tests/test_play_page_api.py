"""What the kitchen page reads and writes for the dish book and the recipe settings: the placeholder
picture of each page, merging an unsorted dish and undoing it, the recipes taken out of picks (listed so
they can be put back), and the ingredients the human does not want recommended."""
from __future__ import annotations

from fastapi.testclient import TestClient

from kitchenette import fridge, inline, service, tools
from kitchenette.api import create_app

from conftest import A, B, play_on

STEAMED_EGG = "hc-e0a19bc9"     # 蒸水蛋: egg


def _cook(clock, dish: str, **extra) -> None:
    fridge.buy_her(A, ["egg"])
    res = tools.call("kitchen_cook", {"dish": dish, "minutes": 5, "ingredients": ["鸡蛋"], **extra}, A)
    assert not res.is_error, res.text
    clock["now"] += 5 * 60 + 1
    service.scan_all()


def test_dish_book_pages_carry_their_placeholder_picture_and_merges_can_be_undone(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    inline.execute(A, "[收藏 可乐鸡翅]", "m-collect")
    _cook(clock, "蒸水蛋", recipe=STEAMED_EGG)
    _cook(clock, "我家 的蛋羹")
    d = c.get("/api/dex", params={"who": A}).json()
    pages = {p["key"]: p for p in d["pages"]}
    assert pages[f"r:{STEAMED_EGG}"]["icon"] == "steamer"
    assert pages["d:我家的蛋羹"]["pending"] is True and isinstance(pages["d:我家的蛋羹"]["icon"], str)
    assert d["merges"] == []
    assert [(s["name"], s["icon"]) for s in d["silhouettes"]] == [("可乐鸡翅", "meat")]

    # merging the unsorted dish into the recipe's page, then undoing it (merging it back onto its own page)
    assert c.put("/api/dex/merge", json={"who": A, "dish": "我家的蛋羹", "page_key": f"r:{STEAMED_EGG}"}).status_code == 200
    d = c.get("/api/dex", params={"who": A}).json()
    pages = {p["key"]: p for p in d["pages"]}
    assert "d:我家的蛋羹" not in pages and pages[f"r:{STEAMED_EGG}"]["made"] == 2
    assert d["merges"] == [{"dish": "我家的蛋羹", "page_key": f"r:{STEAMED_EGG}"}]
    c.put("/api/dex/merge", json={"who": A, "dish": "我家的蛋羹", "page_key": "d:我家的蛋羹"})
    d = c.get("/api/dex", params={"who": A}).json()
    pages = {p["key"]: p for p in d["pages"]}
    assert pages["d:我家的蛋羹"]["made"] == 1 and pages[f"r:{STEAMED_EGG}"]["made"] == 1
    assert d["merges"] == []


def test_a_stopped_recipe_is_listed_and_can_be_put_back(clock):
    play_on("recipes_public")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    found = lambda: [r["id"] for r in c.get("/api/recipes", params={"who": A, "q": "蒸水蛋"}).json()["recipes"]]  # noqa: E731
    assert STEAMED_EGG in found()
    assert c.get("/api/recipes/stopped").json() == {"recipes": []}
    c.put(f"/api/recipes/{STEAMED_EGG}/stop", json={"stopped": True, "why": "火候写错了"})
    assert STEAMED_EGG not in found()
    stopped = c.get("/api/recipes/stopped").json()["recipes"]
    assert [(r["id"], r["name"], r["why"]) for r in stopped] == [(STEAMED_EGG, "蒸水蛋", "火候写错了")]
    c.put(f"/api/recipes/{STEAMED_EGG}/stop", json={"stopped": False})
    assert STEAMED_EGG in found() and c.get("/api/recipes/stopped").json() == {"recipes": []}


def test_dislikes_are_read_back_and_cleared(clock):
    play_on("recipes_public")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.put("/api/prefs", json={"who": A, "dislike": ["egg"]}).json()["dislike"] == ["egg"]
    assert c.get("/api/prefs", params={"who": A}).json()["dislike"] == ["egg"]
    assert STEAMED_EGG not in [r["id"] for r in c.get("/api/recipes", params={"who": A, "q": "蒸水蛋"}).json()["recipes"]]
    assert c.put("/api/prefs", json={"who": A, "dislike": ["no-such-thing"]}).status_code == 400
    c.put("/api/prefs", json={"who": A, "dislike": []})
    assert c.get("/api/prefs", params={"who": A}).json()["dislike"] == []


def test_the_stopped_list_is_off_with_the_public_recipes(clock):
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.get("/api/recipes/stopped").status_code == 409


# ── merging: only onto sorted pages; chains left by older versions are straightened ──

def _dex(c):
    d = c.get("/api/dex", params={"who": A}).json()
    return d, {p["key"]: p for p in d["pages"]}


def test_merging_onto_an_unsorted_page_is_refused_and_a_sorted_one_is_fine(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook(clock, "蒸水蛋")                 # a free pot named like a recipe: a sorted d: page
    _cook(clock, "甲蛋")
    _cook(clock, "乙蛋")
    _, pages = _dex(c)
    assert pages["d:蒸水蛋"]["pending"] is False and pages["d:甲蛋"]["pending"] is True
    r = c.put("/api/dex/merge", json={"who": A, "dish": "甲蛋", "page_key": "d:乙蛋"})
    assert r.status_code == 409 and "待归类" in r.json()["detail"]
    assert c.put("/api/dex/merge", json={"who": A, "dish": "甲蛋", "page_key": "nonsense"}).status_code == 400
    assert c.put("/api/dex/merge", json={"who": A, "dish": "甲蛋", "page_key": "d:蒸水蛋"}).status_code == 200
    assert c.put("/api/dex/merge", json={"who": A, "dish": "乙蛋", "page_key": f"r:{STEAMED_EGG}"}).status_code == 200
    d, pages = _dex(c)
    assert pages["d:蒸水蛋"]["made"] == 2 and pages[f"r:{STEAMED_EGG}"]["made"] == 1
    assert "d:甲蛋" not in pages and "d:乙蛋" not in pages


def test_a_chain_left_by_an_older_version_is_straightened_and_can_be_taken_apart(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook(clock, "蒸水蛋", recipe=STEAMED_EGG)
    _cook(clock, "甲蛋")
    _cook(clock, "乙蛋")
    from kitchenette import db
    conn = db.connect()      # what the old page could do: 甲 onto 乙's unsorted page, then 乙 onto the recipe
    conn.executemany("INSERT INTO dex_merges (who, dish, page_key, at) VALUES (?,?,?,?)",
                     [(A, "甲蛋", "d:乙蛋", 1.0), (A, "乙蛋", f"r:{STEAMED_EGG}", 2.0)])
    conn.commit()
    conn.close()
    d, pages = _dex(c)
    assert pages[f"r:{STEAMED_EGG}"]["made"] == 3 and "d:甲蛋" not in pages and "d:乙蛋" not in pages
    assert sorted(m["dish"] for m in d["merges"] if m["page_key"] == f"r:{STEAMED_EGG}") == ["乙蛋", "甲蛋"]
    c.put("/api/dex/merge", json={"who": A, "dish": "甲蛋", "page_key": "d:甲蛋"})
    d, pages = _dex(c)
    assert pages["d:甲蛋"]["made"] == 1 and pages[f"r:{STEAMED_EGG}"]["made"] == 2
    assert [m["dish"] for m in d["merges"]] == ["乙蛋"]


def test_a_loop_of_merges_is_cut_and_no_pot_is_lost(clock):
    play_on("dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook(clock, "甲蛋")
    _cook(clock, "乙蛋")
    from kitchenette import db
    conn = db.connect()
    conn.executemany("INSERT INTO dex_merges (who, dish, page_key, at) VALUES (?,?,?,?)",
                     [(A, "甲蛋", "d:乙蛋", 1.0), (A, "乙蛋", "d:甲蛋", 2.0)])
    conn.commit()
    conn.close()
    d, pages = _dex(c)
    # the loop is cut where it was found: one dish goes home, the other stays on its page; no pot is lost
    assert sum(p["made"] for p in pages.values()) == 2 and len(pages) == 1
    assert len(d["merges"]) == 1


# ── dislikes one at a time ──

def test_dislikes_are_added_and_removed_one_at_a_time(clock):
    play_on("recipes_public")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.post("/api/prefs/dislike", json={"who": A, "item": "egg"}).json()["dislike"] == ["egg"]
    assert c.post("/api/prefs/dislike", json={"who": A, "item": "egg"}).json()["dislike"] == ["egg"]
    assert c.post("/api/prefs/dislike", json={"who": A, "item": "tomato"}).json()["dislike"] == ["egg", "tomato"]
    assert c.post("/api/prefs/dislike", json={"who": A, "item": "no-such"}).status_code == 400
    assert c.delete("/api/prefs/dislike/egg", params={"who": A}).json()["dislike"] == ["tomato"]
    assert c.delete("/api/prefs/dislike/egg", params={"who": A}).json()["dislike"] == ["tomato"]
    assert c.put("/api/prefs", json={"who": A, "dislike": []}).json()["dislike"] == []   # the old whole-list write still works


# ── buying what a recipe lacks: one transaction per op_id, a retry answers the receipt ──

TOMATO_EGG = "hc-d9b1068d"      # tomato + egg×2


def _batches(c, item: str) -> int:
    return sum(1 for b in c.get("/api/fridge", params={"who": A}).json()["items"] if b["item_id"] == item)


def _buy(c, op: str, recipe: str = TOMATO_EGG):
    return c.post("/api/recipes/buy_missing", json={"who": A, "recipe": recipe, "op_id": op})


def test_a_retry_of_the_same_buying_answers_the_receipt_and_buys_nothing(clock):
    play_on("recipes_public", "recipe_cook")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert c.post("/api/recipes/buy_missing", json={"who": A, "recipe": TOMATO_EGG}).status_code == 400   # no op_id
    first = _buy(c, "op-1").json()
    assert first["ok"] and first["added"] and first["missing"] == [] and first["replayed"] is False
    again = _buy(c, "op-1").json()
    assert again["replayed"] is True and again["added"] == first["added"] and again["missing"] == []
    assert _batches(c, "tomato") == 1
    assert _buy(c, "op-1", recipe=STEAMED_EGG).status_code == 409        # the same op_id for another buying
    assert _buy(c, "op-x", recipe="hc-nope").status_code == 404


def test_a_retry_after_the_food_was_used_up_still_buys_nothing_but_a_new_buying_does(clock):
    play_on("recipes_public", "recipe_cook")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _buy(c, "op-1")
    from kitchenette import db
    conn = db.connect()      # the tomato was cooked away meanwhile
    conn.execute("DELETE FROM batches WHERE who=? AND item_id='tomato'", (A,))
    conn.commit()
    conn.close()
    assert _batches(c, "tomato") == 0
    replay = _buy(c, "op-1").json()
    assert replay["replayed"] is True and _batches(c, "tomato") == 0
    fresh = _buy(c, "op-2").json()
    assert fresh["replayed"] is False and [a["item_id"] for a in fresh["added"]] == ["tomato"]
    assert _batches(c, "tomato") == 1


def test_a_second_buying_works_the_shortage_out_again_and_buys_nothing(clock):
    play_on("recipes_public", "recipe_cook")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _buy(c, "op-1")
    second = _buy(c, "op-2").json()
    assert second["added"] == [] and second["missing"] == [] and second["replayed"] is False
    assert _batches(c, "tomato") == 1


def test_buyings_on_separate_connections_at_once_buy_once(clock):
    import threading
    play_on("recipes_public", "recipe_cook")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert _batches(c, "tomato") == 0      # the database is made before the four meet (making it is not what is tested)
    out = []
    go = threading.Barrier(4)

    def one(op):
        go.wait()
        out.append(_buy(c, op).json())
    ts = [threading.Thread(target=one, args=(f"op-{i}",)) for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(bool(o["added"]) for o in out) == [False, False, False, True]
    assert _batches(c, "tomato") == 1


# ── straightening chains never writes over a merge made in between ──

def _chain(dishes=(("甲蛋", "d:乙蛋"), ("乙蛋", f"r:{STEAMED_EGG}"))):
    from kitchenette import db
    conn = db.connect()
    conn.executemany("INSERT INTO dex_merges (who, dish, page_key, at) VALUES (?,?,?,?)",
                     [(A, d, k, float(i)) for i, (d, k) in enumerate(dishes)])
    conn.commit()
    conn.close()


def _row(dish):
    from kitchenette import db
    conn = db.connect()
    try:
        return conn.execute("SELECT page_key FROM dex_merges WHERE who=? AND dish=?", (A, dish)).fetchone()[0]
    finally:
        conn.close()


def test_straightening_from_an_old_reading_does_not_undo_a_merge_made_after_it(clock):
    """A reads the table (sees the chain), B takes 甲 back out and commits, A then straightens from what it
    read: 甲 must stay where B put it."""
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook(clock, "蒸水蛋", recipe=STEAMED_EGG)
    _cook(clock, "甲蛋")
    _cook(clock, "乙蛋")
    _chain()
    from kitchenette import db, play_api
    reader = db.connect()
    stale = play_api._merge_rows(reader, A)                       # A's reading
    assert c.put("/api/dex/merge", json={"who": A, "dish": "甲蛋", "page_key": "d:甲蛋"}).status_code == 200   # B
    reader.execute("BEGIN IMMEDIATE")
    play_api.flatten_merges(reader, A, stale)                     # A writes from its old reading
    reader.commit()
    reader.close()
    assert _row("甲蛋") == "d:甲蛋"


def test_reading_the_book_straightens_under_the_write_lock_and_writes_nothing_without_a_chain(clock, monkeypatch):
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook(clock, "蒸水蛋", recipe=STEAMED_EGG)
    _cook(clock, "甲蛋")
    _cook(clock, "乙蛋")
    from kitchenette import play_api
    calls = []
    real = play_api.flatten_merges
    monkeypatch.setattr(play_api, "flatten_merges", lambda conn, who, rows=None: calls.append(conn.in_transaction) or real(conn, who, rows))
    c.get("/api/dex", params={"who": A})
    assert calls == []                                            # no chain: no write at all
    _chain()
    c.get("/api/dex", params={"who": A})
    assert calls == [True] and _row("甲蛋") == f"r:{STEAMED_EGG}"


# ── merging onto a recipe's page: the recipe has to exist ──

def test_merging_onto_a_recipe_that_does_not_exist_or_is_not_his_is_refused(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book", "dex")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    _cook(clock, "甲蛋")
    inline.execute(A, "[记菜 拌黄瓜 黄瓜 拌 5 | 夏天吃]", "m-own-a")
    inline.execute(B, "[记菜 拍黄瓜 黄瓜 拌 5]", "m-own-b")
    from kitchenette import db
    conn = db.connect()
    mine = conn.execute("SELECT id FROM recipe_pages WHERE who=? AND kind='own'", (A,)).fetchone()[0]
    theirs = conn.execute("SELECT id FROM recipe_pages WHERE who=? AND kind='own'", (B,)).fetchone()[0]
    conn.close()
    put = lambda key: c.put("/api/dex/merge", json={"who": A, "dish": "甲蛋", "page_key": key})  # noqa: E731
    assert put("r:hc-does-not-exist").status_code == 404
    assert put(f"r:{theirs}").status_code == 404                  # another role's page is as good as none
    assert put(f"r:{STEAMED_EGG}").status_code == 200              # a public recipe
    assert put(f"r:{mine}").status_code == 200                     # his own page
    conn = db.connect()
    conn.execute("UPDATE recipe_pages SET deleted_at=1 WHERE id=?", (mine,))
    conn.commit()
    conn.close()
    r = put(f"r:{mine}")
    assert r.status_code == 409 and "删" in r.json()["detail"]


# ── the old whole-list write, with a version ──

def test_the_whole_list_write_with_a_version_refuses_a_list_changed_since(clock):
    play_on("recipes_public")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    v0 = c.get("/api/prefs", params={"who": A}).json()["version"]
    c.post("/api/prefs/dislike", json={"who": A, "item": "egg"})          # another page, one item
    r = c.put("/api/prefs", json={"who": A, "dislike": ["tomato"], "version": v0})
    assert r.status_code == 409
    assert c.get("/api/prefs", params={"who": A}).json()["dislike"] == ["egg"]   # nothing changed
    v1 = c.get("/api/prefs", params={"who": A}).json()["version"]
    ok = c.put("/api/prefs", json={"who": A, "dislike": ["egg", "tomato"], "version": v1}).json()
    assert ok["dislike"] == ["egg", "tomato"] and ok["version"] != v1
    assert c.put("/api/prefs", json={"who": A, "dislike": []}).status_code == 200   # no version: still replaces


# ── the note of a buying: written with the buying, pushed after, retried if pushing failed ──

def _bought_notes() -> list:
    from kitchenette import db
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute("SELECT id, pushed_at FROM notes WHERE who=? AND kind='fridge.bought'", (A,))]
    finally:
        conn.close()


def test_if_the_note_cannot_be_written_nothing_is_bought_and_a_retry_does_both(clock, monkeypatch):
    from kitchenette import notify
    play_on("recipes_public", "recipe_cook")
    c = TestClient(create_app(scheduler=False, with_mcp=False), raise_server_exceptions=False)
    real = notify.emit_in_tx

    def broken(*a, **kw):
        raise RuntimeError("disk full")
    monkeypatch.setattr(notify, "emit_in_tx", broken)
    assert _buy(c, "op-1").status_code == 500
    assert _batches(c, "tomato") == 0 and _bought_notes() == []          # neither the food nor the note
    monkeypatch.setattr(notify, "emit_in_tx", real)
    r = _buy(c, "op-1").json()                                            # the retry of the same buying
    assert r["replayed"] is False and r["added"]
    assert _batches(c, "tomato") == 1 and len(_bought_notes()) == 1
    _buy(c, "op-1")
    assert _batches(c, "tomato") == 1 and len(_bought_notes()) == 1      # replayed: no second note


def test_a_push_that_failed_is_pushed_once_on_the_retry(clock):
    from kitchenette import config, notify

    class Flaky:
        tries: list = []

        def deliver(self, who, batch):
            self.tries.append([n["kind"] for n in batch])
            return notify.NOT_SENT if len(self.tries) == 1 else notify.SENT
    config.override(notify_mode="webhook", notify_webhook_url="http://127.0.0.1:9/unused")
    notify.set_notifier(Flaky())
    play_on("recipes_public", "recipe_cook")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    assert _buy(c, "op-1").json()["replayed"] is False                    # pushing fails after the commit
    notes = _bought_notes()
    assert len(notes) == 1 and notes[0]["pushed_at"] is None
    assert _buy(c, "op-1").json()["replayed"] is True                     # the retry pushes it
    notes = _bought_notes()
    assert len(notes) == 1 and notes[0]["pushed_at"] is not None
    _buy(c, "op-1")
    assert Flaky.tries == [["fridge.bought"], ["fridge.bought"]]          # tried twice, delivered once


def test_pushing_that_blows_up_after_the_buying_does_not_turn_it_into_an_error(clock, monkeypatch):
    from kitchenette import notify
    play_on("recipes_public", "recipe_cook")
    monkeypatch.setattr(notify, "flush", lambda now=None: (_ for _ in ()).throw(RuntimeError("db gone")))
    c = TestClient(create_app(scheduler=False, with_mcp=False))           # raises any server error into the test
    r = _buy(c, "op-1")
    assert r.status_code == 200 and r.json()["added"] and len(_bought_notes()) == 1


# ── marking an agreed flower kind as ready to sell ──

def test_marking_a_flower_kind_ready_is_reachable_over_http(clock):
    from kitchenette import vendor
    play_on("vendor")
    c = TestClient(create_app(scheduler=False, with_mcp=False))
    inline.execute(A, "[想要花 风信子]", "m-flower")
    req = vendor.flower_requests(A)[0]
    assert c.post(f"/api/vendor/flowers/{req['id']}", json={"approve": True}).json()["ok"] is True
    r = c.post("/api/vendor/flowers/ready", json={"name": "风信子"})
    assert r.status_code == 200 and r.json() == {"changed": 1}
    assert vendor.flower_requests(A)[0]["state"] == "ready"
    assert c.post("/api/vendor/flowers/no-such-id", json={"approve": True}).status_code == 404
