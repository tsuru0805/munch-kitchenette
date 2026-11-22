#!/usr/bin/env python3
# munch-kitchenette · tools/export_vendor.py · unofficial Clawd fan work, Clawd belongs to Anthropic
# SPDX-FileCopyrightText: 2026 tsuru0805
# SPDX-License-Identifier: MIT
"""Exports the vendor clips the kitchen page plays (the moves in states/vendor/, composed by dump_vendor.cjs):
the vendor pushing his cart in, calling with a hand bell, waiting, pushing it away, and a cook paying him,
taking what he hands over and eating a bite. Two looks of the cart: the tanghulu seller's (a straw bundle of
candied haws on the handle; prefix `vendor_th_`) and every other vendor's (a crate of paper bags; prefix `vendor_`).

For each outfit of the buyer (chef-toque -> toque/, chef-scarf -> scarf/):
  <prefix><part>.webp     arrive, call, wait, leave (the vendor alone: the same file in both folders),
                          walkin, pay, give, eat, walkout, walkout_hold, walkout_empty (the cook in that
                          outfit walking over, buying from him and walking back out)
  <prefix><part>_last.png the last frame of the four that play once and stay: leave (the empty roadside), give, eat,
                          walkin (the cook standing at the cart while a treat is still on its way)
  <prefix>still.png       the vendor standing by his cart ("reduce motion" in place of the clips that loop or lead on)

Image spec: the scene is 430 x 245 engine pixels (two Clawds and a cart), scaled x1.4 with nearest neighbour
(one 5 px engine cell = 7 px) and pasted at (15, 235) of a 720 x 720 transparent canvas, so it fills the window the
page shows of every chore clip (x 15-615, y 235-575); the ground sits at y = 564. 45 frames with delays of
70 / 60 / 70 ms, lossless, every frame a key frame, the credit line in the metadata, as export_cook_clips.py.

Needs: Node 20.9+, Python 3 with Pillow.
Usage: python3 export_vendor.py <engine dir with states/vendor/ and outfits/vendor-straw.cjs> <output dir>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

from export_cook_clips import DELAYS, FRAMES, HERE, OUTFITS, XMP, save_png

VARIANTS = {"th": "vendor_th_", "plain": "vendor_"}
ONCE = {"leave", "give", "eat", "walkin"}     # play once and stay on the last frame
BUYER_PARTS = ("walkin", "pay", "give", "eat", "walkout", "walkout_hold", "walkout_empty")  # the scenes with a buyer in them
SCALE_NUM, SCALE_DEN = 7, 5          # x1.4: a 5 px cell becomes 7 px
AT = (15, 235)


def place(raw, w, rows):
    im = Image.frombytes("RGBA", (w, rows), raw).resize((w * SCALE_NUM // SCALE_DEN, rows * SCALE_NUM // SCALE_DEN), Image.NEAREST)
    canvas = Image.new("RGBA", (720, 720), (0, 0, 0, 0))
    canvas.paste(im, AT)
    return canvas


def dump(engine, variant, outfit, only=()):
    tmp = tempfile.mkdtemp(prefix="vendor-")
    subprocess.run(["node", os.path.join(HERE, "dump_vendor.cjs"), engine, tmp, variant, outfit, *only], check=True)
    with open(os.path.join(tmp, "scene.json")) as f:
        meta = json.load(f)
    clips = {}
    n = meta["w"] * meta["rows"] * 4
    for name in os.listdir(tmp):
        if name.endswith(".rgba"):
            with open(os.path.join(tmp, name), "rb") as f:
                raw = f.read()
            assert len(raw) == n * FRAMES, (name, len(raw))
            clips[name[:-5]] = [place(raw[i * n:(i + 1) * n], meta["w"], meta["rows"]) for i in range(FRAMES)]
    shutil.rmtree(tmp)
    return clips, set(meta["buyer"])


def write(frames, d, name, part):
    frames[0].save(os.path.join(d, name + ".webp"), save_all=True, append_images=frames[1:], duration=DELAYS,
                   loop=0, lossless=True, method=6, kmax=1, xmp=XMP)
    if part in ONCE:
        save_png(frames[-1], os.path.join(d, name + "_last.png"))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    engine, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    for variant, prefix in VARIANTS.items():
        alone = None
        for outfit, short in OUTFITS.items():
            d = os.path.join(out, short)
            os.makedirs(d, exist_ok=True)
            # the vendor alone does not depend on the buyer's outfit: render it once, write it into both folders
            clips, with_buyer = dump(engine, variant, outfit, () if alone is None else BUYER_PARTS)
            if alone is None:
                alone = {k: v for k, v in clips.items() if k not in with_buyer}
            for part, frames in {**alone, **{k: v for k, v in clips.items() if k in with_buyer}}.items():
                write(frames, d, prefix + part, part)
            save_png(alone["wait"][0], os.path.join(d, prefix + "still.png"))
            print(short, prefix, len(clips), "clips")


if __name__ == "__main__":
    main()
