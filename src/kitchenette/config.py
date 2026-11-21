"""Every tunable number and table lives here.

Settings come from three layers, later ones winning:

1. the defaults in :class:`Settings` below;
2. a TOML file (``kitchenette.toml`` in the working directory, or the path in
   ``KITCHENETTE_CONFIG``), where ``[section] key = value`` maps to the
   attribute ``section_key``;
3. environment variables named ``KITCHENETTE_<SECTION>_<KEY>``. Scalars are
   parsed by the type of the default; tables and lists are given as JSON.

Rules read the active settings at call time through :func:`get`, so a value
changed in a test or reloaded from disk takes effect immediately.
"""
from __future__ import annotations

import copy
import difflib
import json
import os
import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ENV_PREFIX = "KITCHENETTE_"
DEFAULT_CONFIG_FILE = "kitchenette.toml"

# Ingredient catalog. `category` decides the default shelf life (see
# `fridge_category_days`); an explicit `shelf_days` overrides it. `pack_qty`
# is how many pieces one purchase adds. The id doubles as the artwork key on
# the kitchen page.
DEFAULT_INGREDIENTS: tuple[dict, ...] = (
    {"id": "tomato", "name": "番茄", "category": "veg", "pack_qty": 3, "aliases": ["西红柿"]},
    {"id": "cucumber", "name": "黄瓜", "category": "veg", "pack_qty": 2},
    {"id": "spinach", "name": "菠菜", "category": "leafy", "pack_qty": 1},
    {"id": "shungiku", "name": "茼蒿", "category": "leafy", "pack_qty": 1},
    {"id": "scallion", "name": "小葱", "category": "leafy", "pack_qty": 1,
     "aliases": ["葱", "葱花", "香葱", "大葱"]},
    {"id": "lettuce", "name": "生菜", "category": "leafy", "pack_qty": 1},
    {"id": "carrot", "name": "胡萝卜", "category": "root", "pack_qty": 2},
    {"id": "potato", "name": "土豆", "category": "root", "pack_qty": 2, "aliases": ["马铃薯"]},
    {"id": "onion", "name": "洋葱", "category": "root", "pack_qty": 2},
    {"id": "pepper", "name": "青椒", "category": "veg", "pack_qty": 2, "aliases": ["甜椒", "彩椒"]},
    {"id": "eggplant", "name": "茄子", "category": "veg", "pack_qty": 2},
    {"id": "mushroom", "name": "蘑菇", "category": "veg", "pack_qty": 1, "aliases": ["香菇", "口蘑"]},
    {"id": "cabbage", "name": "白菜", "category": "veg", "pack_qty": 1, "aliases": ["大白菜"]},
    {"id": "egg", "name": "鸡蛋", "category": "dairy", "pack_qty": 6, "aliases": ["蛋"]},
    {"id": "milk", "name": "牛奶", "category": "dairy", "pack_qty": 1},
    {"id": "tofu", "name": "豆腐", "category": "dairy", "pack_qty": 1},
    {"id": "butter", "name": "黄油", "category": "dairy", "pack_qty": 1},
    {"id": "cheese", "name": "奶酪", "category": "dairy", "pack_qty": 1, "aliases": ["芝士"]},
    {"id": "beef", "name": "牛肉", "category": "meat", "pack_qty": 1, "aliases": ["牛腩", "肥牛"]},
    {"id": "pork", "name": "猪肉", "category": "meat", "pack_qty": 1,
     "aliases": ["五花肉", "肉末", "猪肉末"]},
    {"id": "chicken", "name": "鸡腿", "category": "meat", "pack_qty": 1, "aliases": ["鸡肉", "鸡腿肉"]},
    {"id": "shrimp", "name": "虾", "category": "meat", "pack_qty": 1, "aliases": ["虾仁", "大虾"]},
    {"id": "salmon", "name": "三文鱼", "category": "meat", "pack_qty": 1, "aliases": ["鲑鱼"]},
    {"id": "udon", "name": "乌冬面", "category": "staple_food", "pack_qty": 1, "aliases": ["乌冬"]},
    {"id": "strawberry", "name": "草莓", "category": "fruit", "pack_qty": 1, "shelf_days": 3},
    {"id": "apple", "name": "苹果", "category": "fruit", "pack_qty": 2},
    {"id": "lemon", "name": "柠檬", "category": "fruit", "pack_qty": 1},
    {"id": "noodles", "name": "面条", "category": "staple_food", "pack_qty": 1, "aliases": ["挂面", "拉面"]},
    {"id": "miso", "name": "味噌", "category": "dairy", "pack_qty": 1, "shelf_days": 30,
     "aliases": ["味增", "味噌酱"]},
    {"id": "daikon", "name": "白萝卜", "category": "root", "pack_qty": 1, "aliases": ["萝卜", "大根"]},
    {"id": "broccoli", "name": "西蓝花", "category": "veg", "pack_qty": 1, "aliases": ["西兰花", "青花菜"]},
    {"id": "beansprout", "name": "豆芽", "category": "veg", "pack_qty": 1, "shelf_days": 2,
     "aliases": ["绿豆芽", "黄豆芽", "豆芽菜"]},
    {"id": "pork_slice", "name": "猪肉薄切", "category": "meat", "pack_qty": 1,
     "aliases": ["猪肉片", "薄切猪肉", "猪肉薄片"]},
)

# Snack shelf. `gain` is the stamina one serving restores (0-1 scale);
# `default_cap` is servings per day. A snack with `variants` must be eaten by
# variant, and all variants share the one daily cap.
DEFAULT_SNACKS: tuple[dict, ...] = (
    {"id": "coffee", "name": "咖啡", "tier": "mid", "default_cap": 3,
     "variants": [
         {"id": "espresso", "name": "浓缩", "gain": 0.08},
         {"id": "americano", "name": "美式", "gain": 0.06},
         {"id": "latte", "name": "拿铁", "gain": 0.05},
         {"id": "mocha", "name": "摩卡", "gain": 0.04},
     ]},
    {"id": "jelly", "name": "即时元气果冻", "tier": "high", "gain": 0.15, "default_cap": 2,
     "aliases": ["元气果冻", "果冻"]},
    {"id": "pudding", "name": "布丁", "tier": "low", "gain": 0.04, "default_cap": 3},
    {"id": "chocolate", "name": "黑巧克力", "tier": "low", "gain": 0.03, "default_cap": 4,
     "aliases": ["巧克力", "黑巧"]},
    {"id": "cookie", "name": "曲奇", "tier": "low", "gain": 0.02, "default_cap": 5,
     "aliases": ["曲奇饼干", "饼干"]},
)

# Stamina equilibrium for each local hour 0-23 (0-1 scale). Stamina drifts
# toward the current hour's value. This default is a night-owl day: awake
# until 02:00, recovering 02:00-08:00. See examples/schedules/ for others.
EARLY_BIRD_SCHEDULE: tuple[float, ...] = (
    0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95,
    0.95, 0.95,
    0.90, 0.85, 0.85, 0.85, 0.85,
    0.75, 0.75, 0.75, 0.75,
    0.70, 0.70, 0.70,
    0.60, 0.55, 0.55,
)

DEFAULT_SCHEDULE: tuple[float, ...] = (
    0.60, 0.55,
    0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95,
    0.90, 0.85, 0.85, 0.85, 0.85,
    0.75, 0.75, 0.75, 0.75,
    0.70, 0.70, 0.70,
    0.65, 0.65, 0.65,
)


@dataclass
class Settings:
    # ── [server] ────────────────────────────────────────────────────────
    server_host: str = "127.0.0.1"
    server_port: int = 8765
    server_token: str = ""                 # Bearer token for /api and /mcp; empty = no auth
    server_db_path: str = "kitchenette.db"
    server_timezone: str = ""              # IANA name; empty = the machine's local time
    server_timezone_label: str = ""        # prefix shown before reset times, e.g. "JST "
    server_scan_interval_seconds: float = 60.0
    server_dev_clock: bool = False         # expose POST /api/dev/clock (fast-forward for demos)
    # Origins of pages on other sites that may call /api from a browser, e.g.
    # ["https://chat.example.com"]. Empty = only pages served from this server's own origin.
    server_cors_origins: list[str] = field(default_factory=list)
    # Origins of pages on other sites that may show the kitchen page (/page/) in an <iframe>,
    # e.g. ["https://chat.example.com"]. Empty = only pages of this server's own origin.
    server_embed_origins: list[str] = field(default_factory=list)

    # ── [roles] ─────────────────────────────────────────────────────────
    roles_default: str = "companion"          # used when a tool call omits `who`
    roles_allowed: list[str] = field(default_factory=list)   # empty = any id is accepted

    # ── [words] ─────────────────────────────────────────────────────────
    words_human_name: str = "用户"          # how the texts refer to the human
    words_human_pronoun: str = "她"
    words_app_name: str = "App"            # what the texts call the place the human acts from

    # ── [inline] ────────────────────────────────────────────────────────
    # Whether the role acts by writing bracket markers ([吃 菜名]) in its replies. Switch this off
    # for a setup that only uses tools: the sentences that mention markers then name the tool.
    # "auto": behave as switched off until the host has actually sent a reply to /api/inline,
    # and as switched on from then on.
    inline_enabled: bool | str = "auto"

    # ── [fridge] ────────────────────────────────────────────────────────
    fridge_coupon_max: int = 3             # coupons a role can hold
    fridge_buy_max_items: int = 5          # kinds one coupon buys
    fridge_human_buy_max_items: int = 30   # guard against mis-taps, not a rule
    fridge_clear_bad_after_days: float = 3.0   # spoiled batches vanish after this long
    fridge_burn_chance_meh: float = 0.20   # chance a pot with stale ingredients burns
    fridge_category_days: dict[str, float] = field(default_factory=lambda: {
        "leafy": 2, "meat": 3, "dairy": 5, "root": 7, "fruit": 7, "veg": 5, "staple_food": 5})
    # Shelf life for single items, by id or name: {"egg": 10} or {"鸡蛋": 10}. Wins over the category.
    fridge_shelf_days: dict[str, float] = field(default_factory=dict)
    fridge_staples: list[str] = field(default_factory=lambda: ["米", "油", "盐", "酱油"])
    fridge_staple_aliases: list[str] = field(default_factory=lambda: [
        "米", "大米", "米饭", "油", "食用油", "盐", "酱油", "生抽", "老抽", "糖", "醋", "水"])
    fridge_raw_edible: list[str] = field(default_factory=lambda: [
        "strawberry", "apple", "milk", "cheese", "cucumber", "tomato"])
    fridge_hidden_freshness: list[str] = field(default_factory=lambda: ["egg"])
    fridge_ingredients: list[dict] = field(default_factory=lambda: copy.deepcopy(list(DEFAULT_INGREDIENTS)))

    # ── [satiety] ───────────────────────────────────────────────────────
    satiety_enabled: bool = True
    satiety_max: float = 100.0
    satiety_decay_per_hour: float = 9.0
    satiety_init: float = 60.0
    satiety_hungry_below: float = 30.0
    satiety_dizzy_hours: float = 2.5       # how long spoiled food leaves a role dizzy
    satiety_gain: dict[str, float] = field(default_factory=lambda: {
        "great": 45.0, "ok": 40.0, "her": 40.0, "burnt": 15.0, "spoiled": 0.0,
        "raw": 15.0, "raw_meh": 12.0})
    satiety_snack_gain: dict[str, float] = field(default_factory=lambda: {
        "high": 12.0, "mid": 8.0, "low": 5.0})

    # ── [kitchen] ───────────────────────────────────────────────────────
    kitchen_minutes_min: int = 1
    kitchen_minutes_max: int = 1440
    kitchen_worm_enabled: bool = True
    kitchen_worm_min_age_hours: float = 6.0    # a dish must sit at least this long...
    kitchen_worm_day_hour: int = 4             # ...and pass this local hour to grow worms
    kitchen_menu_giveup_seconds: float = 600.0
    kitchen_menu_retry_max_seconds: float = 86400.0

    # ── [snacks] ────────────────────────────────────────────────────────
    snacks_day_boundary_hour: int = 4      # daily caps reset at this local hour
    snacks_cap_min: int = 0
    snacks_cap_max: int = 20
    snacks_catalog: list[dict] = field(default_factory=lambda: copy.deepcopy(list(DEFAULT_SNACKS)))

    # ── [stamina] ───────────────────────────────────────────────────────
    stamina_enabled: bool = True
    stamina_tau_hours: float = 2.5         # time constant of the drift toward the schedule
    stamina_init: float = 0.7
    # 24 values, or the name of a built-in one: "night-owl", "early-bird", "no-sleep".
    stamina_schedule: list[float] | str = field(default_factory=lambda: list(DEFAULT_SCHEDULE))
    stamina_cost_base: float = 0.02        # a round with any work costs this...
    stamina_cost_per_kind: float = 0.04    # ...plus this per distinct kind of work...
    stamina_cost_cap: float = 0.20         # ...capped here
    stamina_recharge_cap: float = 0.25     # most a single round can restore
    stamina_auto_account: bool = True      # settle each of this server's tool calls as it happens
    stamina_auto_round_seconds: float = 120.0   # calls this close together count as one round
    stamina_sleep_debt: bool = False       # apply the sleep factor (see docs/HOOKS.md)
    # tool name -> stamina restored. A tool listed here is rest, never work.
    stamina_rest: dict[str, float] = field(default_factory=lambda: {
        "eat": 0.10, "take_bath": 0.08, "music_play": 0.06, "read_pages": 0.06})
    # tool name -> kind of work. Tools sharing a kind are charged once per round.
    stamina_work: dict[str, str] = field(default_factory=lambda: {
        "kitchen_cook": "kitchen", "kitchen_status": "kitchen",
        "kitchen_cancel": "kitchen", "kitchen_toss": "kitchen"})
    # extra stamina on top of the meal itself, by how the dish turned out
    stamina_outcome_delta: dict[str, float] = field(default_factory=lambda: {
        "great": 0.02, "ok": 0.0, "burnt": -0.07, "spoiled": -0.15, "raw": -0.05, "raw_meh": -0.05})

    # ── [coupons] ───────────────────────────────────────────────────────
    # tool name -> label of what was made. A successful call earns one coupon.
    # Empty by default: which of your companion's tools count is yours to say.
    coupons_earn: dict[str, str] = field(default_factory=dict)
    # Clause naming how coupons are earned; shown when a role runs out. Empty = say nothing.
    coupons_earn_hint: str = ""

    # ── [notify] ────────────────────────────────────────────────────────
    notify_mode: str = "queue"             # queue | webhook | both | none
    notify_webhook_url: str = ""
    notify_webhook_token: str = ""
    notify_quiet_hours: list[str] = field(default_factory=list)   # e.g. ["02:00-06:30"]
    notify_respect_sleep: bool = False     # hold webhook calls while a role is asleep

    # ── [art] ───────────────────────────────────────────────────────────
    art_provider: str = ""                 # "package.module:callable"; empty = text cards only
    art_dir: str = "art"
    # Pictures for the dish book: "package.module:callable" drawing one dish; empty = a placeholder.
    art_dish_provider: str = ""

    # ── [play] ──────────────────────────────────────────────────────────
    # The seventeen things added in the upgrade, one switch each (see docs/UPGRADE.md). A switch that is
    # off means the thing is not installed: its markers are plain text, nothing teaches it, the page
    # hides it, and asking for it directly says it is off. Turning one off never deletes anything.
    # A switch whose parent is off counts as off. Defaults: ten on, seven off.
    play_recipes_public: bool = True       # the public recipe book (300-odd home dishes)
    play_recipes_today: bool = True        # "today you could try" in the kitchen status
    play_recipe_cook: bool = True          # open a pot by a recipe id; buy what a recipe lacks at once
    play_recipe_book: bool = True          # the role's own recipe pages
    play_proficiency: bool = True          # new → practised → signature
    play_mishaps: bool = True              # small mishaps while a hand is still new
    play_new_dish_bonus: bool = True       # a little extra stamina the first time a new dish is eaten
    play_settle_card: bool = True          # the cooking card turns into a settled still when done
    play_dex: bool = True                  # the dish book: one page per dish made
    play_achievements: bool = True         # quiet kitchen achievements
    play_tasting_notes: bool = False       # one line after cooking from a page
    play_orders: bool = False              # the human orders a dish from a recipe
    play_menus: bool = False               # several dishes put together as one meal
    play_recipe_codes: bool = False        # share a page as a string of characters
    play_vendor: bool = False              # street vendors who come by now and then
    play_dishwash: bool = False            # plates: a dishwasher, or the role washes them
    play_seal_jars: bool = False           # jars on the sill: fruit and vegetables turn into treats

    # ── [recipes] ───────────────────────────────────────────────────────
    recipes_skilled_at: int = 3            # pots made well before a dish counts as practised...
    recipes_signature_at: int = 8          # ...and as a signature dish
    recipes_mishap_rate_new: float = 0.10  # chance of a mishap per pot while a dish is new
    recipes_mishap_rate_skilled: float = 1 / 30   # ...once practised (a signature dish has none)
    recipes_new_dish_bonus: float = 0.03   # stamina added the first time a dish cooked by a recipe is eaten
    recipes_avoid_days: float = 3.0        # "today you could try" skips dishes cooked this recently
    # "package.module:callable" returning {"rain": bool | None, "temp_c": float | None} for now;
    # empty = recommendations look only at the hour and the season.
    recipes_weather_provider: str = ""

    # ── [dishwash] ──────────────────────────────────────────────────────
    dishwash_seconds_per_plate: float = 120.0
    dishwash_break_rate: float = 0.05      # about one plate in twenty breaks

    # ── [jars] ──────────────────────────────────────────────────────────
    jars_daily_cap: int = 3                # servings from the jars per day (the human feeding shares it)

    # ── [vendor] ────────────────────────────────────────────────────────
    vendor_order_max: int = 30             # most one order may cost
    vendor_day_max: int = 60               # most the role may spend at the vendors in one day
    # Pocket money comes from one of two places (docs/UPGRADE.md):
    # 1. your own pocket-money system over HTTP: wallet_url (+ wallet_token for a bearer token). Orders are
    #    charged there, and the built-in ledger is not used;
    # 2. otherwise the small ledger in the kitchen's database. It starts at 0 and nothing is paid into it by
    #    itself: the human gives pocket money from the page, as much as they like, whenever they like, and
    #    the role is told.
    vendor_wallet_url: str = ""
    vendor_wallet_token: str = ""
    # "package.module:object" with debit / lookup / void / balance (docs/UPGRADE.md); empty = the
    # small ledger kept in the kitchen's own database.
    vendor_wallet_provider: str = ""
    # "package.module:callable" that plays the vendor: (system, history, line) -> one sentence.
    # Empty = the vendors only say their fixed lines.
    vendor_talk_provider: str = ""


_SECTIONS = ("server", "roles", "words", "inline", "fridge", "satiety", "kitchen", "snacks", "stamina",
             "coupons", "notify", "art", "play", "recipes", "dishwash", "jars", "vendor")
_FIELDS = {f.name: f for f in fields(Settings)}

_current: Settings = Settings()
_version = 0


def get() -> Settings:
    """The active settings."""
    return _current


def version() -> int:
    """Bumped whenever the settings object is replaced or edited via :func:`override`."""
    return _version


def _touch() -> None:
    global _version
    _version += 1


SCHEDULES: dict[str, tuple[float, ...]] = {
    "night-owl": DEFAULT_SCHEDULE,      # up until 02:00, recovering 02:00-09:00
    "early-bird": EARLY_BIRD_SCHEDULE,  # sleepy after 21:00, recovering 00:00-09:00
    "no-sleep": (0.80,) * 24,           # the same level around the clock
}

_DEFAULTS = Settings()


class ConfigError(ValueError):
    """A setting that cannot be used. Carries one sentence in English and one in Chinese, and
    says where the value came from, so the command line can report it without a traceback."""

    def __init__(self, where: str, en: str, zh: str, source: str = ""):
        self.where, self.en, self.zh, self.source = where, en, zh, source
        super().__init__(f"{where}: {en}")

    def lines(self) -> list[str]:
        where = f"{self.where} " if self.where else ""
        src = f"{self.source}: " if self.source and where else (f"{self.source} " if self.source else "")
        src_zh = f"{self.source}：" if self.source and where else (f"{self.source} " if self.source else "")
        return [f"{src}{where}{self.en}", f"{src_zh}{where}{self.zh}"]


def label(name: str) -> str:
    """Attribute name -> the way it is written in the file: "[fridge] coupon_max"."""
    section, _, key = name.partition("_")
    return f"[{section}] {key}"


def _bad(name: str, value: Any, en: str, zh: str) -> ConfigError:
    shown = json.dumps(value, ensure_ascii=False) if isinstance(value, (str, int, float, bool, list, dict)) \
        else repr(value)
    if len(shown) > 60:
        shown = shown[:57] + "..."
    return ConfigError(label(name), f"= {shown}: {en}", f"填的是 {shown}：{zh}")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# name -> (lowest, highest); None = no limit on that side
_RANGES: dict[str, tuple[float | None, float | None]] = {
    "server_port": (1, 65535), "server_scan_interval_seconds": (0.5, None),
    "fridge_coupon_max": (0, None), "fridge_buy_max_items": (1, None), "fridge_human_buy_max_items": (1, None),
    "fridge_clear_bad_after_days": (0, None), "fridge_burn_chance_meh": (0, 1),
    "satiety_max": (1, None), "satiety_decay_per_hour": (0, None), "satiety_init": (0, None),
    "satiety_hungry_below": (0, None), "satiety_dizzy_hours": (0, None),
    "kitchen_minutes_min": (1, None), "kitchen_minutes_max": (1, None), "kitchen_worm_min_age_hours": (0, None),
    "kitchen_worm_day_hour": (0, 23), "kitchen_menu_giveup_seconds": (0, None),
    "kitchen_menu_retry_max_seconds": (0, None),
    "snacks_day_boundary_hour": (0, 23), "snacks_cap_min": (0, None), "snacks_cap_max": (0, None),
    "stamina_tau_hours": (0.01, None), "stamina_init": (0, 1), "stamina_cost_base": (0, 1),
    "stamina_cost_per_kind": (0, 1), "stamina_cost_cap": (0, 1), "stamina_recharge_cap": (0, 1),
    "stamina_auto_round_seconds": (0, None),
    "recipes_skilled_at": (1, None), "recipes_signature_at": (1, None), "recipes_mishap_rate_new": (0, 1),
    "recipes_mishap_rate_skilled": (0, 1), "recipes_new_dish_bonus": (0, 1), "recipes_avoid_days": (0, None),
    "dishwash_seconds_per_plate": (1, None), "dishwash_break_rate": (0, 1), "jars_daily_cap": (0, 20),
    "vendor_order_max": (1, None), "vendor_day_max": (1, None), 
}
# table settings whose values are numbers: name -> (lowest, highest)
_TABLE_RANGES: dict[str, tuple[float | None, float | None]] = {
    "fridge_category_days": (0.01, None), "fridge_shelf_days": (0.01, None),
    "satiety_gain": (0, None), "satiety_snack_gain": (0, None),
    "stamina_rest": (0, 1), "stamina_outcome_delta": (-1, 1),
}
_TEXT_TABLES = ("stamina_work", "coupons_earn")
_TEXT_LISTS = ("server_cors_origins", "server_embed_origins", "roles_allowed", "fridge_staples", "fridge_staple_aliases",
               "fridge_raw_edible", "fridge_hidden_freshness", "notify_quiet_hours")
_QUIET_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d-([01]?\d|2[0-3]):[0-5]\d$")


def _range_words(lo: float | None, hi: float | None) -> tuple[str, str]:
    if lo is not None and hi is not None:
        return f"must be between {lo:g} and {hi:g}", f"要在 {lo:g} 到 {hi:g} 之间"
    if lo is not None:
        return f"must be {lo:g} or more", f"不能小于 {lo:g}"
    return f"must be {hi:g} or less", f"不能大于 {hi:g}"


def _in_range(v: float, lo: float | None, hi: float | None) -> bool:
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def _check_value(name: str, value: Any) -> None:
    """Type and range of one setting. Raises ConfigError naming the setting and what it takes."""
    default = getattr(_DEFAULTS, name)
    if name == "inline_enabled":
        if not (isinstance(value, bool) or value == "auto"):
            raise _bad(name, value, 'expected true, false or "auto"', '只能填 true、false 或 "auto"')
        return
    if name == "stamina_schedule":
        if isinstance(value, str):
            if value not in SCHEDULES:
                names = ", ".join(f'"{n}"' for n in SCHEDULES)
                raise _bad(name, value, f"expected one of {names}, or 24 numbers",
                           f"只能填 {names} 之一，或者 24 个数")
            return
        if not isinstance(value, list) or len(value) != 24 or not all(_is_number(x) for x in value):
            raise _bad(name, value, "expected exactly 24 values (one per hour, 0-23), or the name of a "
                       "built-in schedule", "要正好 24 个数（0 点到 23 点每小时一个），或者填一个预设名")
        if any(not 0.0 <= float(x) <= 1.0 for x in value):
            raise _bad(name, value, "every value must be between 0 and 1", "每个数都要在 0 到 1 之间")
        return
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise _bad(name, value, "expected true or false (no quotes)", "只能填 true 或 false，不加引号")
    elif isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int):
            raise _bad(name, value, "expected a whole number (no quotes)", "要填一个整数，不加引号")
    elif isinstance(default, float):
        if not _is_number(value):
            raise _bad(name, value, "expected a number (no quotes)", "要填一个数，不加引号")
    elif isinstance(default, str):
        if not isinstance(value, str):
            raise _bad(name, value, "expected text in double quotes", "要填文字，用英文双引号括起来")
    elif isinstance(default, list):
        if not isinstance(value, list):
            raise _bad(name, value, "expected a list in square brackets", "要填一个列表，用方括号括起来")
        if name in _TEXT_LISTS and not all(isinstance(x, str) for x in value):
            raise _bad(name, value, "every entry must be text in double quotes", "每一项都要是加了英文双引号的文字")
    elif isinstance(default, dict):
        if not isinstance(value, dict):
            raise _bad(name, value, "expected a table of key = value lines", "要填一张表（一行一个 键 = 值）")
    if name in _RANGES and not _in_range(float(value), *_RANGES[name]):
        raise _bad(name, value, *_range_words(*_RANGES[name]))
    if name in _TABLE_RANGES:
        lo, hi = _TABLE_RANGES[name]
        for k, v in value.items():
            if not _is_number(v) or not _in_range(float(v), lo, hi):
                en, zh = _range_words(lo, hi)
                raise ConfigError(f"{label(name)}.{k}", f"= {json.dumps(v, ensure_ascii=False)}: expected a number; {en}",
                                  f"填的是 {json.dumps(v, ensure_ascii=False)}：要填一个数，{zh}")
    if name in _TEXT_TABLES:
        for k, v in value.items():
            if not isinstance(v, str):
                raise ConfigError(f"{label(name)}.{k}", f"= {json.dumps(v, ensure_ascii=False)}: expected text in double quotes",
                                  f"填的是 {json.dumps(v, ensure_ascii=False)}：要填文字，用英文双引号括起来")


def _validate(s: Settings) -> None:
    """Check every setting and how they fit together. Normalises a named schedule to its 24 values."""
    for name in _FIELDS:
        _check_value(name, getattr(s, name))
    if isinstance(s.stamina_schedule, str):
        s.stamina_schedule = list(SCHEDULES[s.stamina_schedule])
    if s.server_timezone:
        try:
            ZoneInfo(s.server_timezone)
        except Exception:  # noqa: BLE001  (unknown key, malformed name, missing database)
            raise _bad("server_timezone", s.server_timezone,
                       'not a known time zone name; use one like "Asia/Shanghai", "Europe/Berlin" or '
                       '"America/New_York", or "" for this machine\'s own',
                       '不认识这个时区名；请填 "Asia/Shanghai"、"Europe/Berlin"、"America/New_York" 这样的名字，'
                       '或者留空 "" 用这台电脑的时区') from None
    if s.notify_mode not in ("queue", "webhook", "both", "none"):
        raise _bad("notify_mode", s.notify_mode, 'expected "queue", "webhook", "both" or "none"',
                   '只能填 "queue"、"webhook"、"both" 或 "none"')
    if s.notify_mode in ("webhook", "both") and not s.notify_webhook_url:
        raise ConfigError("[notify] webhook_url", f'is empty, but mode = "{s.notify_mode}" needs an address to post to',
                          f'是空的，而 mode = "{s.notify_mode}" 需要一个接收通知的网址')
    for w in s.notify_quiet_hours:
        if not _QUIET_RE.match(w.strip()):
            raise _bad("notify_quiet_hours", w, 'each window is written "HH:MM-HH:MM", e.g. "02:00-06:30"',
                       '每一段写成 "时:分-时:分"，例如 "02:00-06:30"')
    if s.kitchen_minutes_max < s.kitchen_minutes_min:
        raise _bad("kitchen_minutes_max", s.kitchen_minutes_max, "must not be smaller than minutes_min",
                   "不能比 minutes_min 小")
    if s.vendor_wallet_url and not s.vendor_wallet_url.startswith(("http://", "https://")):
        # the address may carry a secret (a key in the path or the query): only its first characters are shown
        raise _bad("vendor_wallet_url", s.vendor_wallet_url[:8] + "…",
                   "expected an address starting with http:// or https://", "要填 http:// 或 https:// 开头的地址")
    if s.recipes_signature_at < s.recipes_skilled_at:
        raise _bad("recipes_signature_at", s.recipes_signature_at, "must not be smaller than skilled_at",
                   "不能比 skilled_at 小")
    if s.snacks_cap_max < s.snacks_cap_min:
        raise _bad("snacks_cap_max", s.snacks_cap_max, "must not be smaller than cap_min", "不能比 cap_min 小")
    if s.satiety_init > s.satiety_max:
        raise _bad("satiety_init", s.satiety_init, "must not be larger than max", "不能比 max 大")
    ids = [it.get("id") for it in s.fridge_ingredients if isinstance(it, dict)]
    if len(ids) != len(s.fridge_ingredients) or len(ids) != len(set(ids)) or not all(ids):
        raise ConfigError("[fridge] ingredients", "every entry needs an id, and no two may share one",
                          "每一样都要有 id，而且不能重复")
    # A category is one of the built-in ones, or one that an ingredient of your own catalog uses.
    # Anything else in the table is a slip of the keyboard.
    in_use = set(_DEFAULTS.fridge_category_days) | {it.get("category") for it in s.fridge_ingredients}
    for key in s.fridge_category_days:
        if key not in in_use:
            close = difflib.get_close_matches(key, sorted(c for c in in_use if c), n=1, cutoff=0.6)
            raise ConfigError(f"[fridge.category_days] {key}",
                              f"is not a category{f' (did you mean {close[0]}?)' if close else ''}; the categories "
                              f"are: {', '.join(_DEFAULTS.fridge_category_days)}",
                              f"不是一个类别{f'（是不是想写 {close[0]}？）' if close else ''}；类别只有这几个："
                              f"{'、'.join(_DEFAULTS.fridge_category_days)}")
    categories = "、".join(s.fridge_category_days)
    for it in s.fridge_ingredients:
        if not it.get("name") or it.get("category") not in s.fridge_category_days:
            raise ConfigError(f"[fridge] ingredients ({it.get('id')})",
                              f"needs a name and a category that is one of: {', '.join(s.fridge_category_days)}",
                              f"要有 name，category 只能是这几个之一：{categories}")
        if isinstance(it.get("pack_qty"), bool) or not isinstance(it.get("pack_qty"), int) or it["pack_qty"] < 1:
            raise ConfigError(f"[fridge] ingredients ({it.get('id')})", "pack_qty must be a whole number, 1 or more",
                              "pack_qty 要填一个整数，不能小于 1")
    known = set(ids) | {it["name"] for it in s.fridge_ingredients}
    for k in s.fridge_shelf_days:
        if k not in known:
            raise ConfigError(f"[fridge.shelf_days] {k}", "is not an ingredient in the catalog (use its id or its name)",
                              "不是清单里的食材（请写它的 id 或名字）")
    for sn in s.snacks_catalog:
        if not isinstance(sn, dict) or not sn.get("id") or not sn.get("name") or sn.get("tier") not in ("high", "mid", "low"):
            raise ConfigError("[snacks] catalog", 'every snack needs an id, a name and a tier of "high", "mid" or "low"',
                              '每样零食都要有 id、name，tier 只能是 "high"、"mid" 或 "low"')


def _coerce(name: str, raw: str, env_name: str) -> Any:
    """An environment variable's text -> a value of the setting's type."""
    default = getattr(_DEFAULTS, name)
    text = raw.strip()
    try:
        if name == "inline_enabled" and text.lower() == "auto":
            return "auto"
        if name == "stamina_schedule" and not text.startswith("["):
            return text
        if isinstance(default, bool):
            if text.lower() in ("1", "true", "yes", "on"):
                return True
            if text.lower() in ("0", "false", "no", "off"):
                return False
            raise ValueError
        if isinstance(default, int):
            return int(text)
        if isinstance(default, float):
            return float(text)
        if isinstance(default, (list, dict)):
            return json.loads(text)
        return raw
    except ValueError:
        kind = ("true or false", "true 或 false") if isinstance(default, bool) else (
            ("a number", "一个数") if isinstance(default, (int, float)) else ("JSON", "JSON 写法"))
        raise ConfigError(label(name), f"= {raw!r}: expected {kind[0]}", f"填的是 {raw!r}：这里要填{kind[1]}") from None


def _put(s: Settings, name: str, value: Any) -> None:
    """Set one value from a file or the environment. Tables are merged key by key into the
    built-in table, so changing one entry keeps the others."""
    _check_value(name, value)
    if isinstance(getattr(_DEFAULTS, name), dict):
        value = {**getattr(s, name), **value}
    setattr(s, name, value)


def build(path: str | os.PathLike | None = None, env: dict[str, str] | None = None) -> Settings:
    """Defaults, then the TOML file, then environment variables. Raises ConfigError."""
    env = os.environ if env is None else env
    s = Settings()
    path = path or env.get(ENV_PREFIX + "CONFIG") or (
        DEFAULT_CONFIG_FILE if Path(DEFAULT_CONFIG_FILE).is_file() else None)
    source = str(path) if path else ""
    from_env: dict[str, str] = {}       # "[section] key" -> the variable that set it
    try:
        if path:
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
            except OSError as e:
                raise ConfigError("", f"cannot be read ({e.strerror or e})", f"读不了（{e.strerror or e}）") from None
            except tomllib.TOMLDecodeError as e:
                if "twice" in str(e) or "Cannot declare" in str(e) or "Cannot overwrite" in str(e):
                    hint = ("The same [section] or key is written twice; put all of a section's lines under "
                            "one heading.", "同一个 [段名] 或同一个键写了两次——同一段的内容要都写在一个标题下面。")
                else:
                    hint = ('Check that line: text needs double quotes ("like this"), and a key that is not '
                            'plain letters, digits, - or _ needs them too ("鸡蛋" = 10).',
                            '请看那一行：文字要加英文双引号（"像这样"）；键名如果不是纯英文字母、数字、- 或 _，'
                            '也要加双引号（"鸡蛋" = 10）。')
                raise ConfigError("", f"is not valid TOML: {e}. {hint[0]}", f"不是合法的 TOML：{e}。{hint[1]}") from None
            for section, table in data.items():
                if section not in _SECTIONS or not isinstance(table, dict):
                    raise ConfigError(f"[{section}]", f"unknown config section; the sections are: {', '.join(_SECTIONS)}",
                                      f"没有这个段名；可以用的段名是：{'、'.join(_SECTIONS)}")
                for key, value in table.items():
                    name = f"{section}_{key}"
                    if name not in _FIELDS:
                        keys = ", ".join(n.partition("_")[2] for n in _FIELDS if n.startswith(section + "_"))
                        raise ConfigError(f"[{section}] {key}", f"unknown config key; this section has: {keys}",
                                          f"这一段里没有这个键；这一段可以写的是：{keys}")
                    _put(s, name, value)
        for name in _FIELDS:
            env_name = ENV_PREFIX + name.upper()
            raw = env.get(env_name)
            if raw is not None:
                from_env[label(name)] = env_name
                try:
                    _put(s, name, _coerce(name, raw, env_name))
                except ConfigError as e:
                    e.source = f"environment ({env_name})"
                    raise
        _validate(s)
    except ConfigError as e:
        if not e.source:
            where = e.where.replace("[fridge.shelf_days]", "[fridge] shelf_days").replace(
                "[fridge.category_days]", "[fridge] category_days")
            env_name = next((v for k, v in from_env.items() if where.startswith(k)), None)
            e.source = f"environment ({env_name})" if env_name else source
        raise
    return s


def load(path: str | os.PathLike | None = None, env: dict[str, str] | None = None) -> Settings:
    """Build settings and make them the active ones."""
    global _current
    _current = build(path, env)
    _touch()
    return _current


def use(settings: Settings) -> Settings:
    """Install a ready-made settings object (used by tests and embedders)."""
    global _current
    _validate(settings)
    _current = settings
    _touch()
    return _current


def override(**changes: Any) -> Settings:
    """Change attributes on the active settings in place (a table given here replaces the table)."""
    for name, value in changes.items():
        if name not in _FIELDS:
            raise AttributeError(f"unknown setting {name!r}")
        setattr(_current, name, value)
    _validate(_current)
    _touch()
    return _current


_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _toml_key(key: str) -> str:
    """A table key as TOML wants it: bare when it is plain letters, digits, - and _; quoted otherwise."""
    return key if _BARE_KEY_RE.match(key) else json.dumps(key, ensure_ascii=False)


def unknown_env(env: dict[str, str] | None = None) -> list[str]:
    """One line per KITCHENETTE_ variable that is not a setting (and so was ignored), naming the
    closest real one. A misspelt variable does not stop the server; it should not pass unnoticed."""
    env = os.environ if env is None else env
    known = [ENV_PREFIX + name.upper() for name in _FIELDS] + [ENV_PREFIX + "CONFIG"]
    out = []
    for name in sorted(env):
        if not name.startswith(ENV_PREFIX) or name in known:
            continue
        # compared without the shared prefix, which would make everything look alike
        close = [ENV_PREFIX + m for m in difflib.get_close_matches(
            name[len(ENV_PREFIX):], [k[len(ENV_PREFIX):] for k in known], n=1, cutoff=0.75)]
        hint_en = f"; did you mean {close[0]}?" if close else ""
        hint_zh = f"；是不是想写 {close[0]}？" if close else ""
        out.append(f"{name} is not a setting and was ignored{hint_en} / 不认识这个变量，已忽略{hint_zh}")
    return out


def dump(s: Settings | None = None) -> str:
    """The settings written the way the file is: [section] headings and key = value lines."""
    s = s or _current
    out: list[str] = []
    for section in _SECTIONS:
        out.append(f"[{section}]")
        tables: list[str] = []
        for name in _FIELDS:
            if not name.startswith(section + "_"):
                continue
            key, value = name.partition("_")[2], getattr(s, name)
            if key.endswith("token") and value:
                value = "***"
            if name == "stamina_schedule":
                preset = next((n for n, v in SCHEDULES.items() if list(v) == list(value)), None)
                out.append(f'{key} = "{preset}"' if preset else f"{key} = {json.dumps(value)}")
            elif isinstance(value, dict):
                tables.append(f"[{section}.{key}]")
                tables += [f"{_toml_key(k)} = {json.dumps(v, ensure_ascii=False)}" for k, v in value.items()]
                tables.append("")
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                names = "、".join(str(x.get("name", x.get("id"))) for x in value)
                out.append(f"# {key}: {len(value)} entries ({names})")
            else:
                out.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
        out.append("")
        out += tables
    return "\n".join(out).rstrip() + "\n"
