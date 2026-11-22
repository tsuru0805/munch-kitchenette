"""「今天可以试试」: three dishes in all — two the fridge can make now and one that is one thing short
(two ready, one short); fewer when fewer fit."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from kitchenette import fridge, menu, recipes, tools
from kitchenette.api import create_app
from kitchenette.texts_play import TEXTS

from conftest import A, play_on


def _r(rid: str, name: str, *items: str, method: str = "stirfry") -> dict:
    return {"id": rid, "name": name, "aliases": [], "main": [{"item": i, "qty": 1} for i in items],
            "optional": [], "staples": [], "method": method, "minutes": 10, "category": "vegetable_dish",
            "category_label": "素菜", "source": "test"}


@pytest.fixture()
def book(monkeypatch):
    """A small recipe book the test fills in; load() returns it."""
    rows: list[dict] = []
    monkeypatch.setattr(recipes, "load", lambda: {"by_id": {r["id"]: r for r in rows}, "list": rows,
                                                  "source": {}})
    return rows


def pick(book_rows, have, **kw):
    args = dict(have=have, meh_items=set(), cooked_names=set(), recent_names=set(), stop=set(), dis=set(),
                sig={}, day="2027-01-15", who=A)
    args.update(kw)
    return recipes.recommend(**args)


def test_plenty_of_both_gives_two_that_can_be_made_and_one_that_is_short(book):
    book += [_r(f"r{i}", f"能做{i}", "egg") for i in range(6)]
    book += [_r(f"n{i}", f"差一样{i}", "egg", "tomato") for i in range(4)]
    got = pick(book, {"egg": 5})
    assert len(got["ready"]) == 2 and len(got["near"]) == 1
    assert got["near"][0][1] == {"tomato": 1}


def test_nothing_short_lets_the_third_be_one_more_that_can_be_made(book):
    book += [_r(f"r{i}", f"能做{i}", "egg") for i in range(6)]
    got = pick(book, {"egg": 5})
    assert len(got["ready"]) == 3 and got["near"] == []


def test_fewer_that_can_be_made_are_not_padded_with_more_short_ones(book):
    book += [_r("r0", "只此一道", "egg")]
    book += [_r(f"n{i}", f"差一样{i}", "egg", "tomato") for i in range(5)]
    got = pick(book, {"egg": 5})
    assert [r["name"] for r in got["ready"]] == ["只此一道"] and len(got["near"]) == 1
    got = pick(book, {})                    # nothing can be made: only the one that is short... of one thing
    assert got["ready"] == [] and len(got["near"]) <= 1


def test_with_two_places_the_stale_one_and_the_new_one_come_first(book):
    book += [_r(f"r{i}", f"老菜{i}", "egg") for i in range(5)]
    book += [_r("stale", "用掉番茄", "egg", "tomato"), _r("fresh", "没做过", "egg", "cucumber"),
             _r("n0", "差一样", "egg", "carrot")]
    cooked = {f"老菜{i}" for i in range(5)} | {"用掉番茄"}
    got = pick(book, {"egg": 5, "tomato": 1, "cucumber": 1}, meh_items={"tomato"}, cooked_names=cooked)
    assert [r["name"] for r in got["ready"]] == ["用掉番茄", "没做过"] and len(got["near"]) == 1


def _lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.startswith("· ")]


def test_every_place_that_shows_the_picks_shows_at_most_three(clock):
    """Looking at the kitchen, the menu view, the browse tool and the page's REST endpoint all print the
    same paragraph, on the real recipe index."""
    play_on("recipes_public", "recipes_today", "recipe_book")
    fridge.buy_her(A, ["egg", "tomato", "cucumber", "potato", "pork", "onion", "pepper", "milk"])
    status = tools.call("kitchen_status", {}, A).text
    today = tools.call("kitchen_recipes", {"what": "today"}, A).text
    rest = TestClient(create_app()).get("/api/recipes/today", params={"who": A}).json()["text"]
    menu_text = menu.read_menu(A)
    menu_para = menu_text[menu_text.index("今天"):]
    para = status[status.index("今天"):]
    for text in (para, today, rest, menu_para):
        picks = _lines(text)
        assert 1 <= len(picks) <= 3, text
        near = [ln for ln in picks if "还缺" in ln]
        assert len(near) <= 1
    assert _lines(today) == _lines(rest) == _lines(para) == _lines(menu_para)
    assert TEXTS["rec_head_near"] in today and len(_lines(today)) == 3
    assert len([ln for ln in _lines(today) if re.search(r"约 \d+ 分钟", ln)]) == 2
