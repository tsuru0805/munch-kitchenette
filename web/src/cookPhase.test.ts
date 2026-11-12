// The event table in cookPhase.ts, row by row.
import {
  ENTER_MS, EXIT_MS, FRESH_S, OUTCOME_WAIT_MS, SERVE_MS, SERVE_SWAP_MS,
  cookProgress, fmtHM, fmtMinutes, fmtRemaining, isFailOutcome, kitchenPhase, kitchenTiming, outcomeWord,
  phaseIsLive, pickTimeZone, revealAtMs, spriteOnStage,
} from "./cookPhase";

const START = 1_800_000_000; // epoch seconds
const DUR = 600;
const startMs = START * 1000;
const dueMs = startMs + DUR * 1000;

describe("kitchenPhase event table", () => {
  test("first mount of a pot that just started: enter -> stir", () => {
    const f = { startedAt: START, durationSec: DUR, mountedAtMs: startMs + 1200, firstSeen: true };
    expect(kitchenPhase(f, f.mountedAtMs)).toBe("enter");
    expect(kitchenPhase(f, f.mountedAtMs + ENTER_MS - 1)).toBe("enter");
    expect(kitchenPhase(f, f.mountedAtMs + ENTER_MS)).toBe("stir");
    expect(kitchenPhase(f, dueMs - 1)).toBe("stir");
  });

  test("the card arrives late (first mounted 90 s after the start): the entrance still plays", () => {
    const f = { startedAt: START, durationSec: DUR, mountedAtMs: startMs + 90_000, firstSeen: true };
    expect(kitchenPhase(f, f.mountedAtMs)).toBe("enter");
    expect(kitchenPhase(f, f.mountedAtMs + ENTER_MS)).toBe("stir");
  });

  test("not due yet, the card scrolls back in and is mounted again (seen): straight to stir, no entrance", () => {
    const f = { startedAt: START, durationSec: DUR, mountedAtMs: startMs + 5_000, firstSeen: false };
    expect(kitchenPhase(f, f.mountedAtMs)).toBe("stir");
    expect(kitchenPhase(f, f.mountedAtMs + 10)).toBe("stir");
  });

  test("the page is reopened on a pot started hours ago (first seen but not fresh): straight to stir", () => {
    const long = { startedAt: START, durationSec: 6 * 3600 };
    const edge = { ...long, mountedAtMs: startMs + FRESH_S * 1000, firstSeen: true };
    expect(kitchenPhase(edge, edge.mountedAtMs)).toBe("enter");
    const old = { ...long, mountedAtMs: startMs + (FRESH_S + 1) * 1000, firstSeen: true };
    expect(kitchenPhase(old, old.mountedAtMs)).toBe("stir");
  });

  test("the pot comes due while the card is mounted: serve -> exit -> done", () => {
    const f = { startedAt: START, durationSec: DUR, mountedAtMs: startMs + 60_000, firstSeen: false, outcomeAtMs: dueMs };
    expect(kitchenPhase(f, dueMs)).toBe("serve");
    expect(kitchenPhase(f, dueMs + SERVE_MS - 1)).toBe("serve");
    expect(kitchenPhase(f, dueMs + SERVE_MS)).toBe("exit");
    expect(kitchenPhase(f, dueMs + SERVE_MS + EXIT_MS - 1)).toBe("exit");
    expect(kitchenPhase(f, dueMs + SERVE_MS + EXIT_MS)).toBe("done");
  });

  test("mounted after the pot was due (a card from history): done, no animation is revived at any time", () => {
    const f = { startedAt: START, durationSec: DUR, mountedAtMs: dueMs, firstSeen: true };
    expect(kitchenPhase(f, dueMs)).toBe("done");
    expect(kitchenPhase(f, dueMs + 1)).toBe("done");
    const late = { ...f, mountedAtMs: dueMs + 86_400_000 };
    expect(kitchenPhase(late, late.mountedAtMs + 5)).toBe("done");
  });

  test("scrolled away during the serve and back (mounted after due): done, nothing is replayed", () => {
    const f = { startedAt: START, durationSec: DUR, mountedAtMs: dueMs + 500, firstSeen: true };
    expect(kitchenPhase(f, dueMs + 600)).toBe("done");
  });

  test("cancelled while on screen: exit -> cancelled", () => {
    const mountedAtMs = startMs + 60_000;
    const seen = mountedAtMs + 30_000;
    const f = { startedAt: START, durationSec: DUR, mountedAtMs, firstSeen: false, cancelledSeenAtMs: seen };
    expect(kitchenPhase(f, seen)).toBe("exit");
    expect(kitchenPhase(f, seen + EXIT_MS - 1)).toBe("exit");
    expect(kitchenPhase(f, seen + EXIT_MS)).toBe("cancelled");
  });

  test("already cancelled at mount: cancelled, no exit animation", () => {
    const mountedAtMs = startMs + 60_000;
    const f = { startedAt: START, durationSec: DUR, mountedAtMs, firstSeen: false, cancelledSeenAtMs: mountedAtMs + 20 };
    expect(kitchenPhase(f, mountedAtMs + 20)).toBe("cancelled");
  });

  test("cancelled wins over due (a cancelled pot is never served)", () => {
    const mountedAtMs = startMs + 60_000;
    const f = { startedAt: START, durationSec: DUR, mountedAtMs, firstSeen: false, cancelledSeenAtMs: mountedAtMs + 5_000 };
    expect(kitchenPhase(f, dueMs + 10)).toBe("cancelled");
  });

  test("bad data does not throw: a NaN time counts as done", () => {
    const f = { startedAt: Number.NaN, durationSec: DUR, mountedAtMs: startMs, firstSeen: true };
    expect(kitchenPhase(f, startMs)).toBe("done");
  });
});

describe("outcome and clip timing", () => {
  const live = { startedAt: START, durationSec: DUR, mountedAtMs: startMs + 60_000, firstSeen: false };

  test("the still last frame comes in at 3150 ms (3000 ms clip + slack); the serve phase lasts 5000 ms", () => {
    expect(kitchenTiming()).toEqual({ playMs: 3000, swapMs: 3150, serveMs: 5000 });
    expect(SERVE_SWAP_MS).toBe(3150);
    expect(SERVE_MS).toBe(5000);
  });

  test("due with no outcome yet: keep cooking; after OUTCOME_WAIT_MS serve as ok", () => {
    expect(kitchenPhase(live, dueMs)).toBe("stir");
    expect(kitchenPhase(live, dueMs + OUTCOME_WAIT_MS - 1)).toBe("stir");
    expect(kitchenPhase(live, dueMs + OUTCOME_WAIT_MS)).toBe("serve");
    expect(revealAtMs(live)).toBe(dueMs + OUTCOME_WAIT_MS);
  });

  test("the reveal = the moment the outcome arrives (clamped between due and due + the wait limit)", () => {
    expect(revealAtMs({ ...live, outcomeAtMs: dueMs + 800 })).toBe(dueMs + 800);
    expect(revealAtMs({ ...live, outcomeAtMs: dueMs - 50 })).toBe(dueMs);
    expect(revealAtMs({ ...live, outcomeAtMs: dueMs + 60_000 })).toBe(dueMs + OUTCOME_WAIT_MS);
    const f = { ...live, outcome: "ok" as const, outcomeAtMs: dueMs + 800 };
    expect(kitchenPhase(f, dueMs + 799)).toBe("stir");
    expect(kitchenPhase(f, dueMs + 800)).toBe("serve");
  });

  test("the serve phase: the cook only leaves after 5000 ms", () => {
    const f = { ...live, outcome: "great" as const, outcomeAtMs: dueMs };
    expect(kitchenPhase(f, dueMs + 4999)).toBe("serve");
    expect(kitchenPhase(f, dueMs + 5000)).toBe("exit");
    expect(kitchenPhase(f, dueMs + 5000 + EXIT_MS)).toBe("done");
  });

  test("burnt / spoiled: still a serve phase (it plays the fail clip)", () => {
    for (const o of ["burnt", "spoiled"] as const) {
      const f = { ...live, outcome: o, outcomeAtMs: dueMs };
      expect(kitchenPhase(f, dueMs + 100)).toBe("serve");
    }
  });

  test("outcome mapping: burnt / spoiled count as failed; words for great / burnt / spoiled, none for ok", () => {
    expect(isFailOutcome("burnt")).toBe(true);
    expect(isFailOutcome("spoiled")).toBe(true);
    expect(isFailOutcome("great")).toBe(false);
    expect(isFailOutcome("ok")).toBe(false);
    expect(isFailOutcome(null)).toBe(false);
    expect(outcomeWord("great")).toBe("很好");
    expect(outcomeWord("burnt")).toBe("糊了");
    expect(outcomeWord("spoiled")).toBe("坏了");
    expect(outcomeWord("ok")).toBeNull();
    expect(outcomeWord(null)).toBeNull();
  });
});

describe("derived checks", () => {
  test("stage and ticker", () => {
    expect((["enter", "stir", "serve", "exit"] as const).every(spriteOnStage)).toBe(true);
    expect(spriteOnStage("done")).toBe(false);
    expect(spriteOnStage("cancelled")).toBe(false);
    expect(phaseIsLive("exit")).toBe(true);
    expect(phaseIsLive("done")).toBe(false);
    expect(phaseIsLive("cancelled")).toBe(false);
  });

  test("time left and progress", () => {
    expect(fmtRemaining(0)).toBe("00:00");
    expect(fmtRemaining(59.2)).toBe("01:00");
    expect(fmtRemaining(600)).toBe("10:00");
    expect(fmtRemaining(3725)).toBe("1:02:05");
    expect(cookProgress(START, DUR, startMs + 150_000)).toEqual({ remainingSec: 450, progress: 0.25 });
    expect(cookProgress(START, DUR, dueMs + 9_999)).toEqual({ remainingSec: 0, progress: 1 });
    expect(cookProgress(START, DUR, startMs - 5_000)).toEqual({ remainingSec: 600, progress: 0 });
    expect(cookProgress(START, 0, startMs)).toEqual({ remainingSec: 0, progress: 1 });
  });

  test("durations in words", () => {
    expect(fmtMinutes(600)).toBe("10 分钟");
    expect(fmtMinutes(3600)).toBe("1 小时");
    expect(fmtMinutes(5400)).toBe("1 小时 30 分");
  });
});

describe("clock times and time zones", () => {
  const t = Date.UTC(2026, 10, 12, 7, 3) / 1000; // 07:03 UTC
  const pad = (n: number) => String(n).padStart(2, "0");
  const onDevice = `${pad(new Date(t * 1000).getHours())}:${pad(new Date(t * 1000).getMinutes())}`;

  test("a time is written in the zone it is given", () => {
    expect(fmtHM(t, "UTC")).toBe("07:03");
    expect(fmtHM(t, "Asia/Tokyo")).toBe("16:03");
    expect(fmtHM(t, "Asia/Shanghai")).toBe("15:03");
    expect(fmtHM(t, "America/New_York")).toBe("02:03");
    expect(fmtHM(Date.UTC(2026, 10, 12, 0, 5) / 1000, "UTC")).toBe("00:05"); // midnight is 00, not 24
  });

  test("no zone, or a name that is not a zone: the device's own time", () => {
    expect(fmtHM(t)).toBe(onDevice);
    expect(fmtHM(t, "Not/AZone")).toBe(onDevice);
  });

  test("which zone is used: the server's, then the card's, then the device's", () => {
    expect(pickTimeZone("Asia/Tokyo", "Europe/Paris")).toBe("Asia/Tokyo");
    expect(pickTimeZone("", "Europe/Paris")).toBe("Europe/Paris");
    expect(pickTimeZone(undefined, " Europe/Paris ")).toBe("Europe/Paris");
    expect(pickTimeZone(undefined, null)).toBeUndefined();
    expect(pickTimeZone("", "")).toBeUndefined();
    expect(pickTimeZone("Not/AZone", "Europe/Paris")).toBe("Europe/Paris"); // a name that is not a zone is skipped
    expect(pickTimeZone("Not/AZone", " ")).toBeUndefined();
  });
});
