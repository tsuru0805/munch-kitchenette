"""An artwork provider for ingredient kinds added from the page.
给页面上新添的食材画小图的函数（例子）。

A provider is a function `draw(name, category)` returning PNG bytes for the
three looks of the ingredient: fresh, stale ("meh") and spoiled ("bad").
Switch it on in kitchenette.toml (the module must be importable, e.g. run the
server from the repository root):

    [art]
    provider = "examples.art_provider:draw"

This one needs no image model: it paints a flat tile, coloured by category
and dulled as the food ages, so you can see the whole path work. Replace the
body of `draw` with a call to your image generator and return its bytes.
Drawing happens in the background, one kind at a time; raise an exception to
record a failure the page can show and retry.
"""
from __future__ import annotations

import struct
import zlib

SIZE = 128
BASE = {"leafy": (96, 170, 84), "veg": (214, 92, 70), "root": (204, 150, 82), "dairy": (240, 232, 208),
        "meat": (196, 98, 104), "staple_food": (226, 200, 150), "fruit": (236, 120, 140)}
AGE = {"fresh": 1.0, "meh": 0.78, "bad": 0.5}


def _png(rgb: tuple[int, int, int], size: int = SIZE) -> bytes:
    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    row = b"\x00" + bytes(rgb) * size
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * size))
            + chunk(b"IEND", b""))


def draw(name: str, category: str) -> dict[str, bytes]:
    base = BASE.get(category, (200, 200, 200))
    return {state: _png(tuple(int(c * k) for c in base)) for state, k in AGE.items()}


if __name__ == "__main__":
    for state, data in draw("柿子", "fruit").items():
        print(state, len(data), "bytes of PNG")
