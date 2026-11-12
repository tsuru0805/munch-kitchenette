// "Tap a thing, hold that thing": which things in the picture can be tapped, where each one is, and
// what a tap means. Pure functions; the components only draw what these return.
// Coordinates are source pixels of the empty-kitchen background (as in sceneSlots); on screen they
// are multiplied by k = width / 1254.
import type { ArtAuth, FridgeItem } from "./fridgeApi";
import type { KitchenOutcome } from "./kitchenApi";
import { BUY_ART, COUPON_ART } from "./couponArt";
import { artRef, type AnyArt } from "./kindArt";
import {
  BUY_SLOT, CORK_RECT, DISH_SLOTS, FRIDGE_RECT, SNACK_IDS, SNACK_SLOTS, STAPLE_SLOTS, STRIP, TABLE_RECT, TICKET_SLOTS, dishArt, fridgePlacements,
  receiptRect, staplePlacements, stripRect, ticketCount, type Rect4, type Slot,
} from "./sceneSlots";

/** The one thing held in the hand */
export type Pick =
  | { k: "item"; id: string }
  | { k: "coupon" }
  | { k: "staple" }
  | { k: "snack"; id: string }
  | { k: "dish"; id: string }
  | { k: "receipt" }
  | { k: "wall" };

/** What tapping a thing does: hold it, or open a sheet (the grocery catalog / put a dish up), or it was an empty spot of the fridge / the counter */
export type Tap = Pick | { k: "buy" } | { k: "write" } | { k: "fridge" } | { k: "table" };

export const tapKey = (t: Tap): string => ("id" in t ? `${t.k}-${t.id}` : t.k);
export const samePick = (a: Pick | null, b: Pick | null): boolean => !!a && !!b && tapKey(a) === tapKey(b);

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface SceneObj {
  tap: Tap;
  /** the name a screen reader says */
  label: string;
  /** where it is (source pixels: top left corner + width and height) */
  box: Box;
  /** a cut-out: which picture, in which slot; paper things (receipt / strip / cork board) have none and are drawn by the scene itself */
  art?: AnyArt;
  slot?: Slot;
  /** what kind of paper thing */
  paper?: "receipt" | "strip" | "blank" | "cork";
  /** a ground zone (the whole fridge / the counter): lies under everything, only gets the taps on empty spots; not drawn, and does not compete with the others for room */
  zone?: boolean;
}

export interface SceneDish {
  key: string;
  name: string;
  outcome: KitchenOutcome | null;
}

export interface SceneInput {
  items: FridgeItem[];
  staples: string[];
  coupons: number;
  dishes: SceneDish[];
  auth: ArtAuth | null;
}

const fit = (slot: Slot, art: AnyArt): Box => {
  const a = artRef(art);
  const s = Math.min(slot.w / a.w, slot.h / a.h);
  const w = a.w * s;
  const h = a.h * s;
  return { x: slot.x - w / 2, y: slot.y - h, w, h };
};
const rectBox = (r: Rect4): Box => ({ x: r[0], y: r[1], w: r[2] - r[0], h: r[3] - r[1] });

const SNACK_NAMES: Record<string, string> = { coffee: "咖啡", jelly: "即时元气果冻", pudding: "布丁", chocolate: "黑巧克力", cookie: "曲奇" };

/** Everything in the picture that can be tapped (array order = drawing order: later ones cover earlier ones) */
export function sceneObjects(inp: SceneInput): SceneObj[] {
  const out: SceneObj[] = [];
  const art = (tap: Tap, label: string, a: AnyArt, slot: Slot) => out.push({ tap, label, art: a, slot, box: fit(slot, a) });

  // The ground zones first (at the very bottom): with an empty fridge and no coupon at all, tapping
  // the fridge still leads to the fridge row (hand out a coupon / buy groceries)
  out.push({ tap: { k: "fridge" }, label: "冰箱", box: rectBox(FRIDGE_RECT), zone: true });
  out.push({ tap: { k: "table" }, label: "桌上", box: rectBox(TABLE_RECT), zone: true });
  for (const s of TICKET_SLOTS.slice(0, ticketCount(inp.coupons))) art({ k: "coupon" }, "买菜券", COUPON_ART, s);
  art({ k: "buy" }, "给他买菜", BUY_ART, BUY_SLOT);
  for (const p of fridgePlacements(inp.items, inp.auth).placed) {
    const it = inp.items.find((i) => i.itemId === p.key);
    art({ k: "item", id: p.key }, it?.name ?? p.key, p.art, p.slot);
  }
  SNACK_SLOTS.forEach((s, i) => art({ k: "snack", id: SNACK_IDS[i] }, SNACK_NAMES[SNACK_IDS[i]], s.art, s.slot));
  for (const p of staplePlacements(inp.staples)) art({ k: "staple" }, "常备", p.art, p.slot);
  out.push({ tap: { k: "wall" }, label: "墙上最近的事", box: rectBox(CORK_RECT), paper: "cork" });
  out.push({ tap: { k: "receipt" }, label: "他今天的用餐记录", box: rectBox(receiptRect()), paper: "receipt" });
  const strips = inp.dishes.slice(0, STRIP.max);
  strips.forEach((d, i) => out.push({ tap: { k: "dish", id: d.key }, label: d.name, box: rectBox(stripRect(i)), paper: "strip" }));
  out.push({ tap: { k: "write" }, label: "挂一道", box: rectBox(stripRect(strips.length)), paper: "blank" });
  inp.dishes.slice(0, DISH_SLOTS.length).forEach((d, i) => art({ k: "dish", id: d.key }, d.name, dishArt(d.name, d.outcome), DISH_SLOTS[i]));
  return out;
}

/** The smallest side a finger can hit (pt) */
export const MIN_HIT = 44;

/**
 * Each thing's tap area (pt): a picture smaller than 44 grows outward to 44, but never past the
 * midline to a neighbour. Between two snacks next to each other, left of the midline belongs to
 * the left one and right of it to the right one; two things that already touch or overlap in the
 * picture each give way to the midline (losing at most three tenths of their own width / height).
 * The several places of one thing (a dish's strip and its bowl, the coupons, the four staples) do
 * not give way to each other.
 */
export function hitBoxes(objs: SceneObj[], k: number, min = MIN_HIT): Box[] {
  const pt = objs.map((o) => ({ x: o.box.x * k, y: o.box.y * k, w: o.box.w * k, h: o.box.h * k }));
  return pt.map((b, i) => {
    if (objs[i].zone) return b;
    const ex = Math.max(0, (min - b.w) / 2);
    const ey = Math.max(0, (min - b.h) / 2);
    let l = ex, r = ex, t = ey, d = ey;
    const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
    pt.forEach((o, j) => {
      if (j === i || objs[j].zone || tapKey(objs[j].tap) === tapKey(objs[i].tap)) return;
      const ox = Math.max(0, (min - o.w) / 2), oy = Math.max(0, (min - o.h) / 2);
      // would the two meet when each has grown all the way? if not, nobody gives way
      const meetX = o.x - ox < b.x + b.w + ex && o.x + o.w + ox > b.x - ex;
      const meetY = o.y - oy < b.y + b.h + ey && o.y + o.h + oy > b.y - ey;
      if (!meetX || !meetY) return;
      // which side the neighbour is on (by centres; ones that already touch / overlap count too: no growing on that side)
      const dx = o.x + o.w / 2 - cx, dy = o.y + o.h / 2 - cy;
      const gapX = dx >= 0 ? o.x - (b.x + b.w) : b.x - (o.x + o.w);
      const gapY = dy >= 0 ? o.y - (b.y + b.h) : b.y - (o.y + o.h);
      // give way along the direction with the larger gap (side by side: left / right; stacked: up / down),
      // as far as the midline between the two. Things that already touch or overlap in the picture
      // (wide ingredients side by side in the fridge) each pull back to the midline: the area is a
      // little smaller than the picture, but the two do not overlap
      if (gapX >= gapY) {
        const half = Math.max(gapX / 2, -b.w * 0.3);
        if (dx >= 0) r = Math.min(r, half);
        else l = Math.min(l, half);
      } else {
        const half = Math.max(gapY / 2, -b.h * 0.3);
        if (dy >= 0) d = Math.min(d, half);
        else t = Math.min(t, half);
      }
    });
    return { x: b.x - l, y: b.y - t, w: b.w + l + r, h: b.h + t + d };
  });
}

/**
 * Where a thing is in the picture (for the leader line): a dish = its bowl (its strip when it is not
 * on the counter); a group (the coupons / the four staples) = the middle of the group's bottom edge.
 * Not in the picture (no room / a dish past the fourth) = null.
 */
export function anchorOf(objs: SceneObj[], pick: Pick | null, k: number): { x: number; y: number } | null {
  if (!pick) return null;
  const key = tapKey(pick);
  const hits = objs.filter((o) => tapKey(o.tap) === key);
  if (!hits.length) return null;
  const arts = hits.filter((h) => h.art);
  const group = pick.k === "dish" ? [arts[0] ?? hits[0]] : arts.length ? arts : hits;
  const x0 = Math.min(...group.map((o) => o.box.x)), x1 = Math.max(...group.map((o) => o.box.x + o.box.w));
  const y1 = Math.max(...group.map((o) => o.box.y + o.box.h));
  return { x: ((x0 + x1) / 2) * k, y: y1 * k };
}

/** What is held on arriving: the thing in the fridge that most needs using up (the server sorted them); empty fridge = the coupon */
export function defaultPick(items: FridgeItem[]): Pick {
  return items.length ? { k: "item", id: items[0].itemId } : { k: "coupon" };
}

/** A tap on an empty spot of the fridge / the counter: the most urgent thing in the fridge (empty = the coupon) / the table (the receipt brings the table row with it) */
export function zonePick(zone: "fridge" | "table", items: FridgeItem[]): Pick {
  return zone === "fridge" ? defaultPick(items) : { k: "receipt" };
}

/** Is the held thing still there (an ingredient used up / a dish taken off -> back to the default) */
export function pickAlive(pick: Pick, items: FridgeItem[], dishKeys: string[]): boolean {
  if (pick.k === "item") return items.some((i) => i.itemId === pick.id);
  if (pick.k === "dish") return dishKeys.includes(pick.id);
  return true;
}

/** The batches of one kind (the hand lists them one per line) */
export function batchesOf(items: FridgeItem[], itemId: string): FridgeItem[] {
  return items.filter((i) => i.itemId === itemId);
}

/** The fridge by kind (the server's urgency order kept), each with its total count */
export function kindsOf(items: FridgeItem[]): { itemId: string; name: string; qty: number; first: FridgeItem }[] {
  const out: { itemId: string; name: string; qty: number; first: FridgeItem }[] = [];
  for (const it of items) {
    const hit = out.find((o) => o.itemId === it.itemId);
    if (hit) hit.qty += it.qty;
    else out.push({ itemId: it.itemId, name: it.name, qty: it.qty, first: it });
  }
  return out;
}
