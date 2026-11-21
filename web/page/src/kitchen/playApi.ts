// What the page reads and writes for the upgrade (docs/UPGRADE.md, docs/API.md "The upgrade"):
//   GET  /api/features                      which of the seventeen are on (an entrance is hidden when off)
//   GET  /api/recipes?q=&who=               the public recipes      GET /api/recipes/today?who=
//   GET  /api/book?who=                     the role's own pages     DELETE /api/book/<page>?who=
//   GET/POST/DELETE /api/orders             ordering a dish from a recipe
//   GET  /api/codes?who=&page=              a page as a code         POST /api/codes/preview · /api/codes/import
//   GET  /api/dex?who=                      the dish book and the achievements   PUT /api/dex/note
//   GET  /api/dishes?who=                   plates                   PUT /api/dishes/settings
//   GET  /api/jars?who=                     the jars and what came out    PUT /api/jars/cap · POST /api/jars/feed
//   GET  /api/vendor?who=                   the vendor downstairs, the sill   POST /api/vendor/treat · /api/vendor/flowers/<id>
//   POST /api/wallet/grant                  pocket money into the built-in ledger
import { req, type Viewer } from "./fridgeApi";

const q = (v: string) => encodeURIComponent(v);
type J = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

export const FEATURE_KEYS = [
  "recipes_public", "recipes_today", "recipe_cook", "recipe_book", "proficiency", "mishaps", "new_dish_bonus",
  "settle_card", "dex", "achievements", "tasting_notes", "orders", "menus", "recipe_codes", "vendor", "dishwash",
  "seal_jars",
] as const;
export type FeatureKey = (typeof FEATURE_KEYS)[number];
export type Features = Record<FeatureKey, boolean>;

export const NO_FEATURES: Features = Object.fromEntries(FEATURE_KEYS.map((k) => [k, false])) as Features;

/** /api/features -> {key: on}; anything unknown or missing counts as off */
export function parseFeatures(j: unknown): Features {
  const out = { ...NO_FEATURES };
  const list = j && typeof j === "object" ? (j as J).features : null;
  if (Array.isArray(list)) {
    for (const f of list) {
      if (f && typeof f.key === "string" && (FEATURE_KEYS as readonly string[]).includes(f.key)) out[f.key as FeatureKey] = f.on === true;
    }
  }
  return out;
}

export async function fetchFeatures(): Promise<Features> {
  return parseFeatures(await req("/api/features"));
}

/** Which entrances the page shows, in this order (one per tab of the sheet) */
export type PlayTab = "recipes" | "dex" | "achievements" | "vendor" | "pocket" | "plates" | "jars";
export const TAB_LABEL: Record<PlayTab, string> = {
  recipes: "食谱", dex: "图鉴", achievements: "成就", vendor: "小贩", pocket: "零花钱", plates: "盘子", jars: "罐子",
};

export function visibleTabs(f: Features): PlayTab[] {
  const out: PlayTab[] = [];
  if (f.recipes_public || f.recipe_book) out.push("recipes");
  if (f.dex) out.push("dex");
  if (f.achievements) out.push("achievements");
  if (f.vendor) out.push("vendor", "pocket");
  if (f.dishwash) out.push("plates");
  if (f.seal_jars) out.push("jars");
  return out;
}

export interface RecipeEntry { id: string; name: string; itemsText: string; method: string; minutes: number; category: string }

const METHOD_CN: Record<string, string> = { stirfry: "炒", fry: "煎", deepfry: "炸", boil: "煮", steam: "蒸", bake: "烤", mix: "拌" };
export const methodWord = (m: string): string => METHOD_CN[m] ?? m;

export function parseRecipes(j: unknown): { total: number; recipes: RecipeEntry[] } {
  const r = (j ?? {}) as J;
  const list: RecipeEntry[] = Array.isArray(r.recipes)
    ? r.recipes.filter((x: J) => x && typeof x.id === "string" && typeof x.name === "string").map((x: J) => ({
      id: x.id, name: x.name, itemsText: String(x.items_text ?? ""), method: String(x.method ?? ""),
      minutes: typeof x.minutes === "number" ? x.minutes : 0, category: String(x.category_label ?? ""),
    }))
    : [];
  return { total: typeof r.total === "number" ? r.total : list.length, recipes: list };
}

export async function searchRecipes(viewer: Viewer, text: string): Promise<{ total: number; recipes: RecipeEntry[] }> {
  return parseRecipes(await req(`/api/recipes?who=${q(viewer)}&limit=60${text ? `&q=${q(text)}` : ""}`));
}

export async function fetchToday(viewer: Viewer): Promise<string> {
  const j = (await req(`/api/recipes/today?who=${q(viewer)}`)) as J;
  return String(j?.text ?? "");
}

export interface BookPage { id: string; kind: string; refId: string | null; name: string; itemsText: string; method: string; minutes: number; note: string; notes: string[] }

export function parseBook(j: unknown): BookPage[] {
  const pages = j && typeof j === "object" ? (j as J).pages : null;
  if (!Array.isArray(pages)) return [];
  return pages.filter((p: J) => p && typeof p.id === "string").map((p: J) => ({
    id: p.id, kind: String(p.kind ?? ""), refId: typeof p.ref_id === "string" ? p.ref_id : null, name: String(p.name ?? ""),
    itemsText: Array.isArray(p.main) ? p.main.map((e: J) => String(e.name ?? e.item ?? "")).filter(Boolean).join("、") : "",
    method: String(p.method ?? ""), minutes: typeof p.minutes === "number" ? p.minutes : 0, note: String(p.note ?? ""),
    notes: Array.isArray(p.notes) ? p.notes.map((n: J) => String(n.text ?? "")).filter(Boolean) : [],
  }));
}

export async function fetchBook(viewer: Viewer): Promise<BookPage[]> {
  return parseBook(await req(`/api/book?who=${q(viewer)}`));
}

export const KIND_WORD: Record<string, string> = { fav: "收藏", adapt: "改编", own: "自创", menu: "一桌", code: "别人的码" };

export async function orderDish(viewer: Viewer, recipe: string): Promise<void> {
  await req("/api/orders", { method: "POST", body: { who: viewer, recipe } });
}

export interface Order { id: string; name: string; state: string; note: string }
export async function fetchOrders(viewer: Viewer): Promise<Order[]> {
  const j = (await req(`/api/orders?who=${q(viewer)}`)) as J;
  return Array.isArray(j?.orders)
    ? j.orders.map((o: J) => ({ id: String(o.id), name: String(o.name ?? ""), state: String(o.state ?? ""), note: String(o.his_note ?? "") }))
    : [];
}
export async function withdrawOrder(viewer: Viewer, id: string): Promise<void> {
  await req(`/api/orders/${q(id)}?who=${q(viewer)}`, { method: "DELETE" });
}
export const ORDER_WORD: Record<string, string> = { received: "收到", planned: "打算做", cooking: "在做", done: "做好了", withdrawn: "撤回了" };

export async function fetchCode(viewer: Viewer, page: string): Promise<string> {
  const j = (await req(`/api/codes?who=${q(viewer)}&page=${q(page)}`)) as J;
  return String(j?.code ?? "");
}
export async function previewCode(code: string): Promise<J> {
  return ((await req("/api/codes/preview", { method: "POST", body: { code } })) as J).preview as J;
}
export async function importCode(viewer: Viewer, code: string): Promise<J> {
  return (await req("/api/codes/import", { method: "POST", body: { who: viewer, code } })) as J;
}

export interface DexPage { key: string; name: string; made: number; good: number; eaten: number; best: string | null; firstAt: number; pending: boolean; method: string; ingredients: string[]; humanNote: string; roleNote: string; artVersion: number | null }
export interface Achievement { key: string; name: string; earned: boolean; why: string }
export interface Dex { pages: DexPage[]; silhouettes: string[]; total: number | null; madePublic: number; artMissing: number; drawing: boolean; achievements: Achievement[] }

export function parseDex(j: unknown): Dex {
  const r = (j ?? {}) as J;
  const t = (r.totals ?? {}) as J;
  return {
    pages: Array.isArray(r.pages) ? r.pages.map((p: J) => ({
      key: String(p.key), name: String(p.name ?? ""), made: p.made | 0, good: p.good | 0, eaten: p.eaten | 0,
      best: typeof p.best === "string" ? p.best : null, firstAt: typeof p.first_at === "number" ? p.first_at : 0,
      pending: p.pending === true, method: String(p.method ?? ""), ingredients: Array.isArray(p.ingredients) ? p.ingredients.map(String) : [],
      humanNote: String(p.human_note ?? ""), roleNote: String(p.role_note ?? ""),
      artVersion: p.art && typeof p.art.chosen === "number" ? p.art.chosen : null,
    })) : [],
    silhouettes: Array.isArray(r.silhouettes) ? r.silhouettes.map((s: J) => String(s.name ?? "")) : [],
    total: typeof t.public === "number" ? t.public : null,
    madePublic: t.made_public | 0,
    artMissing: t.art_missing | 0,
    drawing: r.drawing === true,
    achievements: Array.isArray(r.achievements)
      ? r.achievements.map((a: J) => ({ key: String(a.key), name: String(a.name ?? ""), earned: a.earned === true, why: String(a.why ?? "") }))
      : [],
  };
}

export async function fetchDex(viewer: Viewer): Promise<Dex> {
  return parseDex(await req(`/api/dex?who=${q(viewer)}`));
}
export async function saveDexNote(viewer: Viewer, pageKey: string, text: string): Promise<void> {
  await req("/api/dex/note", { method: "PUT", body: { who: viewer, page_key: pageKey, text } });
}
export const BEST_WORD: Record<string, string> = { great: "很好", ok: "普通", spoiled: "坏了", burnt: "糊了", ruined: "毁了" };

export interface WashJob { id: string; state: string; startedAt: number; perS: number; n: number; endedAt: number | null; breaks: number[] }
export interface Plates {
  selfWash: boolean; quota: number | null; sink: number; washing: number; clean: number; broken: number; machine: number; jobState: string | null;
  /** the last washing (null = never washed) and the server's "now" (seconds), for the rack in the picture */
  job: WashJob | null; now: number;
  /** when a plate last went into the dishwasher (null = never), for the cook loading it */
  machineAt: number | null;
  /** this device's clock (ms) when `now` was read: server time later = now + (Date.now() - readAt) / 1000 */
  readAt: number;
}
export function parsePlates(j: J | null): Plates {
  const c = (j?.counts ?? {}) as J;
  const jb = j?.job as J | null | undefined;
  return { selfWash: j?.self_wash === true, quota: typeof j?.quota === "number" ? j.quota : null,
    sink: c.sink | 0, washing: c.washing | 0, clean: c.clean | 0, broken: c.broken | 0, machine: c.machine | 0,
    jobState: jb ? String(jb.state) : null,
    job: jb ? { id: String(jb.id ?? ""), state: String(jb.state ?? ""), startedAt: Number(jb.started_at ?? 0), perS: Number(jb.per_s ?? 0), n: jb.n | 0,
      endedAt: typeof jb.ended_at === "number" ? jb.ended_at : null,
      breaks: Array.isArray(jb.breaks) ? jb.breaks.filter((x: unknown) => typeof x === "number") : [] } : null,
    now: typeof j?.now === "number" ? j.now : 0,
    machineAt: typeof j?.machine_at === "number" ? j.machine_at : null,
    readAt: Date.now() };
}
export async function fetchPlates(viewer: Viewer): Promise<Plates> {
  return parsePlates((await req(`/api/dishes?who=${q(viewer)}`)) as J);
}
export async function setPlates(viewer: Viewer, change: { self_wash?: boolean; quota?: number | null }): Promise<void> {
  await req("/api/dishes/settings", { method: "PUT", body: { who: viewer, ...change } });
}

export interface Jar { slot: number; state: string; itemName: string; how: string; howWord: string; note: string; dueAt: number | null }
export interface JarGood { id: string; name: string; ok: boolean; left: number; total: number; note: string }
export async function fetchJars(viewer: Viewer): Promise<{ jars: Jar[]; goods: JarGood[]; cap: number }> {
  const j = (await req(`/api/jars?who=${q(viewer)}`)) as J;
  return {
    jars: Array.isArray(j?.jars) ? j.jars.map((x: J) => ({ slot: x.slot | 0, state: String(x.state ?? "empty"), itemName: String(x.item_name ?? ""),
      how: String(x.how ?? ""), howWord: String(x.how_word ?? ""), note: String(x.note ?? ""), dueAt: typeof x.due_at === "number" ? x.due_at : null })) : [],
    goods: Array.isArray(j?.goods) ? j.goods.map((g: J) => ({ id: String(g.id), name: String(g.name ?? ""), ok: g.ok === 1 || g.ok === true,
      left: g.left_n | 0, total: g.total | 0, note: String(g.note ?? "") })) : [],
    cap: typeof j?.cap === "number" ? j.cap : 0,
  };
}
export async function feedJar(viewer: Viewer, name: string, key: string): Promise<string> {
  const j = (await req("/api/jars/feed", { method: "POST", body: { who: viewer, name, key } })) as J;
  return String(j?.text ?? "");
}
export async function setJarCap(viewer: Viewer, cap: number): Promise<void> {
  await req("/api/jars/cap", { method: "PUT", body: { who: viewer, cap } });
}

export interface VendorGood { id: string; name: string; kind: string; unit: string; price: number; left: number }
/** One of the role's orders on this visit (for the cook at the window) */
export interface VendorOrder { id: string; name: string; payer: string; state: string; createdAt: number; updatedAt: number }
export interface VendorView {
  visit: { id: string; name: string; who: string; leftS: number; goods: VendorGood[] } | null;
  /** the role's orders on this visit, oldest first */
  mine: VendorOrder[];
  /** the server's "now" (seconds) and this device's clock (ms) when it was read */
  now: number; readAt: number;
  spent: number; cap: number; balance: number | null; localWallet: boolean;
  flower: { name: string; variety: string; state: string; gifted: boolean; note: string } | null;
  requests: { id: string; name: string; state: string }[];
}
export function parseVendor(j: unknown): VendorView {
  const r = (j ?? {}) as J;
  const v = r.visit as J | null;
  return {
    visit: v ? { id: String(v.id ?? ""), name: String(v.name ?? ""), who: String(v.who ?? ""), leftS: Number(v.left_s ?? 0),
      goods: Array.isArray(v.goods) ? v.goods.map((g: J) => ({ id: String(g.id), name: String(g.name ?? ""), kind: String(g.kind ?? ""),
        unit: String(g.unit ?? ""), price: g.price | 0, left: g.left | 0 })) : [] } : null,
    mine: Array.isArray(r.mine) ? r.mine.filter((o: J) => o && o.id != null).map((o: J) => ({
      id: String(o.id), name: String(o.item_name ?? ""), payer: String(o.payer ?? ""), state: String(o.state ?? ""),
      createdAt: Number(o.created_at ?? 0), updatedAt: Number(o.updated_at ?? o.created_at ?? 0) })) : [],
    now: typeof r.now === "number" ? r.now : 0, readAt: Date.now(),
    spent: r.today?.spent | 0, cap: r.today?.cap | 0,
    balance: typeof r.wallet?.balance === "number" ? r.wallet.balance : null, localWallet: r.wallet?.local === true,
    flower: r.flower ? { name: String(r.flower.name ?? ""), variety: String(r.flower.variety ?? ""), state: String(r.flower.state ?? ""), gifted: r.flower.gifted === true, note: String(r.flower.note ?? "") } : null,
    requests: Array.isArray(r.flower_requests) ? r.flower_requests.map((x: J) => ({ id: String(x.id), name: String(x.name ?? ""), state: String(x.state ?? "") })) : [],
  };
}
export async function fetchVendor(viewer: Viewer): Promise<VendorView> {
  return parseVendor(await req(`/api/vendor?who=${q(viewer)}`));
}
export async function treat(viewer: Viewer, itemId: string, requestId: string): Promise<boolean> {
  const j = (await req("/api/vendor/treat", { method: "POST", body: { who: viewer, item_id: itemId, qty: 1, request_id: requestId } })) as J;
  return j?.ok === true;
}
export async function decideFlower(id: string, approve: boolean): Promise<void> {
  await req(`/api/vendor/flowers/${q(id)}`, { method: "POST", body: { approve } });
}
export async function fetchWallet(viewer: Viewer): Promise<{ local: boolean; balance: number | null }> {
  const j = (await req(`/api/wallet?who=${q(viewer)}`)) as J;
  return { local: j?.local === true, balance: typeof j?.balance === "number" ? j.balance : null };
}
export async function grantPocket(viewer: Viewer, amount: number, key: string): Promise<number> {
  const j = (await req("/api/wallet/grant", { method: "POST", body: { who: viewer, amount, key } })) as J;
  return Number(j?.balance ?? 0);
}
export const FLOWER_STATE: Record<string, string> = { fresh: "刚买的", droopy: "有点蔫了", wilted: "谢了" };
