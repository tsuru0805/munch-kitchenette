// The fridge: data layer of the page. Endpoints (docs/API.md):
//   GET    /api/fridge?who=<role>            stock (most urgent first) + staples + coupons + recent log + satiety + dizzy
//   GET    /api/fridge/catalog               everything buyable (id = file name prefix of the bundled pictures)
//   POST   /api/fridge/buy                   the human buys ({who, items}); no coupon spent; 4xx {detail} on failure
//   POST   /api/fridge/coupon                the human hands out a coupon ({who}); 409 {detail} at the cap
//   POST   /api/fridge/kinds                 add an ingredient kind ({name, category, raw_edible?, pack_qty?, shelf_days?})
//   DELETE /api/fridge/kinds/<id>            stop offering a kind (what is already in a fridge stays)
//   POST   /api/fridge/kinds/<id>/redraw     draw its picture again
//   GET    /api/fridge/art/<id>/<fresh|meh|bad>.png   the picture of an added kind (the built-in ones ship with the page)
// The catalog and every number live on the server; nothing is copied here. An answer of the wrong
// shape is treated as "this part is not there".
// Times: numbers are epoch seconds (< 1e12) or milliseconds, strings are ISO; all become milliseconds.
import { authHeaders, getConn } from "../runtime/session";
import { syncClock } from "../runtime/zone";

/** A role id: whose kitchen this is. */
export type Viewer = string;

export type Freshness = "fresh" | "meh" | "bad";
export type FridgeCategory = "leafy" | "veg" | "root" | "dairy" | "meat" | "staple_food" | "fruit";

export interface FridgeItem {
  batchId: string;
  itemId: string;
  name: string;
  category: FridgeCategory | string;
  qty: number;
  boughtAtMs: number | null;
  by: "her" | "self" | string;
  expiresAtMs: number | null;
  freshness: Freshness;
  /** Only kinds the human added have this (their picture is fetched from the server); built-in kinds do not. */
  art?: KindArt | null;
}

/** Picture of an added kind: none = the server draws no pictures; pending = being drawn; ready; failed (err = why). v = how many times it was drawn (0 = never). */
export interface KindArt {
  state: "none" | "pending" | "ready" | "failed";
  v: number;
  sizes: Partial<Record<Freshness, { w: number; h: number }>>;
  err: string;
}

export interface FridgeLog {
  atMs: number | null;
  kind: string;
  text: string;
}

export interface FridgeState {
  nowMs: number;
  viewer: Viewer;
  items: FridgeItem[];
  staples: string[];
  coupons: { count: number; max: number };
  log: FridgeLog[];
  /** 0–100; null when the server gave none or satiety is switched off */
  satiety: number | null;
  dizzy: { untilMs: number; dish: string } | null;
}

export interface CatalogItem {
  id: string;
  name: string;
  category: FridgeCategory | string;
  packQty: number;
  shelfDays: number;
  /** Added by the human (can be removed and redrawn) */
  custom: boolean;
  rawEdible: boolean;
  art: KindArt | null;
}

export function parseKindArt(v: unknown): KindArt | null {
  if (!v || typeof v !== "object") return null;
  const r = v as Record<string, unknown>;
  const state = r.state === "ready" || r.state === "failed" || r.state === "none" ? r.state : "pending";
  const sizes: KindArt["sizes"] = {};
  const raw = (r.sizes ?? {}) as Record<string, unknown>;
  for (const f of ["fresh", "meh", "bad"] as const) {
    const wh = raw[f];
    if (Array.isArray(wh) && num(wh[0]) > 0 && num(wh[1]) > 0) sizes[f] = { w: num(wh[0]), h: num(wh[1]) };
  }
  return { state, v: Math.max(0, Math.floor(num(r.v))), sizes, err: str(r.err) };
}

/** The server answered 4xx with a detail: its sentence is shown as is. status 0 = wrong shape; -1 = timed out. */
export class FridgeHttpError extends Error {
  status: number;
  /** The reason code the server put in detail (potions give one: gone / busy / energy …); "" when none */
  code: string;
  constructor(status: number, detail: string, code = "") {
    super(detail);
    this.status = status;
    this.code = code;
  }
}

/** A request that hangs would hold its in-flight lock forever, so every request has a deadline. */
export const FRIDGE_TIMEOUT_MS = 20_000;
export const TIMEOUT_TEXT = "网络超时";

/** What to show: the server's own sentence / the timeout sentence / a fallback */
export function fridgeErrText(e: unknown, fallback: string): string {
  if (e instanceof FridgeHttpError && (e.status > 0 || e.status === -1)) return e.message;
  return fallback;
}

// ── pure functions ──────────────────────────────────────────────────

const str = (v: unknown): string => (typeof v === "string" ? v : "");
const num = (v: unknown, d = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : d);

/** Any time to milliseconds: a number < 1e12 is seconds; a string is ISO; anything else is null */
export function toMs(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v < 1e12 ? v * 1000 : v;
  if (typeof v === "string" && v) {
    const t = Date.parse(v);
    return Number.isFinite(t) ? t : null;
  }
  return null;
}

function parseFreshness(v: unknown): Freshness {
  return v === "meh" || v === "bad" ? v : "fresh";
}

function parseItem(v: unknown): FridgeItem | null {
  if (!v || typeof v !== "object") return null;
  const r = v as Record<string, unknown>;
  const itemId = str(r.item_id);
  if (!itemId) return null;
  return {
    batchId: str(r.batch_id) || String(r.batch_id ?? itemId),
    itemId,
    name: str(r.name) || itemId,
    category: str(r.category),
    qty: Math.max(0, Math.floor(num(r.qty, 1))),
    boughtAtMs: toMs(r.bought_at),
    by: str(r.by),
    expiresAtMs: toMs(r.expires_at),
    freshness: parseFreshness(r.freshness),
    art: parseKindArt(r.art),
  };
}

/** Answer -> FridgeState; null when the shape is wrong */
export function parseFridgeState(j: unknown, viewer: Viewer): FridgeState | null {
  if (!j || typeof j !== "object") return null;
  const r = j as Record<string, unknown>;
  if (!Array.isArray(r.items)) return null;
  const c = (r.coupons ?? {}) as Record<string, unknown>;
  const sat = (r.satiety ?? null) as Record<string, unknown> | null;
  const dz = (r.dizzy ?? null) as Record<string, unknown> | null;
  const dzUntil = dz ? toMs(dz.until) : null;
  return {
    nowMs: toMs(r.now) ?? Date.now(),
    viewer: str(r.who) || viewer,
    items: r.items.map(parseItem).filter((x): x is FridgeItem => x !== null),
    staples: Array.isArray(r.staples) ? r.staples.filter((x): x is string => typeof x === "string") : [],
    coupons: { count: Math.max(0, Math.floor(num(c.count))), max: Math.max(1, Math.floor(num(c.max, 3))) },
    log: Array.isArray(r.log)
      ? r.log
          .map((x) => {
            const o = (x ?? {}) as Record<string, unknown>;
            const text = str(o.text);
            return text ? { atMs: toMs(o.at), kind: str(o.kind), text } : null;
          })
          .filter((x): x is FridgeLog => x !== null)
      : [],
    // satiety switched off on the server: the number is not shown at all
    satiety: sat && sat.enabled !== false && typeof sat.value === "number" && Number.isFinite(sat.value)
      ? Math.max(0, Math.min(100, Math.round(sat.value)))
      : null,
    dizzy: dz && dzUntil !== null ? { untilMs: dzUntil, dish: str(dz.dish) } : null,
  };
}

export function parseCatalog(j: unknown): CatalogItem[] | null {
  const arr = Array.isArray(j) ? j : j && typeof j === "object" && Array.isArray((j as { items?: unknown }).items)
    ? (j as { items: unknown[] }).items
    : null;
  if (!arr) return null;
  return arr
    .map((v) => {
      const r = (v ?? {}) as Record<string, unknown>;
      const id = str(r.id);
      return id
        ? {
            id, name: str(r.name) || id, category: str(r.category), packQty: Math.max(1, Math.floor(num(r.pack_qty, 1))), shelfDays: num(r.shelf_days),
            custom: r.custom === true, rawEdible: r.raw_edible === true, art: r.custom === true ? parseKindArt(r.art) : null,
          }
        : null;
    })
    .filter((x): x is CatalogItem => x !== null);
}

// ── network ─────────────────────────────────────────────────────────

export async function req(path: string, init?: { method: "POST" | "DELETE" | "PATCH" | "PUT"; body?: unknown }): Promise<unknown> {
  const headers: Record<string, string> = authHeaders();
  if (init?.body !== undefined) headers["Content-Type"] = "application/json";
  // deadline = AbortController cuts the request + a timer rejects anyway (so a transport that ignores
  // the signal still fails on time); the timer is cleared in finally
  const ctrl = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      ctrl.abort();
      reject(new FridgeHttpError(-1, TIMEOUT_TEXT));
    }, FRIDGE_TIMEOUT_MS);
  });
  let r: Response;
  let body: unknown = null;
  try {
    const opts = init
      ? { method: init.method, headers, ...(init.body !== undefined ? { body: JSON.stringify(init.body) } : {}), signal: ctrl.signal }
      : { headers, signal: ctrl.signal };
    r = await Promise.race([fetch(`${getConn().base}${path}`, opts), timeout]);
    try {
      body = await Promise.race([r.json(), timeout]);
    } catch (e) {
      if (e instanceof FridgeHttpError) throw e;
      // the headers said 200 and the deadline cut the body half-way: that is a timeout, not an empty body
      if (ctrl.signal.aborted) throw new FridgeHttpError(-1, TIMEOUT_TEXT);
      body = null;
    }
  } catch (e) {
    if (e instanceof FridgeHttpError) throw e;
    if (ctrl.signal.aborted) throw new FridgeHttpError(-1, TIMEOUT_TEXT);
    throw e;
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) {
    const d = body && typeof body === "object" ? (body as { detail?: unknown }).detail : null;
    const detail = typeof d === "string" ? d : d && typeof d === "object" && typeof (d as { message?: unknown }).message === "string"
      ? (d as { message: string }).message
      : "";
    const code = d && typeof d === "object" && typeof (d as { code?: unknown }).code === "string" ? (d as { code: string }).code : "";
    throw new FridgeHttpError(r.status, detail || `http_${r.status}`, code);
  }
  return body;
}

export async function fetchFridge(viewer: Viewer): Promise<FridgeState> {
  const st = parseFridgeState(await req(`/api/fridge?who=${encodeURIComponent(viewer)}`), viewer);
  if (!st) throw new FridgeHttpError(0, "fridge bad_shape");
  syncClock(st.nowMs);
  return st;
}

export async function fetchCatalog(): Promise<CatalogItem[]> {
  const c = parseCatalog(await req("/api/fridge/catalog"));
  if (!c) throw new FridgeHttpError(0, "catalog bad_shape");
  return c;
}

export async function buyItems(viewer: Viewer, items: string[]): Promise<{ text: string }> {
  const r = (await req("/api/fridge/buy", { method: "POST", body: { who: viewer, items } })) as Record<string, unknown> | null;
  return { text: str(r?.text) };
}

export async function sendCoupon(viewer: Viewer): Promise<{ count: number; text: string }> {
  const r = (await req("/api/fridge/coupon", { method: "POST", body: { who: viewer } })) as Record<string, unknown> | null;
  return { count: Math.floor(num(r?.count)), text: str(r?.text) };
}

// ── kinds the human adds ────────────────────────────────────────────

export interface NewKind {
  name: string;
  category: FridgeCategory;
  rawEdible: boolean;
  packQty: number;
  /** null = the default number of days for its category */
  shelfDays: number | null;
}

export async function addKind(k: NewKind): Promise<void> {
  await req("/api/fridge/kinds", {
    method: "POST",
    body: { name: k.name, category: k.category, raw_edible: k.rawEdible, pack_qty: k.packQty, shelf_days: k.shelfDays },
  });
}

export async function removeKind(id: string): Promise<void> {
  await req(`/api/fridge/kinds/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function redrawKind(id: string): Promise<void> {
  await req(`/api/fridge/kinds/${encodeURIComponent(id)}/redraw`, { method: "POST" });
}

/** Address and header for fetching a picture (the image element sends its own request, not through req) */
export interface ArtAuth {
  base: string;
  headers: Record<string, string>;
}

export function artAuth(): ArtAuth {
  return { base: getConn().base, headers: authHeaders() };
}

// ── in-flight locks: kept in this module by "action:role", so a sheet that is closed and reopened
// still knows a request is on its way; while one is, the buttons for it are dimmed and a second
// submit is not sent. ───────────────────────────────────────────────

const inflight = new Set<string>();
const inflightListeners = new Set<() => void>();

export type FridgeAction = "buy" | "coupon" | "kind";

export function inflightKey(action: FridgeAction, viewer: Viewer | "all"): string {
  return `${action}:${viewer}`;
}

export function isInflight(key: string): boolean {
  return inflight.has(key);
}

export function subscribeInflight(fn: () => void): () => void {
  inflightListeners.add(fn);
  return () => {
    inflightListeners.delete(fn);
  };
}

function setInflight(key: string, on: boolean) {
  if (on) inflight.add(key);
  else inflight.delete(key);
  [...inflightListeners].forEach((fn) => fn());
}

/** null when the same key is already on its way (nothing is sent); otherwise holds the lock until done */
export async function withInflight<T>(key: string, fn: () => Promise<T>): Promise<T | null> {
  if (inflight.has(key)) return null;
  setInflight(key, true);
  try {
    return await fn();
  } finally {
    setInflight(key, false);
  }
}

/** For tests */
export function _resetInflight(): void {
  inflight.clear();
  inflightListeners.clear();
}
