"""The MCP face, driven by the official client: once in-process, once over real HTTP."""
from __future__ import annotations

import asyncio
import socket
import threading
import time

import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from kitchenette import config, fridge, mcp_server, tools
from kitchenette.api import create_app

from conftest import A, B

NAMES = {"kitchen_cook", "kitchen_status", "kitchen_cancel", "kitchen_toss",
         "kitchen_buy", "eat", "read_menu", "snack_eat", "kitchen_notes"}


def _text(result) -> str:
    return result.content[0].text


async def _walk(client: Client, who: str | None) -> dict:
    extra = {"who": who} if who else {}
    listed = (await client.list_tools()).tools
    cooked = await client.call_tool("kitchen_cook", {"dish": "煎蛋", "minutes": 5, "ingredients": ["鸡蛋"], **extra})
    status = await client.call_tool("kitchen_status", extra)
    bad = await client.call_tool("kitchen_cook", {"dish": "汤", "minutes": 99999, "ingredients": ["鸡蛋"], **extra})
    return {"listed": listed, "cooked": cooked, "status": status, "bad": bad}


def test_in_process_client_lists_tools_and_cooks():
    fridge.buy_her(config.get().roles_default, ["egg"])

    async def main():
        async with Client(mcp_server.build()) as client:
            return await _walk(client, None)

    got = asyncio.run(main())
    assert {t.name for t in got["listed"]} == NAMES
    cook = next(t for t in got["listed"] if t.name == "kitchen_cook")
    assert cook.input_schema == next(s for s in tools.schemas() if s["name"] == "kitchen_cook")["input_schema"]
    assert cook.input_schema["required"] == ["dish", "minutes", "ingredients"]
    assert not got["cooked"].is_error and "『煎蛋』下锅了" in _text(got["cooked"])
    assert got["cooked"].structured_content["attachments"][0]["kind"] == "kitchen_cooking"
    assert "火上 1 锅" in _text(got["status"]) and "煎蛋" in _text(got["status"])
    # a wrong argument is answered in the kitchen's own words
    assert got["bad"].is_error and _text(got["bad"]) == "没开成:minutes 要在 1–1440 之间,收到的是 99999。"


@pytest.fixture()
def live_server():
    """The real app on a real port, in a background thread."""
    config.override(server_token="s3cret")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(scheduler=False), host="127.0.0.1", port=port,
                                           log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_real_http_client_with_bearer_token_and_two_roles(live_server):
    fridge.buy_her(A, ["egg"])

    async def main():
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer s3cret"}, timeout=30) as http:
            async with Client(streamable_http_client(f"{live_server}/mcp", http_client=http)) as client:
                got = await _walk(client, A)
                got["other"] = await client.call_tool("kitchen_status", {"who": B})
                return got

    got = asyncio.run(main())
    assert {t.name for t in got["listed"]} == NAMES
    assert not got["cooked"].is_error and "『煎蛋』下锅了" in _text(got["cooked"])
    assert "火上 1 锅" in _text(got["status"])
    assert _text(got["other"]).splitlines()[0] == "火上没有锅。"       # the other role sees none of it


def test_real_http_without_the_token_is_refused(live_server):
    with httpx2.Client() as http:
        assert http.get(f"{live_server}/api/health").status_code == 200
        assert http.get(f"{live_server}/api/fridge").status_code == 401
        assert http.post(f"{live_server}/mcp", json={}).status_code == 401
        ok = http.get(f"{live_server}/api/fridge", headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200
