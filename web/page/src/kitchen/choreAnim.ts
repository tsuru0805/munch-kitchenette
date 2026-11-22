// Which chore clip plays in a panel of the sheet: loading the dishwasher, the vendor at his cart. Nothing is
// drawn onto the kitchen picture. (Washing plates by hand is a process, and plays where the other processes
// do: on its card in the chat, web/src/washSegments.ts.)
//
//   Dishwasher   a pure function of when plates last went in (machine_at): load -> close -> start ->
//                running (8 s) -> done, which plays once and stays on its last frame.
//   Vendor       a small player per visit (VendorShow), because the server's facts can move faster than the
//                show: an order may be paid and delivered within a second, a poll may come late, the page
//                may sleep, the visit may end while the cook is still at the cart. Every act starts when
//                this device starts showing it and is shown in full before the next one: time that passed
//                unseen never counts as played. A visit always plays in this order:
//                  he pushes the cart in (the first time this device shows the visit, before anything else);
//                  then, for each of the role's orders, oldest first: the cook walks over; pays (only when
//                  the role pays, at least one clip, and for as long as it is being charged); stands and
//                  waits if it is not through yet (a treat); then he hands it over, the cook eats a bite
//                  (a snack) or holds it (anything else), and walks back out carrying it, or, if nothing
//                  came of it (refunded, charge failed), walks back out empty-handed, once;
//                  between orders he calls with his hand bell for 3 s every 15 s and waits;
//                  from the last 3 s of the visit (or once it is over), when no order is on stage, he pushes
//                  the cart away, and the roadside stays empty. An order that turns up while he is leaving
//                  or gone (placed in the last seconds, or read late) brings him back: he pushes the cart in
//                  again, the order plays, and he leaves again. The server returns a visit that just ended as
//                  `ended` for a short while; after that the show finishes from the facts it last had (an
//                  order not through by then is closed with the cook walking back out empty-handed). The
//                  same when a new visit takes over straight away: the old show finishes first (its order,
//                  then that vendor leaving), and only then does the new vendor arrive; meanwhile the new
//                  show takes in its visit's facts (each order noted when first read), without playing.
//                Only an order already finished more than STALE_S before this device first saw it is
//                skipped. Shows are kept per server + role + visit, a few at a time; a show remembers its
//                finished orders as one mark (orders play oldest first, so all up to the mark are over). The tanghulu seller's cart has a straw bundle of candied
//                haws (`vendor_th_*`); every other vendor's a crate of paper bags (`vendor_*`).
//
// Segment name = file name in assets/clawd/<outfit>/ (registered in web/src/manifest.ts, CHORE_SEGMENTS).
// The outfit follows the card's rule (web/src/cookSegments.ts outfitFor): the order id; the vendor alone is
// the same file in both outfits. "Reduce motion": the last frame of a clip that has one; for the vendor
// otherwise him standing by his cart (`_still`); otherwise the still base pose. The vendor's player goes on
// in time either way; only what is shown is still.

import type { Plates, VendorView } from "./playApi";

/** One clip, as long as every clip (45 frames at 70 / 60 / 70 ms) */
export const CLIP_MS = 3000;
export const WASHER_RUN_MS = 8000;
/** The vendor calls (one clip) once every this long; he waits in between */
export const CALL_EVERY_MS = 15000;
export const OUTFITS = ["toque", "scarf"] as const;
export type Outfit = (typeof OUTFITS)[number];

export const WASHER_STEPS: readonly [string, number][] = [
  ["machine_load", CLIP_MS], ["machine_close", CLIP_MS], ["machine_start", CLIP_MS], ["machine_run", WASHER_RUN_MS], ["machine_done", CLIP_MS],
];
/** The clips that play once and then stay on their `_last` frame (and, below, the vendor's) */
export const ONCE = ["machine_done"] as const;
const VENDOR_SEG = /^(vendor_(?:th_)?)(arrive|call|wait|leave|walkin|pay|give|eat|walkout|walkout_hold|walkout_empty)$/;
const VENDOR_ONCE = ["leave", "give", "eat", "walkin"];

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

export interface VendorOrderFacts { id: string; payer: string; state: string; createdAt: number; updatedAt: number; kind?: string }
/**
 * `ended` = the visit is over (the server still returns it for a short while so the show can finish);
 * `frozen` = the server says nothing about it any more: the show finishes from what it last knew.
 */
export interface VendorVisitFacts { id: string; vendor: string; leaveAt: number; ended?: boolean; frozen?: boolean }

/** Which look of the cart: the tanghulu seller's, or every other vendor's */
export function vendorPrefix(vendor: string): "vendor_th_" | "vendor_" {
  return vendor === "tanghulu" ? "vendor_th_" : "vendor_";
}

const CLIP_S = CLIP_MS / 1000;
const CALL_EVERY_S = CALL_EVERY_MS / 1000;
/** An order already finished this long (seconds) before this device first saw it is not played */
export const STALE_S = 30;
/** How many shows the page keeps at once (finished ones of other visits go first) */
export const MAX_SHOWS = 8;
const PAYING = new Set(["created", "debiting", "paid"]);
const NOTHING = new Set(["debit_failed", "refunding", "refunded"]);
const FINISHED = new Set(["delivered", "debit_failed", "refunding", "refunded"]);

type Phase = "walkin" | "pay" | "stand" | "give" | "eat" | "hold" | "walkout" | "walkout_hold" | "walkout_empty";
interface Act { kind: "arrive" | "idle" | "order" | "leave" | "gone"; start: number; order?: string; phase?: Phase }
interface Pending { facts: VendorOrderFacts; firstSeen: number; paid: boolean }

/**
 * The vendor's show for one visit on this device. `pick` is asked for the clip at `nowS` (server seconds)
 * with the latest facts. Every act starts at the moment this device starts showing it and is shown in full
 * before the next one starts: time that passed while nobody was looking (the page asleep, a late answer)
 * never counts as played. So nothing that has not been shown is skipped, and nothing is shown twice.
 */
export class VendorShow {
  private act: Act | null = null;
  // Orders play strictly oldest first, so "everything up to this one is over" is all a show has to remember
  // about finished orders (played, or let go as long done): one mark, however many orders a visit has
  private mark: { createdAt: number; id: string } | null = null;
  private pending = new Map<string, Pending>();

  constructor(readonly visitId: string) {}

  pick(visit: VendorVisitFacts, mine: VendorOrderFacts[], nowS: number): ChoreClip {
    this.observe(mine, nowS);
    if (!this.act) this.act = { kind: "arrive", start: nowS };
    // an act that is over gives way to the next, starting now; one that has just started is never over
    // at once, so this stops after a few steps (an open-ended act can end at once: waiting, standing)
    for (let k = 0; k < 8 && this.over(this.act, visit, nowS); k++) this.act = this.next(visit, nowS);
    return this.clip(this.act, visit, nowS);
  }

  /** The show has nothing left to show: he has left and no order is waiting */
  isDone(visit: VendorVisitFacts, nowS: number): boolean {
    return this.act?.kind === "gone" && this.waiting(nowS) === null && this.leaving(visit, nowS);
  }

  /** For tests: what the show keeps (orders not over yet; finished ones are one mark) */
  sizes(): { pending: number } {
    return { pending: this.pending.size };
  }

  /**
   * Take in the facts without moving the show on (it is waiting for the panel: another visit's show is still
   * finishing). Each order is noted with when this device first saw it, so it is not let go as long done
   * merely because the show got to it late.
   */
  observe(mine: VendorOrderFacts[], nowS: number): void {
    for (const o of mine) {
      if (this.isOver(o)) continue;
      const p = this.pending.get(o.id);
      if (p) p.facts = o;
      else this.pending.set(o.id, { facts: o, firstSeen: nowS, paid: false });
    }
  }

  /** The facts of the orders this show still has to play (all a page needs to keep to finish it later) */
  unfinished(): VendorOrderFacts[] {
    return [...this.pending.values()].map((p) => p.facts);
  }

  private isOver(o: VendorOrderFacts): boolean {
    const m = this.mark;
    return !!m && (o.createdAt < m.createdAt || (o.createdAt === m.createdAt && o.id <= m.id));
  }

  private over(a: Act, visit: VendorVisitFacts, nowS: number): boolean {
    switch (a.kind) {
      case "arrive": case "leave": return nowS >= a.start + CLIP_S;
      case "gone": return this.waiting(nowS) !== null;            // an order after all: he comes back
      case "idle": return this.waiting(nowS) !== null || this.leaving(visit, nowS);
      case "order": {
        const o = this.pending.get(a.order!)?.facts;
        if (!o) return true;
        if (a.phase === "pay") return nowS >= a.start + CLIP_S && (!!visit.frozen || !PAYING.has(o.state));
        if (a.phase === "stand") return !!visit.frozen || FINISHED.has(o.state);
        return nowS >= a.start + CLIP_S;
      }
    }
  }

  private leaving(visit: VendorVisitFacts, nowS: number): boolean {
    return !!visit.ended || !!visit.frozen || nowS >= visit.leaveAt - CLIP_S;
  }

  /** The oldest order not played yet (placed by now); orders long finished before this device saw them are let go */
  private waiting(nowS: number): VendorOrderFacts | null {
    const list = [...this.pending.values()].sort((a, b) => a.facts.createdAt - b.facts.createdAt || (a.facts.id < b.facts.id ? -1 : 1));
    for (const p of list) {
      const o = p.facts;
      if (this.act?.order === o.id) continue;
      if (FINISHED.has(o.state) && p.firstSeen - o.updatedAt > STALE_S) { this.finish(o.id); continue; }
      if (o.createdAt <= nowS + 1) return o;
    }
    return null;
  }

  private finish(id: string): void {
    const p = this.pending.get(id);
    this.pending.delete(id);
    if (p && (!this.mark || !this.isOver(p.facts))) this.mark = { createdAt: p.facts.createdAt, id };
  }

  /** The act after the current one, starting now */
  private next(visit: VendorVisitFacts, nowS: number): Act {
    const a = this.act!;
    if (a.kind === "order") {
      const step = this.orderStep(a, visit, nowS);
      if (step) return step;
    }
    const o = this.waiting(nowS);
    // he had left (or was leaving) and an order came after all: he pushes his cart back in first
    if (a.kind === "leave" || a.kind === "gone") return o ? { kind: "arrive", start: nowS } : { kind: "gone", start: nowS };
    if (o) return { kind: "order", order: o.id, phase: "walkin", start: nowS };
    if (this.leaving(visit, nowS)) return { kind: "leave", start: nowS };
    return { kind: "idle", start: nowS };
  }

  /** The order's next phase, or null when it is over (walked back out, or no longer known) */
  private orderStep(a: Act, visit: VendorVisitFacts, nowS: number): Act | null {
    const id = a.order!, p = this.pending.get(id);
    if (!p) return null;
    const o = p.facts;
    const at = (phase: Phase): Act => ({ kind: "order", order: id, phase, start: nowS });
    // what happened decides what comes after walking over / paying / standing; with the facts frozen, an
    // order not through is closed: the cook walks back out empty-handed
    const outcome = (): Act => (o.state === "delivered" ? at("give") : NOTHING.has(o.state) || visit.frozen ? at("walkout_empty") : at("stand"));
    switch (a.phase) {
      case "walkin":
        if (o.payer !== "her" && o.state !== "debit_failed" && !p.paid) { p.paid = true; return at("pay"); }
        return outcome();
      case "pay": case "stand": return outcome();
      case "give": return at(o.kind === "snack" ? "eat" : "hold");
      case "eat": return at("walkout");
      case "hold": return at("walkout_hold");
      default: this.finish(id); return null;   // walked back out: this order is over, for good
    }
  }

  private clip(a: Act, visit: VendorVisitFacts, nowS: number): ChoreClip {
    const P = vendorPrefix(visit.vendor);
    const alone = outfitFor(this.visitId);
    switch (a.kind) {
      case "arrive": return { segment: `${P}arrive`, outfit: alone, run: `${this.visitId}:arrive:${a.start}` };
      case "leave": return { segment: `${P}leave`, outfit: alone, run: `${this.visitId}:leave:${a.start}` };
      case "gone": return { segment: `${P}leave_last`, outfit: alone, run: `${this.visitId}:gone` };
      case "idle": {
        const k = Math.max(0, nowS - a.start), n = Math.floor(k / CALL_EVERY_S);
        return k % CALL_EVERY_S < CLIP_S
          ? { segment: `${P}call`, outfit: alone, run: `${this.visitId}:call:${a.start}:${n}` }
          : { segment: `${P}wait`, outfit: alone, run: `${this.visitId}:wait:${a.start}` };
      }
      case "order": {
        const segment = a.phase === "stand" ? `${P}walkin_last` : a.phase === "hold" ? `${P}give_last` : `${P}${a.phase}`;
        return { segment, outfit: outfitFor(a.order!), run: `${a.order}:${a.phase}` };
      }
    }
  }
}

/** "Reduce motion": what stands still in place of `segment` */
export function stillFor(segment: string): string {
  if (segment.endsWith("_last") || segment.endsWith("_still") || segment === "base") return segment;
  const v = VENDOR_SEG.exec(segment);
  if (v) return VENDOR_ONCE.includes(v[2]) ? `${segment}_last` : `${v[1]}still`;
  return (ONCE as readonly string[]).includes(segment) ? `${segment}_last` : "base";
}

// ── from what the page read ─────────────────────────────────────────────

/** Server seconds at this device's `nowMs`, from an answer read at `readAt` carrying the server's `now` */
export function serverNow(now: number, readAt: number, nowMs: number): number {
  return now + Math.max(0, nowMs - readAt) / 1000;
}

/** The plates panel: the dishwasher (the washing-up itself plays on its card in the chat) */
export function platesClip(p: Plates, nowMs: number): ChoreClip | null {
  return washerClip(p.machineAt, p.machine, serverNow(p.now, p.readAt, nowMs));
}

// The shows of this page session, by server + role + visit: switching role shows that role's own show, and
// closing and opening the sheet again goes on where it was. Each keeps the facts it last had, so it can finish
// once the server no longer says anything about its visit.
interface Slot { show: VendorShow; visit: VendorVisitFacts; mine: VendorOrderFacts[]; used: number }
const shows = new Map<string, Slot>();
const latest = new Map<string, string>();      // scope -> the show it last showed
let used = 0;
/** For tests: forget every show */
export function forgetShows(): void {
  shows.clear();
  latest.clear();
}
/** For tests: how many shows are kept, and how many orders' facts they keep between them */
export function showCount(): number {
  return shows.size;
}
export function cachedOrderCount(): number {
  let n = 0;
  for (const s of shows.values()) n += s.mine.length;
  return n;
}

/** Finish a show from the facts it last had (its visit no longer comes from the server); null once it is done */
function finishFrom(slot: Slot, nowS: number): ChoreClip | null {
  const frozen = { ...slot.visit, ended: true, frozen: true };
  if (slot.show.isDone(frozen, nowS)) return null;
  const c = slot.show.pick(frozen, slot.mine, nowS);
  slot.mine = slot.show.unfinished();
  return slot.show.isDone(frozen, nowS) ? null : c;
}

function keepFew(keep: (string | null | undefined)[], nowS: number): void {
  for (const [k, s] of shows) if (!keep.includes(k) && s.show.isDone({ ...s.visit, ended: true }, nowS)) shows.delete(k);
  while (shows.size > MAX_SHOWS) {
    let oldest: string | null = null;
    for (const [k, s] of shows) if (!keep.includes(k) && (oldest === null || s.used < shows.get(oldest)!.used)) oldest = k;
    if (oldest === null) break;
    shows.delete(oldest);
  }
  for (const [scope, k] of latest) if (!shows.has(k)) latest.delete(scope);
}

/**
 * The vendor panel. The visit is the live one or, for a short while after it ended, the one that just ended
 * (only to finish a show this device had started: an ended visit it never showed plays nothing). When the
 * server says nothing about it any more, the show finishes from the facts it last had (an order not through
 * by then is closed with the cook walking back out empty-handed), he leaves, and then the panel is empty.
 * What each order is (a snack is eaten on the spot) comes from the order, or else from the goods by name.
 */
export function vendorPanelClip(v: VendorView, nowMs: number): ChoreClip | null {
  const scope = v.scope ?? "";
  const now = serverNow(v.now, v.readAt, nowMs);
  const visit = v.visit ?? v.ended;
  const key = visit?.id ? `${scope}|${visit.id}` : null;
  // the show this page was on is for another visit (or the server no longer mentions it): that one finishes
  // first, from what it last knew (the order on stage, then that vendor leaving), and only then the next
  const prev = latest.get(scope), prevSlot = prev && prev !== key ? shows.get(prev) : undefined;
  // this visit's show takes in what the server says even while it waits its turn: it starts (with his
  // arrival) only when the panel gets to it, but its orders are noted from when this device first read them
  let slot = key && visit ? shows.get(key) : undefined;
  if (key && visit && !slot && v.visit) {
    slot = { show: new VendorShow(visit.id), visit: { id: visit.id, vendor: visit.vendor, leaveAt: visit.leaveAt }, mine: [], used: 0 };
    shows.set(key, slot);
  }
  let mine: VendorOrderFacts[] = [];
  if (slot && visit) {
    const kinds = new Map(visit.goods.map((g) => [g.name, g.kind]));
    slot.visit = { id: visit.id, vendor: visit.vendor, leaveAt: visit.leaveAt, ended: !v.visit };
    slot.used = ++used;
    mine = v.mine.map((o) => ({ ...o, kind: o.kind || kinds.get(o.name) }));
  }
  if (prevSlot) {
    const c = finishFrom(prevSlot, now);
    if (c) {
      if (slot) { slot.show.observe(mine, now); slot.mine = slot.show.unfinished(); }
      keepFew([prev, key], now);
      return c;
    }
    latest.delete(scope);
  }
  if (!slot || !key) return null;
  latest.set(scope, key);
  const c = slot.show.pick(slot.visit, mine, now);
  // keep only what the show still needs: the orders not played yet (finished ones are its one mark)
  slot.mine = slot.show.unfinished();
  keepFew([key], now);
  return c;
}
