"""The tools a role uses, as plain functions.

Both the MCP server and the bracket-marker executor call :func:`call`, so a
tool behaves the same however it was reached. Every tool takes an optional
``who``; left out, the configured default role is used.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from . import config, fridge, kitchen, menu, notify, potion, roles, service, snacks, stamina
from .texts import t

log = logging.getLogger(__name__)

TOOL_COOK = kitchen.TOOL_COOK
TOOL_STATUS = kitchen.TOOL_STATUS
TOOL_CANCEL = kitchen.TOOL_CANCEL
TOOL_TOSS = kitchen.TOOL_TOSS
TOOL_BUY = "kitchen_buy"
TOOL_EAT = "eat"
TOOL_MENU = "read_menu"
TOOL_SNACK = "snack_eat"
TOOL_NOTES = "kitchen_notes"

NAMES = (TOOL_COOK, TOOL_STATUS, TOOL_CANCEL, TOOL_TOSS, TOOL_BUY, TOOL_EAT, TOOL_MENU, TOOL_SNACK, TOOL_NOTES)


@dataclass
class ToolResult:
    text: str
    is_error: bool = False
    attachments: list[dict] = field(default_factory=list)   # e.g. the cooking card of a new pot


def _who_schema() -> dict:
    return {"type": "string"}


def _snack_name_text() -> str:
    """The snack-name parameter, naming the flavours of whatever on the shelf comes in flavours."""
    flavours = "".join(t("tool_snack_name_flavour", name=s["name"], variants="/".join(v["name"] for v in s["variants"]))
                       for s in snacks.catalog() if s.get("variants"))
    return t("tool_snack_name", flavours=flavours)


def schemas() -> list[dict]:
    """JSON schemas of every tool: name, description, input_schema."""
    out = kitchen.tool_schemas() + [
        {"name": TOOL_BUY, "description": t("tool_buy", max=config.get().fridge_buy_max_items,
                                            cap=config.get().fridge_coupon_max),
         "input_schema": {"type": "object",
                          "properties": {"items": {"type": "array", "items": {"type": "string"},
                                                   "description": t("tool_buy_items")}},
                          "required": ["items"], "additionalProperties": False}},
        {"name": TOOL_EAT, "description": t("tool_eat"),
         "input_schema": {"type": "object",
                          "properties": {"meal": {"type": "string", "description": t("tool_eat_meal")},
                                         "note": {"type": "string", "description": t("tool_eat_note")}},
                          "required": ["meal"], "additionalProperties": False}},
        {"name": TOOL_MENU, "description": t("tool_menu"),
         "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": TOOL_SNACK, "description": t("tool_snack"),
         "input_schema": {"type": "object",
                          "properties": {"name": {"type": "string", "description": _snack_name_text()}},
                          "required": ["name"], "additionalProperties": False}},
        {"name": TOOL_NOTES, "description": t("tool_notes"),
         "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    ]
    for s in out:
        s["input_schema"]["properties"]["who"] = _who_schema()
    return out


def _buy(who: str, args: dict, key: str) -> ToolResult:
    items = args.get("items")
    text = " ".join(str(x) for x in items) if isinstance(items, list) else str(items or "")
    try:
        return ToolResult(fridge.buy_self(who, text, key=key))
    except fridge.FridgeError as fe:
        return ToolResult(fe.text, True)
    except Exception:  # noqa: BLE001
        log.warning("buying failed", exc_info=True)
        return ToolResult(t("buy_store_failed"), True)


def _toss(who: str, args: dict, key: str) -> ToolResult:
    what = str(args.get("what") or "")
    try:
        return ToolResult(kitchen.toss_wormed_dish(who, what, key=key) or fridge.toss_self(who, what, key=key))
    except fridge.FridgeError as fe:
        return ToolResult(fe.text, True)
    except Exception as e:  # noqa: BLE001
        log.warning("tossing failed", exc_info=True)
        return ToolResult(t("toss_store_failed", err=type(e).__name__), True)


def _eat(who: str, args: dict, key: str) -> ToolResult:
    try:
        return ToolResult(menu.eat(who, str(args.get("meal") or ""), str(args.get("note") or ""), key=key))
    except menu.EatRefused as e:
        return ToolResult(e.text, True)


def _snack(who: str, args: dict, key: str, told: bool) -> ToolResult:
    hit, why = snacks.resolve_name(str(args.get("name") or ""))
    if hit is None:
        return ToolResult(why, True)
    try:
        r = snacks.eat(who, hit[0], hit[1] or None, snacks.BY_SELF, rid=key, told=told)
    except Exception:  # noqa: BLE001
        log.warning("snack failed", exc_info=True)
        return ToolResult(t("snack_store_failed"), True)
    return ToolResult(snacks.receipt_text(r, who), not r["ok"])     # past the daily cap is a refusal too


def _notes(who: str) -> ToolResult:
    notes = notify.take(who)
    return ToolResult("\n".join(n["text"] for n in notes) if notes else t("notes_empty"))


def call(name: str, args: dict | None = None, who: str | None = None, *,
         key: str | None = None, told: bool = True) -> ToolResult:
    """Run one tool for a role.

    key: a stable id for this call; repeating a call with the same key does not buy, toss, eat or
    snack twice. told: the result is shown to the role right away (False when the caller can only
    deliver it later, which matters for the "you bit into a worm" follow-up).
    """
    args = dict(args or {})
    given = args.pop("who", None) or who
    try:
        who = roles.resolve(given)
    except ValueError:
        return ToolResult(t("role_bad", got=repr(given)), True)
    key = key or uuid.uuid4().hex[:16]
    service.serve_due(who)      # whatever came due is on the menu, with its note, before the role looks
    if name in (TOOL_COOK, TOOL_STATUS, TOOL_CANCEL):
        cards: list[dict] = []
        text, is_error = kitchen.local_tools(cards, who)[name](args)
        res = ToolResult(text, is_error, cards)
    elif name == TOOL_TOSS:
        res = _toss(who, args, key)
    elif name == TOOL_BUY:
        res = _buy(who, args, key)
    elif name == TOOL_EAT:
        res = _eat(who, args, key)
    elif name == TOOL_MENU:
        res = ToolResult(menu.read_menu(who))
    elif name == TOOL_SNACK:
        res = _snack(who, args, key, told)
    elif name == TOOL_NOTES:
        res = _notes(who)
    else:
        return ToolResult(f"unknown tool: {name}", True)
    if not res.is_error and config.get().stamina_auto_account and not potion.is_potion_call(name, args):
        stamina.settle_call(who, name)
    return res
