// The sprite registry: which image file plays for each "<outfit>/<segment>".
// The built-in registry is the Clawd pack in assets/clawd/. To use your own character, hand the
// element a registry of the same shape (see docs/ANIMATION.md for the image spec).
import { COOK_METHODS, assetKey } from "./cookSegments";

export interface SpriteManifest {
  /** Free-form name of the pack */
  name?: string;
  /** Outfit folders. A pot wears outfits[hash(pot id) % outfits.length] from start to finish. */
  outfits: string[];
  /** "<outfit>/<segment>" -> file path relative to the pack's base URL */
  files: Record<string, string>;
}

/** The parts every method has. `_last` parts are still images, the rest are 3 s animated clips. */
export const METHOD_PARTS = ["main", "wipe", "look", "hot", "taste", "serve", "fail", "serve_last", "fail_last"] as const;

/** Every segment an outfit needs: the still base pose, wash, chop, and nine parts for each of the seven methods. */
export function requiredSegments(): string[] {
  const segs = ["base", "wash", "chop"];
  for (const m of COOK_METHODS) for (const k of METHOD_PARTS) segs.push(`${m}_${k}`);
  return segs;
}

/**
 * The chores: washing plates by hand (played by the washing card in the chat), the vendor at his cart and
 * loading the dishwasher (played by the kitchen page). Optional for a pack of your own: without them the
 * washing card only counts, and the page shows no cook in those panels. `_last` = the still last frame of
 * a clip that plays once. The vendor's scenes come in two looks of the cart: `vendor_th_` for the tanghulu
 * seller, `vendor_` for every other vendor; `_still` is the vendor standing by his cart ("reduce motion").
 */
export const CHORE_SEGMENTS = [
  "vendor_arrive", "vendor_call", "vendor_wait", "vendor_leave", "vendor_leave_last", "vendor_walkin", "vendor_walkin_last", "vendor_pay",
  "vendor_give", "vendor_give_last", "vendor_eat", "vendor_eat_last", "vendor_walkout", "vendor_walkout_hold", "vendor_walkout_empty", "vendor_still",
  "vendor_th_arrive", "vendor_th_call", "vendor_th_wait", "vendor_th_leave", "vendor_th_leave_last", "vendor_th_walkin", "vendor_th_walkin_last", "vendor_th_pay",
  "vendor_th_give", "vendor_th_give_last", "vendor_th_eat", "vendor_th_eat_last", "vendor_th_walkout", "vendor_th_walkout_hold", "vendor_th_walkout_empty", "vendor_th_still",
  "dish_sleeve", "dish_soap", "dish_scrub", "dish_rinse", "dish_shake", "dish_dry", "dish_stack", "dish_break", "dish_break_last",
  "machine_load", "machine_close", "machine_start", "machine_run", "machine_done", "machine_done_last",
] as const;

/** Chore keys a registry is missing (empty = the page can show every chore) */
export function missingChoreKeys(manifest: SpriteManifest): string[] {
  return manifest.outfits.flatMap((o) => CHORE_SEGMENTS.map((s) => assetKey(o, s))).filter((k) => manifest.files[k] === undefined);
}

/** Keys a registry is missing. Empty = complete. */
export function missingKeys(manifest: SpriteManifest): string[] {
  const missing: string[] = [];
  for (const o of manifest.outfits) {
    for (const s of requiredSegments()) if (manifest.files[assetKey(o, s)] === undefined) missing.push(assetKey(o, s));
  }
  return missing;
}

// ── Canvas geometry (source pixels -> CSS pixels) ──
export const SRC_CANVAS = 720;
/** The cut line: this row of the image sits on the card's top edge */
export const SRC_LINE_Y = 560;
/** Displayed side of the square canvas */
export const CANVAS_PX = 180;
/** 140: stage height = everything above the cut line */
export const STAGE_PX = (CANVAS_PX * SRC_LINE_Y) / SRC_CANVAS;
