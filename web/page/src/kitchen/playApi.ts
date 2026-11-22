// What the page reads and writes for the upgrade (docs/UPGRADE.md, docs/API.md "The upgrade"):
//   GET  /api/features                      which of the seventeen are on (an entrance is hidden when off)
//   GET  /api/recipes?q=&who=               the public recipes      GET /api/recipes/today?who=
//   PUT  /api/recipes/<id>/stop             a recipe with a mistake out of picks (and back)   GET /api/recipes/stopped
//   GET /api/prefs · POST /api/prefs/dislike · DELETE /api/prefs/dislike/<item>   ingredients not to recommend, one at a time
//   GET /api/recipes/missing?who=&recipe=   what a recipe lacks      POST /api/recipes/buy_missing   buying it (worked out by the server)
//   GET  /api/book?who=                     the role's own pages     DELETE /api/book/<page>?who=
//   GET/POST/DELETE /api/orders             ordering a dish from a recipe
//   GET  /api/codes?who=&page=              a page as a code         POST /api/codes/preview · /api/codes/import
//   GET  /api/dex?who=                      the dish book and the achievements   PUT /api/dex/note · /api/dex/merge
//   POST /api/dex/art/redraw · PUT /api/dex/art/choice · GET /api/dex/art?page_key=&version=   a page's pictures
//   GET  /api/dishes?who=                   plates                   PUT /api/dishes/settings
//   GET  /api/jars?who=                     the jars and what came out    PUT /api/jars/cap · POST /api/jars/feed
//   GET  /api/vendor?who=                   the vendor downstairs, the sill   POST /api/vendor/treat · /api/vendor/flowers/<id>
//   GET  /api/vendor/ledger?who=            one line per order (read only)
//   POST /api/wallet/grant                  pocket money into the built-in ledger
import { getConn } from "../runtime/session";
import { req, type ArtAuth, type Viewer } from "./fridgeApi";

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

/** Take a recipe with a mistake out of picks and search (stopped = false puts it back); pots and pages stay */
export async function stopRecipe(id: string, stopped: boolean, why = ""): Promise<void> {
  await req(`/api/recipes/${q(id)}/stop`, { method: "PUT", body: { stopped, why } });
}

export interface StoppedRecipe { id: string; name: string; why: string }
export function parseStopped(j: unknown): StoppedRecipe[] {
  const list = j && typeof j === "object" ? (j as J).recipes : null;
  return Array.isArray(list)
    ? list.filter((r: J) => r && typeof r.id === "string").map((r: J) => ({ id: r.id, name: String(r.name ?? r.id), why: String(r.why ?? "") }))
    : [];
}
export async function fetchStopped(): Promise<StoppedRecipe[]> {
  return parseStopped(await req("/api/recipes/stopped"));
}

/** The ingredients (catalog ids) the human does not want recommended to this role */
export async function fetchDislikes(viewer: Viewer): Promise<string[]> {
  const j = (await req(`/api/prefs?who=${q(viewer)}`)) as J;
  return Array.isArray(j?.dislike) ? j.dislike.map(String) : [];
}
const dislikeList = (j: J | null): string[] => (Array.isArray(j?.dislike) ? j!.dislike.map(String) : []);
/** Add one ingredient (already there = nothing changes); answers the whole list as it is now */
export async function addDislike(viewer: Viewer, item: string): Promise<string[]> {
  return dislikeList((await req("/api/prefs/dislike", { method: "POST", body: { who: viewer, item } })) as J);
}
/** Take one ingredient off (not there = nothing changes); answers the whole list as it is now */
export async function removeDislike(viewer: Viewer, item: string): Promise<string[]> {
  return dislikeList((await req(`/api/prefs/dislike/${q(item)}?who=${q(viewer)}`, { method: "DELETE" })) as J);
}

export interface Missing { itemId: string; name: string; short: number; sold: boolean; packs: number }
export function parseMissing(j: unknown): { name: string; missing: Missing[] } {
  const r = (j ?? {}) as J;
  return {
    name: String(r.name ?? ""),
    missing: Array.isArray(r.missing) ? r.missing.filter((m: J) => m && typeof m.item_id === "string").map((m: J) => ({
      itemId: m.item_id, name: String(m.name ?? m.item_id), short: Number(m.short ?? 0), sold: m.sold === true, packs: Math.max(1, m.packs | 0),
    })) : [],
  };
}
/** What the fridge lacks for a recipe (or a page of the role's book), in whole packs */
export async function fetchMissing(viewer: Viewer, recipe: string): Promise<{ name: string; missing: Missing[] }> {
  return parseMissing(await req(`/api/recipes/missing?who=${q(viewer)}&recipe=${q(recipe)}`));
}
/**
 * Buy what a recipe lacks for the role. `opId`: one per buying, the same for a retry of it (the server
 * answers a retry with the receipt it kept and buys nothing more; a new buying works the shortage out
 * again). Answers the fridge's sentence and what is still missing
 */
export async function buyMissing(viewer: Viewer, recipe: string, opId: string): Promise<{ text: string; bought: boolean; missing: Missing[] }> {
  const j = (await req("/api/recipes/buy_missing", { method: "POST", body: { who: viewer, recipe, op_id: opId } })) as J;
  return { text: String(j?.text ?? ""), bought: Array.isArray(j?.added) && j.added.length > 0, missing: parseMissing(j).missing };
}
/** The ids to hand to the human's buying for what is missing: one per pack, only what the shop sells */
export function missingToBuy(missing: Missing[]): string[] {
  return missing.filter((m) => m.sold).flatMap((m) => Array.from({ length: m.packs }, () => m.itemId));
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

/** A page's pictures: every version is kept; `chosen` = the one shown (null = none ready yet, the placeholder is shown) */
export interface DexArt {
  chosen: number | null;
  /** the versions that are ready, oldest first (the ones the human can switch back to) */
  ready: number[];
  /** the newest version is being drawn / failed (and why) */
  drawing: boolean;
  failed: string | null;
}
export interface DexPage {
  key: string; name: string; made: number; good: number; eaten: number; best: string | null; firstAt: number; pending: boolean;
  method: string; ingredients: string[]; humanNote: string; roleNote: string;
  /** which of the fourteen small pixel dishes stands in while there is no picture */
  icon: string;
  art: DexArt;
  /** the unsorted dish names merged into this page (each can be taken back out) */
  mergedIn: string[];
}
export interface Achievement { key: string; name: string; earned: boolean; why: string }
export interface Silhouette { name: string; recipeId: string; icon: string }
export interface Dex { pages: DexPage[]; silhouettes: Silhouette[]; total: number | null; madePublic: number; artMissing: number; drawing: boolean; achievements: Achievement[] }

export function parseDexArt(a: unknown): DexArt {
  const r = (a && typeof a === "object" ? a : {}) as J;
  const versions: J[] = Array.isArray(r.versions) ? r.versions.filter((v: J) => v && typeof v.version === "number") : [];
  const last = versions[versions.length - 1];
  return {
    chosen: typeof r.chosen === "number" ? r.chosen : null,
    ready: versions.filter((v) => v.state === "ready").map((v) => v.version as number),
    drawing: last?.state === "pending",
    failed: last?.state === "failed" ? String(last.err || "没画成") : null,
  };
}

export function parseDex(j: unknown): Dex {
  const r = (j ?? {}) as J;
  const t = (r.totals ?? {}) as J;
  const merges: J[] = Array.isArray(r.merges) ? r.merges : [];
  return {
    pages: Array.isArray(r.pages) ? r.pages.map((p: J) => ({
      key: String(p.key), name: String(p.name ?? ""), made: p.made | 0, good: p.good | 0, eaten: p.eaten | 0,
      best: typeof p.best === "string" ? p.best : null, firstAt: typeof p.first_at === "number" ? p.first_at : 0,
      pending: p.pending === true, method: String(p.method ?? ""), ingredients: Array.isArray(p.ingredients) ? p.ingredients.map(String) : [],
      humanNote: String(p.human_note ?? ""), roleNote: String(p.role_note ?? ""),
      icon: String(p.icon ?? ""), art: parseDexArt(p.art),
      mergedIn: merges.filter((m) => m && m.page_key === p.key).map((m) => String(m.dish ?? "")),
    })) : [],
    silhouettes: Array.isArray(r.silhouettes)
      ? r.silhouettes.map((s: J) => ({ name: String(s.name ?? ""), recipeId: String(s.recipe_id ?? ""), icon: String(s.icon ?? "") }))
      : [],
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
/** The dish name an unsorted page stands for (its key without "d:"), as /api/dex/merge wants it */
export const unsortedDish = (pageKey: string): string => (pageKey.startsWith("d:") ? pageKey.slice(2) : pageKey);
/** Merge an unsorted dish into a page; merging it onto its own key ("d:" + dish) takes it back out */
export async function mergeDex(viewer: Viewer, dish: string, pageKey: string): Promise<void> {
  await req("/api/dex/merge", { method: "PUT", body: { who: viewer, dish, page_key: pageKey } });
}
/** Ask for a new picture of a page (drawn in the background; the one shown stays until it is ready) */
export async function redrawDex(pageKey: string): Promise<void> {
  await req("/api/dex/art/redraw", { method: "POST", body: { page_key: pageKey } });
}
/** Show an older (or newer) version of a page's picture */
export async function chooseDexArt(pageKey: string, version: number): Promise<void> {
  await req("/api/dex/art/choice", { method: "PUT", body: { page_key: pageKey, version } });
}
/** One version of a page's picture, fetched with the token as a header */
export function dexArtSource(auth: ArtAuth, pageKey: string, version: number): { uri: string; headers: Record<string, string> } {
  return { uri: `${auth.base}/api/dex/art?page_key=${q(pageKey)}&version=${version}`, headers: auth.headers };
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
export interface VendorOrder { id: string; name: string; payer: string; state: string; createdAt: number; updatedAt: number; kind?: string }
export interface VendorVisit { id: string; vendor: string; name: string; who: string; leftS: number; leaveAt: number; goods: VendorGood[] }
export interface VendorView {
  /** `vendor` = which vendor (e.g. "tanghulu"), for the look of his cart; `leaveAt` in server seconds */
  visit: VendorVisit | null;
  /** The visit that just ended, for a short while after it did (nothing can be bought from it): only so the
   *  panel can finish showing an order under way and the vendor leaving. `mine` is then its orders. */
  ended: VendorVisit | null;
  /** the role's orders on this visit, oldest first */
  mine: VendorOrder[];
  /** the server's "now" (seconds) and this device's clock (ms) when it was read */
  now: number; readAt: number;
  spent: number; cap: number; balance: number | null; localWallet: boolean;
  flower: { name: string; variety: string; state: string; gifted: boolean; note: string } | null;
  requests: { id: string; name: string; state: string }[];
  /** Which server and role this was read for (the vendor panel keeps a show per server + role + visit) */
  scope?: string;
}
function visitOf(v: J, now: unknown): VendorVisit {
  const leftS = Number(v.left_s ?? 0);
  return { id: String(v.id ?? ""), vendor: String(v.vendor ?? ""), name: String(v.name ?? ""), who: String(v.who ?? ""), leftS,
    leaveAt: typeof v.leave_at === "number" ? v.leave_at : (typeof now === "number" ? now : 0) + leftS,
    goods: Array.isArray(v.goods) ? v.goods.map((g: J) => ({ id: String(g.id), name: String(g.name ?? ""), kind: String(g.kind ?? ""),
      unit: String(g.unit ?? ""), price: g.price | 0, left: g.left | 0 })) : [] };
}
export function parseVendor(j: unknown): VendorView {
  const r = (j ?? {}) as J;
  const v = r.visit as J | null;
  return {
    visit: v ? visitOf(v, r.now) : null,
    ended: r.ended ? visitOf(r.ended, r.now) : null,
    mine: Array.isArray(r.mine) ? r.mine.filter((o: J) => o && o.id != null).map((o: J) => ({
      id: String(o.id), name: String(o.item_name ?? ""), payer: String(o.payer ?? ""), state: String(o.state ?? ""),
      createdAt: Number(o.created_at ?? 0), updatedAt: Number(o.updated_at ?? o.created_at ?? 0),
      ...(o.kind ? { kind: String(o.kind) } : {}) })) : [],
    now: typeof r.now === "number" ? r.now : 0, readAt: Date.now(),
    spent: r.today?.spent | 0, cap: r.today?.cap | 0,
    balance: typeof r.wallet?.balance === "number" ? r.wallet.balance : null, localWallet: r.wallet?.local === true,
    flower: r.flower ? { name: String(r.flower.name ?? ""), variety: String(r.flower.variety ?? ""), state: String(r.flower.state ?? ""), gifted: r.flower.gifted === true, note: String(r.flower.note ?? "") } : null,
    requests: Array.isArray(r.flower_requests) ? r.flower_requests.map((x: J) => ({ id: String(x.id), name: String(x.name ?? ""), state: String(x.state ?? "") })) : [],
  };
}
export async function fetchVendor(viewer: Viewer): Promise<VendorView> {
  return { ...parseVendor(await req(`/api/vendor?who=${q(viewer)}`)), scope: `${getConn().base}|${viewer}` };
}
export async function treat(viewer: Viewer, itemId: string, requestId: string): Promise<boolean> {
  const j = (await req("/api/vendor/treat", { method: "POST", body: { who: viewer, item_id: itemId, qty: 1, request_id: requestId } })) as J;
  return j?.ok === true;
}
export interface LedgerLine { id: string; name: string; qty: number; total: number; payer: string; state: string; at: number }
export function parseLedger(j: unknown): LedgerLine[] {
  const list = j && typeof j === "object" ? (j as J).orders : null;
  return Array.isArray(list) ? list.filter((o: J) => o && o.id != null).map((o: J) => ({
    id: String(o.id), name: String(o.item_name ?? ""), qty: o.qty | 0, total: o.total | 0, payer: String(o.payer ?? ""),
    state: String(o.state ?? ""), at: Number(o.created_at ?? 0),
  })) : [];
}
export async function fetchLedger(viewer: Viewer): Promise<LedgerLine[]> {
  return parseLedger(await req(`/api/vendor/ledger?who=${q(viewer)}`));
}
/** How an order stands, in a word (the money is settled by the server; this only reads it) */
export const LEDGER_STATE: Record<string, string> = {
  created: "在办", debiting: "在扣钱", debit_failed: "没买成", paid: "付了", delivered: "到手了", refunding: "在退钱", refunded: "退了钱",
};
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
