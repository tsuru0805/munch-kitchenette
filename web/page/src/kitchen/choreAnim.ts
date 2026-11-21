// Which chore clip the cook plays in a panel of the sheet: washing plates by hand, loading the dishwasher,
// buying from the vendor. Pure functions of the server's facts and the time; the panel only plays what
// these name. Nothing is drawn onto the kitchen picture.
//
//   Washing up   each plate's time (job.per_s) is cut into seven equal parts, played in turn, each part
//                looping its clip: roll up the sleeves -> soap -> scrub -> rinse -> shake the water off ->
//                dry -> stack. The sleeves are rolled up once, at the start of the washing: from the
//                second plate on, the first part is soap as well. Whether a plate broke is only told once
//                its time is up (job.breaks never names a plate still to come): a plate that turns out
//                broken then has the dropped plate, played once, and its last frame for a moment
//                (BREAK_SHOW_MS from the plate's due time), before the next plate goes on.
//   Dishwasher   when plates last went in (machine_at): load -> close -> start -> running (8 s) -> done,
//                which plays once and stays on its last frame.
//   Vendor       a vendor is downstairs: calling him over. The role's latest order of this visit: paying
//                while it is being paid (not when the human treats), then taking the bag (once) and
//                carrying it back (9 s); refunded or failed orders take nothing.
//
// Segment name = file name in assets/clawd/<outfit>/ (registered in web/src/manifest.ts, CHORE_SEGMENTS).
// The outfit follows the card's rule (web/src/cookSegments.ts outfitFor): the washing's id, the order id,
// the visit id. "Reduce motion": the last frame of a clip that has one, otherwise the still base pose.

import type { Plates, VendorView } from "./playApi";

/** One clip, as long as every clip (45 frames at 70 / 60 / 70 ms) */
export const CLIP_MS = 3000;
export const WASHER_RUN_MS = 8000;
export const CARRY_MS = 9000;
/** How long after a broken plate's due time the dropped plate shows (the clip, then its last frame) */
export const BREAK_SHOW_MS = 5000;
export const OUTFITS = ["toque", "scarf"] as const;
export type Outfit = (typeof OUTFITS)[number];

export const WASH_PARTS = ["dish_sleeve", "dish_soap", "dish_scrub", "dish_rinse", "dish_shake", "dish_dry", "dish_stack"] as const;
export const WASHER_STEPS: readonly [string, number][] = [
  ["machine_load", CLIP_MS], ["machine_close", CLIP_MS], ["machine_start", CLIP_MS], ["machine_run", WASHER_RUN_MS], ["machine_done", CLIP_MS],
];
/** The clips that play once and then stay on their `_last` frame */
export const ONCE = ["vendor_take", "dish_break", "machine_done"] as const;

export interface ChoreClip {
  segment: string;
  outfit: Outfit;
  /** Changes whenever the clip should start again from its first frame (a new plate, a new step) */
  run: string;
}

/** Stable string hash (FNV-1a over code points), the same as the card's (web/src/cookSegments.ts) */
export function hashStr(s: string): number {
  let h = 0x811c9dc5;
  for (const ch of Array.from(s)) {
    h ^= ch.codePointAt(0) ?? 0;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export function outfitFor(id: string): Outfit {
  return OUTFITS[hashStr(id) % OUTFITS.length];
}

export interface WashJobFacts { id: string; startedAt: number; perS: number; n: number; endedAt: number | null; breaks: number[] }

/** How long the last step of a plate goes on past its due time while the page reads its result */
export const RESULT_WAIT_S = 2;

/**
 * The washing-up clip at `nowS` (server seconds); null = nobody is washing now. `readS` = the server time of
 * the answer `job` came from: a plate due after it has no result yet, so its last step goes on a moment
 * (RESULT_WAIT_S) while the page reads again, instead of starting the next plate and then breaking this one.
 */
export function washClip(job: WashJobFacts | null, nowS: number, readS = Infinity): ChoreClip | null {
  if (!job || job.n <= 0 || !(job.perS > 0)) return null;
  const end = job.endedAt ?? job.startedAt + job.n * job.perS; // stopped early: ended_at
  if (nowS < job.startedAt) return null;
  const el = nowS - job.startedAt;
  const outfit = outfitFor(job.id);
  // the plate whose time was up last, if it turned out broken and that was a moment ago: the dropped plate
  const due = Math.floor(el / job.perS) - 1;
  const dueAt = job.startedAt + (due + 1) * job.perS;
  if (due >= 0 && due < job.n && dueAt <= end && job.breaks.includes(due) && (nowS - dueAt) * 1000 < BREAK_SHOW_MS) {
    return { segment: (nowS - dueAt) * 1000 < CLIP_MS ? "dish_break" : "dish_break_last", outfit, run: `${job.id}:${due}:break` };
  }
  if (due >= 0 && due < job.n && dueAt <= end && dueAt > readS && nowS - dueAt < RESULT_WAIT_S) {
    return { segment: WASH_PARTS[WASH_PARTS.length - 1], outfit, run: `${job.id}:${due}:${WASH_PARTS.length - 1}` };
  }
  if (nowS >= end) return null;
  const plate = Math.min(job.n - 1, Math.floor(el / job.perS));
  const inPlate = el - plate * job.perS;
  const part = Math.min(WASH_PARTS.length - 1, Math.floor((inPlate / job.perS) * WASH_PARTS.length));
  if (part === 0 && plate > 0) {
    // the sleeves stay rolled up: soap takes the first two sevenths
    return { segment: "dish_soap", outfit, run: `${job.id}:${plate}:1` };
  }
  return { segment: WASH_PARTS[part], outfit, run: `${job.id}:${plate}:${part}` };
}

/** When the page should read the plates again to learn the next plate's result (server seconds; null = none to come) */
export function nextPlateDue(job: WashJobFacts | null, nowS: number): number | null {
  if (!job || job.n <= 0 || !(job.perS > 0)) return null;
  const end = job.endedAt ?? job.startedAt + job.n * job.perS;
  const next = job.startedAt + (Math.floor(Math.max(0, nowS - job.startedAt) / job.perS) + 1) * job.perS;
  return next <= end ? next : null;
}

/** The dishwasher clip at `nowS`; null = no plate has gone into it (or none is in it) */
export function washerClip(machineAt: number | null, inMachine: number, nowS: number, id = "dishwasher"): ChoreClip | null {
  if (machineAt === null || inMachine <= 0) return null;
  const outfit = outfitFor(`${id}:${machineAt}`);
  let t = Math.max(0, (nowS - machineAt) * 1000);
  for (const [segment, ms] of WASHER_STEPS) {
    if (t < ms) return { segment, outfit, run: `${machineAt}:${segment}` };
    t -= ms;
  }
  return { segment: "machine_done_last", outfit, run: `${machineAt}:done_last` };
}

export interface VendorOrderFacts { id: string; payer: string; state: string; createdAt: number; updatedAt: number }

/** The vendor clip at `nowS`; null = no vendor downstairs */
export function vendorClip(visitId: string | null, mine: VendorOrderFacts[], nowS: number): ChoreClip | null {
  if (!visitId) return null;
  const last = mine.reduce<VendorOrderFacts | null>((a, o) => (!a || o.createdAt >= a.createdAt ? o : a), null);
  if (last) {
    const outfit = outfitFor(last.id);
    const treated = last.payer === "her";
    if (last.state === "created" || last.state === "debiting" || last.state === "paid") {
      // paying (the human's treat costs the role nothing: no paying, he just waits at the window)
      return treated ? { segment: "vendor_call", outfit, run: `${last.id}:call` } : { segment: "vendor_pay", outfit, run: `${last.id}:pay` };
    }
    if (last.state === "delivered") {
      const since = (nowS - last.updatedAt) * 1000;
      if (since < CLIP_MS) return { segment: "vendor_take", outfit, run: `${last.id}:take` };
      if (since < CLIP_MS + CARRY_MS) return { segment: "vendor_carry", outfit, run: `${last.id}:carry` };
    }
    // refunding / refunded / debit failed: nothing is taken; and after carrying it back: at the window again
  }
  return { segment: "vendor_call", outfit: outfitFor(visitId), run: `${visitId}:call` };
}

/** "Reduce motion": what stands still in place of `segment` */
export function stillFor(segment: string): string {
  if (segment.endsWith("_last") || segment === "base") return segment;
  return (ONCE as readonly string[]).includes(segment) ? `${segment}_last` : "base";
}

// ── from what the page read ─────────────────────────────────────────────

/** Server seconds at this device's `nowMs`, from an answer read at `readAt` carrying the server's `now` */
export function serverNow(now: number, readAt: number, nowMs: number): number {
  return now + Math.max(0, nowMs - readAt) / 1000;
}

/** The plates panel: the washing-up while it runs, otherwise the dishwasher */
export function platesClip(p: Plates, nowMs: number): ChoreClip | null {
  const t = serverNow(p.now, p.readAt, nowMs);
  return washClip(p.job, t, p.now) ?? washerClip(p.machineAt, p.machine, t);
}

/** The vendor panel */
export function vendorPanelClip(v: VendorView, nowMs: number): ChoreClip | null {
  return vendorClip(v.visit?.id || null, v.mine, serverNow(v.now, v.readAt, nowMs));
}
