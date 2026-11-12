"""The whole chain in one command, on a kitchen of its own.
一条命令看完整条链，用的是它自己临时起的一间厨房。

    python examples/walkthrough.py

It starts a throwaway server (a temporary database, a free port, the
fast-forward clock switched on), walks through

    buy -> cook -> wait -> served, on the menu, a note waiting -> eat ->
    stamina and satiety move -> food goes bad -> leftovers grow worms -> toss

printing every sentence the model would read, refusals included, and then
shuts the server down and deletes the database. Your own kitchenette.db and
any server you have running are never touched.

它会自己起一个用完就扔的服务（临时的库、空闲的端口、开着快进钟），走一遍
买菜 → 开锅 → 等 → 出锅、上菜单、留一句话 → 吃 → 体力和饱食度变化 → 放坏 →
剩菜长虫 → 扔，把模型会读到的每句话（包括被拒绝的）都打印出来，然后关掉服务、
删掉临时库。你自己的 kitchenette.db 和正在跑的服务不会被碰到。

What the role does goes through MCP, exactly as a model would call it. What
the human does (handing out a coupon, buying groceries) and the clock go
through REST.

--base URL runs it against a server you started yourself instead. That server
must have the fast-forward clock on, and the clock is the whole server's:
every role in that database jumps days ahead. Never point it at a kitchen in
use.
加 --base 网址 可以改成对着你自己起的服务跑。那台服务必须开着快进钟，而快进钟拨的是
整台服务的钟：那个库里所有角色都会一起跳过好几天。别对着正在用的厨房跑。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

WHO = "walkthrough"


def rest(base: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(base + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("detail")
        except ValueError:
            detail = None
        return {"error": e.code, "detail": detail}


def start_own_server(tmp: str) -> tuple[subprocess.Popen, str]:
    """A server for this run only: its own database in tmp, a free port, the dev clock on.
    It is started from tmp, so no kitchenette.toml of yours is read."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("KITCHENETTE_")}
    env.update(KITCHENETTE_SERVER_PORT=str(port), KITCHENETTE_SERVER_DB_PATH=os.path.join(tmp, "walkthrough.db"),
               KITCHENETTE_SERVER_DEV_CLOCK="1", KITCHENETTE_ART_DIR=os.path.join(tmp, "art"))
    proc = subprocess.Popen([sys.executable, "-m", "kitchenette", "serve"], cwd=tmp, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit("could not start the server / 服务没起来")
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=1):
                return proc, base
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise SystemExit("the server did not answer in time / 服务迟迟没有应答")


def check_before_touching_anything(base: str, token: str) -> None:
    """Refuse to start unless the server answers, takes the token and has the dev clock on.
    Nothing has been changed on the server when this stops the run."""
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=5):
            pass
    except OSError:
        raise SystemExit(f"no server answers at {base}\n{base} 上没有服务在应答") from None
    probe = rest(base, token, "POST", "/api/dev/clock", {"advance_seconds": 0})
    if probe.get("error") == 401:
        raise SystemExit("the server wants a token: pass --token\n这台服务要口令：请加 --token")
    if "error" in probe:
        raise SystemExit("the fast-forward clock is off on that server, so nothing was done.\n"
                         "Start it with KITCHENETTE_SERVER_DEV_CLOCK=1, or run this without --base.\n"
                         "那台服务没开快进钟，所以什么都没做。\n"
                         "请用 KITCHENETTE_SERVER_DEV_CLOCK=1 启动它，或者不加 --base 直接跑。")


async def walk(base: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(headers=headers, timeout=30) as http:
        async with Client(streamable_http_client(f"{base}/mcp", http_client=http)) as mcp:

            async def role(tool: str, **args) -> str:
                res = await mcp.call_tool(tool, {**args, "who": WHO})
                text = res.content[0].text
                print(("   refused 被拒: " if res.is_error else "   ") + text.replace("\n", "\n   "))
                return text

            def human(method: str, path: str, **body) -> dict:
                got = rest(base, token, method, path, {"who": WHO, **body})
                print("   (human 人)", got.get("text") or got)
                return got

            def forward(hours: float) -> None:
                rest(base, token, "POST", "/api/dev/clock", {"advance_seconds": hours * 3600})
                print(f"   ... {hours:g} hours later / {hours:g} 小时后")

            def step(en: str, zh: str) -> None:
                print(f"\n== {en}\n== {zh}")

            step("no coupon yet: buying is refused", "还没有券：买菜被拒")
            await role("kitchen_buy", items=["番茄"])

            step("the human hands out a coupon and buys eggs and spinach", "人发了一张券，又直接买了鸡蛋和菠菜")
            human("POST", "/api/fridge/coupon")
            human("POST", "/api/fridge/buy", items=["egg", "spinach"])

            step("the role spends its coupon; an unknown name is refused", "他用券买菜；不认得的名字被拒")
            await role("kitchen_buy", items=["龙虾"])
            await role("kitchen_buy", items=["番茄", "苹果"])

            step("cooking takes what is in the fridge; what is missing is named", "开锅要用冰箱里的食材；缺什么会说清楚")
            await role("kitchen_cook", dish="土豆炖牛肉", minutes=30, ingredients=["土豆", "牛肉"])
            await role("kitchen_cook", dish="番茄炒蛋", minutes=10, ingredients=["番茄", "鸡蛋×2"])

            step("it cannot be eaten while it is still on the fire, nor can what was never cooked",
                 "还在火上的吃不到，没做过的也吃不到")
            await role("eat", meal="番茄炒蛋")
            await role("eat", meal="红烧肉")

            step("ten minutes later: served, on the menu, and a note is waiting", "十分钟后：出锅了，挂上了菜单，有一句话在等他")
            forward(0.2)
            await role("kitchen_notes")
            menu = await mcp.call_tool("read_menu", {"who": WHO})
            print("   " + menu.content[0].text.split("\n\n")[0].replace("\n", "\n   "))

            step("eat it: satiety and stamina move", "吃掉它：饱食度和体力都变了")
            before = rest(base, token, "GET", f"/api/stamina?who={WHO}")["energy"]
            await role("eat", meal="番茄炒蛋")
            after = rest(base, token, "GET", f"/api/stamina?who={WHO}")["energy"]
            print(f"   stamina 体力 {before} -> {after}")

            step("cook again, then leave it on the table for a day and a half", "再做一道，然后在桌上放一天半")
            await role("kitchen_cook", dish="煎蛋", minutes=5, ingredients=["鸡蛋"])
            forward(36)
            await role("kitchen_status")

            step("three more days: the spinach is long gone bad", "再过三天：菠菜早就坏了")
            forward(72)
            await role("kitchen_status")

            step("throw out the wormy dish and whatever has spoiled; the dish is gone from the menu at once",
                 "把长虫的菜和坏掉的东西扔掉；那道菜当场从菜单上消失")
            await role("kitchen_toss", what="煎蛋")
            await role("kitchen_toss", what="坏了的")
            await role("eat", meal="煎蛋")

            step("the worm crawled into one of the snacks", "虫子钻进了某一样零食里")
            for name in ("布丁", "果冻", "黑巧克力", "曲奇"):
                await role("snack_eat", name=name)


def main() -> int:
    p = argparse.ArgumentParser(description="Walk the whole chain on a throwaway kitchen.")
    p.add_argument("--base", default="", help="use this server instead of starting one (its clock will jump)")
    p.add_argument("--token", default="")
    a = p.parse_args()
    if a.base:
        check_before_touching_anything(a.base.rstrip("/"), a.token)
        asyncio.run(walk(a.base.rstrip("/"), a.token))
        return 0
    with tempfile.TemporaryDirectory(prefix="kitchenette-walkthrough-") as tmp:
        proc, base = start_own_server(tmp)
        try:
            print(f"a kitchen of its own at {base} (database in {tmp})\n自己起了一间厨房：{base}（库在 {tmp}）")
            asyncio.run(walk(base, ""))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("\ndone; the throwaway kitchen is gone.\n走完了，临时厨房已经收掉。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
