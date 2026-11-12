// The stamina potion: a menu row with a reserved name plus an amount the human sets. Drinking it (or
// being fed it) adds that much stamina at once and is not a meal. Endpoints (docs/API.md):
//   GET    /api/potions?who=             potions still on the menu (menu row id -> amount) + the name / note format / limits
//   POST   /api/potions/hang             put one on the menu and record its amount in one step ({who, pct, memo, by})
//   PATCH  /api/potions/<row>            change the amount / memo
//   DELETE /api/potions/<row>            void the bottle (removed, or only crossed off)
//   POST   /api/potions/<row>/feed       the human feeds it
// POTION_NAME is reserved (the same literal as on the server): a menu row with this name is a potion and
// never a meal, also when the potion list could not be read, so a potion is never fed as a dish.
import { req, type Viewer } from "./fridgeApi";

export const POTION_NAME = "精力补充药剂";

/** Only these five blanks are ignored when matching the name (space, tab, CR, LF, ideographic space): the same set as the server (each language's \s differs) */
export function isPotionName(dish: string): boolean {
  const k = (s: string) => s.replace(/[ \t\r\n\u3000]+/g, "").toLowerCase();
  return k(dish) === k(POTION_NAME);
}

export interface PotionBook {
  name: string;
  noteFmt: string;
  pctMin: number;
  /** what joins the amount and the human's memo (from the server) */
  memoSep: string;
  memoMax: number;
  /** false = stamina is switched off on the server: no potion can be hung */
  enabled: boolean;
  /** menu row id -> amount (percentage points) */
  byRow: Record<string, number>;
  /** menu row id -> the memo written for that bottle ("" when none) */
  memoByRow: Record<string, string>;
}

const num = (v: unknown, d = 0) => (typeof v === "number" && Number.isFinite(v) ? v : d);
const str = (v: unknown) => (typeof v === "string" ? v : "");

export function parsePotionBook(j: unknown): PotionBook | null {
  if (!j || typeof j !== "object") return null;
  const r = j as Record<string, unknown>;
  const name = str(r.name);
  const noteFmt = str(r.note_fmt);
  if (!name || !noteFmt.includes("{pct}") || !Array.isArray(r.items)) return null;
  const byRow: Record<string, number> = {};
  const memoByRow: Record<string, string> = {};
  for (const it of r.items) {
    const o = (it ?? {}) as Record<string, unknown>;
    const id = str(o.menu_row_id);
    if (id && num(o.pct) > 0) {
      byRow[id] = Math.floor(num(o.pct));
      memoByRow[id] = str(o.memo);
    }
  }
  return {
    name, noteFmt, pctMin: Math.max(1, Math.floor(num(r.pct_min, 1))),
    memoSep: str(r.memo_sep) || " · ", memoMax: Math.max(1, Math.floor(num(r.memo_max, 60))),
    enabled: r.enabled !== false, byRow, memoByRow,
  };
}

/** The memo: one line, trimmed, cut to the limit. The characters folded into a space are the same set the server folds. */
const MEMO_BLANKS = /[ \t\r\n\x0b\x0c\x1c-\x1f\x85\u2028\u2029\u3000]+/g;
export function cleanMemo(book: PotionBook, memo: string): string {
  return Array.from(memo.replace(MEMO_BLANKS, " ").replace(/^ +| +$/g, "")).slice(0, book.memoMax).join("");
}

/** The note on the menu row (what the role reads): the amount, then the memo when there is one */
export function potionNote(book: PotionBook, pct: number, memo = ""): string {
  const m = cleanMemo(book, memo);
  return book.noteFmt.replace("{pct}", String(pct)) + (m ? book.memoSep + m : "");
}

/** What was typed -> a whole number; null when it does not qualify (empty / not a whole number / below the minimum). No upper limit; a million and more is taken for a slip (as on the server). */
export const PCT_SANE = 1_000_000;
export const PCT_MAX_DIGITS = 7;
export function parsePct(text: string, book: PotionBook): number | null {
  const t = text.trim();
  if (!new RegExp(`^\\d{1,${PCT_MAX_DIGITS}}$`).test(t)) return null;
  const n = Number(t);
  return n >= book.pctMin && n <= PCT_SANE ? n : null;
}

export async function fetchPotions(viewer: Viewer): Promise<PotionBook> {
  const b = parsePotionBook(await req(`/api/potions?who=${encodeURIComponent(viewer)}`));
  if (!b) throw new Error("potions bad_shape");
  return b;
}

/** Hang a potion: the menu row and its amount in one step. Returns the new menu row's id and note. */
export async function hangPotion(viewer: Viewer, pct: number, memo: string): Promise<{ id: string; note: string }> {
  const r = (await req("/api/potions/hang", { method: "POST", body: { who: viewer, pct, memo, by: "human" } })) as Record<string, unknown> | null;
  const row = (r?.row ?? {}) as Record<string, unknown>;
  const id = str(row.id);
  if (!id) throw new Error("potions bad_shape");
  return { id, note: str(row.note) };
}

export async function updatePotion(viewer: Viewer, menuRowId: string, pct: number, memo: string): Promise<void> {
  await req(`/api/potions/${encodeURIComponent(menuRowId)}`, { method: "PATCH", body: { who: viewer, pct, memo } });
}

export async function dropPotion(menuRowId: string): Promise<void> {
  await req(`/api/potions/${encodeURIComponent(menuRowId)}`, { method: "DELETE" });
}

/** The human feeds the bottle: stamina is added, the menu row is crossed off, the role is told. */
export async function feedPotion(viewer: Viewer, menuRowId: string): Promise<{ text: string }> {
  const r = (await req(`/api/potions/${encodeURIComponent(menuRowId)}/feed`, { method: "POST", body: { who: viewer } })) as Record<string, unknown> | null;
  return { text: str(r?.text) };
}
