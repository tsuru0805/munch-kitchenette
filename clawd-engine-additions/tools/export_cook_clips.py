#!/usr/bin/env python3
# munch-kitchenette · tools/export_cook_clips.py · unofficial Clawd fan work, Clawd belongs to Anthropic
# SPDX-FileCopyrightText: 2026 tsuru0805
# SPDX-License-Identifier: MIT
"""Exports the cooking sprite pack from the clawds-new-clothes engine.

For each outfit (chef-toque -> toque/, chef-scarf -> scarf/):
  <segment>.webp        51 animated clips: wash, chop, and <method>_<part> for 7 methods x 7 parts
  <segment>_last.png    the last frame of every serve / fail clip
  base.png              the still base pose (the engine's `idle` move, frame 0)
and a manifest.json that registers every file.

Image spec: the engine's 300 px canvas scaled x2 (nearest neighbour) and pasted at (6, 14) on a
720 x 720 transparent canvas, which puts the counter line at y = 560. 45 frames per clip with
delays of 70 / 60 / 70 ms (3 s), lossless, every frame a key frame. Every file carries the credit
line in its metadata (WebP: an XMP packet; PNG: a tEXt chunk).

Needs: Node 20.9+, Python 3 with Pillow.
Usage: python3 export_cook_clips.py <engine dir> <output dir> [move id ...]
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, PngImagePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
OUTFITS = {"chef-toque": "toque", "chef-scarf": "scarf"}  # engine outfit -> folder; the order is the registry's
METHODS = ["stirfry", "fry", "deepfry", "boil", "steam", "bake", "mix"]
PARTS = ["main", "wipe", "look", "hot", "taste", "serve", "fail"]
FRAMES = 45
DELAYS = [70, 60, 70] * 15
FRAME_BYTES = 300 * 300 * 4

CREDIT = (
    "Adapted from clawds-new-clothes (https://github.com/CharlieLuinaris/clawds-new-clothes): "
    "Clawd animation & engine by Luin Luinaris (https://github.com/luinluinaris), postie concept & pixel corrections "
    "by Charlie Luinaris. Chef outfits & cooking moves by tsuru0805 for munch-kitchenette. "
    "Unofficial fan work. Clawd (c) Anthropic. Art CC BY-NC-SA 4.0."
)
XMP = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/" xmlns:cc="http://creativecommons.org/ns#" '
    'xmpRights:WebStatement="https://github.com/CharlieLuinaris/clawds-new-clothes" '
    'cc:license="https://creativecommons.org/licenses/by-nc-sa/4.0/">'
    f'<dc:rights><rdf:Alt><rdf:li xml:lang="x-default">{CREDIT}</rdf:li></rdf:Alt></dc:rights>'
    "</rdf:Description></rdf:RDF></x:xmpmeta>"
    '<?xpacket end="w"?>'
).encode("utf-8")


def clips():
    out = [("cook-wash", "wash"), ("cook-chop", "chop")]
    for m in METHODS:
        for k in PARTS:
            out.append((f"cook-{m}-{k}", f"{m}_{k}"))
    return out


def render(engine, outfit, move, count):
    with tempfile.NamedTemporaryFile(suffix=".rgba", delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(["node", os.path.join(HERE, "dump_frames.cjs"), engine, tmp, outfit, move, str(count)], check=True)
        with open(tmp, "rb") as f:
            raw = f.read()
    finally:
        os.unlink(tmp)
    assert len(raw) == FRAME_BYTES * count, (move, len(raw))
    return [place(raw[i * FRAME_BYTES:(i + 1) * FRAME_BYTES]) for i in range(count)]


def place(rgba):
    im = Image.frombytes("RGBA", (300, 300), rgba).resize((600, 600), Image.NEAREST)
    canvas = Image.new("RGBA", (720, 720), (0, 0, 0, 0))
    canvas.paste(im, (6, 14))
    return canvas


def save_png(im, path):
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Luin Luinaris; Charlie Luinaris; tsuru0805")
    info.add_text("Comment", CREDIT)
    im.save(path, optimize=True, pnginfo=info)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    engine, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    only = set(sys.argv[3:])
    files = {}
    for outfit, short in OUTFITS.items():
        d = os.path.join(out, short)
        os.makedirs(d, exist_ok=True)
        for move, name in clips():
            if only and move not in only:
                continue
            frames = render(engine, outfit, move, FRAMES)
            frames[0].save(os.path.join(d, name + ".webp"), save_all=True, append_images=frames[1:], duration=DELAYS,
                           loop=0, lossless=True, method=6, kmax=1, xmp=XMP)
            if name.endswith(("_serve", "_fail")):
                save_png(frames[FRAMES - 1], os.path.join(d, name + "_last.png"))
        if not only:
            save_png(render(engine, outfit, "idle", 1)[0], os.path.join(d, "base.png"))
        for n in sorted(os.listdir(d)):
            if n.endswith((".webp", ".png")):
                files[f"{short}/{os.path.splitext(n)[0]}"] = f"{short}/{n}"
        print(short, "done")
    if not only:
        with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "clawd", "outfits": list(OUTFITS.values()), "files": files}, f, indent=2)
            f.write("\n")
        print(len(files), "files registered")


if __name__ == "__main__":
    main()
