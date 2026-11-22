"""The recipe index and the rules that build it: every ingredient on a line counts, a food inside a
longer word is not that food, the minutes are read in figures and in words."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kitchenette import fridge, recipes
from kitchenette.texts_play import vendor_id

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_recipe_index as bi  # noqa: E402


def _entry(name: str) -> dict:
    return next(r for r in recipes.load()["list"] if r["name"] == name)


def _names(items: list[dict]) -> list[str]:
    return [fridge.item(e["item"])["name"] if fridge.item(e["item"]) else e["item"] for e in items]


# ── the entries that were wrong ─────────────────────────────────────────

def test_fried_rice_noodles_have_their_noodles_and_meat():
    # was: main = 黄瓜 only (the line "炒河粉、猪肉/牛肉" kept just its first word, read as a seasoning)
    main = _names(_entry("炒河粉")["main"])
    assert main[:2] == ["河粉", "猪肉"] and "黄瓜" in main and "鸡蛋" in main


def test_pork_knuckle_is_not_tofu():
    # was: main = 豆腐 ("带脚、爪猪前肘" split at 、, and 豆腐 found inside 红豆腐乳)
    r = _entry("带把肘子")
    assert _names(r["main"]) == ["猪肘"] and "红豆腐乳" in r["staples"]


def test_perfect_boiled_egg_keeps_the_pages_35_minutes():
    # the page itself says 约 35 分钟 (sixteen two-minute moves between two pots)
    assert _entry("完美水煮蛋")["minutes"] == 35


@pytest.mark.parametrize("name, minutes", [("牛奶燕麦", 3), ("螺蛳粉", 10), ("肉蛋盖饭", 15), ("温泉蛋", 30),
                                           ("小炒肉", 60), ("酱牛肉", 200), ("猪皮冻", 120)])
def test_minutes_written_in_words_or_with_hours_of_waiting(name, minutes):
    assert _entry(name)["minutes"] == minutes


def test_names_bought_under_the_previous_index_still_resolve():
    recipes.load()
    for old in ("猪前肘", "热干面特有的碱水面", "泡好的粉丝"):    # old spellings, kept for old stock
        assert recipes.vendor_item(vendor_id(old))["name"] == old


# ── the rules ───────────────────────────────────────────────────────────

def test_every_ingredient_on_a_line_counts():
    got = bi._pieces("黄瓜、面筋块、绿豆芽、鸡蛋、蒜瓣、小葱、淀粉")
    assert [a[0] for a, _o in got] == ["黄瓜", "面筋", "绿豆芽", "鸡蛋", "蒜瓣", "小葱", "淀粉"]
    assert bi._pieces("注：如果有可能，尽量另准备一把菜刀") == []
    assert [a for a, _o in bi._pieces("猪五花肉或猪肉排骨")] == [["猪五花肉", "猪肉排骨"]]


def test_optional_is_read_per_ingredient():
    got = dict((a[0], o) for a, o in bi._pieces("主料：`大肉`、`鸡蛋`（可选）、`豆皮`（可选）"))
    assert got == {"五花肉": False, "鸡蛋": True, "豆皮": True}
    # "（可选牛腩肉或牛尾肉）" names a choice of cut, not an optional beef
    assert bi._pieces("牛肉（可选牛腩肉或牛尾肉）") == [(["牛肉"], False)]


@pytest.mark.parametrize("tok, kind, val", [
    ("红豆腐乳", "staple", "红豆腐乳"),     # fermented bean curd, not tofu
    ("牛肉末", "main", "beef"),
    ("黄瓜丝", "main", "cucumber"),
    ("五花肉片", "main", "pork"),
    ("蕃茄酱", "staple", "蕃茄酱"),         # ketchup, not tomato
    ("甜椒粉", "staple", "甜椒粉"),         # paprika, not a pepper
    ("百香果", "vendor", None),             # a fruit, not the spice 香果
    ("板栗", "vendor", None),               # holds 板, a tool word, but is a chestnut
    ("葱末", "main", "scallion"),
])
def test_a_food_inside_a_longer_word(tok, kind, val):
    k, v = recipes.classify_token(tok)
    assert k == kind and (val is None or v == val)


@pytest.mark.parametrize("text, minutes", [
    ("从备料到上桌大约只需二十分钟。", 20),
    ("预计全程大约花费一个半小时。", 90),
    ("耐心等待一下,从煮面到拌好大约只需十几分钟。", 15),
    ("全程耗时约 8 小时 15 分钟。", 495),
    ("预计备菜 7 分钟，烹饪 10 分钟，总共约 17 分钟就能出锅。", 17),
    ("需提前一天腌制百香果，总耗时约 24 小时，实际动手时间仅 大约 30 分钟。", 30),
    ("实际操作只需几分钟，全程大约四十分钟就能吃上。", 40),     # an air fryer is cooking, not waiting
    ("预计制作时长约 40 分钟（不含木耳泡发时间）。", 40),
])
def test_minutes_from_the_opening(text, minutes):
    assert bi.minutes_pick(text + "\n## 必备原料和工具\n", "boil")[0] == minutes


def test_or_joins_only_its_own_item():
    # "鸡肉、土豆、黄油或玉米油" is chicken, potato, and butter-or-oil (oil is at hand)
    got = bi._pieces("鸡肉、土豆、黄油或玉米油")
    assert [a for a, _o in got] == [["鸡肉"], ["土豆"], ["黄油", "玉米油"]]
    assert [bi._pick(a)[:2] for a, _o in got] == [("main", "chicken"), ("main", "potato"), ("staple", "玉米油")]
    # a slash too
    assert [a for a, _o in bi._pieces("炒河粉、猪肉/牛肉")] == [["河粉"], ["猪肉", "牛肉"]]


def test_a_whole_list_of_alternatives_only_where_a_person_read_the_page():
    # 芥末黄油罗氏虾: 「料酒、朗姆酒或啤酒」is one of the three (the page's step 6: 料酒、啤酒可以放…)
    rel = "dishes/aquatic/芥末黄油罗氏虾/芥末黄油罗氏虾.md"
    assert "料酒、朗姆酒或啤酒" in bi.WHOLE_OR[rel]
    assert bi._pieces("料酒、朗姆酒或啤酒", whole_or=True) == [(["料酒", "朗姆酒", "啤酒"], False)]
    assert [a for a, _o in bi._pieces("料酒、朗姆酒或啤酒")] == [["料酒"], ["朗姆酒", "啤酒"]]
    assert _names(_entry("芥末黄油罗氏虾")["main"]) == ["虾", "黄油"]


def test_an_alternative_always_at_hand_makes_nothing_to_buy():
    assert bi._pick(["黄油", "玉米油"])[0] == "staple"
    assert bi._pick(["柠檬汁", "白醋"])[0] == "staple"
    assert bi._pick(["牛奶", "淡奶油", "炼乳", "奶粉"])[:2] == ("main", "milk")    # 奶粉 is not at hand
    assert "黄油" not in _names(_entry("基础牛奶面包")["main"])


def test_guilin_stuffed_needs_a_wrapper_not_only_pork():
    r = _entry("桂林十八酿")
    assert _names(r["main"]) == ["青椒", "猪肉"]
    assert recipes.feasibility([r["main"]], {"pork": 1})["short"] == {"pepper": 1}


# ── revisions and old names ─────────────────────────────────────────────

def _guide(root: Path, pages: dict[str, str]) -> Path:
    """A tiny HowToCook-shaped git checkout."""
    import subprocess
    repo = root / "guide"
    for rel, items in pages.items():
        f = repo / "dishes" / "vegetable_dish" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# {rel[:-3]}的做法\n\n全程约 10 分钟。\n\n## 必备原料和工具\n\n{items}\n\n## 计算\n\n## 操作\n\n炒。\n",
                     encoding="utf-8")
    run = dict(cwd=repo, check=True, capture_output=True)
    if not (repo / ".git").exists():
        subprocess.run(["git", "init", "-q"], **run)
    subprocess.run(["git", "add", "-A"], **run)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x", "--allow-empty"],
                   **run)
    return repo


def test_a_deleted_entry_is_a_new_revision_and_its_old_version_stays_readable(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(bi, "FIXES", {})
    monkeypatch.setattr(bi, "MINUTES", {})
    monkeypatch.setattr(bi, "WHOLE_OR", {})
    repo = _guide(tmp_path, {"炒黄瓜.md": "- 黄瓜\n- 盐", "炒土豆.md": "- 土豆\n- 盐"})
    out = tmp_path / "data"
    out.mkdir()

    def build():
        monkeypatch.setattr(sys, "argv", ["build", str(repo), "--out", str(out)])
        bi.main()
        return json.loads(next(out.glob("howtocook-*.index.json")).read_text(encoding="utf-8"))
    first = build()
    gone = next(r for r in first["recipes"] if r["name"] == "炒土豆")
    assert first["revision"] == 1 and not (out / "history").exists()
    assert build()["revision"] == 1                          # nothing changed: no new revision
    (repo / "dishes" / "vegetable_dish" / "炒土豆.md").unlink()   # same commit: only a deletion
    second = build()
    assert second["revision"] == 2 and [r["name"] for r in second["recipes"]] == ["炒黄瓜"]
    kept = list((out / "history").glob("*.r1.index.json"))
    assert len(kept) == 1 and json.loads(kept[0].read_text(encoding="utf-8")) == first
    monkeypatch.setenv("KITCHENETTE_RECIPES_INDEX", str(next(out.glob("howtocook-*.index.json"))))
    assert recipes.get(gone["id"]) is None
    assert recipes.get(gone["id"], 1)["name"] == "炒土豆"
    # built from a newer commit of the guide: still one current index, the previous one kept
    (repo / "dishes" / "vegetable_dish" / "炒茄子.md").write_text(
        "# 炒茄子的做法\n\n## 必备原料和工具\n\n- 茄子\n\n## 计算\n\n## 操作\n\n炒。\n", encoding="utf-8")
    _guide(tmp_path, {})
    third = build()
    assert third["revision"] == 3 and len(list(out.glob("howtocook-*.index.json"))) == 1
    assert sorted(p.name.split(".")[-3] for p in (out / "history").glob("*.index.json")) == ["r1", "r2"]


def test_an_entry_deleted_and_brought_back_continues_its_versions(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(bi, "FIXES", {})
    monkeypatch.setattr(bi, "MINUTES", {})
    monkeypatch.setattr(bi, "WHOLE_OR", {})
    repo = _guide(tmp_path, {"炒黄瓜.md": "- 黄瓜\n- 盐", "炒土豆.md": "- 土豆\n- 盐"})
    page = repo / "dishes" / "vegetable_dish" / "炒土豆.md"
    out = tmp_path / "data"
    out.mkdir()

    def build():
        monkeypatch.setattr(sys, "argv", ["build", str(repo), "--out", str(out)])
        bi.main()
        return json.loads(next(out.glob("howtocook-*.index.json")).read_text(encoding="utf-8"))

    def potato(idx):
        return next((r for r in idx["recipes"] if r["name"] == "炒土豆"), None)
    rid = potato(build())["id"]                                   # r1: 炒土豆 v1 (土豆)
    page.write_text(page.read_text(encoding="utf-8").replace("- 土豆", "- 土豆\n- 鸡蛋"), encoding="utf-8")
    assert potato(build())["version"] == 2                        # r2: v2 (土豆、鸡蛋)
    saved = page.read_text(encoding="utf-8")
    page.unlink()
    assert potato(build()) is None                                # r3: deleted
    page.write_text(saved.replace("- 鸡蛋", "- 番茄"), encoding="utf-8")
    back = potato(build())                                        # r4: back, same id, new content
    assert back["id"] == rid and back["version"] == 3
    monkeypatch.setenv("KITCHENETTE_RECIPES_INDEX", str(next(out.glob("howtocook-*.index.json"))))
    got = {v: [e["item"] for e in recipes.get(rid, v)["main"]] for v in (1, 2, 3)}
    assert got == {1: ["potato"], 2: ["potato", "egg"], 3: ["potato", "tomato"]}


def test_aliases_are_checked_when_built(monkeypatch):
    v = vendor_id
    used = {"粉丝", "河粉"}
    # an inherited alias whose name is in use again, or whose target is gone, is dropped
    got = bi._vendor_aliases(["粉丝", "河粉", "旧A", "旧B"], used,
                             {"粉丝": v("河粉"), "旧A": v("已经没有的东西"), "旧B": v("河粉")})
    assert got == {"旧B": v("河粉")}
    # a chain is followed to its end; a loop stops the build
    got = bi._vendor_aliases(["粉丝", "旧C", "旧D"], used, {"旧C": v("旧D"), "旧D": v("粉丝")})
    assert got == {"旧C": v("粉丝"), "旧D": v("粉丝")}
    with pytest.raises(SystemExit):
        bi._vendor_aliases(["旧E", "旧F"], used, {"旧E": v("旧F"), "旧F": v("旧E")})


def test_a_looping_alias_does_not_hang_the_kitchen(monkeypatch):
    v = vendor_id
    recipes.load()
    a, b = v("环一"), v("环二")
    monkeypatch.setitem(recipes._VENDOR_ALIAS, a, b)
    monkeypatch.setitem(recipes._VENDOR_ALIAS, b, a)
    assert fridge.canon(a) in (a, b)
