#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 tsuru0805
# SPDX-License-Identifier: MIT
"""Exports the settled stills: five poses x two outfits, each a 720 x 720 transparent PNG, a front layer
with only the hands, and where the plate goes.

Same image spec as export_cook_clips.py (the engine's 300 px canvas x2, nearest neighbour, pasted at
(6, 14)), so one pixel cell of the engine is 10 canvas pixels, on the lines x = 6 (mod 10), y = 0 (mod 10).

Usage: python3 export_settle.py <engine dir with states/settle/> <output dir>
Writes <out>/<toque|scarf>/settle_<pose>.png and settle_<pose>_front.png, and <out>/settle.json (the plate
positions, the same numbers as web/src/settle.ts).
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
POSES = ["great", "ok", "burnt", "spoiled", "ruined"]
OUTFITS = ["toque", "scarf"]
CELL = 10


def canvas(raw):
    im = Image.frombytes("RGBA", (300, 300), raw).resize((600, 600), Image.NEAREST)
    c = Image.new("RGBA", (720, 720), (0, 0, 0, 0))
    c.paste(im, (6, 14))
    return c


def cx(x):
    return 6 + 2 * x


def cy(y):
    return 14 + 2 * y


def plate(pose, hands):
    """Where the plate goes (engine coordinates of the hands as drawn): its bottom one cell under the top
    of the hand holding it; the front layer then covers the rim."""
    l, r = hands
    if pose == "ruined":
        return None
    if pose == "great":      # held up with both hands, the plate between them
        mid, bottom, tilt = (l["x"] + r["x"] + 20) / 2, l["y"] + 5, 0
    elif pose == "ok":       # flat on the right hand, a little outside it
        mid, bottom, tilt = r["x"] + 35, r["y"] + 5, 0
    elif pose == "burnt":    # held out far on the left hand
        mid, bottom, tilt = l["x"] - 15, l["y"] + 5, 0
    else:                    # spoiled: the left hand hangs, the plate tips outwards
        mid, bottom, tilt = l["x"] - 15, l["y"] + 5, 3
    spec = {"bottom_center": [cx(mid), cy(bottom)], "max_width": 140, "max_height": 100}
    if tilt:
        # Not rotated (that would break the pixel cells): column by column, away from the hand, one cell
        # lower every `tilt` columns
        spec["tilt_every"] = tilt
    return spec


def main(engine, out):
    with tempfile.TemporaryDirectory() as raw:
        subprocess.run(["node", os.path.join(HERE, "dump_settle.cjs"), engine, raw], check=True)
        info = json.load(open(os.path.join(raw, "info.json")))
        plates = {}
        for o in OUTFITS:
            d = os.path.join(out, o)
            os.makedirs(d, exist_ok=True)
            for p in POSES:
                key = f"{o}_{p}"
                canvas(open(os.path.join(raw, key + ".rgba"), "rb").read()).save(os.path.join(d, f"settle_{p}.png"), optimize=True)
                if p != "ruined":
                    canvas(open(os.path.join(raw, key + "_front.rgba"), "rb").read()).save(
                        os.path.join(d, f"settle_{p}_front.png"), optimize=True)
                plates[key] = plate(p, info[key]["hands"])
    json.dump(plates, open(os.path.join(out, "settle.json"), "w"), indent=1)
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
