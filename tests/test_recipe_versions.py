"""A public recipe changed between two indexes: the earlier index stays in data/history/, the entry's
version goes up, a pot keeps the version it followed; and a recipe ingredient the index
now calls by another name still counts when it was bought under the old one."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from kitchenette import book, db, fridge, progress, recipes, service, tools
from kitchenette.texts_play import vendor_id

from conftest import A, play_on

DATA = Path(recipes.DATA_DIR)
R1 = DATA / "history" / "howtocook-58c1b9a.r1.index.json"
NOODLES = "hc-27764b15"     # 西红柿鸡蛋挂面: v1 noodles + egg + pepper; v2 also needs the tomato
SOUP = "hc-581cccda"        # 生汆丸子汤: v2 needs 粉丝, written 泡好的粉丝 in v1


def cook(dish, ingredients, recipe, minutes=10):
    res = tools.call("kitchen_cook", {"dish": dish, "minutes": minutes, "ingredients": ingredients,
                                      "recipe": recipe}, A)
    assert not res.is_error, res.text
    return res.text


def pots():
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute("SELECT id, recipe_id, recipe_version, recipe_link FROM cook_sessions"
                                              " WHERE who=? ORDER BY started_at", (A,))]
    finally:
        conn.close()


def test_the_earlier_index_is_kept_and_only_changed_entries_move_up():
    import json
    old = json.loads(R1.read_text(encoding="utf-8"))
    assert "revision" not in old and all("version" not in r for r in old["recipes"])    # kept as it was
    now = recipes.load()
    assert recipes.get(NOODLES)["version"] == 2 and recipes.get("hc-d9b1068d")["version"] == 1
    old_by_id = {r["id"]: r for r in old["recipes"]}
    for r in now["list"]:
        same = all(old_by_id[r["id"]].get(k) == r.get(k) for k in ("main", "optional", "staples", "minutes", "method"))
        assert r["version"] == (1 if same else 2), r["name"]


def test_an_old_pot_reads_v1_and_a_new_pot_follows_v2(clock, monkeypatch):
    play_on("recipes_public", "recipe_cook")
    # before the upgrade: the index in use is the earlier one
    monkeypatch.setenv("KITCHENETTE_RECIPES_INDEX", str(R1))
    recipes.load()
    fridge.buy_her(A, ["noodles", "egg", "pepper"])
    cook("西红柿鸡蛋挂面", ["面条", "鸡蛋", "青椒"], NOODLES)
    clock["now"] += 11 * 60
    service.scan_all()
    # the upgrade
    monkeypatch.delenv("KITCHENETTE_RECIPES_INDEX")
    recipes.load()
    fridge.buy_her(A, ["noodles", "egg", "pepper", "tomato"])
    cook("西红柿鸡蛋挂面", ["面条", "番茄", "鸡蛋", "青椒"], NOODLES)
    old, new = pots()
    assert (old["recipe_version"], new["recipe_version"]) == (1, 2)
    assert old["recipe_link"] == new["recipe_link"] == "follow"
    conn = db.connect()
    try:
        v1 = book.resolve_ref(conn, A, old["recipe_id"], version=old["recipe_version"])
        v2 = book.resolve_ref(conn, A, new["recipe_id"], version=new["recipe_version"])
        st = progress.settlement(conn, old["id"])
    finally:
        conn.close()
    assert [e["item"] for e in v1["main"]] == ["noodles", "egg", "pepper"] and v1["version"] == 1
    assert [e["item"] for e in v2["main"]] == ["noodles", "tomato", "egg", "pepper"] and v2["version"] == 2
    assert st["recipe_version"] == 1 and progress._recipe_name({**st, "book": "recipe"}) == "西红柿鸡蛋挂面"


def test_a_version_that_never_existed_is_not_found():
    assert recipes.get(NOODLES, 7) is None and recipes.get(NOODLES, 1)["main"][1]["item"] == "egg"


@pytest.mark.parametrize("written", ["粉丝", "泡好的粉丝"])
def test_a_box_bought_under_the_old_name_counts_and_is_taken(clock, written):
    play_on("recipes_public", "recipe_cook")
    recipes.load()
    old_id, new_id = vendor_id("泡好的粉丝"), vendor_id("粉丝")
    assert recipes.vendor_alias(old_id) == new_id and fridge.canon(old_id) == fridge.canon(new_id)
    fridge.buy_her(A, [old_id])                   # bought before the upgrade, under the old name
    soup = recipes.get(SOUP)
    assert new_id in [e["item"] for e in soup["main"]]
    have = recipes.fridge_snapshot(fridge._batches(fridge._conn(), A, clock["now"]))
    assert new_id not in recipes.feasibility([soup["main"]], have)["short"]
    # and the pot really takes that box
    fridge.buy_her(A, ["pork", "egg", "woodear", vendor_id("黄花")])
    cook("生汆丸子汤", ["猪肉", "鸡蛋", "木耳", "黄花", written], SOUP)
    left = [b for b in fridge._batches(fridge._conn(), A, clock["now"]) if b["item_id"] == old_id]
    assert left == []
    assert pots()[-1]["recipe_link"] == "follow"


def test_old_names_without_a_successor_are_not_aliased():
    recipes.load()
    assert recipes.vendor_alias(vendor_id("圆碟子")) is None        # a plate, not a food
    assert recipes.vendor_alias(vendor_id(uuid.uuid4().hex)) is None


def test_a_deleted_page_still_answers_for_the_pot_that_followed_it(clock):
    play_on("recipes_public", "recipe_cook", "recipe_book")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        book.record(conn, A, "溏心蛋盖饭 鸡蛋 煮 10", clock["now"])
        pid = conn.execute("SELECT id FROM recipe_pages WHERE who=?", (A,)).fetchone()["id"]
        conn.commit()
    finally:
        conn.close()
    fridge.buy_her(A, ["egg"])
    cook("溏心蛋盖饭", ["鸡蛋"], pid)
    pot = pots()[-1]
    assert (pot["recipe_id"], pot["recipe_version"], pot["recipe_link"]) == (pid, 1, "follow")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        assert book.delete_page(conn, A, pid, clock["now"])
        conn.commit()
        assert book.resolve_ref(conn, A, pid) is None                 # gone from the book
        old = book.resolve_ref(conn, A, pid, version=pot["recipe_version"])
        assert old["name"] == "溏心蛋盖饭" and [e["item"] for e in old["main"]] == ["egg"]
        assert book.resolve_ref(conn, "birch", pid, version=1) is None   # still only its own
    finally:
        conn.close()
