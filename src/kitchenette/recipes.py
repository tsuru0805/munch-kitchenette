"""The public recipe book, and the three ways an ingredient can come to the kitchen.

- **Always at hand** (no need to buy): ``[fridge] staple_aliases``, plus the seasonings in
  :data:`STAPLES_EXTRA` while the public recipes are on.
- **Sold at the shop**: the catalog (``[fridge] ingredients``) plus :data:`EXTRA_ITEMS`, common main
  ingredients the recipes need, added to the shop while the public recipes are on. Once bought they
  keep being recognised even if the recipes are switched off again.
- **Recipe ingredients outside the catalog** (ids start with ``v_``): sold at the shop while the
  public recipes are on (buying by recipe and ``[买菜 name]`` both take them; the catalog page does
  not list them), so no recipe is out of reach for good. Only the handful in the vendors' own list
  (``texts_play.VENDOR_ONLY_INGREDIENTS``) are **vendor-only**: the shop never sells those.

The recipes come from a small index built once from HowToCook (Anduin2017/HowToCook, Unlicense;
``tools/build_recipe_index.py``). Each entry is one line of facts — id, name, main ingredients,
optional ones, method, rough minutes, category, source — and **no steps**. The method and minutes
were sorted and estimated while building the index; the original has neither column.

Feasibility is a pure function and only uses what the role can see itself (eggs count as "how many",
never good or bad); the real check happens again when the pot is opened.
"""
from __future__ import annotations

import glob
import hashlib
import importlib
import json
import logging
import os
import re
import sys
import threading

from . import clock, config, play
from .texts_play import (METHOD_CN, NIGHT_HOURS, VENDOR_ONLY_INGREDIENTS, WEATHER_COLD_C, WEATHER_HOT_C, tp,
                         vendor_id)

log = logging.getLogger(__name__)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
NOT_A_MEAL = ("condiment", "semi-finished")      # still searchable, never recommended as a meal

# ── sold at the shop once the public recipes are on ─────────────────────
EXTRA_ITEMS: tuple[dict, ...] = (
    {"id": "coriander", "name": "香菜", "category": "leafy", "pack_qty": 1, "aliases": ("芫荽",)},
    {"id": "celery", "name": "芹菜", "category": "veg", "pack_qty": 1, "aliases": ("西芹",)},
    {"id": "chives", "name": "韭菜", "category": "leafy", "pack_qty": 1, "aliases": ("韭黄",)},
    {"id": "wintermelon", "name": "冬瓜", "category": "veg", "pack_qty": 1},
    {"id": "corn", "name": "玉米", "category": "veg", "pack_qty": 2, "aliases": ("玉米粒", "甜玉米")},
    {"id": "ribs", "name": "排骨", "category": "meat", "pack_qty": 1,
     "aliases": ("肋排", "猪排骨", "猪肋排", "小排", "猪小排")},
    {"id": "wings", "name": "鸡翅", "category": "meat", "pack_qty": 1, "aliases": ("鸡翅中", "鸡中翅", "翅中", "鸡翅膀")},
    {"id": "sausage", "name": "火腿肠", "category": "meat", "pack_qty": 2, "shelf_days": 14,
     "aliases": ("火腿", "香肠", "腊肠")},
    {"id": "bacon", "name": "培根", "category": "meat", "pack_qty": 1, "shelf_days": 7},
    {"id": "woodear", "name": "木耳", "category": "veg", "pack_qty": 1, "shelf_days": 30, "aliases": ("黑木耳",)},
    {"id": "greenbean", "name": "豆角", "category": "veg", "pack_qty": 1, "aliases": ("四季豆", "扁豆", "豇豆")},
    {"id": "cauliflower", "name": "花菜", "category": "veg", "pack_qty": 1, "aliases": ("菜花", "花椰菜")},
    {"id": "lettuce_stem", "name": "莴笋", "category": "veg", "pack_qty": 1, "aliases": ("莴苣",)},
    {"id": "bokchoy", "name": "青菜", "category": "leafy", "pack_qty": 1,
     "aliases": ("小白菜", "上海青", "油菜", "小油菜", "油麦菜")},
    {"id": "greencabbage", "name": "卷心菜", "category": "veg", "pack_qty": 1, "aliases": ("包菜", "圆白菜", "甘蓝", "手撕包菜")},
    {"id": "ricecake", "name": "年糕", "category": "staple_food", "pack_qty": 1, "shelf_days": 7},
    {"id": "ricenoodle", "name": "米粉", "category": "staple_food", "pack_qty": 1, "shelf_days": 30, "aliases": ("米线",)},
    {"id": "fish", "name": "鱼", "category": "meat", "pack_qty": 1,
     "aliases": ("鲤鱼", "鲈鱼", "草鱼", "鲫鱼", "鱼片", "鱼肉", "巴沙鱼", "龙利鱼", "鳕鱼")},
    {"id": "duck", "name": "鸭肉", "category": "meat", "pack_qty": 1, "aliases": ("鸭腿", "鸭子")},
    {"id": "cream", "name": "淡奶油", "category": "dairy", "pack_qty": 1, "aliases": ("稀奶油", "动物奶油")},
    {"id": "yogurt", "name": "酸奶", "category": "dairy", "pack_qty": 1, "aliases": ("原味酸奶",)},
    {"id": "century_egg", "name": "皮蛋", "category": "dairy", "pack_qty": 2, "shelf_days": 30, "aliases": ("松花蛋",)},
    {"id": "jujube", "name": "红枣", "category": "fruit", "pack_qty": 1, "shelf_days": 30, "aliases": ("大枣",)},
    {"id": "cola", "name": "可乐", "category": "staple_food", "pack_qty": 1, "shelf_days": 90},
    {"id": "taro", "name": "芋头", "category": "root", "pack_qty": 1, "aliases": ("荔浦芋头", "小芋头")},
    {"id": "sweetpotato", "name": "红薯", "category": "root", "pack_qty": 1, "aliases": ("地瓜", "番薯")},
    {"id": "pumpkin", "name": "南瓜", "category": "root", "pack_qty": 1, "shelf_days": 14},
    {"id": "garlic_sprout", "name": "蒜苗", "category": "leafy", "pack_qty": 1, "aliases": ("蒜苔", "蒜薹", "青蒜")},
    {"id": "chicken_feet", "name": "鸡爪", "category": "meat", "pack_qty": 1, "aliases": ("凤爪",)},
    {"id": "oats", "name": "燕麦", "category": "staple_food", "pack_qty": 1, "shelf_days": 60, "aliases": ("燕麦片",)},
    {"id": "peanut", "name": "花生", "category": "staple_food", "pack_qty": 1, "shelf_days": 60, "aliases": ("花生米",)},
    {"id": "glutinous_rice", "name": "糯米", "category": "staple_food", "pack_qty": 1, "shelf_days": 90},
)
_EXTRA_BY_ID = {it["id"]: it for it in EXTRA_ITEMS}

# Extra ways of writing an ingredient, used only to sort recipe ingredients when building the index.
BUILD_ALIASES: dict[str, str] = {
    "西红柿": "tomato", "蕃茄": "tomato", "番茄": "tomato",
    "鸡蛋黄": "egg", "新鲜鸡蛋": "egg", "蛋清": "egg", "蛋黄": "egg", "鸡蛋液": "egg",
    "猪五花肉": "pork", "带皮五花肉": "pork", "五花肉": "pork", "瘦肉": "pork", "猪里脊": "pork", "里脊": "pork",
    "里脊肉": "pork", "肉末": "pork", "猪肉末": "pork", "肉馅": "pork", "猪肉馅": "pork", "肉": "pork", "肉丝": "pork",
    "猪肉": "pork", "前腿肉": "pork", "梅花肉": "pork",
    "鸡胸肉": "chicken", "鸡胸": "chicken", "鸡肉": "chicken", "鸡腿肉": "chicken", "鸡腿": "chicken", "琵琶腿": "chicken",
    "牛排": "beef", "牛里脊": "beef", "牛腩": "beef", "肥牛": "beef", "肥牛卷": "beef", "牛肉": "beef",
    "罗氏虾": "shrimp", "基围虾": "shrimp", "鲜虾": "shrimp", "虾仁": "shrimp", "大虾": "shrimp", "对虾": "shrimp",
    "娃娃菜": "cabbage", "大白菜": "cabbage", "白菜": "cabbage",
    "香菇": "mushroom", "口蘑": "mushroom", "平菇": "mushroom", "杏鲍菇": "mushroom", "金针菇": "mushroom",
    "蟹味菇": "mushroom", "白玉菇": "mushroom", "鲜香菇": "mushroom",
    "西兰花": "broccoli", "青花菜": "broccoli",
    "青辣椒": "pepper", "尖椒": "pepper", "螺丝椒": "pepper", "红椒": "pepper", "甜椒": "pepper", "彩椒": "pepper",
    "青椒": "pepper", "红甜椒": "pepper", "杭椒": "pepper", "二荆条": "pepper",
    "芝士片": "cheese", "奶油奶酪": "cheese", "马苏里拉": "cheese", "芝士": "cheese", "马苏里拉奶酪": "cheese",
    "无盐黄油": "butter", "全脂牛奶": "milk", "纯牛奶": "milk",
    "老豆腐": "tofu", "嫩豆腐": "tofu", "内酯豆腐": "tofu", "北豆腐": "tofu", "南豆腐": "tofu",
    "意面": "noodles", "意大利面": "noodles", "挂面": "noodles", "面条": "noodles", "手擀面": "noodles", "拉面": "noodles",
    "柠檬汁": "lemon", "马铃薯": "potato", "绿豆芽": "beansprout", "黄豆芽": "beansprout",
    "萝卜": "daikon", "白萝卜": "daikon", "鲑鱼": "salmon",
    "肉沫": "pork", "肉丁": "pork", "猪通脊肉": "pork", "无骨肉": "pork", "大排": "pork",
    "菜椒": "pepper", "灯笼椒": "pepper", "青红辣椒": "pepper", "线椒": "pepper", "美人辣": "pepper",
    "胡箩卜": "carrot", "金菇": "mushroom", "冬菇": "mushroom", "菌菇": "mushroom", "闽星茶树菇": "mushroom",
    "茶树菇": "mushroom", "煎蛋": "egg", "温泉蛋": "egg", "牛柳": "beef", "牛腱子": "beef", "牛腱子肉": "beef",
    "鸡": "chicken", "半只鸡": "chicken", "手枪腿": "chicken", "鸡全翅": "wings", "粟米": "corn",
    "海虾": "shrimp", "活虾": "shrimp", "阿根廷红虾": "shrimp", "香芹": "celery", "新鲜菜心": "bokchoy",
    "黑虎虾": "shrimp", "明虾": "shrimp", "葱头": "onion", "美人椒": "pepper", "菜心": "bokchoy",
    "通心粉": "noodles", "奶油": "cream",
}

# Spring onion and coriander are garnish: they go among the optional ingredients.
GARNISH = frozenset({"scallion", "coriander"})
GARNISH_WORDS = ("葱", "葱花", "香葱", "小葱", "大葱", "葱段", "青葱", "葱白", "小香葱")

STAPLES_EXTRA: frozenset[str] = frozenset("""
盐 食盐 食用盐 精盐 海盐 糖 白糖 白砂糖 冰糖 红糖 黄冰糖 绵白糖 蜂蜜 蔗糖糖浆 糖浆
油 食用油 植物油 花生油 菜籽油 橄榄油 猪油 香油 芝麻油 麻油 玉米油 色拉油
酱油 生抽 老抽 生抽酱油 蚝油 耗油 醋 香醋 陈醋 白醋 米醋 料酒 黄酒 米酒 绍兴酒
姜 生姜 老姜 姜片 姜末 姜丝 蒜 大蒜 蒜头 蒜瓣 蒜末 蒜蓉 蒜粉 蒜片 葱姜蒜
八角 大料 桂皮 香叶 花椒 青花椒 花椒粉 花椒油 花椒碎 麻椒 草果 丁香 陈皮 白芷 小茴香
干辣椒 干辣椒面 辣椒粉 红辣椒粉 小米辣 小米椒 野山椒 泡椒 辣椒油 油泼辣子 藤椒油 辣椒 红辣椒 辣椒面
胡椒粉 白胡椒粉 黑胡椒粉 黑胡椒 黑胡椒粒 白胡椒 五香粉 十三香 孜然 孜然粉 孜然粒
鸡精 味精 鸡粉 鸡汁 高汤 淀粉 生粉 玉米淀粉 土豆淀粉 红薯淀粉 水淀粉
面粉 低筋面粉 中筋面粉 高筋面粉 普通面粉
番茄酱 豆瓣酱 郫县豆瓣酱 黄豆酱 甜面酱 芝麻酱 豆豉 蒸鱼豉油 南乳 柱侯酱 腐乳 咖喱块 咖喱 海鲜酱 沙茶酱
芝麻 白芝麻 熟白芝麻 黑芝麻 水 清水 开水 热水 温水 冷水 冰水 冰块 纯净水
酵母 泡打粉 小苏打 香草精 可可粉 姜黄粉 香菜粉 印度综合香料粉 小豆蔻粉 芥末 蛋黄酱 沙拉酱
米饭 大米 米 剩米饭 隔夜饭 白米饭 冷饭 北方大米 江南米
腐乳 南腐乳 红腐乳 味淋 日式味淋 鱼露 花椒粒 红花椒 酒 白酒 花雕酒 黑椒 黑椒碎 黑胡椒碎 椒盐 芝麻盐
干辣椒段 干辣椒碎 朝天椒 子弹头辣椒 糍粑辣椒 剁椒 泡姜 生姜片 生姜末 姜蒜 蒜水 蒜仔 白熟芝麻 芝麻粒
郫县豆瓣 豆瓣 红油豆瓣 豆鼓 味素 味极鲜 麻辣鲜 老干妈 饮用水 凉白开 凉白开水 矿泉水 盐巴 方糖 冰
月桂叶 肉桂 肉桂皮 肉桂棒 豆蔻 白蔻 红豆蔻 小豆蔻 山奈 草寇 砂仁 荜拨 香茅 甘草 孜然籽 青芥末
香果 干线椒 干红椒 葱姜 葱姜水 葱姜花椒水 凉水 火锅底料 黑盐 印度黑盐 藏红花 东北米
""".split())
STAPLE_SUFFIX = ("粉", "酱", "精", "油", "醋", "汁")
TOOL_WORDS = ("锅", "刀", "碗", "盘", "勺", "铲", "筷", "烤箱", "微波", "机", "器", "纸", "膜", "板", "签",
              "盆", "杯", "模具", "秤", "袋", "锡", "刷", "网", "擀面杖", "炉", "夹", "剪", "布", "架", "盖",
              "手套", "电饭煲", "量杯", "温度计", "牙签", "棉线", "绳", "蒸笼", "秒表", "吸管", "研杵",
              "雪克瓶", "瓦罐", "煲汤盅", "鏊子", "燃气灶", "炭火", "冰箱", "蒸箱", "披萨石", "电饼铛", "斧头",
              "汤匙", "簸箕", "砵", "蘸料碟", "捣药罐", "蒸篦子", "玻璃", "克称", "克数称", "搅拌", "臼", "明火", "笊篱")
DROP_WORDS = frozenset({"", "必备", "原料", "工具", "可选", "注", "注意", "其他", "其它", "调料", "配料", "主料",
                        "辅料", "食材", "以下", "如下", "大约", "原则", "配菜", "小料", "炒料",
                        "蔬菜", "肉类", "面食材料", "菜类材料", "牛羊鱼虾等肉类", "其他调味料", "调味料", "菜码",
                        "叶菜类蔬菜", "可根据口味选择增加", "其余配菜例如马蹄", "带脚", "直径", "一个容量在",
                        "新鲜绿叶", "汤料包", "卤料包", "烧烤料", "烧烤撒料", "面", "容量在"})


class RecipesUnavailable(Exception):
    """The index cannot be read."""


# ── ingredients that are not in the shop's own catalog ──────────────────

def extra_items() -> tuple[dict, ...]:
    """The extra shop items, offered only while the public recipes are on."""
    return EXTRA_ITEMS if play.on("recipes_public") else ()


def extra_item(item_id: str) -> dict | None:
    return _EXTRA_BY_ID.get(item_id)


def resolve_extra(name: str) -> str | None:
    n = (name or "").strip()
    return next((it["id"] for it in EXTRA_ITEMS if n == it["name"] or n in it.get("aliases", ())), None)


_VENDOR_NAMES: dict[str, str] = {}
_VENDOR_ALIAS: dict[str, str] = {}       # v_ id of an old name -> the id the index uses now
_VENDOR_ONLY = {it["id"]: it for it in VENDOR_ONLY_INGREDIENTS}
_VENDOR_ONLY_NAMES = {n: it["id"] for it in VENDOR_ONLY_INGREDIENTS for n in (it["name"], *it.get("aliases", ()))}


def vendor_category(name: str) -> str:
    """Shelf-life category for a vendor-only thing, guessed from its name."""
    if any(w in name for w in ("肉", "鱼", "虾", "蟹", "贝", "鸭", "鹅", "羊", "鱿", "蛤", "蚝", "排", "肠", "肚", "蹄")):
        return "meat"
    if any(w in name for w in ("果", "莓", "桃", "梨", "橙", "柚", "瓜子", "葡萄", "梅", "芒", "蕉", "樱", "枣")):
        return "fruit"
    if any(w in name for w in ("叶", "苗", "菜心", "苋", "蒿", "薄荷")):
        return "leafy"
    if any(w in name for w in ("薯", "芋", "藕", "笋", "萝卜", "山药", "姜")):
        return "root"
    if any(w in name for w in ("奶", "蛋", "豆腐", "乳")):
        return "dairy"
    if any(w in name for w in ("面", "粉丝", "米", "饼", "粉", "馒头", "包子", "皮", "粽", "糕")):
        return "staple_food"
    return "veg"


def _ensure_vendor_names() -> None:
    if not _VENDOR_NAMES:
        try:
            load()
        except RecipesUnavailable:
            pass


def vendor_item(item_id: str) -> dict | None:
    """A v_ id -> its kind: the vendors' own list first (only a vendor brings those), then the recipe
    ingredients the index knows (sold at the shop while the public recipes are on)."""
    it = _VENDOR_ONLY.get(item_id)
    if it is not None:
        return {**it, "vendor_only": True}
    _ensure_vendor_names()
    n = _VENDOR_NAMES.get(item_id)
    if n is None:
        return None
    return {"id": item_id, "name": n, "category": vendor_category(n), "pack_qty": 1, "vendor_only": False}


def is_vendor_only(item_id: str) -> bool:
    """Only a vendor brings it (the vendors' own list); other v_ ids are recipe ingredients the shop sells."""
    return str(item_id) in _VENDOR_ONLY


def vendor_resolve(name: str) -> str | None:
    n = (name or "").strip()
    if n in _VENDOR_ONLY_NAMES:
        return _VENDOR_ONLY_NAMES[n]
    _ensure_vendor_names()
    vid = vendor_id(n)
    return vid if vid in _VENDOR_NAMES else None


def is_staple_extra(name: str) -> bool:
    return (name or "").strip() in STAPLES_EXTRA and play.on("recipes_public")


def _alias_index() -> dict[str, str]:
    out: dict[str, str] = {}
    for it in list(config.get().fridge_ingredients) + list(EXTRA_ITEMS):
        out[it["name"]] = it["id"]
        for a in it.get("aliases", ()):
            out[a] = it["id"]
    out.update(BUILD_ALIASES)
    return out


def names_of(item_id: str) -> tuple[str, ...]:
    out = [k for k, v in _alias_index().items() if v == item_id]
    n = _VENDOR_NAMES.get(item_id)
    if n:
        out.append(n)
    return tuple(out)


# A known ingredient inside a longer word only names that word when what follows it is a cut or a
# part ("黄瓜丝", "五花肉片", "白菜心"). Anything else after it makes a different thing: "红豆腐乳" is
# fermented bean curd, not tofu; "牛肉丸" are meatballs; "花生酱" is a sauce.
CUT_TAIL = frozenset("丝片丁块段条末粒碎泥茸蓉心叶根头尖仁瓣卷馅液薄细结")
# Seasonings that end other foods' names too ("百香果" is a fruit, not 香果).
SUFFIX_UNSAFE = frozenset({"香果"})
# Noodle-like things that end in 粉 but are not a powder or a seasoning.
NOODLE_ENDS = ("河粉", "米粉", "粉丝", "粉条", "粉皮", "凉粉", "肠粉", "螺蛳粉", "米线")


def _sub_hit(t: str, keys) -> str | None:
    """The known word inside ``t`` that names it (see CUT_TAIL), longest and right-most first."""
    best = None
    for k in keys:
        if len(k) < 2 or k == t:
            continue
        i = t.rfind(k)
        if i < 0:
            continue
        tail = t[i + len(k):]
        if len(tail) > 2 or any(c not in CUT_TAIL for c in tail):
            continue
        rank = (len(k), -i)          # longest, then the one that starts first ("牛肉末" -> 牛肉)
        if best is None or rank > best[0]:
            best = (rank, k)
    return best[1] if best else None


def is_known_staple(tok: str) -> bool:
    """A seasoning the kitchen always has, by name ("白醋", "玉米油", "红酱油") — not merely a word that
    ends like one ("奶粉", "石榴粉")."""
    t = (tok or "").strip()
    staples = STAPLES_EXTRA | frozenset(config.get().fridge_staple_aliases)
    if t in _alias_index():
        return False
    return t in staples or any(len(s) >= 2 and t.endswith(s) and s not in SUFFIX_UNSAFE for s in staples)


def classify_token(tok: str) -> tuple[str, str]:
    """For the index builder: one recipe ingredient -> (kind, value); kind is skip / tool / staple /
    main / vendor. main's value is a catalog id, staple's is the name, vendor's is a v_ id."""
    t = (tok or "").strip()
    if (t in DROP_WORDS or len(t) > 10 or re.fullmatch(r"[\W_a-zA-Z0-9]*", t)
            or any(w in t for w in ("?", "？", " or ", "!", "牌子", "品牌", "一个", "一包"))):
        return "skip", t
    idx = _alias_index()
    if t in idx:
        return "main", idx[t]
    bare = t.rstrip("".join(CUT_TAIL)) or t
    if "洋葱" not in t and (bare in GARNISH_WORDS or bare.endswith(GARNISH_WORDS)):
        return "main", "scallion"
    staples = STAPLES_EXTRA | frozenset(config.get().fridge_staple_aliases)
    if t in staples:
        return "staple", t
    if t in _VENDOR_ONLY_NAMES:                 # "板栗" holds 板, a tool word
        return "vendor", _VENDOR_ONLY_NAMES[t]
    if any(w in t for w in TOOL_WORDS) and not any(k in t for k in idx):
        return "tool", t
    if t.endswith(NOODLE_ENDS):
        return "vendor", vendor_id(t)
    # a seasoning that ends the word wins over a food inside it ("红豆腐乳" -> 腐乳)
    if any(len(s) >= 2 and t.endswith(s) and s not in SUFFIX_UNSAFE for s in staples):
        return "staple", t
    hit = _sub_hit(t, idx)
    if hit:
        return "main", idx[hit]
    if t.endswith(STAPLE_SUFFIX) or any(s in t for s in ("调料", "调味料", "香料", "酱汁", "蘸水")):
        return "staple", t
    if any(w in t for w in TOOL_WORDS):
        return "tool", t
    return "vendor", vendor_id(t)


def dish_aliases(name: str) -> list[str]:
    out = set()
    for a, b in (("西红柿", "番茄"), ("番茄", "西红柿"), ("土豆", "马铃薯"), ("西兰花", "西蓝花")):
        if a in name:
            out.add(name.replace(a, b))
    out.discard(name)
    return sorted(out)


# ── the index ───────────────────────────────────────────────────────────

_lock = threading.Lock()
_cache: dict = {"sig": None, "data": None}


def _index_path() -> str:
    env = os.environ.get("KITCHENETTE_RECIPES_INDEX")
    if env:
        return env
    found = sorted(glob.glob(os.path.join(DATA_DIR, "howtocook-*.index.json")))
    if not found:
        raise RecipesUnavailable("no index file")
    return found[-1]


def load() -> dict:
    """{"by_id", "list", "source"}; raises RecipesUnavailable."""
    p = _index_path()
    try:
        st = os.stat(p)
    except OSError as e:
        raise RecipesUnavailable(f"index unreadable: {e}") from e
    sig = (p, st.st_mtime_ns, st.st_size)
    with _lock:
        if _cache["sig"] == sig:
            return _cache["data"]
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if raw.get("schema") != 1 or not isinstance(raw.get("recipes"), list):
            raise ValueError("wrong shape")
        out = _entries(raw)
        for n in raw.get("vendor_items") or ():
            _VENDOR_NAMES[vendor_id(n)] = n
        _VENDOR_ALIAS.clear()
        for n, target in (raw.get("vendor_aliases") or {}).items():
            _VENDOR_ALIAS[vendor_id(n)] = str(target)
    except Exception as e:  # noqa: BLE001
        raise RecipesUnavailable(f"index broken: {e!r}") from e
    data = {"by_id": {r["id"]: r for r in out}, "list": out, "source": raw.get("source") or {}}
    with _lock:
        _cache.update(sig=sig, data=data)
    return data


def _entries(raw: dict) -> list[dict]:
    if raw.get("schema") != 1 or not isinstance(raw.get("recipes"), list):
        raise ValueError("wrong shape")
    out = []
    for r in raw["recipes"]:
        if not r.get("id") or not r.get("name") or r.get("method") not in METHOD_CN:
            raise ValueError(f"incomplete entry {r.get('id')}")
        v = r.get("version", 1)                 # an index from before versions: every entry is 1
        if not isinstance(v, int) or v < 1:
            raise ValueError(f"bad version {r.get('id')}")
        out.append(r if "version" in r else {**r, "version": 1})
    return out


_history: dict = {"dir": None, "sig": None, "by_key": {}}


def _history_dir() -> str:
    """Earlier indexes, kept as they were (history/<name>.r<revision>.index.json next to the index)."""
    return os.path.join(os.path.dirname(os.path.abspath(_index_path())), "history")


def _history_entries() -> dict[tuple[str, int], dict]:
    d = _history_dir()
    files = sorted(glob.glob(os.path.join(d, "*.index.json")))
    sig = tuple((f, os.stat(f).st_mtime_ns) for f in files)
    with _lock:
        if _history["dir"] == d and _history["sig"] == sig:
            return _history["by_key"]
    by_key: dict[tuple[str, int], dict] = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                for r in _entries(json.load(fh)):
                    by_key.setdefault((r["id"], r["version"]), r)
        except Exception as e:  # noqa: BLE001
            log.warning("old recipe index %s unreadable: %r", f, e)
    with _lock:
        _history.update(dir=d, sig=sig, by_key=by_key)
    return by_key


def get(rid: str, version: int | None = None) -> dict | None:
    """A public recipe by id; with a version, that version (a pot keeps the version it followed: an
    older one is read from the kept earlier indexes). None when not found."""
    rid = (rid or "").strip()
    try:
        r = load()["by_id"].get(rid)
        if version is None or (r is not None and r["version"] == int(version)):
            return r
        return _history_entries().get((rid, int(version)))
    except (RecipesUnavailable, ValueError, OSError):
        return None


def vendor_alias(item_id: str) -> str | None:
    """A recipe-only ingredient the index now calls something else -> the id it uses now (a box bought
    under the old name counts as the new thing), else None."""
    if _cache["data"] is None:
        try:
            load()
        except RecipesUnavailable:
            return None
    return _VENDOR_ALIAS.get(str(item_id))


def item_name(item_id: str) -> str:
    from . import fridge
    it = fridge.item(item_id)
    return it["name"] if it else item_id


def item_sold(item_id: str) -> bool:
    """Can it be bought at the shop right now (catalog, extras while on, custom kinds)?"""
    from . import fridge
    if str(item_id).startswith("v_"):
        return play.on("recipes_public") and fridge.item(item_id) is not None and not is_vendor_only(item_id)
    return any(it["id"] == item_id for it in fridge.all_items())


def items_text(entries: list[dict]) -> str:
    return "、".join((e.get("name") or item_name(e["item"])) + (f"×{e['qty']}" if e.get("qty", 1) > 1 else "")
                    for e in entries) or tp("staples_none")


# ── feasibility (pure) ──────────────────────────────────────────────────

def fridge_snapshot(batches: list[dict]) -> dict[str, int]:
    from . import fridge
    have: dict[str, int] = {}
    for b in batches:
        k = fridge.canon(b["item_id"])
        have[k] = have.get(k, 0) + int(b["qty"])
    return have


def feasibility(recipes_main: list[list[dict]], have: dict[str, int]) -> dict:
    """Several recipes at once (a menu, buying for a recipe): shared ingredients add up.
    Returns {need, short, ok}."""
    from . import fridge
    need: dict[str, int] = {}
    for main in recipes_main:
        for e in main:
            k = fridge.canon(e["item"])
            need[k] = need.get(k, 0) + int(e.get("qty") or 1)
    short = {k: n - have.get(k, 0) for k, n in need.items() if have.get(k, 0) < n}
    return {"need": need, "short": short, "ok": not short}


def covers(main: list[dict], wanted_ids: dict[str, int]) -> list[str]:
    """Main ingredients the role's list does not cover (empty = covered)."""
    from . import fridge
    got: dict[str, int] = {}
    for k, n in wanted_ids.items():
        got[fridge.canon(k)] = got.get(fridge.canon(k), 0) + n
    return [e["item"] for e in main if got.get(fridge.canon(e["item"]), 0) < int(e.get("qty") or 1)]


def short_text(short: dict[str, int]) -> str:
    parts = []
    for k, n in short.items():
        nm = item_name(k) + (f"×{n}" if n > 1 else "")
        parts.append(nm if item_sold(k) else tp("rec_not_sold", name=nm))
    return "、".join(parts)


# ── stopped recipes and dislikes ────────────────────────────────────────

def stopped_ids(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT recipe_id FROM recipe_flags WHERE stopped=1").fetchall()}


def dislikes(conn, who: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT item FROM kitchen_prefs WHERE who=? AND kind='dislike'",
                                       (who,)).fetchall()}


def _blocked(r: dict, stop: set[str], dis: set[str]) -> bool:
    if r["id"] in stop:
        return True
    if not dis:
        return False
    from . import fridge
    dis_c = {fridge.canon(d) for d in dis}
    return any(fridge.canon(e["item"]) in dis_c for e in r["main"] + r.get("optional", []))


def search(q: str, *, conn=None, who: str | None = None, limit: int = 50) -> list[dict]:
    """By name, alias, ingredient or category. Stopped recipes and the human's dislikes are left out."""
    from . import fridge
    q = (q or "").strip()
    if not q:
        return []
    data = load()
    stop = stopped_ids(conn) if conn is not None else set()
    dis = dislikes(conn, who) if conn is not None and who else set()
    iid = fridge.resolve(q, gone=True) or _alias_index().get(q) or vendor_resolve(q)
    iid = fridge.canon(iid) if iid else iid
    hits = []
    for r in data["list"]:
        if _blocked(r, stop, dis):
            continue
        score = 0
        if q == r["name"] or q in r.get("aliases", []):
            score = 100
        elif q in r["name"]:
            score = 60
        elif iid and any(fridge.canon(e["item"]) == iid for e in r["main"]):
            score = 40
        elif iid and any(fridge.canon(e["item"]) == iid for e in r.get("optional", [])):
            score = 20
        elif q in (r.get("category_label") or "") or q == r.get("category"):
            score = 10
        if score:
            hits.append((score, r))
    hits.sort(key=lambda x: (-x[0], len(x[1]["main"]), x[1]["name"]))
    return [r for _s, r in hits[:limit]]


def categories() -> list[str]:
    seen: list[str] = []
    for r in load()["list"]:
        if r.get("category_label") and r["category_label"] not in seen:
            seen.append(r["category_label"])
    return seen


def line(r: dict) -> str:
    return tp("browse_line", name=r["name"], rid=r["id"], items=items_text(r["main"]),
              method=METHOD_CN.get(r["method"], r["method"]), minutes=r["minutes"])


# ── today you could try ─────────────────────────────────────────────────

_weather_fn = None


def set_weather_provider(fn) -> None:
    """Install a weather reader directly (overrides [recipes] weather_provider)."""
    global _weather_fn
    _weather_fn = fn


def _weather_reader():
    if _weather_fn is not None:
        return _weather_fn
    spec = config.get().recipes_weather_provider
    if not spec:
        return None
    mod, _, attr = spec.partition(":")
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    return getattr(importlib.import_module(mod), attr or "read")


def weather_signals(now: float) -> dict:
    """Three inputs that may add up: the weather (None when not configured or unreadable), the hour, the season."""
    dt = clock.local(now)
    sig = {"rain": None, "cold": None, "hot": None, "night": dt.hour in NIGHT_HOURS,
           "season": ("winter" if dt.month in (12, 1, 2) else "summer" if dt.month in (6, 7, 8)
                      else "spring" if dt.month in (3, 4, 5) else "autumn")}
    try:
        fn = _weather_reader()
        if fn is not None:
            w = fn() or {}
            if w.get("rain") is not None:
                sig["rain"] = bool(w["rain"])
            if w.get("temp_c") is not None:
                sig["cold"] = float(w["temp_c"]) <= WEATHER_COLD_C
                sig["hot"] = float(w["temp_c"]) >= WEATHER_HOT_C
    except Exception as e:  # noqa: BLE001
        log.info("weather unreadable, hour and season only: %r", e)
    return sig


def _weather_bonus(r: dict, sig: dict) -> float:
    m = r["method"]
    b = 0.0
    warm = m in ("boil", "steam") or r.get("category") == "soup"
    cool = m == "mix" or (m == "stirfry" and len(r["main"]) <= 2)
    if sig.get("rain") or sig.get("cold") or sig.get("night"):
        b += 1.0 if warm else 0.0
    if sig.get("hot"):
        b += 1.0 if cool else 0.0
    if sig.get("season") == "winter" and warm:
        b += 0.3
    if sig.get("season") == "summer" and cool:
        b += 0.3
    return b


def weather_line(sig: dict) -> str:
    return "".join(tp(f"weather_{k}") for k in ("rain", "cold", "hot", "night") if sig.get(k))


def _stable(seed: str) -> float:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


PICKS_MAX = 3      # "today you could try": three dishes in all


def recommend(*, have: dict[str, int], meh_items: set[str], cooked_names: set[str], recent_names: set[str],
              stop: set[str], dis: set[str], sig: dict, day: str, who: str) -> dict:
    """Three dishes in all (PICKS_MAX), as the receipt reads: two that the fridge can make now and
    one that is one thing short. When nothing is one thing short, the third is one more that can be
    made now; when fewer can be made now, fewer are given — a dish that is short is never added to
    fill the gap, and at most one is listed. Among the ones that can be made: first one that uses up
    something going stale, then one never made before, then the rest by weather and the day's draw.
    Dishes cooked recently are skipped. The same day and fridge give the same picks.
    Returns {"ready": [r...], "near": [(r, short)...]}, len(ready) + len(near) <= PICKS_MAX."""
    data = load()
    pool = [r for r in data["list"]
            if r.get("category") not in NOT_A_MEAL and r["main"]
            and not _blocked(r, stop, dis) and r["name"] not in recent_names]

    def score(r):
        return _weather_bonus(r, sig) + _stable(f"{day}:{who}:{r['id']}")
    ready, near = [], []
    for r in pool:
        f = feasibility([r["main"]], have)
        if f["ok"]:
            ready.append(r)
        elif len(f["short"]) == 1 and sum(f["short"].values()) <= 2:
            near.append((r, f["short"]))
    ready.sort(key=score, reverse=True)
    near.sort(key=lambda x: score(x[0]), reverse=True)
    near = near[:1]
    room = PICKS_MAX - len(near)
    picked: list[dict] = []

    def take(cands):
        for r in cands:
            if len(picked) < room and r not in picked:
                picked.append(r)
                return True
        return False
    take([r for r in ready if any(e["item"] in meh_items for e in r["main"])])
    take([r for r in ready if r["name"] not in cooked_names])
    while take(ready):
        pass
    return {"ready": picked, "near": near}


def kitchen_day(ts: float) -> str:
    """The kitchen's day turns over at the snack reset hour."""
    from datetime import timedelta
    return (clock.local(ts) - timedelta(hours=config.get().snacks_day_boundary_hour)).strftime("%Y-%m-%d")


def today_text(who: str, now: float) -> str:
    """The "today you could try" paragraph (raises; the caller turns a failure into one line)."""
    from . import db, fridge
    conn = db.connect()
    try:
        batches = fridge._batches(conn, who, now)
        have = fridge_snapshot(batches)
        meh = {b["item_id"] for b in batches
               if b["freshness"] == fridge.MEH and not fridge.hidden_freshness(b["item_id"])}
        cooked = {r[0] for r in conn.execute("SELECT DISTINCT dish FROM cook_sessions WHERE who=?"
                                             " AND status='served'", (who,)).fetchall()}
        recent = {r[0] for r in conn.execute(
            "SELECT DISTINCT dish FROM cook_sessions WHERE who=? AND started_at>?",
            (who, now - config.get().recipes_avoid_days * 86400)).fetchall()}
        stop = stopped_ids(conn)
        dis = dislikes(conn, who)
        conn.commit()
    finally:
        conn.close()
    sig = weather_signals(now)
    rec = recommend(have=have, meh_items=meh, cooked_names=cooked, recent_names=recent, stop=stop, dis=dis,
                    sig=sig, day=kitchen_day(now), who=who)
    lines = []
    wl = weather_line(sig)
    if wl:
        lines.append(wl)
    if rec["ready"]:
        lines.append(tp("rec_head_only_one") if len(rec["ready"]) == 1 else tp("rec_head_ready"))
        for r in rec["ready"]:
            lines.append(tp("rec_line", name=r["name"], rid=r["id"], items=items_text(r["main"]),
                            method=METHOD_CN[r["method"]], minutes=r["minutes"]))
    if rec["near"]:
        lines.append(tp("rec_head_near"))
        for r, sh in rec["near"]:
            lines.append(tp("rec_line_near", name=r["name"], rid=r["id"], missing=short_text(sh)))
    if not rec["ready"] and not rec["near"]:
        lines.append(tp("rec_none"))
    if dis:
        lines.append(tp("rec_dislike", items="、".join(item_name(i) for i in sorted(dis))))
    return "\n".join(lines)
