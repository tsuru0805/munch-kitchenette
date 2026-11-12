// Words and small merges for the kitchen page (dates, time left, how a dish on the table turned out,
// ticking things in the catalog). Pure functions; the components only render what these return.
// Dates are written in the kitchen's time zone (runtime/zone), which is the visitor's own unless the
// server names one.
import { wall } from "../runtime/zone";
import type { CatalogItem, FridgeItem } from "./fridgeApi";
import type { KitchenOutcome, KitchenSessionWire } from "./kitchenApi";

const pad2 = (n: number) => (n < 10 ? `0${n}` : String(n));

/** month.day, e.g. 10.25 */
export function fmtMD(ms: number): string {
  const d = wall(ms);
  return `${d.month}.${d.day}`;
}

/** The right-hand cell of a batch: spoiled = the day it went bad; otherwise 「到 10.25」; no expiry date = empty */
export function expiryText(it: Pick<FridgeItem, "freshness" | "expiresAtMs">): string {
  if (it.expiresAtMs === null) return "";
  return it.freshness === "bad" ? fmtMD(it.expiresAtMs) : `到 ${fmtMD(it.expiresAtMs)}`;
}

/** Time left in plain words: an hour or more 「1 小时 20 分」, otherwise 「20 分钟」 (under a minute counts as one) */
export function fmtLeft(ms: number): string {
  const m = Math.max(1, Math.ceil(ms / 60000));
  if (m < 60) return `${m} 分钟`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} 小时 ${r} 分` : `${h} 小时`;
}

/** month.day hour:minute */
export function fmtStamp(ms: number): string {
  const d = wall(ms);
  return `${d.month}.${d.day} ${pad2(d.hour)}:${pad2(d.minute)}`;
}

/** Which part of the day a meal fell in (「早 · 鸡蛋三明治」) */
export function mealSlot(ms: number): string {
  const h = wall(ms).hour;
  if (h >= 4 && h < 10) return "早";
  if (h >= 10 && h < 15) return "午";
  if (h >= 15 && h < 21) return "晚";
  return "夜";
}

/**
 * How a dish on the table turned out. Only "this menu row is the one that pot was put on" counts
 * (menu row id == the pot's menu_row_id). When nothing matches (a dish the human put up, a pot not
 * on the menu yet), only the words the kitchen wrote into this row's own note are read
 * (坏了 / 糊了 / 火候刚好). A past pot of the same name is never used. Nothing found = null (ordinary).
 */
export function dishOutcome(menuRowId: string | null, note: string, recent: KitchenSessionWire[]): KitchenOutcome | null {
  if (menuRowId !== null) {
    const hit = recent.find((r) => r.menu_row_id != null && String(r.menu_row_id) === String(menuRowId) && r.outcome);
    if (hit?.outcome) return hit.outcome;
  }
  if (note.includes("坏了")) return "spoiled";
  if (note.includes("糊了")) return "burnt";
  if (note.includes("火候刚好")) return "great";
  return null;
}

// ── the grocery sheet ───────────────────────────────────────────────

/** Tap to tick, tap again to untick (keeps the order things were ticked in) */
export function toggleSelect(sel: string[], id: string): string[] {
  return sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id];
}

export const CATEGORY_ORDER: { key: string; label: string }[] = [
  { key: "leafy", label: "叶菜" },
  { key: "veg", label: "蔬菜" },
  { key: "root", label: "根茎" },
  { key: "dairy", label: "蛋奶豆" },
  { key: "meat", label: "肉和海鲜" },
  { key: "staple_food", label: "主食" },
  { key: "fruit", label: "水果" },
];

/** The catalog grouped by category (fixed order; unknown categories go under 「其他」 at the end; empty groups are left out) */
export function groupCatalog(items: CatalogItem[]): { key: string; label: string; items: CatalogItem[] }[] {
  const known = new Set(CATEGORY_ORDER.map((c) => c.key));
  const groups = CATEGORY_ORDER.map((c) => ({ ...c, items: items.filter((i) => i.category === c.key) }));
  const rest = items.filter((i) => !known.has(i.category));
  if (rest.length) groups.push({ key: "other", label: "其他", items: rest });
  return groups.filter((g) => g.items.length > 0);
}

const CN = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
/** The small line printed on the coupon: one coupon buys once, up to this many kinds */
export function couponRule(maxItems: number): string {
  return `一张买一次 · 最多${maxItems >= 0 && maxItems <= 10 ? CN[maxItems] : ` ${maxItems} `}样`;
}
