// The kitchen picture is put together in layers: the empty kitchen, then cut-out pictures placed in
// fixed slots. This file is the one table of slot coordinates, plus the pure functions that decide
// what goes where.
// Coordinates are pixels on the empty-kitchen background as a 1254 × 1254 square (measured against
// the picture itself: a different background needs measuring again); on screen everything is scaled
// by width / 1254. A slot = centre x + bottom line y (things "stand" on a shelf) + the largest width
// and height; a picture is scaled to fit and sits on the bottom line, centred.
import type { FridgeArtId } from "./art.generated";
import type { ArtAuth, FridgeItem } from "./fridgeApi";
import type { KitchenOutcome } from "./kitchenApi";
import { artOf, type AnyArt } from "./kindArt";

export const SCENE_SRC = 1254;

export interface Slot {
  /** centre x */
  x: number;
  /** bottom line y (the thing's bottom edge rests here) */
  y: number;
  /** largest width */
  w: number;
  /** largest height */
  h: number;
  /** rotation in degrees */
  rot?: number;
}

const row = (xs: number[], y: number, w: number, h: number): Slot[] => xs.map((x) => ({ x, y, w, h }));

/** The fridge compartment: three shelves + the crisper drawer + the door rack (the liner spans x 195–580) */
const COLS = [262, 388, 514];
export const FRIDGE_SLOTS = {
  /** top shelf: eggs, dairy, tofu, meat and seafood */
  dairyMeat: row(COLS, 602, 132, 120),
  /** middle shelf: vegetables, roots, fruit, staples */
  veg: row(COLS, 714, 132, 100),
  /** bottom shelf (on the drawer lid): leafy greens, and whatever has gone bad */
  leafyBad: row(COLS, 852, 136, 118),
  /** in the drawer: what did not fit above */
  drawer: row([272, 388, 504], 996, 120, 96),
  /** door rack: bottles and cartons (a tall lower pocket, a short upper one) */
  door: [
    { x: 136, y: 968, w: 74, h: 150 },
    { x: 136, y: 652, w: 74, h: 96 },
  ] as Slot[],
};

/** Bottles and cartons that go in the door rack */
export const DOOR_ITEMS = new Set(["milk"]);

/** Upper wall shelf: one of each snack on the default shelf (coffee is drawn as an americano) */
export const SNACK_SLOTS: { art: FridgeArtId; slot: Slot }[] = [
  { art: "snack_coffee_americano", slot: { x: 700, y: 216, w: 92, h: 100 } },
  { art: "snack_jelly", slot: { x: 806, y: 216, w: 92, h: 104 } },
  { art: "snack_pudding", slot: { x: 912, y: 216, w: 100, h: 96 } },
  { art: "snack_chocolate", slot: { x: 1034, y: 216, w: 92, h: 92 } },
  { art: "snack_cookie", slot: { x: 1150, y: 216, w: 100, h: 96 } },
];

/** Lower wall shelf: the four staples (name = the word in the server's staples list) */
export const STAPLE_SLOTS: { name: string; art: FridgeArtId; slot: Slot }[] = [
  { name: "油", art: "staple_oil", slot: { x: 692, y: 452, w: 64, h: 150 } },
  { name: "酱油", art: "staple_soy", slot: { x: 772, y: 452, w: 76, h: 122 } },
  { name: "盐", art: "staple_salt", slot: { x: 848, y: 452, w: 60, h: 96 } },
  { name: "米", art: "staple_rice", slot: { x: 942, y: 452, w: 104, h: 124 } },
];

/** Grocery coupons on the freezer door (0–3) */
export const TICKET_SLOTS: Slot[] = [
  { x: 330, y: 250, w: 168, h: 130, rot: -6 },
  { x: 488, y: 276, w: 150, h: 120, rot: 5 },
  { x: 404, y: 392, w: 156, h: 120, rot: -2 },
];

/** Paper notes on the cork board (0–3) and their paper colours */
export const NOTE_SLOTS: (Slot & { color: string })[] = [
  { x: 1086, y: 400, w: 74, h: 66, rot: -5, color: "#f7eedc" },
  { x: 1176, y: 372, w: 62, h: 56, rot: 4, color: "#cfe0ea" },
  { x: 1150, y: 500, w: 74, h: 58, rot: -2, color: "#f4cdd2" },
];

/** Dishes on the counter (the first three on the menu) */
export const DISH_SLOTS: Slot[] = row([748, 932, 1116], 752, 150, 104);

/** Top left of the freezer door: the "buy him groceries" memo */
export const BUY_SLOT: Slot = { x: 186, y: 304, w: 124, h: 204 };

/** The server's snack ids for the five on the shelf (same order as SNACK_SLOTS) */
export const SNACK_IDS = ["coffee", "jelly", "pudding", "chocolate", "cookie"] as const;

/** The whole fridge / the counter and cabinet: a tap on an empty spot counts too (fridge = what is in it, counter = the table); they lie under everything else */
export const FRIDGE_RECT: [number, number, number, number] = [0, 60, 630, 1160];
export const TABLE_RECT: [number, number, number, number] = [634, 660, 1254, 1100];

/** The whole cork board (rectangle in source pixels [x0, y0, x1, y1]) */
export const CORK_RECT: [number, number, number, number] = [1020, 280, 1245, 530];

/**
 * Paper hanging under the lower shelf: leftmost the "meals today" receipt, then one strip per dish,
 * and last an empty strip = put a dish up. All [x0, y0, x1, y1] in source pixels. At this scale
 * lettering would be unreadable, so a strip carries none: it only shows how many dishes are up.
 */
export const STRIP = { x0: 664, y: 476, w: 46, h: 164, receiptH: 118, afterReceipt: 64, step: 56, max: 4 } as const;   // four strips + the empty one; any more would run into the cork board
export type Rect4 = [number, number, number, number];
export function receiptRect(): Rect4 {
  return [STRIP.x0, STRIP.y, STRIP.x0 + STRIP.w, STRIP.y + STRIP.receiptH];
}
/** Strip number i (from 0); the one at i = number of dishes is the empty one */
export function stripRect(i: number): Rect4 {
  const x = STRIP.x0 + STRIP.afterReceipt + i * STRIP.step;
  return [x, STRIP.y, x + STRIP.w, STRIP.y + STRIP.h];
}

// ── placing things ──────────────────────────────────────────────────

export interface Placed {
  key: string;
  /** a bundled picture = its key; an added kind = the picture the server drew */
  art: AnyArt;
  slot: Slot;
}

type Shelf = "dairyMeat" | "veg" | "leafyBad" | "door";

/** Which shelf a thing goes on (door bottles > spoiled / leafy > eggs, dairy, meat > the rest) */
export function shelfFor(it: Pick<FridgeItem, "itemId" | "category" | "freshness">): Shelf {
  if (DOOR_ITEMS.has(it.itemId)) return "door";
  if (it.freshness === "bad" || it.category === "leafy") return "leafyBad";
  if (it.category === "dairy" || it.category === "meat") return "dairyMeat";
  return "veg";
}

/**
 * What is drawn in the fridge, and where. items come sorted by urgency (from the server): several
 * batches of one kind are drawn once, with the freshness of the first batch (the one to use up
 * first decides); things go to their shelf, to the drawer when the shelf is full, and are not drawn
 * when the drawer is full too (they are still in the row under the picture); a kind without a
 * picture is not drawn. auth = where and how to fetch server-drawn pictures; without it only
 * bundled pictures are drawn.
 */
export function fridgePlacements(items: FridgeItem[], auth: ArtAuth | null = null): { placed: Placed[]; hidden: string[] } {
  const seen = new Set<string>();
  const free: Record<Shelf | "drawer", Slot[]> = {
    dairyMeat: [...FRIDGE_SLOTS.dairyMeat],
    veg: [...FRIDGE_SLOTS.veg],
    leafyBad: [...FRIDGE_SLOTS.leafyBad],
    door: [...FRIDGE_SLOTS.door],
    drawer: [...FRIDGE_SLOTS.drawer],
  };
  const placed: Placed[] = [];
  const hidden: string[] = [];
  for (const it of items) {
    if (seen.has(it.itemId)) continue;
    seen.add(it.itemId);
    const art = artOf(it.itemId, it.freshness, it.art, auth);
    if (!art) {
      hidden.push(it.itemId);
      continue;
    }
    const slot = free[shelfFor(it)].shift() ?? free.drawer.shift();
    if (!slot) {
      hidden.push(it.itemId);
      continue;
    }
    placed.push({ key: it.itemId, art, slot });
  }
  return { placed, hidden };
}

/** Staples: the ones the server lists go on the shelf (a word with no picture is not drawn) */
export function staplePlacements(staples: string[]): Placed[] {
  const have = new Set(staples);
  return STAPLE_SLOTS.filter((s) => have.has(s.name)).map((s) => ({ key: `staple-${s.name}`, art: s.art, slot: s.slot }));
}

/** A stable hash of a string (FNV-1a over code points) */
export function hashName(s: string): number {
  let h = 0x811c9dc5;
  for (const ch of Array.from(s)) {
    h ^= ch.codePointAt(0) ?? 0;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

const VESSELS = ["bowl", "plate", "cup"] as const;

/** What a dish is served in: bowl / plate / cup, picked by a hash of its name so it never changes; burnt or spoiled uses the burnt picture */
export function dishArt(name: string, outcome: KitchenOutcome | null): FridgeArtId {
  const v = VESSELS[hashName(name) % VESSELS.length];
  const burnt = outcome === "burnt" || outcome === "spoiled";
  return `dish_${v}${burnt ? "_burnt" : ""}` as FridgeArtId;
}

/** How many coupons are stuck on the door, how many notes are pinned (0–3) */
export function ticketCount(count: number): number {
  return Math.max(0, Math.min(TICKET_SLOTS.length, Math.floor(count)));
}
export function noteCount(logLen: number): number {
  return Math.max(0, Math.min(NOTE_SLOTS.length, Math.floor(logLen)));
}

/** Slot -> box on screen: the picture scaled to fit w × h, on the bottom line, centred */
export function fitInSlot(slot: Slot, art: { w: number; h: number }, k: number): { left: number; top: number; width: number; height: number } {
  const s = Math.min(slot.w / art.w, slot.h / art.h);
  const w = art.w * s;
  const h = art.h * s;
  return { left: (slot.x - w / 2) * k, top: (slot.y - h) * k, width: w * k, height: h * k };
}
