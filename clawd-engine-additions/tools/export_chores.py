#!/usr/bin/env python3
# munch-kitchenette · tools/export_chores.py · unofficial Clawd fan work, Clawd belongs to Anthropic
# SPDX-FileCopyrightText: 2026 tsuru0805
# SPDX-License-Identifier: MIT
"""Exports the chore clips of washing plates by hand and loading the dishwasher (thirteen moves in
states/chores/), in both outfits. (Buying from the vendor has its own scenes: export_vendor.py.)

For each outfit (chef-toque -> toque/, chef-scarf -> scarf/):
  <segment>.webp        dish_{sleeve,soap,scrub,rinse,shake,dry,stack,break}, machine_{load,close,start,run,done}
  <segment>_last.png    the last frame of the two clips that play once: dish_break, machine_done

Same image spec, frame delays and credit metadata as export_cook_clips.py. Segment name = move id with
"-" turned into "_". Run web/scripts/gen-manifest.mjs afterwards to register the files.

Needs: Node 20.9+, Python 3 with Pillow.
Usage: python3 export_chores.py <engine dir with states/chores/> <output dir> [move id ...]
"""
import os
import shutil
import subprocess
import sys
import tempfile

from export_cook_clips import DELAYS, FRAME_BYTES, FRAMES, HERE, OUTFITS, XMP, place, save_png

MOVES = [
    "dish-sleeve", "dish-soap", "dish-scrub", "dish-rinse", "dish-shake", "dish-dry", "dish-stack", "dish-break",
    "machine-load", "machine-close", "machine-start", "machine-run", "machine-done",
]
ONCE = {"dish-break", "machine-done"}   # play once and stay on the last frame


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    engine, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    want = [m for m in MOVES if len(sys.argv) < 4 or m in sys.argv[3:]]
    for outfit, short in OUTFITS.items():
        d = os.path.join(out, short)
        os.makedirs(d, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="chores-")
        try:
            subprocess.run(["node", os.path.join(HERE, "dump_chores.cjs"), engine, tmp, outfit, *want], check=True)
            for move in want:
                with open(os.path.join(tmp, move + ".rgba"), "rb") as f:
                    raw = f.read()
                assert len(raw) == FRAME_BYTES * FRAMES, (move, len(raw))
                frames = [place(raw[i * FRAME_BYTES:(i + 1) * FRAME_BYTES]) for i in range(FRAMES)]
                name = move.replace("-", "_")
                frames[0].save(os.path.join(d, name + ".webp"), save_all=True, append_images=frames[1:], duration=DELAYS,
                               loop=0, lossless=True, method=6, kmax=1, xmp=XMP)
                if move in ONCE:
                    save_png(frames[-1], os.path.join(d, name + "_last.png"))
        finally:
            shutil.rmtree(tmp)
        print(short, len(want), "clips")


if __name__ == "__main__":
    main()
