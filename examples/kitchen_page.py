"""See the kitchen page, on a kitchen of its own.
看一眼厨房页，用的是它自己临时起的一间厨房。

    python examples/kitchen_page.py

It starts a throwaway server (a temporary database, a free port, the
fast-forward clock switched on), puts things in it first

    a stocked fridge (some of it past its best), two grocery coupons,
    a dish the companion cooked, two dishes and a potion on the menu,
    a meal eaten today, a few notes on the cork board, a second role

and prints the address of the page. Open it in a browser. Because the
fast-forward clock is on, the page shows a very small "过一小时 / 过一天" in
its corner: press it and watch food go off and leftovers grow worms.
Ctrl-C stops the server and deletes the database. Your own kitchenette.db
and any server you have running are never touched.

它会自己起一个用完就扔的服务（临时的库、空闲的端口、开着快进钟），先往里放好东西：
一冰箱食材（有些已经不太新鲜）、两张买菜券、伙伴自己做好的一道菜、菜单上挂着的两道菜
和一瓶药剂、今天吃过的一顿、软木板上的几张纸条、第二个角色；然后打印页面地址，用浏览器
打开就行。因为开着快进钟，页面角上会有一个很小的「过一小时 / 过一天」，点它就能看到
食材变坏、剩菜长虫。按 Ctrl-C 停掉服务并删掉临时库。你自己的 kitchenette.db 和正在跑的
服务不会被碰到。

Options / 选项:
    --port N      use this port instead of a free one / 指定端口（默认找一个空闲的）
    --token T     make the server ask for this token, to see the page's token step
                  让服务要口令，用来看页面问口令的那一步
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import tempfile

WHO = "小满"          # any name is a role; these two are only for the demo
OTHER = "阿树"
HOUR = 3600.0


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stock(port: int, token: str, tmp: str) -> None:
    """Settings for this run only, then a kitchen with something in every corner."""
    for name in [n for n in os.environ if n.startswith("KITCHENETTE_")]:
        del os.environ[name]            # no setting of yours leaks into the demo
    os.chdir(tmp)                       # and no kitchenette.toml of yours is read
    from kitchenette import clock, config, fridge, menu, potion, service, tools

    config.load()
    config.override(server_port=port, server_token=token, server_dev_clock=True, roles_default=WHO,
                    server_db_path=os.path.join(tmp, "kitchen-page.db"), art_dir=os.path.join(tmp, "art"))

    def role(tool: str, **args) -> None:
        res = tools.call(tool, args, WHO)
        if res.is_error:
            raise SystemExit(f"stocking the demo kitchen failed at {tool}: {res.text}")

    # The stocking spans two days. The clock starts that far back and is walked forward to the
    # present, so the kitchen's "now" is the real now once the page opens.
    clock.advance(-(30 + 1 + 17 + 0.5) * HOUR)
    # two days ago: a first round of groceries (by now past its best)
    fridge.buy_her(WHO, ["spinach", "tomato", "egg", "milk", "strawberry"])
    service.fast_forward(30 * HOUR)
    # yesterday: the companion earns nothing here, so the human hands out coupons; it buys with one and cooks
    fridge.grant_coupon_by_her(WHO)
    role("kitchen_buy", items=["胡萝卜", "牛肉", "洋葱"])
    role("kitchen_cook", dish="番茄炒蛋", minutes=10, ingredients=["番茄", "鸡蛋"], method="stirfry")
    service.fast_forward(1 * HOUR)      # served, and on the menu
    role("eat", meal="番茄炒蛋")
    service.fast_forward(17 * HOUR)
    # today
    fridge.buy_her(WHO, ["tofu", "cucumber", "salmon", "apple", "udon", "lettuce"])
    role("kitchen_cook", dish="味噌汤", minutes=15, ingredients=["豆腐"], method="boil", note="多放葱")
    service.fast_forward(0.5 * HOUR)
    role("snack_eat", name="布丁")
    menu.add("葱油拌面", "human", WHO, "面煮软一点")
    menu.add("冰镇酸梅汤", "human", WHO, "饭后喝")
    potion.hang(WHO, 30, "困了就喝")
    menu.feed(menu.add("鸡蛋三明治", "human", WHO)["id"])
    fridge.grant_coupon_by_her(WHO)
    fridge.grant_coupon_by_her(WHO)
    # a second role, so the page has someone to switch to
    fridge.buy_her(OTHER, ["egg", "noodles"])
    menu.add("阳春面", "human", OTHER)


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the kitchen page on a throwaway kitchen.")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    port = args.port or free_port()
    with tempfile.TemporaryDirectory(prefix="kitchenette-page-") as tmp:
        stock(port, args.token, tmp)
        import uvicorn

        from kitchenette.api import PAGE_DIR, create_app
        if not (PAGE_DIR / "index.html").is_file():
            print("This install has no kitchen page; build it first (docs/PAGE.md).\n"
                  "这份安装里没有厨房页，请先构建（见 docs/PAGE.md）。", file=sys.stderr)
            return 1
        url = f"http://127.0.0.1:{port}/page/"
        print(f"\n  the kitchen page / 厨房页:  {url}")
        if args.token:
            print(f"  token / 口令:  {args.token}")
        print("  Ctrl-C to stop / 按 Ctrl-C 停止\n", flush=True)
        try:
            uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
