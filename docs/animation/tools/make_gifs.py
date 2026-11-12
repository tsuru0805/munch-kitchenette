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
          "Luin Luinaris, postie concept & pixel corrections by Charlie Luinaris. Chef outfits & cooking moves by tsuru0805 "
          "for munch-kitchenette. Unofficial fan work. Clawd (c) Anthropic. Art CC BY-NC-SA 4.0.")
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
total = 0
for n in sorted(os.listdir(OUT)):
    if n.endswith(".gif"):
        s = os.path.getsize(os.path.join(OUT, n)); total += s
        im = Image.open(os.path.join(OUT, n)); print(f"{n:28s} {s:7d} bytes {im.n_frames:3d} frames")
print("total", total)
