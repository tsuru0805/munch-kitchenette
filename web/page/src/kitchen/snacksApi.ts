// The snack shelf: data layer. Endpoints (docs/API.md):
//   GET  /api/snacks?who=       the shelf + today's counts + caps
//   POST /api/snacks/eat        the human feeds one ({who, snack, variant}); 409 past the cap (detail carries eaten/cap/message)
//   PUT  /api/snacks/caps       the human changes daily caps ({who, caps: {id: n}})
// The shelf and its numbers live on the server only. A server without this part (404/405) is its
// own case, and the page says so in plain words.
import { authHeaders, getConn } from "../runtime/session";
import { wall } from "../runtime/zone";
import type { Viewer } from "./fridgeApi";

export type SnackTier = "high" | "mid" | "low";

export interface SnackVariant {
  id: string;
  name: string;
  gain: number;
}

export interface Snack {
  id: string;
  name: string;
  tier: SnackTier;
  tierLabel: string;
  gain: number | null; // null for a snack with flavours (coffee): see variants
  variants: SnackVariant[];
  cap: number;
  defaultCap: number;
  eaten: number;
}

export interface SnackState {
  viewer: Viewer;
  day: string;
  resetsAt: number; // epoch seconds
  energyEnabled: boolean; // stamina switched on: show what a serving restores
  capMin: number;
  capMax: number;
  snacks: Snack[];
}

export interface EatResult {
  name: string;
  energyDelta: number;
  energy: number | null;
  eaten: number;
  cap: number;
}

// ── pure functions ──────────────────────────────────────────────────

const num = (v: unknown, d = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : d);
const str = (v: unknown): string => (typeof v === "string" ? v : "");

function parseSnack(v: unknown): Snack | null {
  if (!v || typeof v !== "object") return null;
  const r = v as Record<string, unknown>;
  const id = str(r.id);
  const tier = r.tier === "high" || r.tier === "mid" || r.tier === "low" ? r.tier : null;
  if (!id || !tier) return null;
  const variants = Array.isArray(r.variants)
    ? r.variants
        .map((x) => {
          const o = (x ?? {}) as Record<string, unknown>;
          return str(o.id) ? { id: str(o.id), name: str(o.name), gain: num(o.gain) } : null;
        })
        .filter((x): x is SnackVariant => x !== null)
    : [];
  return {
    id,
    name: str(r.name) || id,
    tier,
    tierLabel: str(r.tier_label),
    gain: typeof r.gain === "number" ? r.gain : null,
    variants,
    cap: Math.max(0, Math.floor(num(r.cap))),
    defaultCap: Math.max(0, Math.floor(num(r.default_cap))),
    eaten: Math.max(0, Math.floor(num(r.eaten))),
  };
}

// Answer -> SnackState; null when the shape is wrong (the caller treats it as "this part is not there").
export function parseSnackState(j: unknown): SnackState | null {
  if (!j || typeof j !== "object") return null;
  const r = j as Record<string, unknown>;
  if (!str(r.who) || !Array.isArray(r.snacks)) return null;
  const snacks = r.snacks.map(parseSnack).filter((x): x is Snack => x !== null);
  return {
    viewer: str(r.who),
    day: str(r.day),
    resetsAt: num(r.resets_at),
    energyEnabled: r.energy_enabled === true,
    capMin: Math.floor(num(r.cap_min, 0)),
    capMax: Math.floor(num(r.cap_max, 20)),
    snacks,
  };
}

/** What one serving restores, as text (only shown while stamina is on). Coffee uses the chosen flavour. */
export function gainText(gain: number): string {
  return `+${gain.toFixed(2)}`;
}

/** The reset moment as HH:MM in the kitchen's time zone */
export function resetText(resetsAt: number): string {
  const w = wall(resetsAt * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(w.hour)}:${pad(w.minute)}`;
}

/** Step a cap, clamped to [min, max] */
export function stepCap(v: number, delta: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v + delta));
}

// ── network ─────────────────────────────────────────────────────────

const TIMEOUT_MS = 8000;

export class SnacksUnsupportedError extends Error {
  constructor() {
    super("snacks unsupported");
    this.name = "SnacksUnsupportedError";
  }
}

/** Past the cap (409): message is the server's sentence (eaten / cap / when it resets) */
export class SnackCapError extends Error {
  eaten: number;
  cap: number;
  constructor(message: string, eaten: number, cap: number) {
    super(message);
    this.name = "SnackCapError";
    this.eaten = eaten;
    this.cap = cap;
  }
}

async function call(path: string, init?: RequestInit): Promise<unknown> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const r = await fetch(`${getConn().base}${path}`, {
      ...init,
      headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...authHeaders() },
      signal: ctrl.signal,
    });
    if (r.status === 404 || r.status === 405) throw new SnacksUnsupportedError();
    if (!r.ok) {
      let detail: unknown = null;
      try {
        detail = ((await r.json()) as { detail?: unknown }).detail;
      } catch {
        // an error body that is not JSON: only the status is reported
      }
      if (r.status === 409 && detail && typeof detail === "object") {
        const d = detail as Record<string, unknown>;
        throw new SnackCapError(str(d.message) || "今天这款已经吃满了", num(d.eaten), num(d.cap));
      }
      throw new Error(typeof detail === "string" && detail ? detail : `零食 ${r.status}`);
    }
    return await r.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchSnacks(viewer: Viewer): Promise<SnackState> {
  const parsed = parseSnackState(await call(`/api/snacks?who=${encodeURIComponent(viewer)}`));
  if (!parsed) throw new SnacksUnsupportedError();
  return parsed;
}

export async function feedSnack(
  viewer: Viewer,
  snack: string,
  variant: string | null,
): Promise<{ result: EatResult; notified: boolean; state: SnackState }> {
  const j = (await call("/api/snacks/eat", {
    method: "POST",
    body: JSON.stringify({ who: viewer, snack, ...(variant ? { variant } : {}) }),
  })) as Record<string, unknown>;
  const st = parseSnackState(j.state);
  if (!st) throw new SnacksUnsupportedError();
  const r = (j.result ?? {}) as Record<string, unknown>;
  return {
    result: {
      name: str(r.name),
      energyDelta: num(r.energy_delta),
      energy: typeof r.energy === "number" ? r.energy : null,
      eaten: num(r.eaten),
      cap: num(r.cap),
    },
    notified: j.notified === true,
    state: st,
  };
}

export async function saveSnackCaps(viewer: Viewer, caps: Record<string, number>): Promise<SnackState> {
  const parsed = parseSnackState(
    await call("/api/snacks/caps", { method: "PUT", body: JSON.stringify({ who: viewer, caps }) }),
  );
  if (!parsed) throw new SnacksUnsupportedError();
  return parsed;
}
