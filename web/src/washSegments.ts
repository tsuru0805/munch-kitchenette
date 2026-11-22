// The washing card: which clip the cook plays at this moment, and whether he is on stage at all. Pure
// functions of facts (when the washing started, how many plates, how long each, what the backend said and
// when the card first saw it); recomputed on every tick, so a card that is shown again, or a page reloaded,
// lands on the right moment instead of replaying anything.
//
//   Washing      plate i is washed in [start + i × per_s, start + (i+1) × per_s). Each plate's time is cut
//                into seven equal parts, played in turn, each looping its clip: roll up the sleeves -> soap
//                -> scrub -> rinse -> shake the water off -> dry -> stack. The sleeves are rolled up once, at
//                the start of the washing (one clip, then soap); from the second plate on soap takes the
//                first two parts.
//   A plate      whether it broke is only told once its time is up (the backend keeps it "washing" until
//                then). Due, result not read yet: the stacking goes on a moment (RESULT_WAIT_MS) while the
//                card reads again. Broke: the dropped plate, once, then its last frame, BREAK_SHOW_MS from
//                when the card saw it; then the next plate goes on. A break the card learns of long after
//                (BREAK_LATE_MS: a card shown again later) is not played.
//   The end      after the last plate (and its dropped plate, if it broke) the cook sinks below the card
//                (EXIT_MS) and the card shows how it went. Stopped midway (the human took the washing back,
//                or switched plates off): he sinks from the moment the card learns it.
//   On stage     not before the backend's first answer (the washing may already be over or stopped), unless
//                the card cannot read back at all; never on a card that first appears after the washing is
//                over.
import { EXIT_MS } from "./cookPhase";
import { CLIP_MS } from "./cookSegments";

export const WASH_PARTS = ["dish_sleeve", "dish_soap", "dish_scrub", "dish_rinse", "dish_shake", "dish_dry", "dish_stack"] as const;
/** Every clip the washing card can show (the chore registry's dish_* entries) */
export const WASH_SEGMENTS = [...WASH_PARTS, "dish_break", "dish_break_last"] as const;
/** How long the last step of a due plate goes on while the card reads its result */
export const RESULT_WAIT_MS = 4000;
/** The dropped plate: the clip once, then its last frame, this long in all */
export const BREAK_SHOW_MS = 5000;
/** A break the card first saw this long after the plate was due is not played (it is history by then) */
export const BREAK_LATE_MS = 20_000;

/** The facts fixed when the washing started (the card attachment) */
export interface WashFacts {
  jobId: string;
  /** epoch seconds */
  startedAt: number;
  perS: number;
  n: number;
}

export interface WashPlate {
  /** 0-based, in washing order */
  i: number;
  /** washing / clean / broken / machine */
  state: string;
  doneAt: number | null;
}

/** One washing as the backend tells it (GET /api/dishes/jobs/<id>) */
export interface WashRead {
  /** server time of the answer, epoch seconds */
  now: number;
  /** running / done / stopped */
  state: string;
  startedAt: number;
  perS: number;
  n: number;
  endedAt: number | null;
  counts: { washing: number; clean: number; broken: number; machine: number };
  dishes: WashPlate[];
  timezone: string;
}

export interface WashMoment {
  nowMs: number;
  facts: WashFacts;
  /** The latest answer (null = none yet, or the card cannot read back) */
  read: WashRead | null;
  /** When this card first saw each plate's result (device ms) */
  seenAtMs: Record<number, number>;
  /** When this card first saw the washing done or stopped (device ms) */
  endSeenAtMs?: number;
  /** The card cannot read back (no backend given, or reading failed): play by time only, wait for nothing */
  unavailable: boolean;
  /** When this card was put on the page (device ms) */
  mountedAtMs: number;
}

export type WashPhase = "wait" | "wash" | "exit" | "done";

export interface WashFrame {
  /** wait = on screen, the backend not answered yet; wash = he is at the sink; exit = sinking; done = gone */
  phase: WashPhase;
  /** The clip on stage (null = nobody) */
  segment: string | null;
  /** Changes whenever the clip should start again from its first frame */
  run: string;
  /** The plate being washed (0-based); n once it is over */
  index: number;
  /** The washing is over (by time, or the backend said it stopped) */
  finished: boolean;
  /** Stopped before every plate was washed */
  stopped: boolean;
  /** While the dropped plate plays mid-washing: which plate (0-based) broke */
  broke?: number;
}

export function isFinal(read: WashRead | null): boolean {
  return !!read && (read.state === "done" || read.state === "stopped");
}

/** When the washing is over: by time, or when the backend says it stopped */
export function washEndMs(facts: WashFacts, read: WashRead | null): number {
  const byTime = (facts.startedAt + Math.max(0, facts.n) * facts.perS) * 1000;
  if (isFinal(read) && read!.endedAt !== null) return Math.min(byTime, read!.endedAt * 1000);
  return byTime;
}

/** When plate i is due (device ms, from the server's start time) */
export function dueMs(facts: WashFacts, i: number): number {
  return (facts.startedAt + (i + 1) * facts.perS) * 1000;
}

/**
 * Plate i's result: "broken", "clean", "machine", or undefined while it is not known. A plate the backend
 * still calls "washing" in an answer given after it was due did not break (the backend settles on reading).
 */
export function resultOf(m: Pick<WashMoment, "facts" | "read">, i: number): string | undefined {
  const r = m.read;
  if (!r) return undefined;
  const d = r.dishes.find((x) => x.i === i);
  if (d && d.state !== "washing") return d.state;
  return r.now * 1000 >= dueMs(m.facts, i) ? "clean" : undefined;
}

/** The dropped plate's window for plate i, when it broke and the card saw it in time; null otherwise */
export function breakWindow(m: WashMoment, i: number): { from: number; to: number } | null {
  if (resultOf(m, i) !== "broken") return null;
  const due = dueMs(m.facts, i);
  const seen = m.seenAtMs[i] ?? m.nowMs;
  if (seen - due > BREAK_LATE_MS) return null;
  const from = Math.max(due, seen);
  return { from, to: from + BREAK_SHOW_MS };
}

/** The clip by time alone, while plate `idx` is being washed (t = device ms) */
function partAt(m: WashMoment, t: number): { segment: string; run: string; index: number } {
  const { facts } = m;
  const id = facts.jobId;
  const dishMs = facts.perS * 1000;
  const el = Math.max(0, t - facts.startedAt * 1000);
  const idx = Math.min(facts.n - 1, Math.floor(el / dishMs));
  const within = el - idx * dishMs;
  const part = Math.min(WASH_PARTS.length - 1, Math.floor((within / dishMs) * WASH_PARTS.length));
  if (part === 0 && idx === 0 && within < CLIP_MS) return { segment: "dish_sleeve", run: `${id}:0:0`, index: 0 };
  // the sleeves stay rolled up: soap takes the first two parts (one run across both)
  if (part === 0) return { segment: "dish_soap", run: `${id}:${idx}:1`, index: idx };
  return { segment: WASH_PARTS[part], run: `${id}:${idx}:${part}`, index: idx };
}

function breakClip(m: WashMoment, i: number, w: { from: number; to: number }): { segment: string; run: string } {
  return { segment: m.nowMs - w.from < CLIP_MS ? "dish_break" : "dish_break_last", run: `${m.facts.jobId}:${i}:break` };
}

export function washFrame(m: WashMoment): WashFrame {
  const { facts, read, nowMs } = m;
  const id = facts.jobId;
  const n = Math.max(0, Math.floor(facts.n));
  const off = (phase: WashPhase, finished: boolean, index: number, stopped = false): WashFrame =>
    ({ phase, segment: null, run: "", index, finished, stopped });
  if (n <= 0 || !(facts.perS > 0)) return off("done", true, 0);
  const startMs = facts.startedAt * 1000;
  const dishMs = facts.perS * 1000;
  const byTimeEnd = startMs + n * dishMs;
  const endMs = washEndMs(facts, read);
  const stopped = isFinal(read) && read!.state === "stopped" && endMs < byTimeEnd;
  const finished = nowMs >= endMs;
  const index = finished ? n : Math.max(0, Math.min(n - 1, Math.floor((nowMs - startMs) / dishMs)));
  // A card first shown after it was over: no cook at all
  if (m.mountedAtMs >= byTimeEnd || (isFinal(read) && m.mountedAtMs >= endMs)) return off("done", finished, index, stopped);
  // Nothing on stage until the backend has answered once (unless there is no backend to answer)
  if (!read && !m.unavailable) return off("wait", finished, index, stopped);

  // ── over: the last plate's result, then sinking below the card ──
  if (finished) {
    let leaveAt: number;
    let last: { segment: string; run: string };
    if (stopped) {
      leaveAt = Math.max(endMs, m.endSeenAtMs ?? nowMs);
      const due = Math.min(n, Math.floor((endMs - startMs) / dishMs)) - 1; // the last plate washed before the stop
      const w = due >= 0 ? breakWindow(m, due) : null;
      if (w && w.to > leaveAt) {
        // the plate washed just before the stop broke: the dropped plate first
        if (nowMs < w.to) return { phase: "wash", ...breakClip(m, due, w), index, finished, stopped };
        leaveAt = w.to;
        last = { segment: "dish_break_last", run: `${id}:${due}:break` };
      } else {
        const at = partAt(m, Math.min(leaveAt, byTimeEnd) - 1);
        last = { segment: at.segment, run: at.run };
      }
    } else {
      const lastIdx = n - 1;
      const result = resultOf(m, lastIdx);
      const waitUntil = endMs + RESULT_WAIT_MS;
      if (result === undefined && !m.unavailable && nowMs < waitUntil) {
        // still reading the last plate's result: the stacking goes on
        return { phase: "wash", segment: "dish_stack", run: `${id}:${lastIdx}:${WASH_PARTS.length - 1}`, index, finished, stopped };
      }
      const seen = m.seenAtMs[lastIdx];
      // the last plate broke, and the card learnt it while he was still at the sink
      const w = seen === undefined || seen <= waitUntil ? breakWindow(m, lastIdx) : null;
      if (w) {
        if (nowMs < w.to) return { phase: "wash", ...breakClip(m, lastIdx, w), index, finished, stopped };
        leaveAt = w.to;
        last = { segment: "dish_break_last", run: `${id}:${lastIdx}:break` };
      } else {
        leaveAt = result === undefined && !m.unavailable ? waitUntil : Math.max(endMs, seen !== undefined && seen <= waitUntil ? seen : endMs);
        last = { segment: "dish_stack", run: `${id}:${lastIdx}:${WASH_PARTS.length - 1}` };
      }
    }
    if (m.mountedAtMs >= leaveAt) return off("done", finished, index, stopped);
    if (nowMs < leaveAt + EXIT_MS) return { phase: "exit", ...last, index, finished, stopped };
    return off("done", finished, index, stopped);
  }

  // ── washing ──
  if (nowMs < startMs) return { phase: "wash", segment: "dish_sleeve", run: `${id}:0:0`, index: 0, finished, stopped };
  const at = partAt(m, nowMs);
  // a plate washed a moment ago that broke: the dropped plate (the latest such plate)
  for (let i = at.index - 1; i >= Math.max(0, at.index - 10); i--) {
    const w = breakWindow(m, i);
    if (w && nowMs >= w.from && nowMs < w.to) return { phase: "wash", ...breakClip(m, i, w), index: i, finished, stopped, broke: i };
  }
  // the plate just due, its result not read yet: its stacking goes on a moment
  const prev = at.index - 1;
  if (prev >= 0 && !m.unavailable && resultOf(m, prev) === undefined && nowMs - dueMs(facts, prev) < RESULT_WAIT_MS) {
    return { phase: "wash", segment: "dish_stack", run: `${id}:${prev}:${WASH_PARTS.length - 1}`, index: prev, finished, stopped };
  }
  return { phase: "wash", segment: at.segment, run: at.run, index, finished, stopped };
}

/** When the card should read the washing again (device ms; null = nothing more to learn by reading) */
export function nextReadAtMs(m: Pick<WashMoment, "facts" | "read" | "nowMs">, lastReadMs: number, pollMs: number, lagMs: number): number | null {
  if (isFinal(m.read)) return null;
  const { facts } = m;
  const byTimeEnd = (facts.startedAt + Math.max(0, facts.n) * facts.perS) * 1000;
  // long past the end and still not told it is over: stop asking (the page coming back asks again)
  if (m.nowMs > byTimeEnd + 2 * pollMs) return null;
  const startMs = facts.startedAt * 1000;
  const dishMs = facts.perS * 1000;
  // the next plate due (a plate due less than `lagMs` ago still counts: its read is still to come)
  const next = startMs + (Math.floor(Math.max(0, m.nowMs - startMs - lagMs) / dishMs) + 1) * dishMs;
  const due = Math.min(next, byTimeEnd) + lagMs;
  const candidates = [lastReadMs + pollMs];
  if (due > m.nowMs) candidates.push(due);
  return Math.max(m.nowMs, Math.min(...candidates));
}

/** "Reduce motion" / a hidden page: what stands still in place of a clip */
export function washStill(segment: string): string {
  if (segment.endsWith("_last")) return segment;
  return segment === "dish_break" ? "dish_break_last" : "base";
}

// ── the server's clock ──────────────────────────────────────────────────
// The device's clock may be minutes off. Every time below that the rules compare with the washing's start
// (the plates' due times, "shown after it was over", when to stop asking) is the server's: the card keeps
// the offset between the two from each answer (the answer's `now` against the device clock when it came
// back) and adds it. Until the first answer the offset is 0: the attachment's start time and the device's
// clock, as well as can be done; the first answer puts it right.

/** What a card holds, in device milliseconds, plus the offset to the server's clock */
export interface WashCardState {
  facts: WashFacts;
  read: WashRead | null;
  /** server time minus device time (ms); 0 until the first answer */
  offsetMs: number;
  /** when the card first saw each plate's result / the end (device ms) */
  seenAtDeviceMs: Record<number, number>;
  endSeenAtDeviceMs?: number;
  unavailable: boolean;
  mountedAtDeviceMs: number;
}

/** The offset an answer gives: its server time against the device clock the moment it came back */
export function offsetFrom(read: WashRead, deviceAtResponseMs: number): number {
  return read.now > 0 ? read.now * 1000 - deviceAtResponseMs : 0;
}

/** The moment the rules see, every time on the server's clock */
export function momentAt(s: WashCardState, deviceNowMs: number): WashMoment {
  const off = s.offsetMs;
  const seen: Record<number, number> = {};
  for (const [k, v] of Object.entries(s.seenAtDeviceMs)) seen[Number(k)] = v + off;
  return {
    nowMs: deviceNowMs + off, facts: s.facts, read: s.read, seenAtMs: seen,
    endSeenAtMs: s.endSeenAtDeviceMs === undefined ? undefined : s.endSeenAtDeviceMs + off,
    unavailable: s.unavailable, mountedAtMs: s.mountedAtDeviceMs + off,
  };
}

/** When to read again, on the device's clock (the rule itself works on the server's); null = no more */
export function nextReadAtDevice(s: WashCardState, deviceNowMs: number, lastReadDeviceMs: number, pollMs: number, lagMs: number): number | null {
  const off = s.offsetMs;
  const at = nextReadAtMs({ facts: s.facts, read: s.read, nowMs: deviceNowMs + off }, lastReadDeviceMs + off, pollMs, lagMs);
  return at === null ? null : at - off;
}
