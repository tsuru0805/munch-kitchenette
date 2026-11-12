// Where the cook is on the card, as a pure function of facts. The element only renders what this says.
//
// A chat list may unmount a card when it scrolls away and mount it again later, and a page may be
// reloaded mid-pot. So the phase is never remembered: it is recomputed every time from the facts
// (start time, duration, when this card was mounted, whether the pot was cancelled, the outcome).
//
//   situation                                        the cook
//   mounted after the pot was already due            done: finished card, no cook
//   first time this page sees a freshly started pot  enter -> stir
//   mounted again (scrolled back / page reopened)    straight to stir, the entrance is not replayed
//   the pot comes due while the card is mounted      serve (once) -> hold the last frame -> exit -> done
//   cancelled                                        already cancelled at mount = no cook;
//                                                    cancelled while mounted = exit -> cancelled
//   due, outcome not known yet                       keeps cooking (up to OUTCOME_WAIT_MS), then reveals
//   revealed: great / ok                             serve -> hold -> exit
//   revealed: burnt / spoiled                        the "fail" clip -> hold -> exit
//
// Units: nowMs / mountedAtMs are milliseconds; startedAt is epoch seconds (as the backend sends it).

export type KitchenPhase = "enter" | "stir" | "serve" | "exit" | "done" | "cancelled";

/** How the pot turned out. Decided by the backend the moment the pot is served; never changes after. */
export type KitchenOutcome = "great" | "ok" | "burnt" | "spoiled";

/**
 * The entrance is only for a pot that was just started: first seen by this page (see seen.ts) and
 * started no more than FRESH_S ago. A plain time window is not enough on its own, because a card
 * often mounts tens of seconds after the pot started (the message that carries it has to finish
 * first); FRESH_S only stops a reopened page from replaying the entrance for a pot started hours ago.
 */
export const FRESH_S = 300;
/** Entrance slide duration */
export const ENTER_MS = 700;
/** Exit slide duration */
export const EXIT_MS = 450;
/** How long the last frame is held before the cook leaves */
export const HOLD_MS = 2000;
/** Extra wait after a one-shot clip before swapping to its still last frame, so a slow decode never cuts the ending */
export const SWAP_SLACK_MS = 150;
/**
 * How long to wait for the outcome after the pot is due (it has to be read back from the backend;
 * if it never arrives the card serves as "ok"). Meanwhile the cook keeps cooking, so the card never
 * serves a dish and then flips it to burnt.
 */
export const OUTCOME_WAIT_MS = 6000;

export interface KitchenTiming {
  /** Length of the serve / fail clip itself */
  playMs: number;
  /** When to swap to the still last frame (measured from the reveal) */
  swapMs: number;
  /** Whole serve / fail phase = clip + hold */
  serveMs: number;
}

/** Clip timing, one source of truth: every clip is 45 frames at 70/60/70 ms, i.e. 3000 ms. */
export function kitchenTiming(): KitchenTiming {
  const playMs = 3000;
  return { playMs, swapMs: playMs + SWAP_SLACK_MS, serveMs: playMs + HOLD_MS };
}

export const SERVE_PLAY_MS = kitchenTiming().playMs;
export const SERVE_SWAP_MS = kitchenTiming().swapMs;
export const SERVE_MS = kitchenTiming().serveMs;

/** burnt / spoiled = the cook plays the fail clip */
export function isFailOutcome(o: KitchenOutcome | null | undefined): boolean {
  return o === "burnt" || o === "spoiled";
}

/** The word shown for an outcome ("ok" shows nothing) */
export function outcomeWord(o: KitchenOutcome | null | undefined): string | null {
  if (o === "great") return "很好";
  if (o === "burnt") return "糊了";
  if (o === "spoiled") return "坏了";
  return null;
}

export interface KitchenFacts {
  startedAt: number; // epoch seconds
  durationSec: number;
  mountedAtMs: number;
  /** First time this page (this run of it) sees the pot */
  firstSeen: boolean;
  /** When this page observed the pot as cancelled (ms, local clock). Not cancelled = undefined */
  cancelledSeenAtMs?: number;
  /** Outcome (null = the backend did not say; treated as "ok") */
  outcome?: KitchenOutcome | null;
  /** When this page learned the outcome (ms). Unknown yet = undefined (waits up to OUTCOME_WAIT_MS after due) */
  outcomeAtMs?: number;
}

/** The reveal: the moment the outcome is known after the pot is due (never before due, never later than due + OUTCOME_WAIT_MS) */
export function revealAtMs(f: KitchenFacts): number {
  const dueMs = (f.startedAt + Math.max(0, f.durationSec)) * 1000;
  if (f.outcomeAtMs === undefined) return dueMs + OUTCOME_WAIT_MS;
  return Math.min(Math.max(dueMs, f.outcomeAtMs), dueMs + OUTCOME_WAIT_MS);
}

export function kitchenPhase(f: KitchenFacts, nowMs: number): KitchenPhase {
  const startMs = f.startedAt * 1000;
  const dueMs = startMs + Math.max(0, f.durationSec) * 1000;
  if (!Number.isFinite(startMs) || !Number.isFinite(dueMs)) return "done";

  if (f.cancelledSeenAtMs !== undefined) {
    // Already cancelled when the card mounted (a card from history) = no exit animation;
    // cancelled while the card was on screen = play the exit once
    const seenLive = f.cancelledSeenAtMs > f.mountedAtMs + 50;
    if (seenLive && nowMs < f.cancelledSeenAtMs + EXIT_MS) return "exit";
    return "cancelled";
  }

  // Mounted after the pot was due: a card from history, no animation is ever revived
  if (f.mountedAtMs >= dueMs) return "done";

  if (nowMs < dueMs) {
    const fresh = f.firstSeen && f.mountedAtMs - startMs <= FRESH_S * 1000;
    if (fresh && nowMs < f.mountedAtMs + ENTER_MS) return "enter";
    return "stir";
  }
  const reveal = revealAtMs(f);
  if (nowMs < reveal) return "stir"; // due, outcome not here yet: keep cooking
  const t = kitchenTiming();
  if (nowMs < reveal + t.serveMs) return "serve";
  if (nowMs < reveal + t.serveMs + EXIT_MS) return "exit";
  return "done";
}

/** Is the cook on stage in this phase (does the stage take up height) */
export function spriteOnStage(p: KitchenPhase): boolean {
  return p === "enter" || p === "stir" || p === "serve" || p === "exit";
}

/** Does the card still need its ticker (no timers at all after done / cancelled) */
export function phaseIsLive(p: KitchenPhase): boolean {
  return p !== "done" && p !== "cancelled";
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** Time left: mm:ss under an hour, otherwise h:mm:ss */
export function fmtRemaining(sec: number): string {
  const s = Math.max(0, Math.ceil(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  return h > 0 ? `${h}:${pad2(m)}:${pad2(r)}` : `${pad2(m)}:${pad2(r)}`;
}

export interface CookProgress {
  remainingSec: number;
  /** 0..1 */
  progress: number;
}

export function cookProgress(startedAt: number, durationSec: number, nowMs: number): CookProgress {
  const total = Math.max(0, durationSec);
  if (!Number.isFinite(startedAt) || total <= 0) return { remainingSec: 0, progress: 1 };
  const elapsed = Math.max(0, nowMs / 1000 - startedAt);
  return {
    remainingSec: Math.max(0, total - elapsed),
    progress: Math.min(1, elapsed / total),
  };
}

/**
 * Which time zone the clock times on the card are written in: the server's when it says one, else the
 * one set on the card, else none (undefined = the visitor's device). Names that are not real time zones
 * are skipped.
 */
export function pickTimeZone(fromServer: string | null | undefined, fromCard: string | null | undefined): string | undefined {
  for (const tz of [fromServer, fromCard]) {
    if (typeof tz !== "string" || tz.trim() === "") continue;
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: tz.trim() });
      return tz.trim();
    } catch {
      // not a time zone this device knows
    }
  }
  return undefined;
}

/** HH:MM in the given time zone (an IANA name such as "Asia/Tokyo"); without one, in the device's */
export function fmtHM(epochSec: number, timeZone?: string): string {
  const d = new Date(epochSec * 1000);
  if (timeZone) {
    try {
      const parts = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(d);
      const get = (type: string): string => parts.find((p) => p.type === type)?.value ?? "";
      const h = get("hour"), m = get("minute");
      if (h && m) return `${h}:${m}`;
    } catch {
      // unknown zone: fall through to the device's
    }
  }
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** A duration in words, whole minutes */
export function fmtMinutes(durationSec: number): string {
  const m = Math.round(durationSec / 60);
  if (m < 60) return `${m} 分钟`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r === 0 ? `${h} 小时` : `${h} 小时 ${r} 分`;
}
