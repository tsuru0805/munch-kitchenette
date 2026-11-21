"""The seventeen things the upgrade added, one switch each — the single place that says what is on.

Each row: key, name, the one that must be on first (parent), the default, the markers it brings.
The switches live under ``[play]`` in the settings (``play_<key>``). A switch that is off means the
thing is not installed:

- its markers are not recognised (they stay in the reply as plain text);
- nothing the role reads teaches it, and the tool and tool arguments it adds are not offered;
- the page hides its entrance (``GET /api/features``);
- asking for it directly answers "this is off".

Turning one off never deletes anything; turning it back on finds everything where it was. A switch
whose parent is off counts as off, and says why.
"""
from __future__ import annotations

from . import config

FEATURES: tuple[dict, ...] = (
    {"key": "recipes_public", "name": "公共食谱", "parent": None, "default": True, "markers": ()},
    {"key": "recipes_today", "name": "今天可以试试", "parent": "recipes_public", "default": True, "markers": ()},
    {"key": "recipe_cook", "name": "照谱开锅", "parent": "recipes_public", "default": True, "markers": ()},
    {"key": "recipe_book", "name": "他的食谱本", "parent": None, "default": True, "markers": ("收藏", "记菜")},
    {"key": "proficiency", "name": "熟练度", "parent": None, "default": True, "markers": ()},
    {"key": "mishaps", "name": "小意外", "parent": "proficiency", "default": True, "markers": ()},
    {"key": "new_dish_bonus", "name": "新菜加成", "parent": "recipe_cook", "default": True, "markers": ()},
    {"key": "settle_card", "name": "结算卡", "parent": None, "default": True, "markers": ()},
    {"key": "dex", "name": "图鉴", "parent": None, "default": True, "markers": ()},
    {"key": "achievements", "name": "厨房成就", "parent": "dex", "default": True, "markers": ()},
    {"key": "tasting_notes", "name": "试菜札记", "parent": "recipe_book", "default": False, "markers": ("札记",)},
    {"key": "orders", "name": "点菜", "parent": "recipe_cook", "default": False, "markers": ("接单",)},
    {"key": "menus", "name": "一桌菜单", "parent": "recipe_book", "default": False, "markers": ("配一桌",)},
    {"key": "recipe_codes", "name": "食谱码", "parent": "recipe_book", "default": False, "markers": ("出码",)},
    {"key": "vendor", "name": "流动小贩", "parent": None, "default": False,
     "markers": ("问小贩", "买", "送花", "想要花")},
    {"key": "dishwash", "name": "刷盘子", "parent": None, "default": False, "markers": ("刷盘子",)},
    {"key": "seal_jars", "name": "窗台密封罐", "parent": None, "default": False, "markers": ("封罐",)},
)
KEYS = tuple(f["key"] for f in FEATURES)
_BY_KEY = {f["key"]: f for f in FEATURES}

# marker -> the feature it belongs to
MARKER_FEATURE: dict[str, str] = {m: f["key"] for f in FEATURES for m in f["markers"]}
MARKERS = tuple(MARKER_FEATURE)
# The existing [买菜] also takes "照 <id>" (buy what a recipe lacks); that belongs to recipe_cook.
BUY_RECIPE_FEATURE = "recipe_cook"


def wanted(key: str) -> bool:
    """This switch's own setting."""
    return bool(getattr(config.get(), f"play_{key}"))


def effective() -> dict[str, dict]:
    """{key: {on, wanted, reason}}; reason is empty when on, otherwise says why not."""
    out: dict[str, dict] = {}
    for f in FEATURES:                 # parents come before their children in the table
        k = f["key"]
        w = wanted(k)
        reason = ""
        if not w:
            reason = "off"
        elif f["parent"] and not out[f["parent"]]["on"]:
            reason = f"needs {f['parent']}"
        out[k] = {"on": not reason, "wanted": w, "reason": reason}
    return out


def on(key: str) -> bool:
    if key not in _BY_KEY:
        raise KeyError(key)
    return effective()[key]["on"]


def any_on(*keys: str) -> bool:
    eff = effective()
    return any(eff[k]["on"] for k in keys)


def marker_enabled(name: str) -> bool:
    """Is this marker recognised right now? [收藏] also needs the public recipes (it collects from them)."""
    k = MARKER_FEATURE.get(name)
    if k is None or not on(k):
        return False
    if name == "收藏":
        return on("recipes_public")
    return True


def enabled_markers() -> tuple[str, ...]:
    return tuple(m for m in MARKERS if marker_enabled(m))


def capabilities() -> dict:
    """What the page reads to show or hide each entrance."""
    eff = effective()
    return {"features": [{"key": f["key"], "name": f["name"], "parent": f["parent"], "default": f["default"],
                          "markers": list(f["markers"]), **eff[f["key"]]} for f in FEATURES]}


def startup_lines() -> list[str]:
    """One line per switch that was asked for but does not take effect, for the server log."""
    out = []
    for f in FEATURES:
        e = effective()[f["key"]]
        if e["wanted"] and not e["on"]:
            parent = _BY_KEY[f["parent"]]["name"] if f["parent"] else ""
            out.append(f"[play] {f['key']} is on but its parent [play] {f['parent']} is off, so it does nothing"
                       f" / 「{f['name']}」开着，但要先开着的「{parent}」关着，所以它不起作用")
    return out
