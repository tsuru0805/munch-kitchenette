// The settled still: once a pot is served and the backend sent its settlement, the cook's last pose is a
// still of him holding the dish (or, ruined, staring at the spilt pot). It is put together here from
// three pictures of the sprite pack: the pose (empty hands), the dish (one pixel per cell, scaled ×10 on
// the cook's grid) and a front layer with only the hands, laid back over the plate's rim.
// Plate positions come from clawd-engine-additions/tools/export_settle.py (settle.json), in canvas pixels.

export type SettlePose = "great" | "ok" | "burnt" | "spoiled" | "ruined";

export interface PlateSpot {
  /** where the middle of the plate's bottom lands */
  bottomCenter: [number, number];
  /** spoiled: column by column away from the hand, one cell lower every `tiltEvery` columns */
  tiltEvery?: number;
}

/** Engine cell = 10 canvas pixels, grid lines at x ≡ 6 (mod 10), y ≡ 0 (mod 10) */
export const CELL = 10;
const GRID_X = 6;

export const PLATES: Record<string, Record<Exclude<SettlePose, "ruined">, PlateSpot>> = {
  toque: {
    great: { bottomCenter: [306, 270] },
    ok: { bottomCenter: [466, 510] },
    burnt: { bottomCenter: [156, 510] },
    spoiled: { bottomCenter: [156, 520], tiltEvery: 3 },
  },
  scarf: {
    great: { bottomCenter: [306, 330] },
    ok: { bottomCenter: [466, 510] },
    burnt: { bottomCenter: [156, 510] },
    spoiled: { bottomCenter: [156, 520], tiltEvery: 3 },
  },
};

const ICONS = new Set([
  "stirfry", "soup", "noodles", "donburi", "friedrice", "friedegg", "fish", "meat", "steamer", "bake", "salad",
  "dessert", "drink", "bowl",
]);

/** The pose for an outcome; anything unknown is not a settled still */
export function poseFor(outcome: string): SettlePose | null {
  return outcome === "great" || outcome === "ok" || outcome === "burnt" || outcome === "spoiled" || outcome === "ruined"
    ? outcome
    : null;
}

/** The sprite-pack keys this still needs: [pose, front, dish]; dish and front are absent for "ruined" */
export function settleKeys(outfit: string, pose: SettlePose, icon: string | null | undefined): string[] {
  const keys = [`${outfit}/settle_${pose}`];
  if (pose === "ruined") return keys;
  const kind = icon && ICONS.has(icon) ? icon : "bowl";
  keys.push(`${outfit}/settle_${pose}_front`, `dishes/${kind}${pose === "burnt" ? "_burnt" : ""}_cells`);
  return keys;
}

/** Where the dish's top-left goes and how its columns drop (pure; exported for the tests) */
export function placeDish(spot: PlateSpot, cols: number, rows: number): { x: number; y: number; drop: (c: number) => number } {
  const [bx, by] = spot.bottomCenter;
  const x = Math.round((bx - (cols * CELL) / 2 - GRID_X) / CELL) * CELL + GRID_X;
  const n = spot.tiltEvery;
  // tipped outwards (to the left): the column by the hand stays where it is, its bottom on bottomCenter's
  // height; every n columns further out sit one cell lower
  const drop = n ? (c: number) => Math.floor((cols - 1 - c) / n) : () => 0;
  return { x, y: by - rows * CELL, drop };
}

/**
 * Draws the still onto a 720 × 720 canvas: pose, dish, front. Images must be loaded. Returns false when
 * the canvas cannot be drawn on (no 2D context), and the caller keeps the ordinary last frame.
 */
export function drawSettle(
  canvas: HTMLCanvasElement, pose: SettlePose, outfit: string,
  imgs: { pose: CanvasImageSource; front?: CanvasImageSource; dish?: HTMLImageElement },
): boolean {
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;
  canvas.width = 720;
  canvas.height = 720;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, 720, 720);
  ctx.drawImage(imgs.pose, 0, 0);
  if (pose !== "ruined" && imgs.dish) {
    const spot = PLATES[outfit]?.[pose] ?? PLATES.toque[pose];
    const cols = imgs.dish.naturalWidth;
    const rows = imgs.dish.naturalHeight;
    const p = placeDish(spot, cols, rows);
    for (let c = 0; c < cols; c++) {
      ctx.drawImage(imgs.dish, c, 0, 1, rows, p.x + c * CELL, p.y + p.drop(c) * CELL, CELL, rows * CELL);
    }
  }
  if (imgs.front) ctx.drawImage(imgs.front, 0, 0);
  return true;
}

// ── showing the still inside the card's left column ──
//
// Every settled still is shown through the same frame of the engine canvas, at the same scale, so the
// five poses stand the same size with their feet on one line, whichever pose and dish a card has; the frame
// sits in the middle of the column, top to bottom.
// The frame holds every still of the built-in pack (five poses x fourteen dishes x two outfits; measured
// from the pictures, and the dish positions are checked by a test). To keep it narrow enough for the cook
// to be shown large, the props were drawn closer to him: the ruined pot's pot and lid
// (states/settle/settle-ruined.cjs), and the burnt and spoiled plates (PLATES above). Its left edge is the
// ok pose's left hand and the ruined pose's left hand, its right edge the burnt pose's drop of sweat; its
// top the sparkles over the dish held up, its bottom the feet line.

/** The frame on the 720 x 720 engine canvas: on the cell grid, its bottom on the feet line (SRC_LINE_Y) */
export const PIC_FRAME = { x: 96, y: 150, w: 480, h: 410 } as const;
/** One engine cell = 4 CSS px (the cook's body 96 px wide) */
export const PIC_SCALE = 0.4;
/** On a narrow card (under PIC_NARROW_BELOW_PX wide) every still is shown at this scale instead: 3 CSS px a cell */
export const PIC_SCALE_NARROW = 0.3;
export const PIC_NARROW_BELOW_PX = 360;
/** Space above and below the frame inside the column (CSS px) */
export const PIC_PAD_Y = 8;

/** Size of the frame as shown, and the width of the picture column (CSS px), at a scale */
export function picBox(scale: number): { w: number; h: number; col: number; minH: number } {
  const w = PIC_FRAME.w * scale;
  const h = PIC_FRAME.h * scale;
  return { w, h, col: Math.ceil(w), minH: Math.ceil(h) + 2 * PIC_PAD_Y };
}

/** Cuts the frame out of a drawn still (the same frame for every pose). Null when there is no 2D context. */
export function frameStill(src: CanvasImageSource): HTMLCanvasElement | null {
  const out = document.createElement("canvas");
  out.width = PIC_FRAME.w;
  out.height = PIC_FRAME.h;
  const o = out.getContext("2d");
  if (!o) return null;
  o.imageSmoothingEnabled = false;
  o.drawImage(src, PIC_FRAME.x, PIC_FRAME.y, PIC_FRAME.w, PIC_FRAME.h, 0, 0, PIC_FRAME.w, PIC_FRAME.h);
  return out;
}

/**
 * The drawn stills, shared by every card on the page, by the URLs of their pictures. A still that failed to
 * load (a picture missing, a network hiccup) is not given up for good: each card asks again once, the next
 * time it is put on the page (`tried` is that card's own list for its current appearance).
 */
export class StillCache<T> {
  #m = new Map<string, { state: "loading"; waiting: Set<() => void> } | { state: "failed" } | { state: "ready"; value: T }>();

  /**
   * The still when it is ready, else null; starts loading it when nobody is, and either nobody tried yet or it
   * failed and this card has not tried in this appearance. While it is loading (started by this card or by
   * another one), `done` is kept and called once when the load settles, so every card waiting for the same
   * pictures draws itself again.
   */
  get(key: string, tried: Set<string>, load: () => Promise<T | null>, done: () => void): T | null {
    const e = this.#m.get(key);
    if (e?.state === "ready") return e.value;
    if (e?.state === "loading") {
      e.waiting.add(done);
      return null;
    }
    if (e?.state === "failed" && tried.has(key)) return null;
    tried.add(key);
    const entry = { state: "loading" as const, waiting: new Set([done]) };
    this.#m.set(key, entry);
    load()
      .then((v) => this.#m.set(key, v === null ? { state: "failed" } : { state: "ready", value: v }))
      .catch(() => this.#m.set(key, { state: "failed" }))
      .finally(() => {
        for (const fn of entry.waiting) {
          try {
            fn();
          } catch {
            // one card failing to redraw does not keep the others from it
          }
        }
      });
    return null;
  }

  /** For tests */
  state(key: string): "loading" | "failed" | "ready" | undefined {
    return this.#m.get(key)?.state;
  }
}
