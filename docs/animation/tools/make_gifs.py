# Builds the documentation GIFs from the sprite pack: each clip cropped to where the cook stands,
# at half size, on a flat tile.
#   python3 make_gifs.py <assets/clawd> <docs/animation>
import os, sys
from PIL import Image

PACK, OUT = sys.argv[1], sys.argv[2]
BG = (233, 227, 214)
# Everything any clip ever draws lies inside x 96-606, y 270-560 of the 720 px canvas
CROP = (80, 240, 620, 560)
# One-shot clips (serve, fail) rest on their last frame before the GIF loops
HOLD_MS = 1500
CREDIT = ("Adapted from clawds-new-clothes (https://github.com/CharlieLuinaris/clawds-new-clothes): Clawd animation & engine by "
          "Luin Luinaris, postie concept & pixel corrections by Charlie Luinaris. Chef and street vendor outfits, cooking "
          "and chore moves, and the street vendor's cart by tsuru0805 for munch-kitchenette. Unofficial fan work. "
          "Clawd (c) Anthropic. Art CC BY-NC-SA 4.0.")
METHODS = ["stirfry", "fry", "deepfry", "boil", "steam", "bake", "mix"]

def frames_of(path):
    im = Image.open(path)
    out = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        f = im.convert("RGBA").crop(CROP).resize(((CROP[2] - CROP[0]) // 2, (CROP[3] - CROP[1]) // 2), Image.NEAREST)
        tile = Image.new("RGBA", f.size, BG + (255,))
        tile.alpha_composite(f)
        out.append((tile.convert("RGB"), im.info.get("duration", 70)))
    return out

def save_gif(frames, path):
    # One shared palette for the whole clip (pixel art: far fewer than 256 colours)
    colours = []
    seen = set()
    for im, _ in frames:
        for _, c in im.getcolors(1 << 20):
            if c not in seen:
                seen.add(c); colours.append(c)
    assert len(colours) <= 256, (path, len(colours))
    pal = Image.new("P", (1, 1))
    flat = [v for c in colours for v in c] + [0] * (768 - 3 * len(colours))
    pal.putpalette(flat)
    ps = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im, _ in frames]
    ps[0].save(path, save_all=True, append_images=ps[1:], duration=[d for _, d in frames], loop=0, optimize=False,
               disposal=1, comment=CREDIT.encode("ascii"))

def clip(outfit, seg, name):
    frames = frames_of(os.path.join(PACK, outfit, seg + ".webp"))
    if seg.endswith(("_serve", "_fail")):
        frames[-1] = (frames[-1][0], frames[-1][1] + HOLD_MS)
    save_gif(frames, os.path.join(OUT, name + ".gif"))

os.makedirs(OUT, exist_ok=True)
for m in METHODS:
    clip("toque", f"{m}_main", f"{m}-main-toque")
    clip("scarf", f"{m}_main", f"{m}-main-scarf")
    clip("toque", f"{m}_serve", f"{m}-serve-toque")
    clip("scarf", f"{m}_fail", f"{m}-fail-scarf")
clip("toque", "wash", "wash-toque")
clip("scarf", "chop", "chop-scarf")
clip("toque", "boil_wipe", "boil-wipe-toque")
clip("scarf", "stirfry_look", "stirfry-look-scarf")
clip("toque", "steam_hot", "steam-hot-toque")
clip("scarf", "mix_hot", "mix-hot-scarf")
clip("scarf", "fry_taste", "fry-taste-scarf")
# ── the chores the kitchen page plays (the vendor at his cart, washing up, the dishwasher) ──
# Each a run of whole clips in the order the page plays them, every clip 3 s here (on the page a washing-up
# step lasts a seventh of each plate's time, and the dishwasher runs for 8 s). The strip puts the three side
# by side; each lane is eight clips long, so they loop together.
CHORE_CROP = (16, 234, 616, 574)        # everything a chore draws lies inside x 26-606, y 244-564
LANES = {
    "vendor": ("scarf", ["vendor_th_arrive", "vendor_th_call", "vendor_th_walkin", "vendor_th_pay", "vendor_th_give", "vendor_th_eat", "vendor_th_walkout", "vendor_th_leave"]),
    "wash": ("toque", ["dish_sleeve", "dish_soap", "dish_scrub", "dish_rinse", "dish_shake", "dish_dry", "dish_stack", "dish_break"]),
    "washer": ("scarf", ["machine_load", "machine_close", "machine_start", "machine_run", "machine_run", "machine_run", "machine_done", "machine_done_last"]),
}
GAP = 12

def chore_frames(outfit, seg):
    path = os.path.join(PACK, outfit, seg + (".png" if seg.endswith("_last") else ".webp"))
    im = Image.open(path)
    w, h = (CHORE_CROP[2] - CHORE_CROP[0]) // 2, (CHORE_CROP[3] - CHORE_CROP[1]) // 2
    out = []
    n = getattr(im, "n_frames", 1)
    # A frame that does not change is stored once with the delays added up: lay the stored frames out on
    # the clip's own clock and pick, for each of the 45 frame slots, the one showing at that moment
    starts, t = [], 0
    for j in range(n):
        im.seek(j); im.load()
        starts.append(t); t += im.info.get("duration") or 70
    t = 0
    for i in range(45):
        im.seek(max(j for j in range(n) if starts[j] <= t))
        t += [70, 60, 70][i % 3]
        f = im.convert("RGBA").crop(CHORE_CROP).resize((w, h), Image.NEAREST)
        tile = Image.new("RGBA", f.size, BG + (255,))
        tile.alpha_composite(f)
        out.append((tile.convert("RGB"), [70, 60, 70][i % 3]))
    return out

def lane(name):
    outfit, segs = LANES[name]
    return [f for s in segs for f in chore_frames(outfit, s)]

lanes = {k: lane(k) for k in LANES}
for k, fr in lanes.items():
    save_gif(fr, os.path.join(OUT, f"chores-{k}.gif"))
first = next(iter(lanes.values()))
strip = []
for i in range(0, len(first), 2):            # every other frame (each shown twice as long): keeps the file small
    w, h = first[i][0].size
    im = Image.new("RGB", (3 * w + 2 * GAP, h), (255, 255, 255))
    for j, k in enumerate(LANES):
        im.paste(lanes[k][i][0], (j * (w + GAP), 0))
    strip.append((im, sum(d for _, d in first[i:i + 2])))
save_gif(strip, os.path.join(OUT, "chores.gif"))

total = 0
for n in sorted(os.listdir(OUT)):
    if n.endswith(".gif"):
        s = os.path.getsize(os.path.join(OUT, n)); total += s
        im = Image.open(os.path.join(OUT, n)); print(f"{n:28s} {s:7d} bytes {im.n_frames:3d} frames")
print("total", total)
