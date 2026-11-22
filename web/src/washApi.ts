// Reading one washing back from the kitchenette backend: GET <base>/api/dishes/jobs/<id>.
// The washing card plays from the facts it was given (start time, plates, seconds each) against the local
// clock; it asks the backend only for what the facts cannot tell: which plates broke, whether the washing
// was stopped midway, and how many ended up clean, broken or in the dishwasher.
import { KitchenFetchError, getJson } from "./api";
import type { WashFacts, WashPlate, WashRead } from "./washSegments";

/** The card attachment a [刷盘子] that started a washing hands the chat (kind "kitchen_washing") */
export interface WashingAttachment {
  kind?: string;
  job_id: string;
  who?: string;
  n: number;
  per_s: number;
  /** epoch seconds */
  started_at: number;
}

/** Reads the washing again. fresh = skip any cache. Resolves null when the backend does not know it. */
export type WashProbeFn = (jobId: string, fresh?: boolean) => Promise<WashRead | null>;

const num = (v: unknown, d = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : d);
const numOrNull = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string => (typeof v === "string" ? v : "");

/** The attachment as the card's facts; null when it is not a washing card */
export function factsFromAttachment(a: unknown): WashFacts | null {
  const o = a && typeof a === "object" ? (a as Record<string, unknown>) : null;
  if (!o) return null;
  const jobId = str(o.job_id) || str(o.id);
  if (!jobId) return null;
  const startedAt = numOrNull(o.started_at);
  if (startedAt === null) return null;
  return { jobId, startedAt, perS: num(o.per_s, 120), n: Math.max(0, Math.floor(num(o.n))) };
}

/** The body of GET /api/dishes/jobs/<id>; null when it is not one washing */
export function parseWashRead(body: unknown): WashRead | null {
  const o = body && typeof body === "object" ? (body as Record<string, unknown>) : null;
  if (!o || !str(o.id) || numOrNull(o.started_at) === null) return null;
  const c = o.counts && typeof o.counts === "object" ? (o.counts as Record<string, unknown>) : {};
  const cn = (k: string): number => Math.max(0, Math.floor(num(c[k])));
  const dishes: WashPlate[] = (Array.isArray(o.dishes) ? o.dishes : []).flatMap((x) => {
    const r = x && typeof x === "object" ? (x as Record<string, unknown>) : null;
    if (!r || typeof r.i !== "number") return [];
    return [{ i: Math.floor(r.i), state: str(r.state), doneAt: numOrNull(r.done_at) }];
  });
  return {
    now: num(o.now), state: str(o.state), startedAt: num(o.started_at), perS: num(o.per_s, 120),
    n: Math.max(0, Math.floor(num(o.n))), endedAt: numOrNull(o.ended_at),
    counts: { washing: cn("washing"), clean: cn("clean"), broken: cn("broken"), machine: cn("machine") },
    dishes, timezone: str(o.timezone),
  };
}

/** The facts a card that was only given an id starts from */
export function factsFromRead(id: string, r: WashRead): WashFacts {
  return { jobId: id, startedAt: r.startedAt, perS: r.perS, n: r.n };
}

/**
 * Reads one washing. Rejects with a KitchenFetchError that says why (unreachable, blocked, unauthorized,
 * not_found, server, bad_response).
 */
export async function fetchWashing(base: string, jobId: string, token?: string | null): Promise<WashRead> {
  const url = `${base.replace(/\/+$/, "")}/api/dishes/jobs/${encodeURIComponent(jobId)}`;
  let body: unknown;
  try {
    body = await getJson(url, token);
  } catch (e) {
    if (e instanceof KitchenFetchError && e.kind === "not_found") {
      throw new KitchenFetchError("not_found", e.status, `the kitchen server has no washing with this id${e.status ? ` (status ${e.status})` : ""}`);
    }
    throw e;
  }
  const r = parseWashRead(body);
  if (!r) throw new KitchenFetchError("bad_response", null, "the kitchen server's answer was not understood");
  return r;
}

/** A probe that reads from the backend at `base`, with an optional Bearer token (a string, or a function returning the current one) */
export function washApiProbe(base: string, token?: string | null | (() => string | null | undefined)): WashProbeFn {
  return async (jobId) => {
    try {
      return await fetchWashing(base, jobId, typeof token === "function" ? token() : token);
    } catch (e) {
      if (e instanceof KitchenFetchError && e.kind === "not_found") return null;
      throw e;
    }
  };
}
