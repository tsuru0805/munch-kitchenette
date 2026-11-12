// The rest of what the page reads and writes (docs/API.md):
//   GET    /api/about                 who lives here, which parts are switched on, the words for the human
//   GET    /api/kitchen?who=          pots on the stove / recently served (the table shows how a dish turned out)
//   GET    /api/menu?pending=1&for_who=   what is on the table
//   POST   /api/menu                  put a dish up ({dish, by, for_who, note})
//   PATCH  /api/menu/<id>             change it, or cross it off ({eaten_at, if_pending})
//   DELETE /api/menu/<id>             take it off
//   POST   /api/menu/<id>/feed        feed it to the role: crossed off, counted as a meal, the role is told
//   GET    /api/meals?who=            today's meals
//   POST   /api/dev/clock             fast-forward (only on a server that switched it on)
import { req, toMs, type Viewer } from "./fridgeApi";
import { setZone, syncClock } from "../runtime/zone";

export type KitchenOutcome = "great" | "ok" | "burnt" | "spoiled";

/** The word next to a dish; an ordinary dish gets none */
export function outcomeWord(o: KitchenOutcome | null | undefined): string | null {
  if (o === "great") return "很好";
  if (o === "burnt") return "糊了";
  if (o === "spoiled") return "坏了";
  return null;
}

export interface KitchenSessionWire {
  id: string;
  dish: string;
  outcome?: KitchenOutcome | null;
  /** the menu row this pot's dish was put on once served; null when it is not on the menu */
  menu_row_id?: string | null;
}

const OUTCOMES = new Set(["great", "ok", "burnt", "spoiled"]);
const str = (v: unknown): string => (typeof v === "string" ? v : "");

/** Only the four known values count; anything else is null (an ordinary dish) */
export function parseOutcome(v: unknown): KitchenOutcome | null {
  return typeof v === "string" && OUTCOMES.has(v) ? (v as KitchenOutcome) : null;
}

export function parseRecent(j: unknown): KitchenSessionWire[] {
  const v = j && typeof j === "object" ? (j as { recent?: unknown }).recent : null;
  return Array.isArray(v)
    ? (v as Record<string, unknown>[])
        .filter((x) => x && typeof x.dish === "string")
        .map((x) => ({ id: String(x.id ?? ""), dish: String(x.dish), outcome: parseOutcome(x.outcome), menu_row_id: x.menu_row_id == null ? null : String(x.menu_row_id) }))
    : [];
}

export async function fetchRecentPots(viewer: Viewer): Promise<KitchenSessionWire[]> {
  return parseRecent(await req(`/api/kitchen?who=${encodeURIComponent(viewer)}`));
}

// ── about ───────────────────────────────────────────────────────────

export interface About {
  roles: string[];
  defaultRole: string;
  stamina: boolean;
  satiety: boolean;
  devClock: boolean;
  /** satiety below this is shown in red */
  hungryBelow: number;
  /** how many kinds one coupon buys */
  buyMaxItems: number;
}

export function parseAbout(j: unknown): About | null {
  if (!j || typeof j !== "object") return null;
  const r = j as Record<string, unknown>;
  const roles = (r.roles ?? {}) as Record<string, unknown>;
  const sw = (r.switches ?? {}) as Record<string, unknown>;
  const lim = (r.limits ?? {}) as Record<string, unknown>;
  const list = Array.isArray(roles.list) ? roles.list.filter((x): x is string => typeof x === "string" && x !== "") : [];
  const def = str(roles.default) || list[0] || "";
  if (!def) return null;
  const n = (v: unknown, d: number) => (typeof v === "number" && Number.isFinite(v) ? v : d);
  return {
    roles: list.includes(def) ? list : [def, ...list],
    defaultRole: def,
    stamina: sw.stamina !== false,
    satiety: sw.satiety !== false,
    devClock: sw.dev_clock === true,
    hungryBelow: n(lim.hungry_below, 30),
    buyMaxItems: Math.max(1, Math.floor(n(lim.buy_max_items, 5))),
  };
}

export async function fetchAbout(): Promise<About> {
  const j = await req("/api/about");
  const a = parseAbout(j);
  if (!a) throw new Error("about bad_shape");
  const r = j as Record<string, unknown>;
  setZone(str(r.timezone));
  const now = toMs(r.now);
  if (now !== null) syncClock(now);
  return a;
}

// ── menu ────────────────────────────────────────────────────────────

export interface DishRow {
  id: string;
  dish: string;
  note: string | null;
}

function parseRow(v: unknown): DishRow | null {
  if (!v || typeof v !== "object") return null;
  const r = v as Record<string, unknown>;
  const id = r.id == null ? "" : String(r.id);
  return id && typeof r.dish === "string" ? { id, dish: r.dish, note: typeof r.note === "string" ? r.note : null } : null;
}

/** Still on the table, oldest first (the order they were put up) */
export async function fetchMenu(viewer: Viewer): Promise<DishRow[]> {
  const j = await req(`/api/menu?pending=1&for_who=${encodeURIComponent(viewer)}`);
  if (!Array.isArray(j)) throw new Error("menu bad_shape");
  return j.map(parseRow).filter((x): x is DishRow => x !== null).reverse();
}

/** Who put a dish up when it was done from this page (the role's own pots carry the role's id) */
export const BY_HUMAN = "human";

export async function postMenu(dish: string, viewer: Viewer, note?: string): Promise<DishRow> {
  const row = parseRow(await req("/api/menu", { method: "POST", body: { dish, by: BY_HUMAN, for_who: viewer, note } }));
  if (!row) throw new Error("menu bad_shape");
  return row;
}

export async function patchMenu(id: string, patch: { dish?: string; note?: string | null; eaten_at?: number; if_pending?: boolean }): Promise<void> {
  await req(`/api/menu/${encodeURIComponent(id)}`, { method: "PATCH", body: patch });
}

export async function deleteMenu(id: string): Promise<void> {
  await req(`/api/menu/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** Feed a dish to its role. notified = a note was written for the role. */
export async function feedMenu(id: string): Promise<{ notified: boolean }> {
  const r = (await req(`/api/menu/${encodeURIComponent(id)}/feed`, { method: "POST" })) as Record<string, unknown> | null;
  return { notified: r?.notified === true };
}

// ── meals ───────────────────────────────────────────────────────────

export interface Meal {
  atMs: number;
  meal: string;
}

export function parseMeals(j: unknown): Meal[] {
  const v = j && typeof j === "object" ? (j as { meals?: unknown }).meals : null;
  if (!Array.isArray(v)) return [];
  return v
    .map((x) => {
      const o = (x ?? {}) as Record<string, unknown>;
      const at = toMs(o.at);
      return at !== null && typeof o.meal === "string" && o.meal ? { atMs: at, meal: o.meal } : null;
    })
    .filter((x): x is Meal => x !== null);
}

/** Today's meals (the server's day, in its own time zone), oldest first */
export async function fetchMeals(viewer: Viewer): Promise<Meal[]> {
  return parseMeals(await req(`/api/meals?who=${encodeURIComponent(viewer)}`));
}

// ── fast-forward (demos) ────────────────────────────────────────────

export async function advanceClock(seconds: number): Promise<void> {
  const r = (await req("/api/dev/clock", { method: "POST", body: { advance_seconds: seconds } })) as Record<string, unknown> | null;
  const now = toMs(r?.now);
  if (now !== null) syncClock(now);
}
