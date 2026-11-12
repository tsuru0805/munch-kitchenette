// Which clip the cook plays at this moment. Pure function; the element only plays what this names.
//
// Everything is recomputed from facts each time, so a card that is mounted again (scrolled back,
// page reloaded) lands directly on the segment it should be in.
//   1. Progress through the cooking time
//      wash    only for a pot that was just started and that this page sees for the first time,
//              once (3 s); skipped for quick dishes under 3 minutes
//      chop    the first 20% of the time, at most 5 minutes
//      main    the method's main action; inside every 30 s there is a fixed window (seconds 12-15)
//              for one small action (wipe the brow / look up / caught by the steam). Which one is
//              decided by "this pot + which 30 s slot", so reopening at the same moment shows the
//              same one. One of the four choices is "nothing this time".
//      taste   the last 10% of the time, at most 2 minutes
//   2. The outcome (only known when the pot is due)
//      good = plate it and bring it out -> still frame; burnt / spoiled = the fail clip -> still frame;
//      cancelled = leaves while still doing the main action
//   3. Fixed the moment the pot starts: the method (from the backend) and the outfit (from the pot id)
//
// Segment name = asset file name: wash / chop / <method>_<main|wipe|look|hot|taste|serve|fail> /
// <method>_<serve|fail>_last. Asset key = "<outfit>/<segment>" (see manifest.ts).
import { FRESH_S, isFailOutcome, kitchenTiming, type KitchenOutcome, type KitchenPhase } from "./cookPhase";

export const COOK_METHODS = ["stirfry", "fry", "deepfry", "boil", "steam", "bake", "mix"] as const;
export type CookMethod = (typeof COOK_METHODS)[number];
export type CookOutfit = "toque" | "scarf";
export const COOK_OUTFITS: readonly CookOutfit[] = ["toque", "scarf"];

/** Unknown or missing method = stir-fry, the same fallback the backend uses when it cannot guess */
export const METHOD_DEFAULT: CookMethod = "stirfry";
export const METHOD_LABEL: Record<CookMethod, string> = {
  stirfry: "炒", fry: "煎", deepfry: "炸", boil: "煮", steam: "蒸", bake: "烤", mix: "拌",
};

export function parseMethod(v: unknown): CookMethod {
  return typeof v === "string" && (COOK_METHODS as readonly string[]).includes(v) ? (v as CookMethod) : METHOD_DEFAULT;
}

/** Stable string hash (FNV-1a over code points) */
export function hashStr(s: string): number {
  let h = 0x811c9dc5;
  for (const ch of Array.from(s)) {
    h ^= ch.codePointAt(0) ?? 0;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/**
 * Which outfit this pot wears: decided by the pot id, so one pot never changes clothes.
 * A sprite pack with other outfits passes its own list (see docs/ANIMATION.md).
 */
export function outfitFor(sessionId: string): CookOutfit;
export function outfitFor(sessionId: string, outfits: readonly string[]): string;
export function outfitFor(sessionId: string, outfits: readonly string[] = COOK_OUTFITS): string {
  return outfits[hashStr(sessionId) % outfits.length];
}

/** Length of one clip (45 frames at 70/60/70 ms) */
export const CLIP_MS = 3000;
/** Dishes shorter than this skip the hand-washing */
export const WASH_MIN_TOTAL_S = 180;
export const CHOP_FRAC = 0.2;
export const CHOP_MAX_S = 300;
export const TASTE_FRAC = 0.1;
export const TASTE_MAX_S = 120;
/** The beat of the small actions: one slot every SLOT_S seconds; the action plays once from second IDLE_AT_S of the slot */
export const SLOT_S = 30;
export const IDLE_AT_S = 12;
const IDLES = [null, "wipe", "look", "hot"] as const;

export interface CookSegmentInput {
  phase: KitchenPhase;
  nowMs: number;
  /** When the pot started (epoch seconds) */
  startedAt: number;
  durationSec: number;
  mountedAtMs: number;
  firstSeen: boolean;
  /** Time since the reveal (ms; negative before it) */
  sinceRevealMs: number;
  outcome: KitchenOutcome | null;
  method: CookMethod;
  sessionId: string;
}

/** The segment to play right now; null = the cook is not on stage */
export function cookSegment(i: CookSegmentInput): string | null {
  const m = i.method;
  if (i.phase === "done" || i.phase === "cancelled") return null;
  const fail = isFailOutcome(i.outcome);
  const swapMs = kitchenTiming().swapMs;
  if (i.phase === "serve") {
    const k = fail ? "fail" : "serve";
    return i.sinceRevealMs < swapMs ? `${m}_${k}` : `${m}_${k}_last`;
  }
  if (i.phase === "exit") {
    if (i.sinceRevealMs < 0) return `${m}_main`; // cancelled: nothing was revealed, so nothing is carried out
    return fail ? `${m}_fail_last` : `${m}_serve_last`;
  }
  // enter / stir: by progress
  const startMs = i.startedAt * 1000;
  const totalMs = Math.max(0, i.durationSec) * 1000;
  const el = i.nowMs - startMs;
  if (el >= totalMs) return `${m}_main`; // due, outcome not here yet: keep cooking
  const fresh = i.firstSeen && i.mountedAtMs - startMs <= FRESH_S * 1000;
  if (fresh && totalMs >= WASH_MIN_TOTAL_S * 1000 && i.nowMs < i.mountedAtMs + CLIP_MS) return "wash";
  if (el < Math.min(totalMs * CHOP_FRAC, CHOP_MAX_S * 1000)) return "chop";
  if (el >= totalMs - Math.min(totalMs * TASTE_FRAC, TASTE_MAX_S * 1000)) return `${m}_taste`;
  const slot = Math.floor(el / (SLOT_S * 1000));
  const inSlot = el - slot * SLOT_S * 1000;
  const idle = IDLES[hashStr(`${i.sessionId}:${slot}`) % IDLES.length];
  if (idle && inSlot >= IDLE_AT_S * 1000 && inSlot < IDLE_AT_S * 1000 + CLIP_MS) return `${m}_${idle}`;
  return `${m}_main`;
}

/** Asset key */
export function assetKey(outfit: string, segment: string): string {
  return `${outfit}/${segment}`;
}
