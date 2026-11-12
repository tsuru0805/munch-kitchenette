"""Bracket markers: letting the model act by writing a line in its reply.
方括号标签：让模型在回复里单独写一行来做事。

Some setups have no tool calling, or prefer the model to act in the flow of
its text. A reply may contain lines like

    [买菜 番茄 鸡蛋]      buy with one coupon
    [吃 番茄炒蛋]         eat
    [零食 拿铁]           a snack
    [扔掉 坏了的]         throw out what has spoiled

each alone on its line. Send the reply to POST /api/inline (or call
`kitchenette.inline.execute` directly, as below). You get back one receipt
per marker, and the reply with the marker lines removed for display. Hand the
receipts' `rendered` sentences to the model with its next turn.

Pass the same `message_id` when you process the same reply again: nothing is
bought or eaten twice.

    python examples/inline_markers.py        # runs against a throwaway database
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from kitchenette import config, fridge, inline

REPLY = """冰箱快空了，我去买点菜。
[买菜 番茄 鸡蛋]
顺便吃点零食垫一垫。
[零食 拿铁]
[吃 红烧肉]
"""

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        config.override(server_db_path=str(Path(tmp) / "demo.db"))
        fridge.grant_coupon_by_her("companion")          # one coupon to spend
        print("markers found:", [(a.marker, a.args) for a in inline.parse(REPLY)])
        print("\nshown to the human:\n" + inline.strip(REPLY))
        for receipt in inline.execute("companion", REPLY, message_id="reply-1"):
            print("ok " if receipt.ok else "NO ", receipt.rendered)
        again = inline.execute("companion", REPLY, message_id="reply-1")
        print("\nsame reply again ->", len(again), "receipts, coupons still:",
              fridge.overview("companion")["coupons"]["count"])
