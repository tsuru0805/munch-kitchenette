"""The kitchen page: the built web app under /page/, and the read-only endpoints it leans on."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kitchenette import api, config, fridge, menu, potion, snacks

from conftest import A, B, DAY

HOST = "https://chat.example.com"


def _client() -> TestClient:
    return TestClient(api.create_app(scheduler=False, with_mcp=False))


@pytest.fixture()
def built(tmp_path, monkeypatch):
    """A stand-in for the built page, so these tests do not depend on a build being present."""
    page = tmp_path / "page"
    (page / "_expo" / "static" / "js" / "web").mkdir(parents=True)
    (page / "fonts").mkdir()
    (page / "index.html").write_text("<!doctype html><title>Kitchenette</title>", encoding="utf-8")
    (page / "_expo" / "static" / "js" / "web" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    (page / "fonts" / "a.woff2").write_bytes(b"wOF2")
    (page / "assets").mkdir()
    (page / "assets" / "base_day.abc.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    (tmp_path / "secret.txt").write_text("not part of the page", encoding="utf-8")
    monkeypatch.setattr(api, "PAGE_DIR", page)
    return page


# ── /page/ ──────────────────────────────────────────────────────────────

def test_the_page_is_served_without_a_token_even_when_the_api_wants_one(built):
    config.override(server_token="s3cret")
    c = _client()
    r = c.get("/page/")
    assert r.status_code == 200 and "Kitchenette" in r.text
    assert r.headers["content-type"].startswith("text/html")
    assert c.get("/api/about").status_code == 401            # the data behind it still needs the token
    assert c.get("/api/about", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_page_without_the_slash_goes_to_the_page(built):
    r = _client().get("/page", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/page/"


def test_files_of_the_page_and_how_long_they_may_be_kept(built):
    c = _client()
    js = c.get("/page/_expo/static/js/web/index-abc.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "immutable" in js.headers["cache-control"]          # its name carries a hash of its content
    assert c.get("/page/index.html").headers["cache-control"] == "no-cache"
    assert c.get("/page/fonts/a.woff2").headers["content-type"] == "font/woff2"
    assert c.get("/page/assets/base_day.abc.webp").headers["content-type"] == "image/webp"   # whatever the system's table says
    assert c.get("/page/index.html").headers["x-content-type-options"] == "nosniff"


def test_nothing_outside_the_page_folder_is_served(built):
    c = _client()
    assert c.get("/page/nope.js").status_code == 404
    assert c.get("/page/..%2Fsecret.txt").status_code == 404
    assert c.get("/page/%2e%2e/secret.txt").status_code == 404
    assert c.get("/page/fonts").status_code == 404              # a folder is not a file


def test_only_listed_sites_may_frame_the_page(built):
    c = _client()
    assert c.get("/page/").headers["content-security-policy"] == "frame-ancestors 'self'"
    config.override(server_embed_origins=[HOST + "/", "https://app.example.org:8443", "not an origin", "https://x.example/path"])
    assert _client().get("/page/").headers["content-security-policy"] == (
        f"frame-ancestors 'self' {HOST} https://app.example.org:8443")


def test_an_install_without_the_build_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PAGE_DIR", tmp_path / "no-page-here")
    r = _client().get("/page/")
    assert r.status_code == 404 and "docs/PAGE.md" in r.json()["detail"]


def test_embed_origins_must_be_a_list_of_text():
    with pytest.raises(config.ConfigError):
        config.override(server_embed_origins=[1])
    config.override(server_embed_origins=[])


# ── GET /api/about ──────────────────────────────────────────────────────

def test_about_lists_roles_and_what_is_switched_on(clock):
    fridge.buy_her(B, ["egg"])                                  # a role exists once it has left a trace
    r = _client().get("/api/about").json()
    assert r["roles"] == {"default": "companion", "list": ["birch", "companion"]}
    assert r["switches"] == {"stamina": True, "satiety": True, "worms": True, "dev_clock": False, "art": False}
    assert r["timezone"] == "Asia/Tokyo" and r["now"] == clock["now"]
    assert r["limits"] == {"coupon_max": 3, "buy_max_items": 5, "hungry_below": 30.0}
    assert r["words"]["human_name"] == "用户"


def test_about_follows_the_settings(clock):
    config.override(stamina_enabled=False, satiety_enabled=False, server_dev_clock=True,
                    roles_default=A, roles_allowed=[A, B], fridge_buy_max_items=3)
    r = _client().get("/api/about").json()
    assert r["roles"] == {"default": A, "list": [A, B]}
    assert r["switches"]["stamina"] is False and r["switches"]["satiety"] is False
    assert r["switches"]["dev_clock"] is True
    assert r["limits"]["buy_max_items"] == 3


# ── GET /api/meals ──────────────────────────────────────────────────────

def test_meals_today_are_the_dishes_eaten_since_midnight(clock):
    c = _client()
    row = menu.add("昨天的面", "human", A)
    menu.feed(row["id"])
    clock["now"] += DAY                                         # T0 is 17:00, so this is 17:00 the next day
    assert c.get("/api/meals", params={"who": A}).json()["meals"] == []
    menu.feed(menu.add("茄汁滑蛋", "human", A)["id"])
    clock["now"] += 3600
    with pytest.raises(menu.EatRefused):
        menu.eat(A, "茄汁滑蛋")                                   # no longer on the table: refused, and not a meal
    got = c.get("/api/meals", params={"who": A}).json()
    assert [m["meal"] for m in got["meals"]] == ["茄汁滑蛋"]
    assert got["meals"][0]["at"] == clock["now"] - 3600 and got["who"] == A
    assert got["since"] == clock["now"] - 18 * 3600             # midnight in Asia/Tokyo
    assert c.get("/api/meals", params={"who": B}).json()["meals"] == []
    both = c.get("/api/meals", params={"who": A, "since": 0}).json()["meals"]
    assert [m["meal"] for m in both] == ["昨天的面", "茄汁滑蛋"]


def test_snacks_and_potions_are_not_meals(clock):
    snacks.eat(A, "pudding", None, snacks.BY_HER)
    potion.feed(A, potion.hang(A, 20)["row"]["id"])
    assert _client().get("/api/meals", params={"who": A}).json()["meals"] == []


# ── feeding from the page ───────────────────────────────────────────────

def test_feeding_a_dish_says_whether_the_role_was_told(clock):
    c = _client()
    r = c.post(f"/api/menu/{menu.add('味噌汤', 'human', A)['id']}/feed").json()
    assert r["ok"] is True and r["notified"] is True
    config.override(notify_mode="none")
    r = _client().post(f"/api/menu/{menu.add('冷面', 'human', A)['id']}/feed").json()
    assert r["ok"] is True and r["notified"] is False
