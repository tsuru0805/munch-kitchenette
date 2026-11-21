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
    burnt: { bottomCenter: [146, 510] },
    spoiled: { bottomCenter: [136, 520], tiltEvery: 3 },
  },
  scarf: {
    great: { bottomCenter: [306, 330] },
    ok: { bottomCenter: [466, 510] },
    burnt: { bottomCenter: [146, 510] },
    spoiled: { bottomCenter: [136, 520], tiltEvery: 3 },
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
