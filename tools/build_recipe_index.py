"""Build the small recipe index from HowToCook (Anduin2017/HowToCook, Unlicense) — no network, read-only.

    python tools/build_recipe_index.py <path to a HowToCook checkout> [--out src/kitchenette/data]

Writes ``howtocook-<short commit>.index.json``: per dish only id / name / aliases / main ingredients /
optional ones / method (one of seven) / minutes / category / source line. **No steps.** The method
and the minutes are estimated here (the original has neither).

Ids stay the same across versions: hc- + sha1 of the path (without .md and 「的做法」), and an entry
with the same name and category as in the previous index keeps its old id (--prev, or the newest
index in --out).

Ingredients are sorted by the rules in :mod:`kitchenette.recipes` (purely mechanical):
  main     -> an item of the shop catalog ([fridge] ingredients + recipes.EXTRA_ITEMS)
  staple   -> seasonings always at hand (recipes.STAPLES_EXTRA + [fridge] staple_aliases)
  tool     -> dropped
  the rest -> vendor-only (known to the kitchen, not sold at the shop; v_ ids)
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
ITEM_RE = re.compile(r"^\s*[*-]\s+(.+)$", re.M)
MIN_RE = re.compile(r"(?:大约|约|大概|只需|需要|需|耗时|全程)\s*(?:只需)?\s*(\d{1,3})\s*(?:-|~|到|至)?\s*(\d{1,3})?\s*分钟")
HOUR_RE = re.compile(r"(?:大约|约|大概|只需|需要|需|耗时|全程)\s*(\d{1,2}(?:\.\d)?)\s*(?:个)?\s*小时")

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


def _norm(s: str) -> tuple[str, bool]:
    optional = "可选" in s
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)       # keep a markdown link's text
    s = re.split(r"[，,：:；;、/]|或|和(?=[一-鿿])", s)[0]
    s = re.sub(r"[\d\.]+.*$", "", s)
    s = s.strip(" *-`[]　")
    return s, optional


def _dish_name(path: Path, text: str) -> str:
    m = re.search(r"^#\s*(.+?)\s*$", text, re.M)
    name = m.group(1) if m else path.stem
    name = re.sub(r"的(做法|制作方法|做法与吃法)$", "", name).strip()
    return name or path.stem


def _minutes(text: str, method: str) -> int:
    head = text.split("## 必备原料和工具")[0]
    m = MIN_RE.search(head)
    if m:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        v = round((a + b) / 2)
        if 1 <= v <= 1440:
            return v
    h = HOUR_RE.search(head)
    if h:
        v = round(float(h.group(1)) * 60)
        if 1 <= v <= 1440:
            return v
    return METHOD_MINUTES[method]


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


def build(repo: Path, prev: dict | None) -> dict:
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
        main, optional, staples = [], [], []
        for raw in ITEM_RE.findall(sec.group(1)):
            tok, opt = _norm(raw)
            kind, val = rc.classify_token(tok)
            if kind in ("skip", "tool"):
                continue
            if kind == "staple":
                if val not in staples:
                    staples.append(val)
                continue
            if kind == "vendor":
                vendor.setdefault(tok, []).append(name)
                rc._VENDOR_NAMES[rc.vendor_id(tok)] = tok
            iid = val
            bucket = optional if (opt or iid in rc.GARNISH) else main
            if any(x["item"] == iid for x in main + optional):
                continue
            names = rc.names_of(iid) + (tok,)
            bucket.append({"item": iid, "qty": _qty(calc, iid, names)})
            if kind == "vendor":
                residue[tok] = residue.get(tok, 0) + 1
        if not main and optional:
            main, optional = optional[:1], optional[1:]
        method = _method(name, text)
        key = str(rel.with_suffix("")).replace("的做法", "")
        rid = prev_ids.get((name, cat)) or "hc-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
        out.append({"id": rid, "name": name, "aliases": rc.dish_aliases(name), "main": main,
                    "optional": optional, "staples": staples, "method": method,
                    "minutes": _minutes(text, method), "category": cat,
                    "category_label": CATEGORY_LABEL.get(cat, cat),
                    "source": f"HowToCook@{commit[:7]} {rel.as_posix()}"})
    ids = [r["id"] for r in out]
    if len(ids) != len(set(ids)):
        raise SystemExit("two entries got the same id: change the hash length or fix by hand")
    return {"schema": 1, "source": {"repo": "https://github.com/Anduin2017/HowToCook", "commit": commit,
                                    "license": "Unlicense(公共领域)"},
            "recipes": out, "vendor_items": sorted(vendor), "_residue": residue}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out", default=str(ROOT / "src" / "kitchenette" / "data"))
    ap.add_argument("--prev", default="")
    ap.add_argument("--report", action="store_true", help="print what was left unsorted; write nothing")
    a = ap.parse_args()
    repo = Path(a.repo)
    prev = None
    if a.prev:
        prev = json.loads(Path(a.prev).read_text(encoding="utf-8"))
    else:
        olds = sorted(Path(a.out).glob("howtocook-*.index.json"))
        if olds:
            prev = json.loads(olds[-1].read_text(encoding="utf-8"))
    idx = build(repo, prev)
    residue = idx.pop("_residue")
    if a.report:
        print(len(idx["recipes"]), "recipes")
        print(sorted(residue.items(), key=lambda kv: -kv[1]))
        return
    path = Path(a.out) / f"howtocook-{idx['source']['commit'][:7]}.index.json"
    path.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", path, len(idx["recipes"]), "recipes;", len(idx["vendor_items"]), "vendor-only items")


if __name__ == "__main__":
    main()
