#!/usr/bin/env python3
"""Writes src/kitchen/__fixtures__/server_contract.json: what the server's own code answers, for the
page's tests to read. Run it again whenever a field of an answer changes; the tests then go red first.

Needs the kitchenette package importable (pip install -e . from the repository root).
Usage: python3 web/page/scripts/contract_fixture.py
"""
import json
import os
import tempfile

from fastapi.testclient import TestClient

from kitchenette import api, config, fridge, menu, potion

WHO = "aster"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "kitchen", "__fixtures__", "server_contract.json")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        s = config.Settings()
        s.server_db_path = os.path.join(tmp, "contract.db")
        s.server_timezone = "Asia/Tokyo"
        s.art_dir = os.path.join(tmp, "art")
        from kitchenette import play
        defaults = {k: getattr(s, f"play_{k}") for k in play.KEYS}
        for k in play.KEYS:                  # the answers from before the upgrade: every switch off
            setattr(s, f"play_{k}", False)
        config.use(s)
        c = TestClient(api.create_app(scheduler=False, with_mcp=False))
        get = lambda path, **params: c.get(path, params=params).json()   # noqa: E731

        fridge.buy_her(WHO, ["spinach", "egg", "udon"])
        fridge.grant_coupon_by_her(WHO)
        fridge.make_dizzy(WHO, "坏汤")
        out = {"fridge": get("/api/fridge", who=WHO), "catalog": get("/api/fridge/catalog")}

        from kitchenette import service, tools
        tools.call("kitchen_cook", {"dish": "煎蛋", "minutes": 5, "ingredients": ["鸡蛋"], "method": "fry"}, WHO)
        service.fast_forward(600)
        out["kitchen"] = get("/api/kitchen", who=WHO)

        menu.feed(menu.add("茄汁滑蛋", "human", WHO)["id"])
        out["meals"] = get("/api/meals", who=WHO)
        hung = potion.hang(WHO, 30, "困了就喝")
        out["potions"] = get("/api/potions", who=WHO)
        out["potion_row_note"] = hung["row"]["note"]
        out["snacks"] = get("/api/snacks", who=WHO)
        out["about"] = get("/api/about")

        c.post("/api/fridge/kinds", json={"name": "柿子", "category": "fruit"})
        fridge.buy_her(WHO, [k["id"] for k in fridge.kinds() if k["name"] == "柿子"])
        out["catalog_kinds"] = get("/api/fridge/catalog")
        out["fridge_kinds"] = get("/api/fridge", who=WHO)

        config.override(stamina_enabled=False, satiety_enabled=False, server_dev_clock=True)
        out["about_off"] = get("/api/about")
        out["fridge_off"] = get("/api/fridge", who=WHO)
        out["potions_off"] = get("/api/potions", who=WHO)
        out["snacks_off"] = get("/api/snacks", who=WHO)

        # The upgrade: every switch on (vendors, plates and jars too), one of each thing to read
        import random

        from kitchenette import vendor
        config.override(stamina_enabled=True, satiety_enabled=True, **{f"play_{k}": True for k in play.KEYS})
        out["features"] = get("/api/features")
        c.post("/api/orders", json={"who": WHO, "recipe": "hc-e0a19bc9"})
        from kitchenette import inline
        fridge.buy_her(WHO, ["egg", "apple"])
        inline.execute(WHO, "[收藏 蒸水蛋]\n[记菜 拌黄瓜 黄瓜 拌 5 | 夏天吃]\n[封罐 苹果 冰糖 | 给冬天]", "m1")
        tools.call("kitchen_cook", {"dish": "蒸水蛋", "minutes": 5, "ingredients": ["鸡蛋"], "recipe": "hc-e0a19bc9"}, WHO)
        service.fast_forward(600)
        menu.eat(WHO, "蒸水蛋")
        out["recipes"] = get("/api/recipes", who=WHO, q="鸡蛋", limit=3)
        out["book"] = get("/api/book", who=WHO)
        out["orders"] = get("/api/orders", who=WHO)
        out["dex"] = get("/api/dex", who=WHO)
        out["dishes"] = get("/api/dishes", who=WHO)
        out["jars"] = get("/api/jars", who=WHO)
        conn = __import__("kitchenette.db", fromlist=["x"]).connect()
        now = __import__("kitchenette.clock", fromlist=["x"]).now()
        conn.execute("INSERT INTO vendor_visits (id, day, slot, vendor, arrive_at, leave_at, goods_json, created_at)"
                     " VALUES (?,?,?,?,?,?,?,?)", ("v1", vendor.kitchen_day(now), 0, "tanghulu", now, now + 3000,
                                                   json.dumps(vendor.stock_goods(conn, "tanghulu", now, random.Random(1)),
                                                              ensure_ascii=False), now))
        conn.commit()
        conn.close()
        out["vendor"] = get("/api/vendor", who=WHO)
        out["about_play"] = get("/api/about")
        config.override(**{f"play_{k}": v for k, v in defaults.items()})
        out["features_default"] = get("/api/features")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("written", os.path.relpath(OUT))


if __name__ == "__main__":
    main()
