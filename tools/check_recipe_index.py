"""Go over every entry of the recipe index and list the ones that look wrong — no network, read-only.

    python tools/check_recipe_index.py <path to the HowToCook checkout the index was built from>
           [--index src/kitchenette/data/howtocook-<commit>.index.json] [--ok tools/recipe_checked.txt]

It cannot say an entry is right; it says where a person should read the guide's page. The rules:

  NAME   a word of the dish name is a known ingredient (shop catalog, extra shop items, build aliases,
         recipe-only ingredients; two characters or more), but that ingredient is neither a main nor an
         optional one (a name that ends with the word is the dish itself: 面包, 饼干, 凉粉). (炒河粉 whose rice noodles were lost; 带把肘子 whose main was 豆腐.)
  EMPTY  no main ingredient at all.
  MANY   more than eight main ingredients (a list that was read too greedily).
  ALTSCOPE a list line whose last item says 或 ("料酒、朗姆酒或啤酒"): the builder reads the 或 as joining
         only the words of that item; a person checks the page does not mean "any one of the whole
         list" (if it does, the line goes into the builder's WHOLE_OR with the page's evidence).
  ALTSTAPLE an ingredient picked from alternatives one of which is a seasoning always at hand ("黄油或
         玉米油"): then nothing needs buying, yet the shop item was made required.
  INSIDE a main or optional ingredient was found inside a longer word of the page whose first part is
         two characters or more ("红豆腐乳" -> 豆腐 was this kind).
  LOST   a piece of the page's ingredient list holds a known ingredient word but was dropped.
  ODDNAME a recipe-only ingredient whose name looks like a description, a package or a tool (longer than
         five characters, or holding 罐头 / 的 / 牌 / 套 / 一, or ending in 包 but not 面包).
  LONG   more than 150 minutes.          SHORT  less than 5 minutes.
  WAIT   the clause the minutes came from also talks about waiting (提前 / 腌 / 冷藏 / 过夜 / 发酵 /
         浸泡 / 静置 / 冷冻 / 等待 / 泡发), so the number may include time nobody stands at the stove.
  OTHER  the page's opening gives another whole-time figure that disagrees with the minutes by more
         than half (e.g. a total with waiting next to the time at the stove).
  DEFAULT the opening gives no time at all; the minutes are the builder's default for the method.
  SIMPLE one or two main ingredients, stir-fry / pan-fry / mix, and more than 40 minutes.

Entries fixed by hand in the builder (``FIXES`` for ingredients, ``MINUTES`` for minutes) are not
flagged again for that part. Entries listed in --ok (one "id  reason-code  note" per line, # for comments) were read by a person and
judged right; they are reported as checked instead of suspicious. Exit code 0 always; the report is the
output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_recipe_index as bi  # noqa: E402
from kitchenette import fridge, recipes as rc  # noqa: E402
from kitchenette.texts_play import vendor_id  # noqa: E402

WAIT_WORDS = bi.WAIT_WORDS
ODD_CHARS = ("包", "罐头", "的", "牌", "套", "一")


def _known_words(index: dict) -> dict[str, str]:
    words = {k: v for k, v in rc._alias_index().items() if len(k) >= 2}
    for n in index.get("vendor_items", []):
        if len(n) >= 2:
            words.setdefault(n, vendor_id(n))
    return words


def _names(iid: str, vnames: dict[str, str]) -> set[str]:
    out = set(rc.names_of(iid))
    if iid in vnames:
        out.add(vnames[iid])
    it = fridge.item(iid)
    if it:
        out.add(it["name"])
    return out


def check(repo: Path, index: dict) -> list[tuple[dict, list[str]]]:
    words = _known_words(index)
    vnames = {vendor_id(n): n for n in index.get("vendor_items", [])}
    out = []
    for r in index["recipes"]:
        why: list[str] = []
        rel = r["source"].split(" ", 1)[1]
        page = (repo / rel).read_text(encoding="utf-8")
        have = {fridge.canon(e["item"]) for e in r["main"] + r["optional"]}
        # NAME
        for w, iid in sorted(words.items(), key=lambda kv: -len(kv[0])):
            if (w in r["name"] and not r["name"].endswith(w) and fridge.canon(iid) not in have
                    and not any(w in s for s in r["staples"])):
                if not any(w in w2 and w2 in r["name"] and fridge.canon(i2) in have for w2, i2 in words.items()):
                    why.append(f"NAME 菜名里的「{w}」不在用料里")
                    break
        if not r["main"]:
            why.append("EMPTY 没有主料")
        if len(r["main"]) > 8:
            why.append(f"MANY 主料 {len(r['main'])} 样")
        # INSIDE / LOST: read the page's list again the way the builder does
        sec = bi.SECTION_RE.search(page)
        if sec and rel not in bi.FIXES:
            for line in sec.group(1).splitlines():
                mm = bi.ITEM_RE.match(line)
                if not mm:
                    continue
                body = bi._unbracket(mm.group(1))
                body = bi._split_top(body, "：:")[-1]
                parts = [x for x in bi._split_top(body, "，,、；;") if x.strip()]
                whole = mm.group(1).strip() in bi.WHOLE_OR.get(rel, {})
                if len(parts) > 1 and bi.OR_WORDS.search(parts[-1]) and not whole:
                    why.append(f"ALTSCOPE 「{mm.group(1).strip()[:30]}」的「或」按只管它那一项读")
            for alts, _opt in bi._section_pieces(sec.group(1), frozenset(bi.WHOLE_OR.get(rel, {}))):
                kind, val, tok = bi._pick(alts)
                if len(alts) > 1 and kind in ("main", "vendor"):
                    easy = [a for a in alts if rc.is_known_staple(a)]
                    if easy:
                        why.append(f"ALTSTAPLE 「{'或'.join(alts)}」里有常备的{easy[0]},却把{tok}算成要买的料")
                if kind == "main" and tok not in rc._alias_index():
                    hit = rc._sub_hit(tok, rc._alias_index())
                    if hit and tok.find(hit) >= 2:
                        why.append(f"INSIDE 「{tok}」算成了{rc.item_name(val)}")
                if kind == "skip":
                    for a in alts:
                        if any(w in a for w in words):
                            why.append(f"LOST 「{a}」被丢了")
                            break
        for e in r["main"] + r["optional"]:
            n = vnames.get(e["item"])
            if n and (len(n) > 5 or any(c in n for c in ODD_CHARS if c != "包")
                      or (n.endswith("包") and not n.endswith("面包"))):
                why.append(f"ODDNAME 「{n}」")
        # minutes
        m = r["minutes"]
        if m > 150:
            why.append(f"LONG {m} 分钟")
        if m < 5:
            why.append(f"SHORT {m} 分钟")
        picked, clause = bi.minutes_pick(page, r["method"])
        if rel not in bi.MINUTES and picked == m:
            if clause and any(w in re.sub(r"[（(][^）)]*[)）]", "", clause) for w in WAIT_WORDS):
                why.append(f"WAIT 时长那句提到等待:「{clause[:40]}」")
            others = [v for v, rank, _c in bi.time_candidates(page) if rank <= 1 and v != m]
            if any(abs(v - m) > max(v, m) / 2 for v in others):
                why.append(f"OTHER 开头还写了别的整体时长 {sorted(set(others))},取了 {m} 分钟")
            if not clause:
                why.append(f"DEFAULT 开头没写时长,按做法给了默认 {m} 分钟")
        if len(r["main"]) <= 2 and r["method"] in ("stirfry", "fry", "mix") and m > 40:
            why.append(f"SIMPLE {len(r['main'])} 样主料的{r['method']}要 {m} 分钟")
        # what a person already fixed by hand in the builder's tables is not flagged again
        if rel in bi.FIXES:
            why = [w for w in why if w.split()[0] not in ("NAME", "EMPTY", "MANY", "INSIDE", "LOST", "ODDNAME")]
        if rel in bi.MINUTES:
            why = [w for w in why if w.split()[0] not in ("LONG", "SHORT", "WAIT", "HOURS", "SIMPLE")]
        if why:
            out.append((r, why))
    return out


def _load_ok(path: Path) -> dict[tuple[str, str], str]:
    ok = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                rid, code, *note = line.split(None, 2)
                ok[(rid, code)] = note[0] if note else ""
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--index", default="")
    ap.add_argument("--ok", default=str(ROOT / "tools" / "recipe_checked.txt"))
    a = ap.parse_args()
    idx_path = Path(a.index) if a.index else sorted((ROOT / "src" / "kitchenette" / "data").glob(
        "howtocook-*.index.json"))[-1]
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    for n in index.get("vendor_items", []):
        rc._VENDOR_NAMES[vendor_id(n)] = n
    ok = _load_ok(Path(a.ok))
    flagged = check(Path(a.repo), index)
    open_n = checked_n = 0
    for r, why in flagged:
        rest = [w for w in why if (r["id"], w.split()[0]) not in ok]
        done = [w for w in why if (r["id"], w.split()[0]) in ok]
        checked_n += bool(done)
        if rest:
            open_n += 1
            main = "、".join(rc.item_name(e["item"]) for e in r["main"])
            print(f"{r['id']}  {r['name']}  [{main}] {r['method']} {r['minutes']}分  {r['source'].split(' ', 1)[1]}")
            for w in rest:
                print("    " + w)
    raised = {(r["id"], w.split()[0]) for r, why in flagged for w in why}
    for key in sorted(set(ok) - raised):
        print(f"no longer flagged, drop from the checked list: {key[0]} {key[1]}")
    print(f"\n{len(index['recipes'])} entries; {open_n} still suspicious; {checked_n} with flags a person checked")


if __name__ == "__main__":
    main()
