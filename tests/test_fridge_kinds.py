"""Ingredient kinds added from the page, and the optional artwork provider."""
from __future__ import annotations

import sqlite3
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from kitchenette import art, config, fridge
from kitchenette.api import create_app

from conftest import A, B, DAY, T0


def _png(w: int = 4, h: int = 3) -> bytes:
    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xf0\x80\x10\xff" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _three(name, category):
    return {s: _png() for s in art.STATES}


def test_added_kind_joins_catalog_and_he_can_see_and_buy_it(clock):
    k = fridge.add_kind("柿子", "fruit")
    assert k["id"].startswith("u_") and k["art"]["state"] == "pending"
    row = next(c for c in fridge.catalog() if c["id"] == k["id"])
    assert row["custom"] is True and row["shelf_days"] == 7 and row["raw_edible"] is True
    assert row["category_label"] == "水果" and row["art"]["state"] == "pending"
    assert fridge.resolve("柿子") == k["id"]
    assert "柿子" in fridge.status_text(A).split("能买的:", 1)[1]
    fridge.grant_coupon_by_her(A)
    assert "柿子×1" in fridge.buy_self(A, "柿子", key="k1")
    items = fridge.overview(A)["items"]
    assert items[0]["item_id"] == k["id"] and items[0]["freshness"] == "fresh" and items[0]["art"]["state"] == "pending"
    clock["now"] = T0 + 8 * DAY
    assert fridge.overview(A)["items"][0]["freshness"] == "bad"


def test_builtin_catalog_rows_unchanged_shape():
    row = next(c for c in fridge.catalog() if c["id"] == "tomato")
    assert row["custom"] is False and row["raw_edible"] is True and "art" not in row
    assert next(c for c in fridge.catalog() if c["id"] == "lemon")["raw_edible"] is False


def test_options_shelf_days_pack_and_not_raw(clock):
    k = fridge.add_kind("栗子", "fruit", raw_edible=False, pack_qty=5, shelf_days=14)
    assert fridge.is_raw_edible(k["id"]) is False
    assert fridge.buy_her(B, [k["id"]])["added"] == [{"item_id": k["id"], "name": "栗子", "qty": 5}]
    clock["now"] = T0 + 10 * DAY
    assert fridge.overview(B)["items"][0]["freshness"] == "meh"
    assert fridge.is_raw_edible(fridge.add_kind("柿子", "fruit")["id"]) is True
    assert fridge.is_raw_edible(fridge.add_kind("山药", "root")["id"]) is False


@pytest.mark.parametrize("name,category,needle", [
    ("", "fruit", "还没写名字"),
    ("苹果", "fruit", "已经有苹果了"),
    ("西红柿", "veg", "已经算在番茄里了"),
    ("酱油", "veg", "常备"),
    ("柿子 橘子", "fruit", "不能有空格"),
    ("柿子2", "fruit", "数字"),
    ("这个名字实在是太长了", "fruit", "最多 8 个字"),
    ("柿子", "candy", "哪一类"),
])
def test_bad_kind_is_refused_with_words(name, category, needle):
    with pytest.raises(fridge.FridgeError) as e:
        fridge.add_kind(name, category)
    assert needle in e.value.text
    assert not fridge.kinds()


def test_same_name_twice_is_refused():
    fridge.add_kind("柿子", "fruit")
    with pytest.raises(fridge.FridgeError) as e:
        fridge.add_kind("柿子", "fruit")
    assert "已经有柿子了" in e.value.text and e.value.code == "duplicate"


def test_reading_kinds_inside_someone_elses_write_transaction_does_not_lock(tmp_path):
    config.override(server_db_path=str(tmp_path / "fresh.db"))
    assert fridge.kinds() == [] and fridge.item("u_none") is None
    outer = sqlite3.connect(str(tmp_path / "fresh.db"), timeout=0.2)
    outer.execute("CREATE TABLE t (x)")
    outer.execute("BEGIN IMMEDIATE")
    try:
        fridge._kinds_cache.clear()
        assert fridge.kinds() == [] and fridge.resolve("柿子", gone=True) is None
        assert fridge.is_raw_edible("apple") and fridge.freshness("tomato", 0, 1) == "fresh"
    finally:
        outer.rollback()
        outer.close()
    k = fridge.add_kind("柿子", "fruit")
    outer = sqlite3.connect(str(tmp_path / "fresh.db"), timeout=0.2)
    outer.execute("BEGIN IMMEDIATE")
    try:
        fridge._kinds_cache.clear()
        assert fridge.resolve("柿子") == k["id"] and fridge.is_raw_edible(k["id"])
    finally:
        outer.rollback()
        outer.close()


def test_buying_a_kind_she_just_removed_fails_inside_the_transaction_and_keeps_the_coupon(clock):
    k = fridge.add_kind("柿子", "fruit")
    fridge.grant_coupon_by_her(A)
    assert fridge.resolve("柿子") == k["id"]
    conn = fridge._conn()
    conn.execute("UPDATE kinds SET removed_at=1 WHERE id=?", (k["id"],))
    conn.commit()
    conn.close()
    with pytest.raises(fridge.FridgeError) as e:
        fridge.buy_self(A, "柿子 番茄", key="race")
    assert "柿子已经撤掉了" in e.value.text
    ov = fridge.overview(A)
    assert ov["coupons"]["count"] == 1 and ov["items"] == []
    with pytest.raises(fridge.FridgeError) as e:
        fridge.buy_her(A, ["tomato", k["id"]])
    assert "已经撤掉了" in e.value.text and fridge.overview(A)["items"] == []


def test_old_stock_keeps_its_own_shelf_days_when_kind_comes_back_changed(clock):
    k = fridge.add_kind("栗子", "fruit", shelf_days=14)
    fridge.buy_her(A, [k["id"]])
    clock["now"] = T0 + 5 * DAY
    fridge.remove_kind(k["id"])
    again = fridge.add_kind("栗子", "fruit", shelf_days=3)
    assert again["id"] == k["id"]
    fridge.buy_her(A, [k["id"]])
    clock["now"] = T0 + 9 * DAY
    by_age = sorted(fridge.overview(A)["items"], key=lambda b: b["bought_at"])
    assert [b["freshness"] for b in by_age] == ["meh", "bad"]
    assert by_age[0]["expires_at"] == T0 + 14 * DAY and by_age[1]["expires_at"] == T0 + 8 * DAY


def test_removed_kind_cannot_be_bought_but_stock_stays(clock):
    k = fridge.add_kind("柿子", "fruit")
    fridge.buy_her(A, [k["id"]])
    fridge.remove_kind(k["id"])
    assert fridge.resolve("柿子") is None and all(c["id"] != k["id"] for c in fridge.catalog())
    assert "柿子" not in fridge.status_text(A).split("能买的:", 1)[1]
    with pytest.raises(fridge.FridgeError) as e:
        fridge.buy_her(A, [k["id"]])
    assert "没有这样东西" in e.value.text
    fridge.grant_coupon_by_her(A)
    with pytest.raises(fridge.FridgeError) as e:
        fridge.buy_self(A, "柿子", key="k2")
    assert "柿子 不在能买的单子上" in e.value.text
    left = fridge.overview(A)["items"]
    assert [b["name"] for b in left] == ["柿子"]
    assert fridge.resolve("柿子", gone=True) == k["id"] and fridge.is_raw_edible(k["id"])
    fridge.buy_her(B, [fridge.add_kind("梨", "fruit")["id"]])
    fridge.remove_kind(fridge.resolve("梨"))
    assert "梨" in fridge.toss_self(B, "梨", key="t1") and not fridge.overview(B)["items"]
    assert fridge.take_for_cooking(A, [("柿子", 1)]) and not fridge.overview(A)["items"]
    with pytest.raises(fridge.FridgeError):
        fridge.remove_kind(k["id"])
    with pytest.raises(fridge.FridgeError):
        fridge.remove_kind("tomato")


def test_readding_removed_name_brings_back_same_kind_and_keeps_art():
    k = fridge.add_kind("柿子", "fruit")
    fridge.set_art(k["id"], "ready", sizes={"fresh": [256, 200], "meh": [256, 200], "bad": [256, 200]})
    fridge.remove_kind(k["id"])
    again = fridge.add_kind("柿子", "fruit", shelf_days=5)
    assert again["id"] == k["id"] and again["art"]["state"] == "ready" and again["shelf_days"] == 5
    assert again["removed"] is False




def test_run_draws_and_marks_ready():
    k = fridge.add_kind("柿子", "fruit")
    seen = {}
    art.set_provider(lambda name, cat: seen.update(name=name, cat=cat) or _three(name, cat))
    assert art.run(k["id"]) == "ready"
    assert seen == {"name": "柿子", "cat": "fruit"}
    got = fridge.kind(k["id"])["art"]
    assert got["state"] == "ready" and got["v"] == 1 and got["sizes"] == {s: [4, 3] for s in art.STATES}
    for s in art.STATES:
        assert art.art_path(k["id"], s, 1).read_bytes().startswith(b"\x89PNG")
    fridge.redraw_kind(k["id"])
    assert fridge.kind(k["id"])["art"]["state"] == "pending" and art.art_path(k["id"], "fresh", 1).is_file()
    assert art.run(k["id"]) == "ready" and fridge.kind(k["id"])["art"]["v"] == 2
    assert art.art_path(k["id"], "bad", 2).is_file() and not art.art_path(k["id"], "fresh", 1).exists()


def test_redraw_during_drawing_discards_that_round_and_draws_again():
    k = fridge.add_kind("柿子", "fruit")
    calls = []

    def draw(name, cat):
        calls.append(name)
        if len(calls) == 1:
            fridge.redraw_kind(k["id"])
        return _three(name, cat)
    art.set_provider(draw)
    assert art.run(k["id"]) == "pending"
    got = fridge.kind(k["id"])["art"]
    assert got["state"] == "pending" and got["v"] == 0 and not list(art.art_dir().rglob("*.png"))
    assert art.run_queued(k["id"]) == "ready"
    assert len(calls) == 2 and fridge.kind(k["id"])["art"]["v"] == 1


def test_redraw_storm_ends_as_visible_failure_not_a_stuck_pending():
    k = fridge.add_kind("柿子", "fruit")

    def draw(name, cat):
        fridge.redraw_kind(k["id"])
        return _three(name, cat)
    art.set_provider(draw)
    assert art.run_queued(k["id"]) == "failed"
    got = fridge.kind(k["id"])["art"]
    assert got["state"] == "failed" and "redraw" in got["err"]


def test_failed_drawing_leaves_previous_version_untouched_and_records_why():
    k = fridge.add_kind("柿子", "fruit")
    art.set_provider(_three)
    art.run(k["id"])
    before = art.art_path(k["id"], "fresh", 1).read_bytes()
    fridge.redraw_kind(k["id"])

    def boom(name, cat):
        raise RuntimeError("took too long")
    art.set_provider(boom)
    assert art.run(k["id"]) == "failed"
    got = fridge.kind(k["id"])["art"]
    assert got["state"] == "failed" and got["v"] == 1 and "took too long" in got["err"]
    assert art.art_path(k["id"], "fresh", 1).read_bytes() == before
    art.set_provider(lambda name, cat: {"fresh": b"not a png", "meh": _png(), "bad": _png()})
    fridge.redraw_kind(k["id"])
    assert art.run(k["id"]) == "failed" and "PNG" in fridge.kind(k["id"])["art"]["err"]


def test_art_is_off_by_default_and_new_kinds_are_text_cards():
    assert art.enabled() is False and art.start("u_x") is False and art.resume_pending() == 0
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    k = client.post("/api/fridge/kinds", json={"name": "柿子", "category": "fruit"}).json()["kind"]
    assert k["art"]["state"] == "none"
    assert client.post(f"/api/fridge/kinds/{k['id']}/redraw").status_code == 409
    assert client.get(f"/api/fridge/art/{k['id']}/fresh.png").status_code == 404


def test_rest_add_remove_redraw_and_art(monkeypatch, clock):
    client = TestClient(create_app(scheduler=False, with_mcp=False))
    art.set_provider(_three)
    started = []
    monkeypatch.setattr(art, "start", lambda kid: started.append(kid) or True)
    r = client.post("/api/fridge/kinds", json={"name": "柿子", "category": "fruit"})
    assert r.status_code == 200
    kid = r.json()["kind"]["id"]
    assert started == [kid] and r.json()["kind"]["art"]["state"] == "pending"
    assert client.post("/api/fridge/kinds", json={"name": "柿子", "category": "fruit"}).status_code == 409
    bad = client.post("/api/fridge/kinds", json={"name": "柿子 2", "category": "fruit"})
    assert bad.status_code == 400 and "不能有空格" in bad.json()["detail"]
    cat = client.get("/api/fridge/catalog").json()
    assert len(cat) == 34 and cat[-1]["id"] == kid and cat[-1]["custom"] is True
    assert client.get(f"/api/fridge/art/{kid}/fresh.png").status_code == 404
    assert art.run(kid) == "ready"
    img = client.get(f"/api/fridge/art/{kid}/fresh.png")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content.startswith(b"\x89PNG")
    assert client.get(f"/api/fridge/art/{kid}/fresh.png", params={"v": 1}).status_code == 200
    assert client.get(f"/api/fridge/art/{kid}/fresh.png", params={"v": 7}).status_code == 404
    assert client.get(f"/api/fridge/art/{kid}/rotten.png").status_code == 404
    assert client.get("/api/fridge/art/u_nope/fresh.png").status_code == 404
    assert client.post("/api/fridge/buy", json={"who": A, "items": [kid]}).status_code == 200
    ov = client.get("/api/fridge", params={"who": A}).json()
    assert ov["items"][0]["art"]["state"] == "ready" and ov["items"][0]["art"]["sizes"]["fresh"][0] > 0
    r = client.post(f"/api/fridge/kinds/{kid}/redraw")
    assert r.status_code == 200 and r.json()["kind"]["art"]["state"] == "pending" and started == [kid, kid]
    assert client.delete(f"/api/fridge/kinds/{kid}").json()["kind"]["removed"] is True
    assert client.delete(f"/api/fridge/kinds/{kid}").status_code == 404
    assert client.post(f"/api/fridge/kinds/{kid}/redraw").status_code == 404
    assert len(client.get("/api/fridge/catalog").json()) == 33
