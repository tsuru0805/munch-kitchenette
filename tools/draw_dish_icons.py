#!/usr/bin/env python3
"""The dishes the cook holds up on a settled card: one small pixel icon per kind of dish, drawn by hand
here, one character per cell (on the card one cell = 10 canvas pixels, the cook's own grid).

Each icon is a vessel plus food. Upper case = vessel or not food (kept as it is in the burnt version);
lower case = food (pressed into four shades of char when burnt); '.' = transparent; 'X' = steam on the
normal version (the burnt one has a thin grey wisp instead).

Usage: python3 tools/draw_dish_icons.py
Writes assets/clawd/dishes/<kind>_cells.png and <kind>_burnt_cells.png (one pixel per cell), and
src/kitchenette/data/dish_icons.json (which kind a dish name belongs to). Needs Pillow and numpy.
"""
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CELL = 10
CANVAS = 720
BG = (243, 240, 230)

PAL = {
    # —— 器皿 / 非食物(与小人共用的几种在前)——
    "W": (251, 247, 238),  # chefWhite:白盘白碗
    "R": (217, 205, 184),  # chefShade:盘口 / 碗口
    "S": (190, 176, 152),  # 盘底朝下的外沿
    "K": (38, 35, 41),     # 小人眼睛那种近黑:锅柄
    "L": (191, 81, 71),    # 漆碗亮面(小人腮红色)
    "D": (168, 50, 43),    # 漆碗暗面
    "N": (72, 104, 140),   # 蓝釉碗
    "M": (52, 76, 104),    # 蓝釉碗暗面
    "P": (60, 74, 87),     # 平底锅(小人领结的深蓝灰)
    "Q": (96, 112, 126),   # 平底锅锅沿
    "T": (214, 170, 100),  # 竹蒸笼
    "U": (168, 122, 64),   # 竹蒸笼暗面 / 编纹
    "A": (156, 158, 166),  # 烤盘
    "Z": (112, 114, 124),  # 烤盘暗面
    "C": (164, 198, 176),  # 青瓷浅碗
    "E": (118, 160, 138),  # 青瓷暗面
    "O": (206, 150, 98),   # 陶碗
    "V": (150, 102, 64),   # 陶碗暗面 / 筷子
    "I": (214, 232, 238),  # 玻璃杯亮面
    "J": (150, 186, 200),  # 玻璃杯边
    "X": (178, 172, 180),  # 热气(只在正常版)
    "F": (110, 70, 44),    # 筷子
    "B": (255, 254, 250),  # 骨头(不算食物,糊了也是白的)
    "G": (226, 216, 196),  # 骨头暗面
    # —— 食物 ——
    "g": (110, 172, 72),   # 绿菜
    "h": (62, 120, 52),    # 深绿
    "y": (246, 192, 48),   # 蛋黄
    "z": (222, 148, 36),   # 蛋黄暗面
    "o": (240, 125, 50),   # 胡萝卜 / 橙
    "r": (216, 70, 60),    # 红(番茄 / 樱桃 / 吸管)
    "b": (172, 100, 52),   # 煎过的肉 / 面包皮
    "d": (112, 62, 38),    # 深褐
    "l": (220, 154, 78),   # 金黄
    "k": (242, 198, 112),  # 浅金黄
    "a": (226, 168, 70),   # 炒饭粒暗
    "n": (246, 224, 156),  # 面条
    "m": (214, 180, 104),  # 面条暗
    "s": (200, 138, 78),   # 汤(味噌色)
    "w": (255, 254, 250),  # 白色食物:豆腐 / 米饭 / 蛋白 / 包子 / 骨头
    "v": (226, 216, 196),  # 白色食物的暗面
    "f": (110, 140, 168),  # 鱼背
    "e": (214, 220, 222),  # 鱼肚
    "c": (248, 214, 118),  # 布丁
    "p": (240, 150, 160),  # 火腿粉
    "j": (246, 150, 40),   # 橙汁
    "i": (252, 196, 90),   # 橙汁亮
    "q": (150, 52, 40),    # 焦糖 / 深红
}

CHAR = [(30, 26, 28), (52, 40, 36), (74, 51, 40), (104, 82, 68)]   # 与 settle/pixelate.py 的焦黑四档一致
SMOKE_DARK = (122, 116, 128)   # 小人 burnt 姿势头顶那颗烟点的灰
SMOKE_LIGHT = (164, 158, 168)

# 类别英文名 → (中文名, 格子)
ICONS = {
    "stirfry": ("炒菜", [
        ".....hg.....",
        "....gobyh...",
        "...ybgrboy..",
        "..ogbyrbgod.",
        ".gyrbhgobygo",
        "RWdbogyrbbWR",
        ".RWWWWWWWWR.",
        "..SSSSSSSS..",
    ]),
    "soup": ("汤", [
        "..LLLLLLLL..",
        ".LsswwsgswL.",
        "LswwsshswwsL",
        "LssgsswwsssL",
        "LLLLLLLLLLLL",
        ".DDDDDDDDDD.",
        "..DDDDDDDD..",
        "...DDDDDD...",
        "....SSSS....",
    ]),
    "noodles": ("面", [
        ".........F.F",
        "........F.F.",
        ".......FnF..",
        "......nnFn..",
        ".....n.nn...",
        ".NNNNnNnnNN.",
        "NnmnnmnnmyyN",
        "NmnnmnnmnyzN",
        "NNNNNNNNNNNN",
        ".MNNNNNNNNM.",
        "..MNWNWNWM..",
        "....SSSS....",
    ]),
    "donburi": ("盖饭", [
        "....dbbd....",
        "..gbybbyb...",
        ".wbbyddbybw.",
        "wwwwgwwwwwvw",
        "NwvwwwwvwwwN",
        "NNNNNNNNNNNN",
        ".MNNNNNNNNM.",
        "..MNNNNNNM..",
        "...MMMMMM...",
        "....SSSS....",
    ]),
    "friedrice": ("炒饭", [
        ".....ka.....",
        "...kakgak...",
        "..akpakako..",
        ".kakgakpkga.",
        ".akoakakakak",
        "RkakpakgakaR",
        ".RWWWWWWWWR.",
        "..SSSSSSSS..",
    ]),
    "friedegg": ("煎蛋", [
        "..QQQQQQQ....",
        ".QPPwwwwPQ...",
        "QPwwwwwwwPQ..",
        "QPwwwyywwPQ..",
        "QPwwwyzwwPQKK",
        "QPPwwwwwvPQ..",
        ".QPPvPPPPQ...",
        "..PPPPPPP....",
    ]),
    "fish": ("鱼", [
        "....fff......",
        "..fffffff..ff",
        ".fKffffffffff",
        "feeeeeeeeeff.",
        ".eeeeeeee..ff",
        "RWWWWWWWWWWWR",
        ".RWWWWWWWWWR.",
        "..SSSSSSSSS..",
    ]),
    "meat": ("肉排 / 鸡腿", [
        ".........BB.",
        "........BGBB",
        ".......BG.B.",
        "......BG....",
        "..llllG.....",
        ".lkklllb....",
        "lkllbllbd...",
        "llbllbbdd...",
        "RbbbbddddWR.",
        ".RWWWWWWWR..",
        "..SSSSSSS...",
    ]),
    "steamer": ("蒸笼", [
        "...v.....v...",
        "..www...www..",
        ".wwwwv.wwwwv.",
        ".wwwwv.wwwwv.",
        "UTTTTTTTTTTTU",
        "TUTUTUTUTUTUT",
        "TTTTTTTTTTTTT",
        "UUUUUUUUUUUUU",
        ".SSSSSSSSSSS.",
    ]),
    "bake": ("烤物", [
        "....bbbbb....",
        "..bkbbkbbkb..",
        ".bbbkbbkbbkb.",
        ".lllllllllll.",
        ".lllllllllll.",
        "ZlllllllllllZ",
        "ZAAAAAAAAAAAZ",
        ".ZZZZZZZZZZZ.",
    ]),
    "salad": ("凉拌", [
        "...g...o.w..",
        "..o.gw.go.r.",
        ".wgo.ogwhgo.",
        "CgwhogwoghwC",
        "CCCCCCCCCCCC",
        ".EEEEEEEEEE.",
        "..EEEEEEEE..",
        "...SSSSSS...",
    ]),
    "dessert": ("甜品", [
        ".....h....",
        "....rr....",
        "...qqqq...",
        "..qcqqcq..",
        "..ccccck..",
        ".cccccckk.",
        ".ccccccck.",
        "RWWWWWWWWR",
        ".SSSSSSSS.",
    ]),
    "drink": ("饮料", [
        "........r.",
        ".......w..",
        "......r...",
        ".JIIIwIJ..",
        "yJjjrjjJ..",
        "yJijjjjJ..",
        ".JijjjjJ..",
        ".JijjjjJ..",
        ".JijjjjJ..",
        ".JIIIIIJ..",
        ".SSSSSSS..",
    ]),
    "bowl": ("一碗(通用)", [
        "...X...X....",
        "....X...X...",
        "...X...X....",
        ".OOOOOOOOOO.",
        "OsbsgbsbsbsO",
        "OOOOOOOOOOOO",
        ".VOOOOOOOOV.",
        "..VOOOOOOV..",
        "...VVVVVV...",
    ]),
}

# 菜名 → 类别:从上往下,第一条命中的算数(子串包含);都不中 → fallback。classify.py 是按这张表跑的纯函数。
RULES = {
    "match": "子串包含,不分大小写;ordered 从上往下第一条命中即返回",
    "fallback": "bowl",
    "ordered": [
        {"category": "bake", "why": "整词例外:含「面」「粉」但是面包类",
         "keywords": ["面包", "吐司", "贝果", "司康", "可颂", "欧包", "法棍", "披萨", "比萨", "面饼"]},
        {"category": "dessert", "why": "整词例外", "keywords": ["汤圆", "冰粉", "藕粉", "糖水", "西米露", "红豆沙"]},
        {"category": "steamer", "why": "整词例外", "keywords": ["汤包", "肠粉", "粉蒸", "煎饺", "锅贴"]},
        {"category": "donburi", "why": "整词例外", "keywords": ["拌饭", "茶泡饭", "煲仔饭", "汤泡饭"]},
        {"category": "salad", "why": "整词例外", "keywords": ["凉粉", "凉皮"]},
        {"category": "stirfry", "why": "整词例外:不是鱼", "keywords": ["鱼香"]},
        {"category": "meat", "why": "整词例外:不是饮料", "keywords": ["可乐鸡"]},
        {"category": "friedegg", "keywords": ["煎蛋", "荷包蛋", "太阳蛋"]},
        {"category": "friedrice", "keywords": ["炒饭", "抓饭", "蛋包饭"]},
        {"category": "noodles", "keywords": ["面", "粉", "乌冬", "米线", "意面", "荞麦", "拉面", "udon", "ramen", "pasta"]},
        {"category": "dessert", "keywords": ["蛋糕", "布丁", "甜品", "甜点", "冰淇淋", "雪糕", "慕斯", "提拉米苏", "双皮奶",
                                             "芋圆", "奶冻", "果冻", "蛋挞", "舒芙蕾", "曲奇", "饼干", "泡芙", "大福",
                                             "团子", "羊羹", "圣代", "松饼", "可丽饼"]},
        {"category": "drink", "keywords": ["茶", "咖啡", "拿铁", "果汁", "奶昔", "汽水", "可乐", "豆浆", "可可", "酒",
                                           "饮", "柠檬水", "苏打", "椰奶"]},
        {"category": "donburi", "keywords": ["盖饭", "丼", "盖浇", "咖喱饭", "饭"]},
        {"category": "soup", "keywords": ["汤", "羹", "味噌", "浓汤", "煲汤"]},
        {"category": "salad", "keywords": ["凉拌", "拌", "沙拉", "色拉", "拍黄瓜", "凉菜", "泡菜", "腌"]},
        {"category": "steamer", "keywords": ["包子", "饺", "烧卖", "烧麦", "小笼", "馒头", "花卷", "点心"]},
        {"category": "stirfry", "keywords": ["炒", "爆", "煸", "小炒"]},
        {"category": "fish", "keywords": ["鱼", "鲑", "三文", "鳕", "鲈", "鳗", "金枪", "虾", "蟹", "贝", "鱿", "海鲜", "刺身"]},
        {"category": "meat", "keywords": ["鸡腿", "鸡翅", "排骨", "牛排", "猪排", "肉排", "炸鸡", "烤肉", "叉烧", "五花",
                                          "肉", "鸡", "牛", "猪", "羊", "鸭"]},
        {"category": "steamer", "why": "上面都没中才按做法归", "keywords": ["蒸"]},
        {"category": "bake", "why": "上面都没中才按做法归", "keywords": ["烤", "焗", "烘"]},
    ],
}

# 糊了版的烟:相对图标右上角往上长,(行偏移, 列偏移从右数, 颜色)
SMOKE = [(-1, 2, SMOKE_LIGHT), (-2, 1, SMOKE_LIGHT), (-3, 2, SMOKE_DARK), (-4, 1, SMOKE_LIGHT)]


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def char_of(c, r, col):
    L = lum(c)
    i = 3 if L > 185 else 2 if L > 140 else 1 if L > 95 else 0
    if (r * 3 + col * 5) % 7 == 0:   # 疏疏地压暗一档,焦得不均
        i = max(0, i - 1)
    return CHAR[i]


def cells(name, burnt=False):
    """返回 rows×cols×4 的 uint8(一格一像素)。"""
    grid = ICONS[name][1]
    w = len(grid[0])
    assert all(len(r) == w for r in grid), name
    h = len(grid)
    top = 4 if burnt else 0
    out = np.zeros((h + top, w, 4), np.uint8)
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "." or (burnt and ch == "X"):
                continue
            col = PAL[ch]
            if burnt and ch.islower():
                col = char_of(col, r, c)
            out[r + top, c] = (*col, 255)
    if burnt:
        # 烟从右侧食物最高处往上冒
        food_rows = [r for r, row in enumerate(grid) if any(ch.islower() for ch in row[w // 2:])]
        r0 = (food_rows[0] if food_rows else 0) + top
        for dr, dc, col in SMOKE:
            out[r0 + dr, w - 1 - dc] = (*col, 255)
        # 去掉上方空行
        nz = np.flatnonzero(out[..., 3].any(axis=1))
        out = out[nz[0]:]
    return out


def to_canvas(cellimg):
    h, w = cellimg.shape[:2]
    big = Image.fromarray(cellimg, "RGBA").resize((w * CELL, h * CELL), Image.NEAREST)
    cv = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    x0 = (CANVAS - w * CELL) // 2 // CELL * CELL
    y0 = (CANVAS - h * CELL) // 2 // CELL * CELL
    cv.alpha_composite(big, (x0, y0))
    return cv


def main():
    root = os.path.dirname(HERE)
    out = os.path.join(root, "assets", "clawd", "dishes")
    os.makedirs(out, exist_ok=True)
    for name in ICONS:
        for burnt in (False, True):
            stem = name + ("_burnt" if burnt else "")
            Image.fromarray(cells(name, burnt), "RGBA").save(os.path.join(out, stem + "_cells.png"), optimize=True)
    meta = {"note": "Which icon a dish name gets: rules from the top, the first keyword found in the name wins; "
                    "nothing found = the fallback.",
            "kinds": list(ICONS), "rules": RULES}
    with open(os.path.join(root, "src", "kitchenette", "data", "dish_icons.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=1)
        fp.write("\n")
    print(len(ICONS), "kinds")


if __name__ == "__main__":
    main()
