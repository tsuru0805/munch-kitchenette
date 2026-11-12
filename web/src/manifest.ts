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
