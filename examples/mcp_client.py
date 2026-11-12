"""Connect to a running kitchenette with the official MCP client, list the tools,
open a pot and look at the kitchen.
用官方的 MCP 客户端连上一台正在跑的 kitchenette：列出工具、开一锅、看一眼厨房。

    kitchenette serve                      # in one terminal / 一个终端
    python examples/mcp_client.py          # in another / 另一个终端

Options / 可选参数: --url http://127.0.0.1:8765/mcp  --token <口令>  --who <角色名>

The fridge must hold an egg for the pot to open: buy one first on the page, or
冰箱里要有鸡蛋才能开这一锅：先在页面上买，或者

    curl -X POST localhost:8765/api/fridge/buy -H 'content-type: application/json' \
         -d '{"items": ["egg"]}'
"""
from __future__ import annotations

import argparse
import asyncio
import urllib.error
import urllib.request

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


def check_reachable(url: str, token: str) -> None:
    """Say plainly what is wrong before the MCP client gets to raise something unreadable."""
    base = url.rsplit("/mcp", 1)[0]
    req = urllib.request.Request(base + "/api/roles")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5):
            return
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit(
                ("The server refused the token." if token else "This server wants a token and none was given.")
                + " Pass the value of server.token with --token.\n"
                + ("口令不对。" if token else "这台服务要口令，而你没给。")
                + "请用 --token 带上设置里 server.token 的那个值。") from None
        raise SystemExit(f"The server answered {e.code} at {base}; is this a kitchenette?\n"
                         f"{base} 回了 {e.code}，这是 kitchenette 的地址吗？") from None
    except OSError:
        raise SystemExit(f"Nothing answers at {base}. Start the server first: kitchenette serve\n"
                         f"{base} 上没有服务在应答。请先启动：kitchenette serve") from None


async def main(url: str, token: str, who: str | None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(headers=headers, timeout=30) as http:
        async with Client(streamable_http_client(url, http_client=http)) as client:
            tools = await client.list_tools()
            print("tools:", ", ".join(t.name for t in tools.tools))
            extra = {"who": who} if who else {}
            cooked = await client.call_tool(
                "kitchen_cook", {"dish": "煎蛋", "minutes": 1, "ingredients": ["鸡蛋"], **extra})
            print("\nkitchen_cook ->", "(refused / 被拒)" if cooked.is_error else "")
            print(cooked.content[0].text)
            if cooked.structured_content:
                print("card:", cooked.structured_content["attachments"][0])
            status = await client.call_tool("kitchen_status", extra)
            print("\nkitchen_status ->")
            print(status.content[0].text)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8765/mcp")
    p.add_argument("--token", default="")
    p.add_argument("--who", default=None)
    a = p.parse_args()
    check_reachable(a.url, a.token)
    try:
        asyncio.run(main(a.url, a.token, a.who))
    except Exception as e:  # noqa: BLE001
        cause = e
        while isinstance(cause, BaseExceptionGroup) and cause.exceptions:
            cause = cause.exceptions[0]
        raise SystemExit(f"The MCP connection failed: {type(cause).__name__}: {cause}\n"
                         f"MCP 连接出错了：{type(cause).__name__}: {cause}") from None
