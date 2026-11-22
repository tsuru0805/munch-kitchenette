// The washing card's rules: which clip plays when, the dropped plate, the end, and a card that cannot read back.
import { EXIT_MS } from "./cookPhase";
import { CLIP_MS } from "./cookSegments";
import {
  BREAK_LATE_MS, BREAK_SHOW_MS, RESULT_WAIT_MS, WASH_PARTS, momentAt, nextReadAtDevice, nextReadAtMs, offsetFrom, washFrame, washStill,
  type WashCardState, type WashFacts, type WashMoment, type WashRead,
} from "./washSegments";
import { washFace } from "./washFace";
import { washStringsFor } from "./washStrings";

// three plates, 70 s each (10 s a part), started at t = 1000 s
const S = 1000;
const facts: WashFacts = { jobId: "job1", startedAt: S, perS: 70, n: 3 };
const ms = (s: number) => s * 1000;

/** What the backend would answer at server time `at`, with these plates broken (a plate's result only once due) */
function readAt(at: number, broken: number[] = [], over: Partial<WashRead> = {}): WashRead {
  const dishes = [0, 1, 2].map((i) => {
    const due = S + (i + 1) * 70;
    return { i, state: due <= at ? (broken.includes(i) ? "broken" : "clean") : "washing", doneAt: due <= at ? due : null };
  });
  const c = { washing: 0, clean: 0, broken: 0, machine: 0 } as Record<string, number>;
  for (const d of dishes) c[d.state]++;
  const done = at >= S + 210;
  return {
    now: at, state: done ? "done" : "running", startedAt: S, perS: 70, n: 3, endedAt: done ? S + 210 : null,
    counts: c as WashRead["counts"], dishes, timezone: "", ...over,
  };
}

function moment(nowS: number, over: Partial<WashMoment> = {}): WashMoment {
  return { nowMs: ms(nowS), facts, read: readAt(S), seenAtMs: {}, unavailable: false, mountedAtMs: ms(S), ...over };
}
const seg = (nowS: number, over: Partial<WashMoment> = {}) => washFrame(moment(nowS, over)).segment;

describe("plate by plate", () => {
  test("each plate's time in seven parts in order; the sleeves once at the start, then soap", () => {
    // read just after each moment: every plate due so far is known clean
    const at = (s: number) => seg(s, { read: readAt(s) });
    expect(at(S + 1)).toBe("dish_sleeve");
    expect(at(S + CLIP_MS / 1000 + 1)).toBe("dish_soap"); // after one clip of sleeves, soap for the rest of the part
    expect([10, 20, 30, 40, 50, 60].map((p) => at(S + p + 1))).toEqual(WASH_PARTS.slice(1));
    // the second plate: soap takes the first two parts, as one run
    expect([0, 10, 20, 30, 40, 50, 60].map((p) => at(S + 70 + p + 1))).toEqual(
      ["dish_soap", "dish_soap", "dish_scrub", "dish_rinse", "dish_shake", "dish_dry", "dish_stack"]);
    const f = (s: number) => washFrame(moment(s, { read: readAt(s) }));
    expect(f(S + 71).run).toBe(f(S + 81).run);
    expect(f(S + 71).run).not.toBe(f(S + 61).run);
    expect(f(S + 71).index).toBe(1);
    expect(f(S + 71).phase).toBe("wash");
  });

  test("nothing on stage until the backend has answered once", () => {
    const f = washFrame(moment(S + 5, { read: null }));
    expect([f.phase, f.segment, f.finished]).toEqual(["wait", null, false]);
  });

  test("a plate just due whose result is not read yet: its stacking goes on a moment, then the next plate", () => {
    const old = readAt(S + 60); // read before plate 0 was due
    expect(seg(S + 70.5, { read: old })).toBe("dish_stack");
    expect(washFrame(moment(S + 70.5, { read: old })).run).toBe(washFrame(moment(S + 69, { read: old })).run); // no restart
    expect(seg(S + 70 + RESULT_WAIT_MS / 1000, { read: old })).toBe("dish_soap"); // nothing came: go on
    expect(seg(S + 70.5, { read: readAt(S + 70.2) })).toBe("dish_soap"); // read after it was due: it did not break
  });
});

describe("a broken plate", () => {
  test("told once its time is up: the dropped plate once, its last frame, then the next plate", () => {
    const seen = { 1: ms(S + 141) }; // plate 1 (due at S+140) read as broken at S+141
    const read = readAt(S + 141, [1]);
    expect(seg(S + 139, { read: readAt(S + 139, [1]) })).toBe("dish_stack"); // not told before its time
    expect(seg(S + 141, { read, seenAtMs: seen })).toBe("dish_break");
    expect(seg(S + 141 + CLIP_MS / 1000 + 0.1, { read, seenAtMs: seen })).toBe("dish_break_last");
    expect(seg(S + 141 + BREAK_SHOW_MS / 1000, { read, seenAtMs: seen })).toBe("dish_soap");
    expect(washFrame(moment(S + 142, { read, seenAtMs: seen })).run).toBe("job1:1:break");
    // while it drops, the card names the plate that broke (not the next one)
    const f = washFrame(moment(S + 142, { read, seenAtMs: seen }));
    expect([f.index, f.broke]).toEqual([1, 1]);
    expect(washFace(f, facts, read, ms(S + 142), washStringsFor("zh")).word).toBe("第 2 / 3 只 · 碎了");
    expect(washFrame(moment(S + 141 + BREAK_SHOW_MS / 1000, { read, seenAtMs: seen })).broke).toBeUndefined();
  });

  test("a break the card only learns of long after (shown again later) is not played", () => {
    const late = { 0: ms(S + 70) + BREAK_LATE_MS + 1000 };
    expect(seg(S + 70 + BREAK_LATE_MS / 1000 + 1.5, { read: readAt(S + 100, [0]), seenAtMs: late })).toBe("dish_scrub"); // plate 1 goes on
  });

  test("the last plate broke: dropped after the washing is over, then he sinks below the card", () => {
    const end = S + 210;
    const seen = { 2: ms(end + 1) };
    const read = readAt(end + 1, [2]);
    expect(seg(end + 0.5, { read: readAt(end - 1) })).toBe("dish_stack"); // its result not read yet
    expect(washFrame(moment(end + 0.5, { read: readAt(end - 1) })).finished).toBe(true);
    expect(seg(end + 1.5, { read, seenAtMs: seen })).toBe("dish_break");
    expect(seg(end + 1 + 4, { read, seenAtMs: seen })).toBe("dish_break_last");
    const leave = end + 1 + BREAK_SHOW_MS / 1000;
    const exit = washFrame(moment(leave + 0.1, { read, seenAtMs: seen, endSeenAtMs: ms(end + 1) }));
    expect([exit.phase, exit.segment]).toEqual(["exit", "dish_break_last"]);
    expect(washFrame(moment(leave + EXIT_MS / 1000 + 0.1, { read, seenAtMs: seen })).phase).toBe("done");
  });
});

describe("the end", () => {
  test("every plate clean: he stacks the last one, then sinks; the card says how it went", () => {
    const end = S + 210;
    const read = readAt(end + 1);
    const seen = { 0: ms(S + 71), 1: ms(S + 141), 2: ms(end + 1) };
    expect(washFrame(moment(end + 1.2, { read, seenAtMs: seen })).phase).toBe("exit");
    const done = washFrame(moment(end + 1 + EXIT_MS / 1000 + 0.1, { read, seenAtMs: seen }));
    expect([done.phase, done.segment, done.finished, done.index]).toEqual(["done", null, true, 3]);
    const face = washFace(done, facts, read, ms(end + 2), washStringsFor("zh"), "UTC");
    expect([face.clock, face.word, face.result, face.progress]).toEqual([null, "刷完了", "刷了 3 只 · 一只都没碎", null]);
    expect(face.foot).toBe("00:16 开刷 · 3 只 · 00:20 刷完");
  });

  test("one broke: the card counts it", () => {
    const read = readAt(S + 300, [1]);
    const f = washFrame(moment(S + 300, { read }));
    expect(washFace(f, facts, read, ms(S + 300), washStringsFor("zh")).result).toBe("刷了 3 只 · 碎了 1 只");
    expect(washFace(f, facts, read, ms(S + 300), washStringsFor("en")).result).toBe("washed 3 · 1 broke");
  });

  test("stopped midway: he sinks from when the card learns it; what was washed and what went into the dishwasher", () => {
    // stopped at S+100: plate 0 washed, plates 1 and 2 into the dishwasher; the card reads it at S+110
    const read: WashRead = {
      ...readAt(S + 110), state: "stopped", endedAt: S + 100, counts: { washing: 0, clean: 1, broken: 0, machine: 2 },
      dishes: [{ i: 0, state: "clean", doneAt: S + 70 }, { i: 1, state: "machine", doneAt: S + 100 }, { i: 2, state: "machine", doneAt: S + 100 }],
    };
    expect(seg(S + 109, { read: readAt(S + 90) })).toBe("dish_rinse"); // before it learns: still washing by time
    const f = washFrame(moment(S + 110.1, { read, endSeenAtMs: ms(S + 110) }));
    expect([f.phase, f.finished, f.stopped]).toEqual(["exit", true, true]);
    expect(f.segment).toBe("dish_rinse"); // what he was doing when the card learnt it
    expect(washFrame(moment(S + 111, { read, endSeenAtMs: ms(S + 110) })).phase).toBe("done");
    const face = washFace(f, facts, read, ms(S + 111), washStringsFor("zh"), "UTC");
    expect([face.word, face.result]).toEqual(["停下了", "刷了 1 只 · 2 只进了洗碗机"]);
    expect(face.foot).toBe("00:16 开刷 · 3 只 · 00:18 停下");
  });

  test("a card first shown after the washing is over: no cook at all, only how it went", () => {
    const read = readAt(S + 900, [0]);
    for (const read_ of [null, read]) {
      const f = washFrame(moment(S + 900, { read: read_, mountedAtMs: ms(S + 900) }));
      expect([f.phase, f.segment, f.finished]).toEqual(["done", null, true]);
    }
  });
});

describe("reading back fails", () => {
  test("no answer at all: the card plays by time, waits for nothing, and says only that it is done", () => {
    const m = (s: number) => moment(s, { read: null, unavailable: true });
    expect(washFrame(m(S + 1)).segment).toBe("dish_sleeve"); // on stage without an answer
    expect(washFrame(m(S + 70.5)).segment).toBe("dish_soap"); // no waiting for a result that cannot come
    expect(washFrame(m(S + 210.1)).phase).toBe("exit"); // leaves right at the end
    const done = washFrame(m(S + 211));
    expect(done.phase).toBe("done");
    const face = washFace(done, facts, null, ms(S + 211), washStringsFor("zh"), "UTC");
    expect([face.word, face.result]).toEqual(["刷完了", ""]); // how it went is not known: not guessed
  });

  test("answered once, then the reads fail: the last answer stands; the last plate is waited for, then he leaves", () => {
    const stale = readAt(S + 150);
    expect(seg(S + 210.5, { read: stale })).toBe("dish_stack");
    const f = washFrame(moment(S + 210 + RESULT_WAIT_MS / 1000 + 0.1, { read: stale }));
    expect([f.phase, f.segment]).toEqual(["exit", "dish_stack"]);
    expect(washFace(f, facts, stale, ms(S + 215), washStringsFor("zh")).result).toBe(""); // not over by the backend's word
  });
});

describe("while washing, the card says", () => {
  test("time left, which plate, progress", () => {
    const f = washFrame(moment(S + 80, { read: readAt(S + 80) }));
    const face = washFace(f, facts, readAt(S + 80), ms(S + 80), washStringsFor("zh"), "UTC");
    expect([face.clock, face.word]).toEqual(["02:10", "第 2 / 3 只"]);
    expect(face.progress).toBeCloseTo(80 / 210);
    expect(face.foot).toBe("00:16 开刷 · 3 只 · 约 4 分钟 · 00:20 刷完");
  });
});

test("when to read again: right after the next plate is due, at most every poll", () => {
  const m = (s: number, read: WashRead | null = readAt(S)) => ({ facts, read, nowMs: ms(s) });
  expect(nextReadAtMs(m(S + 1), ms(S + 1), 15_000, 1200)).toBe(ms(S + 16)); // the poll comes first
  expect(nextReadAtMs(m(S + 60), ms(S + 60), 15_000, 1200)).toBe(ms(S + 71.2)); // plate 0 due at S+70
  expect(nextReadAtMs(m(S + 70.5), ms(S + 60), 15_000, 1200)).toBe(ms(S + 71.2)); // just due, not read yet
  expect(nextReadAtMs(m(S + 205), ms(S + 205), 15_000, 1200)).toBe(ms(S + 211.2)); // the end
  expect(nextReadAtMs(m(S + 300, readAt(S + 300)), ms(S + 300), 15_000, 1200)).toBeNull(); // over: nothing to learn
  expect(nextReadAtMs(m(S + 300, null), ms(S + 290), 15_000, 1200)).toBeNull(); // long past the end: stop asking
});

test("reduce motion: the dropped plate's last frame, otherwise the standing pose", () => {
  expect(washStill("dish_break")).toBe("dish_break_last");
  expect(washStill("dish_break_last")).toBe("dish_break_last");
  expect(washStill("dish_scrub")).toBe("base");
});

describe("the server's clock, not the device's", () => {
  const FIVE_MIN = 5 * 60_000;
  // the server is at S+95 (plate 2 of 3, scrubbing); the device clock is `skew` ms off
  const serverAt = S + 95;
  function card(skew: number, answered: boolean): { st: WashCardState; dev: number } {
    const dev = ms(serverAt) + skew;
    const read = answered ? readAt(serverAt) : null;
    return {
      dev,
      st: {
        facts, read, offsetMs: read ? offsetFrom(read, dev) : 0, seenAtDeviceMs: answered ? { 0: dev } : {},
        unavailable: false, mountedAtDeviceMs: ms(S + 5) + skew,
      },
    };
  }

  for (const [name, skew] of [["5 minutes fast", FIVE_MIN], ["5 minutes slow", -FIVE_MIN]] as const) {
    test(`a device ${name}: once answered, the card is where the server is`, () => {
      const { st, dev } = card(skew, true);
      expect(st.offsetMs).toBe(-skew);
      const right = washFrame(momentAt(card(0, true).st, ms(serverAt)));
      const f = washFrame(momentAt(st, dev));
      expect([f.phase, f.segment, f.index, f.finished]).toEqual([right.phase, right.segment, right.index, right.finished]);
      expect([f.phase, f.segment, f.index]).toEqual(["wash", "dish_scrub", 1]);
      const face = washFace(f, facts, st.read, momentAt(st, dev).nowMs, washStringsFor("zh"));
      expect([face.clock, face.word]).toEqual(["01:55", "第 2 / 3 只"]);
      // and it keeps asking: every poll, and just after plate 2 is due (S+140), on the device's clock
      expect(nextReadAtDevice(st, dev, dev, 15_000, 1200)).toBe(dev + 15_000);
      expect(nextReadAtDevice(st, dev + 40_000, dev + 40_000, 15_000, 1200)).toBe(ms(S + 141.2) + skew);
    });
  }

  test("uncalibrated, a device 5 minutes fast would call it over and stop asking: why the offset is there", () => {
    const { st, dev } = card(FIVE_MIN, true);
    const wrong = washFrame(momentAt({ ...st, offsetMs: 0 }, dev));
    expect(wrong.finished).toBe(true);
    expect(nextReadAtDevice({ ...st, offsetMs: 0, read: readAt(S) }, dev, dev, 15_000, 1200)).toBeNull();
    expect(washFrame(momentAt(st, dev)).finished).toBe(false);
  });

  test("before the first answer: the attachment's start and the device's clock; the answer puts it right", () => {
    const { st, dev } = card(FIVE_MIN, false);
    const before = washFrame(momentAt(st, dev));
    expect([before.phase, before.finished]).toEqual(["done", true]); // the device thinks it is long over
    expect(nextReadAtDevice(st, dev, -Infinity, 15_000, 1200)).toBeNull(); // (the card reads once at mount regardless)
    const read = readAt(serverAt);
    const after = washFrame(momentAt({ ...st, read, offsetMs: offsetFrom(read, dev), seenAtDeviceMs: { 0: dev } }, dev));
    expect([after.phase, after.segment, after.finished]).toEqual(["wash", "dish_scrub", false]);
  });
});
