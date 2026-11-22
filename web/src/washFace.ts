// What the washing card says at a moment, as a pure function. The element only draws it.
//
//   while washing   the time left (big), which plate of how many, a progress line, and when it started /
//                   how long / when it will be done
//   once over       刷完了 or 停下了; under the title how it went (washed / broke / into the dishwasher),
//                   only once the backend has said so (never guessed); when it started and ended
import { fmtHM, fmtRemaining } from "./cookPhase";
import { isFinal, type WashFacts, type WashFrame, type WashRead } from "./washSegments";
import type { WashCardStrings } from "./washStrings";

export interface WashFace {
  /** Time left, while washing (null once over) */
  clock: string | null;
  /** The word on the right: which plate, or done / stopped */
  word: string;
  /** The line under the title (empty = none) */
  result: string;
  /** 0..1 while washing; null once over */
  progress: number | null;
  foot: string;
  aria: string;
}

export function washFace(
  frame: WashFrame, facts: WashFacts, read: WashRead | null, nowMs: number, t: WashCardStrings, tz?: string,
): WashFace {
  const n = Math.max(0, Math.floor(facts.n));
  const total = n * facts.perS;
  const start = fmtHM(facts.startedAt, tz);
  if (!frame.finished) {
    const el = Math.max(0, nowMs / 1000 - facts.startedAt);
    const remaining = fmtRemaining(Math.max(0, total - el));
    return {
      clock: remaining,
      word: frame.broke !== undefined ? t.plateBroke(frame.broke, n) : t.plateOf(frame.index, n),
      result: "",
      progress: total > 0 ? Math.min(1, el / total) : 1,
      foot: t.footWashing(start, n, t.minutes(total), fmtHM(facts.startedAt + total, tz)),
      aria: t.ariaWashing(frame.index, n, remaining),
    };
  }
  const word = frame.stopped ? t.stopped : t.done;
  const result = isFinal(read) ? t.result(read!.counts, frame.stopped) : "";
  const endSec = isFinal(read) && read!.endedAt !== null ? Math.min(read!.endedAt, facts.startedAt + total) : facts.startedAt + total;
  const end = fmtHM(endSec, tz);
  return {
    clock: null,
    word,
    result,
    progress: null,
    foot: frame.stopped ? t.footStopped(start, n, end) : t.footDone(start, n, end),
    aria: t.ariaDone(word, result),
  };
}
