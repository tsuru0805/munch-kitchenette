// Reading one pot back from the kitchenette backend: GET <base>/api/kitchen?session_id=<id> -> { now, session }.
// The card counts down from the facts it already has (start time + duration) against the local clock;
// it asks the backend only for what the facts cannot tell: whether the pot was cancelled, and how it
// turned out. A failed request rejects; the card then carries on as if nothing had changed.
import type { KitchenOutcome } from "./cookPhase";

export interface KitchenIngredient {
  name: string;
  freshness?: string;
}

/** One pot, as the backend sends it */
export interface KitchenSession {
  id: string;
  dish: string;
  note?: string;
  duration_seconds: number;
  /** epoch seconds */
  started_at: number;
  status?: "cooking" | "served" | "cancelled";
  served_at?: number | null;
  cancelled_at?: number | null;
  remaining_seconds?: number;
  outcome?: KitchenOutcome | null;
  ingredients?: KitchenIngredient[];
  /** stirfry | fry | deepfry | boil | steam | bake | mix; anything else plays as stir-fry */
  method?: string | null;
}

/**
 * The settled card (the backend's "settle_card" switch): the facts of the moment the pot was served,
 * written once and never changed. Present only when the backend has it.
 */
export interface KitchenSettlement {
  outcome: string;
  /** follow = cooked by a recipe; changed = by a recipe, changed; free = no recipe */
  link: string;
  /** null when proficiency is switched off */
  proficiency: { tier: string; n: number; toNext: number | null } | null;
  /** null = not shown (switched off, or not known); state none = nothing happened, had = what happened */
  mishap: { state: "none" | "had" | "unknown"; text: string | null } | null;
  stamps: string[];
  /** which dish picture the cook holds up (a kind such as "stirfry"; "" = the plain bowl) */
  icon: string;
}

/** The `settlement` object of an answer; null unless it says it has one */
export function parseSettlement(v: unknown): KitchenSettlement | null {
  if (!v || typeof v !== "object") return null;
  const s = v as Record<string, unknown>;
  if (s.has !== true) return null;
  const pr = s.proficiency && typeof s.proficiency === "object" ? (s.proficiency as Record<string, unknown>) : null;
  const mi = s.mishap && typeof s.mishap === "object" ? (s.mishap as Record<string, unknown>) : null;
  const state = mi && (mi.state === "none" || mi.state === "had" || mi.state === "unknown") ? mi.state : null;
  return {
    outcome: typeof s.outcome === "string" ? s.outcome : "",
    link: typeof s.link === "string" ? s.link : "free",
    proficiency: pr && typeof pr.tier === "string"
      ? { tier: pr.tier, n: typeof pr.n === "number" ? pr.n : 0, toNext: typeof pr.to_next === "number" ? pr.to_next : null }
      : null,
    mishap: state ? { state, text: typeof mi!.text === "string" ? mi!.text : null } : null,
    icon: typeof s.icon === "string" ? s.icon : "",
    stamps: Array.isArray(s.stamps) ? s.stamps.map((x) => (x && typeof x === "object" ? String((x as { text?: unknown }).text ?? "") : "")).filter(Boolean) : [],
  };
}

export interface KitchenProbe {
  /** null = the backend does not know this pot */
  status: "cooking" | "served" | "cancelled" | null;
  outcome: KitchenOutcome | null;
  /** The whole pot, when the source has it (lets a card that was only given an id fill itself in) */
  session?: KitchenSession | null;
  /** The server's time zone, when the source knows it ("" = none set) */
  timezone?: string;
  /** The settled card, when the source has one */
  settlement?: KitchenSettlement | null;
}

/** fresh = true skips any cache (used right after the pot is due, when a cached answer may still say "cooking") */
export type ProbeFn = (sessionId: string, fresh?: boolean) => Promise<KitchenProbe>;

const OUTCOMES = new Set(["great", "ok", "burnt", "spoiled"]);

/** Only the four known outcomes count; anything else is null (treated as "ok") */
export function parseOutcome(v: unknown): KitchenOutcome | null {
  return typeof v === "string" && OUTCOMES.has(v) ? (v as KitchenOutcome) : null;
}

export function probeFromSession(s: KitchenSession | null | undefined): KitchenProbe {
  if (!s) return { status: null, outcome: null, session: null };
  const status = s.status === "served" || s.status === "cancelled" || s.status === "cooking" ? s.status : null;
  return { status, outcome: parseOutcome(s.outcome), session: s };
}

/**
 * Why a pot could not be read:
 *   unreachable   no answer at all: the server is not running, the address is wrong, or the device is offline
 *   blocked       the server answered, but the browser did not let this page read it (the page is not on the
 *                 server's list of allowed sites)
 *   unauthorized  the server refused the request: the token is missing or wrong (401 / 403)
 *   not_found     the server has no pot with this id
 *   server        the server answered with another error status
 *   bad_response  the answer was not the expected JSON
 */
export type KitchenErrorKind = "unreachable" | "blocked" | "unauthorized" | "not_found" | "server" | "bad_response";

export class KitchenFetchError extends Error {
  readonly kind: KitchenErrorKind;
  /** HTTP status, when the server answered and the browser let the page see it */
  readonly status: number | null;
  constructor(kind: KitchenErrorKind, status: number | null, message: string) {
    super(message);
    this.name = "KitchenFetchError";
    this.kind = kind;
    this.status = status;
  }
}

const REASON: Record<KitchenErrorKind, string> = {
  unreachable: "the kitchen server cannot be reached",
  blocked: "the browser blocked the request: this page is not on the kitchen server's list of allowed sites",
  unauthorized: "the kitchen server refused the request: the token is missing or wrong",
  not_found: "the kitchen server has no pot with this id",
  server: "the kitchen server answered with an error",
  bad_response: "the kitchen server's answer was not understood",
};

function fail(kind: KitchenErrorKind, status: number | null = null): KitchenFetchError {
  return new KitchenFetchError(kind, status, status === null ? REASON[kind] : `${REASON[kind]} (status ${status})`);
}

/** Any error from reading a pot, as a KitchenFetchError */
export function asKitchenError(e: unknown): KitchenFetchError {
  return e instanceof KitchenFetchError ? e : fail("unreachable");
}

export interface KitchenAnswer {
  session: KitchenSession | null;
  /** The time zone the server keeps its clock times in (an IANA name); "" when it has none set */
  timezone: string;
  settlement: KitchenSettlement | null;
}

/** Turns the body of GET /api/kitchen?session_id= into an answer; anything unexpected reads as "no pot, no time zone" */
export function parseAnswer(body: unknown): KitchenAnswer {
  const b = (body && typeof body === "object" ? body : {}) as { session?: unknown; timezone?: unknown; settlement?: unknown };
  const session = b.session && typeof b.session === "object" ? (b.session as KitchenSession) : null;
  return { session, timezone: typeof b.timezone === "string" ? b.timezone : "", settlement: parseSettlement(b.settlement) };
}

/**
 * Reads one pot. Rejects with a KitchenFetchError that says why (see KitchenErrorKind).
 * A pot the server does not know is not an error here: the answer's `session` is null.
 */
export async function fetchKitchen(base: string, sessionId: string, token?: string | null): Promise<KitchenAnswer> {
  const url = `${base.replace(/\/+$/, "")}/api/kitchen?session_id=${encodeURIComponent(sessionId)}`;
  let r: Response;
  try {
    r = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    // The browser gives no reason. Ask once more in a way that needs no permission from the server (the
    // answer cannot be read, only whether there was one): an answer means the server is up and it was the
    // browser that stopped the first request.
    let reachable = false;
    try {
      await fetch(url, { mode: "no-cors", cache: "no-store" });
      reachable = true;
    } catch {
      reachable = false;
    }
    throw fail(reachable ? "blocked" : "unreachable");
  }
  if (r.status === 401 || r.status === 403) throw fail("unauthorized", r.status);
  if (r.status === 404) throw fail("not_found", r.status);
  if (!r.ok) throw fail("server", r.status);
  try {
    return parseAnswer(await r.json());
  } catch {
    throw fail("bad_response", r.status);
  }
}

export async function fetchSession(base: string, sessionId: string, token?: string | null): Promise<KitchenSession | null> {
  return (await fetchKitchen(base, sessionId, token)).session;
}

export function notFound(): KitchenFetchError {
  return fail("not_found");
}

// A list that mounts the same card over and over would otherwise ask over and over:
// one request per pot per CACHE_MS, shared while it is in flight.
const CACHE_MS = 5000;
const cache = new Map<string, { at: number; p: Promise<KitchenAnswer> }>();

/** A probe that reads from the backend at `base`, with an optional Bearer token (a string, or a function returning the current one) */
export function apiProbe(base: string, token?: string | null | (() => string | null | undefined)): ProbeFn {
  return async (sessionId, fresh = false) => {
    const key = `${base}\n${sessionId}`;
    const now = Date.now();
    let hit = cache.get(key);
    if (fresh || !hit || now - hit.at > CACHE_MS) {
      for (const [k, v] of cache) if (now - v.at > CACHE_MS) cache.delete(k);
      const p = fetchKitchen(base, sessionId, typeof token === "function" ? token() : token);
      hit = { at: now, p };
      cache.set(key, hit);
      p.catch(() => {
        if (cache.get(key)?.p === p) cache.delete(key); // a failure does not stay cached
      });
    }
    const answer = await hit.p;
    return { ...probeFromSession(answer.session), timezone: answer.timezone, settlement: answer.settlement };
  };
}

/** For tests */
export function _resetApiCache(): void {
  cache.clear();
}
