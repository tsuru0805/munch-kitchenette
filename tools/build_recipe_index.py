"""Build the small recipe index from HowToCook (Anduin2017/HowToCook, Unlicense) — no network, read-only.

    python tools/build_recipe_index.py <path to a HowToCook checkout> [--out src/kitchenette/data]

Writes ``howtocook-<short commit>.index.json``: per dish only id / name / aliases / main ingredients /
optional ones / method (one of seven) / minutes / category / source line. **No steps.** The method
and the minutes are estimated here (the original has neither).

Ids stay the same across versions: hc- + sha1 of the path (without .md and 「的做法」), and an entry
with the same name and category as in the previous index keeps its old id (--prev, or the newest
index in --out).

Versions (a pot records id + version and must still find what it followed): every entry
carries ``version``; one whose content (name, ingredients, method, minutes, category) differs from the
previous index gets the previous version + 1, the rest keep theirs. The file carries ``revision``;
when anything changed, the previous index is kept byte for byte as
``history/howtocook-<commit>.r<revision>.index.json`` (``recipes.get(id, version)`` reads it there).
Recipe-only ingredients the index no longer names (an old spelling) get ``vendor_aliases``: old name
-> the id used now, so a box bought under the old name still counts and is taken.

Ingredients are sorted by the rules in :mod:`kitchenette.recipes` (purely mechanical):
  main     -> an item of the shop catalog ([fridge] ingredients + recipes.EXTRA_ITEMS)
  staple   -> seasonings always at hand (recipes.STAPLES_EXTRA + [fridge] staple_aliases)
  tool     -> dropped
  the rest -> recipe-only ingredients (v_ ids; the shop sells them while the public recipes are on)
Every ingredient of a list line counts, with its alternatives and its own "optional" mark (see
"reading the ingredient list" below). The minutes come from the page's opening, figures or words
(:func:`minutes_pick`). What the rules cannot read is fixed by hand in ``FIXES`` / ``MINUTES``, each
with its reason; names of the previous index's recipe-only ingredients are kept so old stock resolves.

After building, go over the result with ``tools/check_recipe_index.py <checkout>``: it lists the entries
that look wrong; what a person checked and found right is in ``tools/recipe_checked.txt``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kitchenette import kitchen, recipes as rc  # noqa: E402

SECTION_RE = re.compile(r"##\s*必备原料和工具(.*?)(?=\n##\s)", re.S)
CALC_RE = re.compile(r"##\s*计算(.*?)(?=\n##\s)", re.S)
ITEM_RE = re.compile(r"^\s*[*+-]\s+(.+)$", re.M)

# Default minutes per method (only when the text gives no time; all estimates)
METHOD_MINUTES = {"stirfry": 15, "fry": 15, "deepfry": 30, "boil": 40, "steam": 30, "bake": 40, "mix": 10}
# category -> label
CATEGORY_LABEL = {"aquatic": "水产", "breakfast": "早餐", "condiment": "酱料", "dessert": "甜品",
                  "drink": "饮品", "meat_dish": "荤菜", "semi-finished": "半成品", "soup": "汤",
                  "staple": "主食", "vegetable_dish": "素菜"}
# Technique words in the steps (used when the name gives no method, or only the default stir-fry)
_OP_VERBS = (("deepfry", ("油炸", "下锅炸", "炸至", "复炸")), ("steam", ("上锅蒸", "蒸锅", "蒸 ", "蒸制", "隔水蒸")),
             ("bake", ("烤箱", "空气炸锅", "烤盘")), ("boil", ("炖", "煮", "焖", "小火慢")),
             ("fry", ("煎至", "平底锅", "煎 ")), ("mix", ("拌匀", "凉拌", "搅拌均匀")))


# ── reading the ingredient list ─────────────────────────────────────────
# A line of the list can hold several ingredients ("黄瓜、面筋块、绿豆芽、鸡蛋"), each may offer
# alternatives ("猪肉/牛肉", "料酒或啤酒"), and some lines are notes, labels or descriptions. Every
# ingredient on a line counts (an earlier version kept only the first, and lost e.g. the meat and the
# rice noodles of 炒河粉).

# "optional" written next to one ingredient: （可选）, （可选，…）, [可选], 可选：…, …可选
OPT_RE = re.compile(r"[（(\[【]\s*(可选|备选)\s*([)）\]】，,、]|但)|[（(]\s*低脂版本\s*[)）]|^\s*(可选|备选)\s*[：:]|(可选|备选|可以不用)\s*[)）\]】]?\s*$|可选但")
# a whole line that only offers extras
LINE_OPTIONAL = ("可根据", "可依据", "自行添加", "选择增加", "装饰", "点缀")
# a sub-heading or a plain sentence that makes the lines under it optional
BLOCK_OPTIONAL = ("可选", "选配", "点缀", "例如", "比如", "自行选择")
# Words before a colon that only label what follows ("主料：…", "炒料：…", "必备：…").
LABELS = ("主料", "辅料", "原料", "炒料", "调料", "配料", "小料", "调味料", "其他调味料", "全香料", "必备",
          "可选", "备选", "")
ALT_RE = re.compile(r"或者|或|/| or |二选一")
OR_WORDS = re.compile(r"或者|或| or ")      # a slash only joins the two words next to it ("猪肉/牛肉")
# pieces that describe the previous ingredient or the cooking, not an ingredient
DESC_STARTS = ("用于", "用来", "建议", "其中", "需", "参见", "见", "火候", "不够", "不要", "最好", "记得", "能够",
               "一般", "选择", "推荐")
# words that describe the previous ingredient when they stand alone ("黑鳕鱼，带皮")
DESC_WORDS = frozenset({"带皮", "去皮", "去骨", "去壳", "带骨", "带脚"})
LEAD_STRIP = re.compile(r"^(例如|比如|如|也可以是|可以是|也可以|袋装|网购|盒装|带皮|去皮|去壳|去骨|带骨|去心|新鲜|半干)(?=..)")
_CN_NUM = "一二两三四五六七八九十半几数"
_CN_UNIT = "个颗根片只条块瓣把勺段粒张包盒袋瓶罐碗杯克斤两"
# A few ways the guide writes one ingredient that the rules cannot read (whole piece -> name; "" drops it).
PIECE_RENAME = {"炒河粉": "河粉", "爪猪前肘": "猪肘", "带脚": "", "大肉": "五花肉", "摊鸡蛋皮": "鸡蛋",
                "农村玉米鸡": "鸡", "土豆干粉条": "粉条", "安琪甜酒曲": "甜酒曲",
                "面筋块": "面筋", "羊排肉": "羊排", "东北酸菜": "酸菜", "袋泡红茶": "红茶", "水浸金枪鱼罐头": "金枪鱼罐头",
                "午餐肉罐头": "午餐肉", "罐头菠萝片": "菠萝罐头", "甘竹牌鲮鱼罐头": "豆豉鲮鱼罐头", "北京麻辣方便面": "方便面",
                "汤力水气泡水": "汤力水", "茉莉绿茶茶叶": "茉莉绿茶", "爱尔兰百利甜酒": "百利甜酒", "蓝天原味伏特加": "伏特加",
                "放凉浓缩咖啡": "浓缩咖啡", "红茶包": "红茶", "酸梅晶固体饮料": "酸梅晶"}


def _split_top(s: str, seps: str) -> list[str]:
    """Split on any of ``seps`` outside brackets."""
    out, buf, depth = [], "", 0
    for ch in s:
        if ch in "（(【[":
            depth += 1
        elif ch in "）)】]" and depth:
            depth -= 1
        if ch in seps and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return out


def _unbracket(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)       # keep a markdown link's text
    s = s.replace("`", "").replace("*", "")
    prev = None
    while prev != s:                                      # nested brackets, innermost first
        prev = s
        s = re.sub(r"[（(【\[][^（(【\[）)】\]]*[)）】\]]", "", s)
    return re.sub(r"[（(【\[].*$", "", s)                 # an unclosed one runs to the end


def _clean(s: str) -> str:
    s = s.strip(" 　-`。.…")
    if s in rc.DROP_WORDS or s in DESC_WORDS or "牌子" in s or "品牌" in s:
        return ""
    s = LEAD_STRIP.sub("", s)
    s = re.sub(r"^[^的]{1,6}的(?=.)", "", s)                             # "泡好的粉丝", "未过期的…"
    s = re.sub(r"\s+", "", s)
    s = re.sub(rf"^[\d\.]+[a-zA-Z]*[{_CN_UNIT}]?", "", s)                # "2cm 两段葱段", "1 袋半成品薯条"
    s = re.sub(rf"^[{_CN_NUM}]+[小大]?[{_CN_UNIT}]", "", s)               # "两片姜片"
    s = re.sub(rf"[{_CN_NUM}]+[小大]?[{_CN_UNIT}].*$", "", s) if len(s) > 2 else s   # "八角三小片"
    s = re.sub(r"[\d\.]+.*$", "", s).strip()
    s = re.sub(r"(各|等.*|少许|适量|若干|左右)$", "", s)
    s = s.strip(" 　-`。.…）)】]")
    s = PIECE_RENAME.get(s, s)
    return "" if s in rc.DROP_WORDS else s


def _pieces(raw: str, block_opt: bool = False, whole_or: bool = False) -> list[tuple[list[str], bool]]:
    """One line of the ingredient list -> [(alternatives, optional)]. A note line ("注：…", or one that
    exclaims) holds none."""
    raw = raw.strip()
    if raw.startswith("注") or raw.startswith(">") or "！" in _unbracket(raw) or "!" in _unbracket(raw):
        return []
    line_opt = block_opt or any(w in raw for w in LINE_OPTIONAL) or bool(re.match(r"^[（(\[【]\s*(可选|备选)", raw))
    raw = re.sub(r"^[（(\[【]\s*(可选|备选)\s*[)）\]】]", "", raw).strip()
    parts = _split_top(raw, "：:")
    if len(parts) > 1:
        label = _clean(_unbracket(parts[0]))
        if label in ("原则", "注", "注意"):
            return []
        is_label = label in LABELS or label.endswith(("材料", "食材")) or label in rc.DROP_WORDS
        if is_label and re.match(r"^\s*(可选|备选)", parts[0]):
            line_opt = True
        body = "：".join(parts[1:]) if is_label else parts[0]
    else:
        body = raw
    out = []
    pieces = [x for x in _split_top(body, "，,、；;") if _unbracket(x).strip()]
    if whole_or and len(pieces) > 1:
        # a line a person read as "any one of the whole list" (WHOLE_OR); by default 或 only joins the
        # words of its own item ("鸡肉、土豆、黄油或玉米油" is chicken, potato, and butter-or-oil)
        alts, opt = [], line_opt
        for piece in pieces:
            opt = opt or bool(OPT_RE.search(piece.strip()))
            piece = re.sub(r"^(例如|比如|如)", "", _unbracket(piece).strip())
            if piece and not piece.startswith(DESC_STARTS):
                alts += [a for a in (_clean(x) for x in ALT_RE.split(piece)) if a]
        return [(alts, opt)] if alts else []
    for piece in pieces:
        opt = line_opt or bool(OPT_RE.search(piece.strip()))
        piece = re.sub(r"[—–]+\s*可(以)?用(.+?)(替代|代替)", r"或\2", piece)
        piece = re.sub(r"^(例如|比如|如)", "", _unbracket(piece).strip())
        if not piece or piece.startswith(DESC_STARTS):
            continue
        for sub in re.split(r"(?<=[一-鿿])和(?=[一-鿿])", piece):
            alts = [a for a in (_clean(x) for x in ALT_RE.split(sub)) if a]
            if alts:
                out.append((alts, opt))
    return out


def _pick(alts: list[str]) -> tuple[str, str, str]:
    """(kind, value, the name used) for one ingredient with alternatives: a shop item first, then a
    seasoning, then anything else that is food. Alternatives to a tool are tools ("炭火或燃气"); when one
    alternative is a seasoning always at hand, the whole is that seasoning."""
    seen = [(a,) + rc.classify_token(a) for a in alts]
    if any(kind == "tool" for _a, kind, _v in seen):
        return "tool", "", alts[0]
    # one of them is always at hand ("柠檬汁或白醋", "黄油或玉米油"): nothing needs buying
    if len(alts) > 1:
        for a in alts:
            if rc.is_known_staple(a):
                return "staple", a, a
    for want in ("main", "staple", "vendor"):
        for a, kind, val in seen:
            if kind == want:
                return kind, val, a
    return "skip", "", alts[0]


def _section_pieces(section: str, whole_or: frozenset = frozenset()):
    """Every ingredient of the section with its optional flag, following sub-headings and the plain
    sentences that make what is under them optional ("下列原料供…选配", "额外用作点缀的食材，可选").
    ``whole_or``: list lines (as written) whose 或 takes the whole list (see WHOLE_OR)."""
    block_opt = False
    example_parent = False
    for line in section.splitlines():
        if not line.strip():
            continue
        m = ITEM_RE.match(line)
        if not m:                                   # a sub-heading (or a short label line) resets;
            hit = any(w in line for w in BLOCK_OPTIONAL)      # a longer sentence can only add
            bare = re.sub(r"[#*：:\s]", "", line)
            block_opt = hit if (line.lstrip().startswith("#") or len(bare) <= 12) else (block_opt or hit)
            continue
        nested = len(line) - len(line.lstrip()) >= 2
        if not nested:
            example_parent = any(w in m.group(1) for w in ("例如", "比如"))
        yield from _pieces(m.group(1), block_opt or (nested and example_parent),
                           whole_or=m.group(1).strip() in whole_or)


# List lines whose 或 takes the whole list ("any one of these"), read by a person on the page. By rule
# 或 only joins the words of its own item. path -> {line as written: why}
WHOLE_OR: dict[str, dict[str, str]] = {
    "dishes/aquatic/芥末黄油罗氏虾/芥末黄油罗氏虾.md": {
        "料酒、朗姆酒或啤酒": "第 34 行「料酒、朗姆酒或啤酒 15g 到 30g」是一份的量,第 45 行「加入酒(料酒、啤酒可以放…)」"},
    "dishes/breakfast/意式香肠北非蛋.md": {
        "意式猪肉香肠（去肠衣）、辣香肠 (Chorizo) 或切块的午餐肉": "三种肉肠任用一种,做法里只放一种「香肠」"},
    "dishes/breakfast/煎饺.md": {"芝麻、葱花（切段）或其他配料": "出锅撒的点缀,任选"},
}


# Entries the rules cannot read right, fixed by hand after reading the guide's page (path -> the
# ingredient names to use; each name still goes through the same sorting). Keep the reason.
FIXES: dict[str, dict] = {
    # a free-form page: "any noodles, any vegetables"; only the noodles are needed
    "dishes/staple/汤面.md": {"main": ["面条"], "optional": ["鸡蛋", "生菜", "菠菜", "油麦菜", "青椒", "番茄", "胡萝卜"]},
    # made from a bagged kit; what follows "其中应该包含" is what the bag holds
    "dishes/staple/螺蛳粉.md": {"main": ["螺蛳粉"], "optional": []},
    # wrappers are "any tube-shaped thing" (one of them is needed) and the filling is "mainly minced
    # pork". An entry has no "one of these" group, so it is the page's first-listed wrapper, 青椒, with
    # the basic pork filling; the other wrappers and fillings are optional swaps.
    "dishes/meat_dish/桂林十八酿/桂林十八酿.md": {
        "main": ["青椒", "猪肉馅"], "optional": ["苦瓜", "茄子", "豆腐", "香菇", "冬瓜", "番茄", "虾滑馅", "鱼肉馅"]},
    # 米粉 here is rice flour (the page says 用大米研磨成的粉), not rice noodles
    "dishes/staple/茄子肉煎饼/茄子肉煎饼.md": {"main": ["大米粉", "鸡蛋", "腊肉", "茄子"], "optional": []},
    # "叶菜类蔬菜": any leafy vegetable; 青菜 (小白菜 / 上海青 / 油菜 / 油麦菜) stands for it
    "dishes/vegetable_dish/水油焖蔬菜.md": {"main": ["青菜"], "optional": []},
    # the jelly powder is the dish, not a seasoning
    "dishes/dessert/龟苓膏/龟苓膏.md": {"main": ["龟苓膏粉"], "optional": []},
    # "面" (the page's word) is noodles
    "dishes/staple/老干妈拌面.md": {"main": ["面条"], "optional": []},
    # the jelly is made from the pea starch; peanuts go on top
    "dishes/staple/凉粉/凉粉.md": {"main": ["豌豆淀粉", "花生"], "optional": []},
    # the tea powder is the tea
    "dishes/drink/泰国手标红茶/泰国手标红茶.md": {"main": ["茶粉", "炼乳", "牛奶"], "optional": []},
    # "通心粉" is pasta and "肉类" is the bacon of the name
    "dishes/meat_dish/奶酪培根通心粉/奶酪培根通心粉.md": {"main": ["通心粉", "奶酪", "培根", "洋葱", "黄油", "牛奶"],
                                                         "optional": []},
}

# Minutes read by hand. The builder takes the first time figure of the page's opening, which on some
# pages is a step ("炒制过程约 15 分钟" after a total of 1 hour), a total that counts hours of waiting, or
# garbled. Rule for these: the page's whole time, without any wait of an hour or more that is done
# before the cooking starts (soaking, marinating, settling) or after it ends (chilling, setting,
# overnight); waiting in the middle (dough rising, a long simmer) stays.
# path -> (minutes, how they were read)
MINUTES: dict[str, tuple[int, str]] = {
    "dishes/drink/冰粉/冰粉.md": (30, "约 3 小时,其中 2.5 小时为静置凝固"),
    "dishes/dessert/酸奶意式奶冻/酸奶意式奶冻.md": (60, "约 5 小时,其中冷藏 4 小时"),
    "dishes/drink/泰国手标红茶/泰国手标红茶.md": (20, "约 4 小时 20 分钟,其中冰箱 4 小时"),
    "dishes/meat_dish/甜辣烤全翅.md": (60, "约 3 小时,其中冷藏静置腌制 120 分钟"),
    "dishes/meat_dish/黄油鸡.md": (45, "共约 1 小时 45 分钟,其中提前腌制 1 小时"),
    "dishes/meat_dish/奥尔良风味烤鸡腿/奥尔良风味烤鸡腿.md": (60, "约 3 小时,其中冷藏腌制 2-4 小时(按 2 小时算);开头的 20 分钟只是手动操作,不含烤"),
    "dishes/soup/银耳莲子粥/银耳莲子粥.md": (90, "约 3.5 小时,其中银耳莲子提前浸泡 2 小时"),
    "dishes/meat_dish/梅菜扣肉/梅菜扣肉.md": (90, "约 2.5 小时,连同浸泡梅菜 1 小时"),
    "dishes/staple/印度烤饼.md": (30, "总耗时约 1.5 小时,其中提前发酵 1 小时"),
    "dishes/meat_dish/贵州辣子鸡/贵州辣子鸡.md": (90, "原文「预计需要 1.大约 5 小时」,读作 1.5 小时"),
    "dishes/meat_dish/无骨鸡爪/无骨鸡爪.md": (135, "约 8 小时 15 分钟,其中冰箱腌一晚 6 小时"),
    "dishes/meat_dish/猪皮冻/猪皮冻.md": (120, "约 24 小时,其中提前浸泡 12 小时、之后冷藏凝固;熬煮 90 分钟加焯水搓洗"),
    "dishes/meat_dish/酱牛肉/酱牛肉.md": (200, "约 10 小时,含浸泡 1 小时、腌制 4-6 小时、之后冷藏;炖 180 分钟加焯水"),
    "dishes/drink/酸梅汤/酸梅汤.md": (60, "约 6 小时,含提前浸泡 2 小时与冷藏;两煎 40+20 分钟"),
    "dishes/meat_dish/小炒肉.md": (60, "开头「从备料到出锅大约需要 1 小时,其中腌制 30 分钟,炒制过程约 15 分钟」,原取了 15"),
    "dishes/meat_dish/老式锅包肉/老式锅包肉.md": (30, "约 90 分钟,其中淀粉加水静置沉降 60 分钟(开炸之前)"),
    "dishes/meat_dish/卤菜/卤菜.md": (60, "开头「提前浸泡去血水、熬糖色和高压卤制约需 1 小时,再浸泡过夜」"),
    "dishes/vegetable_dish/包菜炒鸡蛋粉丝/包菜炒鸡蛋粉丝.md": (20, "约 1 小时 20 分钟,其中粉丝先冷水浸泡 1 小时"),
    "dishes/aquatic/红烧鱼头.md": (45, "全程(含腌制)约 2-2.5 小时,其中腌制静置 1-2 小时"),
    "dishes/drink/冬瓜茶.md": (150, "约 4-5 小时,其中熬之前冷藏 2 小时;熬 1-2 小时"),
    "dishes/condiment/草莓酱/草莓酱.md": (60, "约 2 小时,其中熬之前静置 1 小时"),
    "dishes/breakfast/韩国麻药鸡蛋.md": (20, "约 1.5 小时,含之后冷藏入味 1-2 小时;煮蛋 7 分钟加调汁"),
    "dishes/breakfast/温泉蛋/温泉蛋.md": (30, "开头「耐心等待约半小时」,这段等待就是 70℃ 保温 25 分钟再焖 3 分钟"),
    "dishes/semi-finished/速冻水饺.md": (15, "开头没写;下饺子后约 8 分钟浮起,加烧水"),
    "dishes/vegetable_dish/凉拌木耳/凉拌木耳.md": (60, "开头没写;泡发约 45 分钟、煮 2 分钟、入味约 15 分钟"),
}


def _fixed(fix: dict, calc: str) -> tuple[list, list]:
    out = ([], [])
    for i, key in enumerate(("main", "optional")):
        for n in fix.get(key, ()):
            kind, val, tok = _pick([n])
            if kind == "staple":                  # a person said it is the ingredient here
                kind, val = "vendor", rc.vendor_id(tok)
            if kind == "vendor":
                rc._VENDOR_NAMES[val] = tok
            elif kind != "main":
                raise SystemExit(f"FIXES: {n} is not an ingredient ({kind})")
            if all(x["item"] != val for x in out[0] + out[1]):
                out[i].append({"item": val, "qty": _qty(calc, val, rc.names_of(val) + (tok,))})
    return out


def _dish_name(path: Path, text: str) -> str:
    m = re.search(r"^#\s*(.+?)\s*$", text, re.M)
    name = m.group(1) if m else path.stem
    name = re.sub(r"的(做法|制作方法|做法与吃法)$", "", name).strip()
    return name or path.stem


_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# a clause that names the time at the stove, apart from waiting
HANDS_WORDS = ("实际动手", "实际操作", "动手操作", "手动操作", "动手时间", "正式制作", "烹饪时间", "实际烧制",
               "不算冷藏", "除去浸泡", "从准备到出炉")
# a clause that names the dish's whole time
TOTAL_WORDS = ("全程", "整个", "总共", "总计", "总耗时", "从", "预计", "整体", "大约", "约", "需要", "只需", "仅需",
               "一般", "通常", "耗时", "完成", "搞定", "上桌", "出锅")
WAIT_WORDS = ("提前", "腌", "冷藏", "过夜", "发酵", "浸泡", "静置", "冷冻", "等待", "泡发")
# in a clause about waiting, only these make the figure the whole time ("约" alone does not)
WHOLE_WORDS = ("全程", "整个", "总共", "总计", "总耗时", "整体", "从")


def _cn_number(t: str) -> str:
    """Chinese numerals in a time phrase -> digits ("二十分钟" -> "20分钟", "一个半小时" -> "1.5小时",
    "半小时" -> "30分钟", "十几分钟" -> "15分钟", "几分钟" / "三五分钟" -> "5分钟")."""
    t = re.sub(r"(\d)\s+(分钟|小时|个)", r"\1\2", t)
    t = re.sub(r"(?<![一二两三四五六七八九十个\d])半\s*(个)?\s*小时", "30分钟", t)
    t = re.sub(r"几十\s*分钟", "30分钟", t)
    t = re.sub(r"十几\s*分钟", "15分钟", t)
    t = re.sub(r"(三五|几)\s*分钟", "5分钟", t)

    def num(m):
        w = m.group(1)
        if "十" in w:
            a, _, b = w.partition("十")
            v = (_CN_DIGIT.get(a, 1) if a else 1) * 10 + (_CN_DIGIT.get(b, 0) if b else 0)
        else:
            v = _CN_DIGIT[w]
        half = ".5" if m.group(2) else ""
        return f"{v}{half}{m.group(3)}"
    return re.sub(r"([一二两三四五六七八九]?十[一二三四五六七八九]?|[一二两三四五六七八九])\s*个?\s*(半)?\s*(分钟|小时)",
                  num, t)


TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:个)?\s*(?:(?:-|~|–|～|到|至)\s*(\d+(?:\.\d+)?)\s*(?:个)?\s*)?(分钟|小时)"
                     r"(?:\s*(\d+)\s*分钟)?")


def time_candidates(text: str) -> list[tuple[int, int, str]]:
    """Every time figure in the page's opening: (minutes, rank, the clause it sits in); rank 0 = the
    time at the stove apart from waiting, 1 = the dish's whole time ("全程", "总共", "从…到…"),
    2 = a looser "about this long", 3 = anything else. Words in brackets ("(不含木耳泡发时间)") are read
    past. A figure in a clause that only talks about waiting is left out."""
    head = text.split("## 必备原料和工具")[0]
    out = []
    for clause in re.split(r"[，。,；;！!\n]", _cn_number(head)):
        main = re.sub(r"[（(][^）)]*[)）]", "", clause)
        for m in TIME_RE.finditer(main):
            a = float(m.group(1))
            b = float(m.group(2)) if m.group(2) else a
            v = (a + b) / 2 * (60 if m.group(3) == "小时" else 1) + (int(m.group(4)) if m.group(4) else 0)
            if not 1 <= v <= 1440:
                continue
            hands = any(w in main for w in HANDS_WORDS)
            whole = any(w in main for w in WHOLE_WORDS)
            if any(w in main for w in WAIT_WORDS) and not hands and not whole:
                continue
            rank = 0 if hands else 1 if whole else 2 if any(w in main for w in TOTAL_WORDS) else 3
            out.append((round(v), rank, clause.strip()))
    return out


def minutes_pick(text: str, method: str) -> tuple[int, str]:
    """(minutes, the clause they came from; "" for the default). The page's opening says how long the
    dish takes, in figures or in words ("约二十分钟", "一个半小时"). The dish's whole time wins over a
    looser figure, which wins over any other, the first one wins a tie; a figure for the time at the
    stove ("实际动手约 30 分钟") wins only when the opening also talks about waiting (soaking,
    chilling, …), so an air fryer's 40 minutes are not cut to "a few minutes of work".
    No figure at all -> a default per method (an estimate)."""
    c = time_candidates(text)
    head = text.split("## 必备原料和工具")[0]
    if not any(w in head for w in WAIT_WORDS):
        c = [x for x in c if x[1] != 0] or [(v, 1, cl) for v, _r, cl in c]
    if c:
        v, _r, clause = min(c, key=lambda x: x[1])
        return v, clause
    return METHOD_MINUTES[method], ""


def _minutes(text: str, method: str) -> int:
    return minutes_pick(text, method)[0]


def _method(name: str, text: str) -> str:
    by_name = kitchen.guess_method(name)
    if by_name != kitchen.METHOD_DEFAULT or any(w in name for w in ("炒", "爆", "烹", "熘")):
        return by_name
    ops = text.split("## 操作", 1)[-1]
    best = None
    for key, words in _OP_VERBS:
        n = sum(ops.count(w) for w in words)
        if n and (best is None or n > best[0]):
            best = (n, key)
    if best:
        return best[1]
    if "炒" in ops:
        return "stirfry"
    return by_name


def _qty(calc: str, item_id: str, names: tuple[str, ...]) -> int:
    """Counted items in the calculation section ("鸡蛋 = 1.5 个 * 份数"), rounded up (1-3); everything else is 1."""
    for n in names:
        m = re.search(re.escape(n) + r"\s*=\s*(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*个", calc)
        if m:
            return max(1, min(3, math.ceil(float(m.group(1)))))
    return 1


def build(repo: Path, prev: dict | None, history: list[dict] | None = None) -> dict:
    """``prev``: the index this one replaces; ``history``: the earlier indexes kept in history/ (an entry
    deleted and later brought back under the same id continues after the highest version it ever had)."""
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    prev_ids = {}
    for r in (prev or {}).get("recipes", []):
        prev_ids[(r["name"], r["category"])] = r["id"]
    out, residue, vendor = [], {}, {}
    for p in sorted(repo.glob("dishes/**/*.md")):
        rel = p.relative_to(repo)
        if "template" in rel.parts:
            continue
        cat = rel.parts[1]
        text = p.read_text(encoding="utf-8")
        sec = SECTION_RE.search(text)
        if not sec:
            continue
        name = _dish_name(p, text)
        calc = (CALC_RE.search(text) or [None, ""])[1] if CALC_RE.search(text) else ""
        main, optional, staples, seen_vendor = [], [], [], {}
        for alts, opt in _section_pieces(sec.group(1), frozenset(WHOLE_OR.get(rel.as_posix(), {}))):
            kind, val, tok = _pick(alts)
            if kind in ("skip", "tool"):
                continue
            if kind == "staple":
                if val not in staples:
                    staples.append(val)
                continue
            if kind == "vendor":                    # a vendor-only thing keeps its own name
                seen_vendor[val] = rc._VENDOR_ONLY[val]["name"] if val in rc._VENDOR_ONLY else tok
            iid = val
            bucket = optional if (opt or iid in rc.GARNISH) else main
            if any(x["item"] == iid for x in main):
                continue
            was = next((x for x in optional if x["item"] == iid), None)
            if was is not None:
                if bucket is main:                  # listed as optional first, required later
                    optional.remove(was)
                    main.append(was)
                continue
            names = rc.names_of(iid) + (tok,)
            bucket.append({"item": iid, "qty": _qty(calc, iid, names)})
        fix = FIXES.get(rel.as_posix())
        if fix is not None:
            main, optional = _fixed(fix, calc)
            seen_vendor = {e["item"]: rc._VENDOR_NAMES[e["item"]] for e in main + optional
                           if e["item"].startswith("v_")}
        for e in main + optional:                  # only names an entry really uses become shop items
            tok = seen_vendor.get(e["item"])
            if tok is not None:
                vendor.setdefault(tok, []).append(name)
                rc._VENDOR_NAMES[e["item"]] = tok
                residue[tok] = residue.get(tok, 0) + 1
        if not main and optional:
            main, optional = optional[:1], optional[1:]
        method = _method(name, text)
        key = str(rel.with_suffix("")).replace("的做法", "")
        rid = prev_ids.get((name, cat)) or "hc-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
        out.append({"id": rid, "name": name, "aliases": rc.dish_aliases(name), "main": main,
                    "optional": optional, "staples": staples, "method": method,
                    "minutes": MINUTES[rel.as_posix()][0] if rel.as_posix() in MINUTES else _minutes(text, method),
                    "category": cat,
                    "category_label": CATEGORY_LABEL.get(cat, cat),
                    "source": f"HowToCook@{commit[:7]} {rel.as_posix()}"})
    seen = {r["source"].split(" ", 1)[1] for r in out}
    stale = sorted(set(FIXES) - seen) + sorted(set(MINUTES) - seen) + sorted(set(WHOLE_OR) - seen)
    if stale:
        raise SystemExit(f"FIXES / MINUTES / WHOLE_OR name pages that were not read: {stale}")
    ids = [r["id"] for r in out]
    if len(ids) != len(set(ids)):
        raise SystemExit("two entries got the same id: change the hash length or fix by hand")
    # versions: an entry whose content is the same as in the previous index keeps its version; one that
    # changed gets the next one (the previous index file is kept in history/, so a pot that followed
    # the old version can still read it)
    prev_by_id = {r["id"]: r for r in (prev or {}).get("recipes", [])}
    # an entry that is gone is a change too (its last version stays readable from history/)
    changed = bool(set(prev_by_id) - {r["id"] for r in out})
    ever: dict[str, int] = {}
    for idx in list(history or []) + ([prev] if prev else []):
        for h in idx.get("recipes", []):
            ever[h["id"]] = max(ever.get(h["id"], 0), h.get("version", 1))
    for r in out:
        old = prev_by_id.get(r["id"])
        if old is None:
            r["version"] = ever.get(r["id"], 0) + 1      # new, or back after a deletion
            changed = changed or prev is not None
        elif _content_key(old) == _content_key(r):
            r["version"] = old.get("version", 1)
        else:
            r["version"] = old.get("version", 1) + 1
            changed = True
    # names from the previous index stay, so things already bought keep their name
    used = set(vendor)
    names = sorted(used | set((prev or {}).get("vendor_items", [])))
    aliases = _vendor_aliases(names, used, (prev or {}).get("vendor_aliases", {}))
    revision = (prev or {}).get("revision", 1)
    if prev is not None and (changed or names != sorted(prev.get("vendor_items", []))
                             or commit != prev.get("source", {}).get("commit")
                             or aliases != prev.get("vendor_aliases", {})):
        revision += 1
    return {"schema": 1, "revision": revision,
            "source": {"repo": "https://github.com/Anduin2017/HowToCook", "commit": commit,
                       "license": "Unlicense(公共领域)"},
            "recipes": out, "vendor_items": names, "vendor_aliases": aliases, "_residue": residue}


CONTENT_FIELDS = ("name", "aliases", "main", "optional", "staples", "method", "minutes", "category",
                  "category_label")


def _content_key(r: dict) -> str:
    return json.dumps([r.get(k) for k in CONTENT_FIELDS], ensure_ascii=False, sort_keys=True)


# Old recipe-only names the cleaning rules alone cannot map to what the index calls the thing now.
OLD_NAME_FIX = {"猪前肘": "猪肘", "剑骨鱼": "鱼", "红泡椒": "", "高筋": ""}


def _vendor_aliases(names: list[str], used: set[str], prev_aliases: dict) -> dict:
    """Old name -> the id the index uses now, for names no entry uses any more, so a box bought under
    the old name counts as the new thing (feasibility and taking from the fridge both compare through
    fridge.canon). "" in OLD_NAME_FIX = no successor (it became a seasoning, or is not a food).
    Aliases of the previous index carry over only while still valid. Checked: every target is a shop
    item or a recipe ingredient the index names, no target is itself an alias, a name in use is never
    one."""
    out = {}
    for n in names:
        if n in used:
            continue
        new = OLD_NAME_FIX.get(n, _clean(n))
        if not new:
            continue
        kind, val, tok = _pick([new])
        if kind == "vendor" and tok not in used and val not in rc._VENDOR_ONLY:
            continue                               # nothing in the index carries that name either
        if kind in ("main", "vendor") and val != rc.vendor_id(n):
            out[n] = val
    for n, target in prev_aliases.items():
        if n not in used and n not in out:
            out[n] = target
    keys = {rc.vendor_id(n): n for n in out}
    for n in list(out):                            # an old target that has itself become an old name
        seen = {rc.vendor_id(n)}
        while out[n] in keys:
            if out[n] in seen:
                raise SystemExit(f"vendor_aliases: a loop through {n}")
            seen.add(out[n])
            out[n] = out[keys[out[n]]]
    catalog = {it["id"] for it in list(rc.config.get().fridge_ingredients) + list(rc.EXTRA_ITEMS)}
    known = {rc.vendor_id(u) for u in used} | set(rc._VENDOR_ONLY)
    for n, target in list(out.items()):
        if target not in catalog and target not in known:
            del out[n]                             # its target is gone: no successor any more
    for n, target in out.items():
        assert target not in keys and n not in used, (n, target)
    return dict(sorted(out.items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out", default=str(ROOT / "src" / "kitchenette" / "data"))
    ap.add_argument("--prev", default="")
    ap.add_argument("--report", action="store_true", help="print what was left unsorted; write nothing")
    a = ap.parse_args()
    repo = Path(a.repo)
    prev, prev_path = None, None
    if a.prev:
        prev_path = Path(a.prev)
    else:
        olds = sorted(Path(a.out).glob("howtocook-*.index.json"))
        prev_path = olds[-1] if olds else None
    if prev_path is not None:
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
    hist_dir = Path(a.out) / "history"
    history = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(hist_dir.glob("*.index.json"))]
    if prev_path is not None and prev_path.parent.name == "history":
        history += [json.loads(f.read_text(encoding="utf-8")) for f in sorted(prev_path.parent.glob("*.index.json"))]
    idx = build(repo, prev, history)
    residue = idx.pop("_residue")
    if a.report:
        print(len(idx["recipes"]), "recipes")
        print(sorted(residue.items(), key=lambda kv: -kv[1]))
        return
    path = Path(a.out) / f"howtocook-{idx['source']['commit'][:7]}.index.json"
    if prev_path is not None and prev is not None and idx["revision"] > prev.get("revision", 1):
        # keep the previous index as it was: old pots read the version they followed from it
        keep = Path(a.out) / "history" / (f"howtocook-{prev['source']['commit'][:7]}"
                                           f".r{prev.get('revision', 1)}.index.json")
        if not keep.exists() and prev_path.resolve() != keep.resolve():
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_bytes(prev_path.read_bytes())
            print("kept the previous index as", keep)
        if prev_path.parent.resolve() == path.parent.resolve() and prev_path.name != path.name:
            prev_path.unlink()                     # built from another commit: one current index only
    path.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", path, len(idx["recipes"]), "recipes;", len(idx["vendor_items"]), "vendor-only items")


if __name__ == "__main__":
    main()
