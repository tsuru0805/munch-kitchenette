// Segment selection at its edges: progress through the cooking time (wash / chop / main + small actions /
// taste), the outcome (serve / fail / cancelled), quick dishes, landing on the right segment when mounted
// again, small actions being stable for a given moment, and every segment existing for both outfits.
import {
  CHOP_MAX_S, CLIP_MS, COOK_METHODS, IDLE_AT_S, SLOT_S, TASTE_MAX_S, assetKey, cookSegment, hashStr, outfitFor,
  parseMethod, type CookSegmentInput,
} from "./cookSegments";
import { CLAWD_MANIFEST } from "./manifest.generated";

const T0 = 1_800_000_000; // pot started (seconds)
const base = (o: Partial<CookSegmentInput> & { atS: number }): CookSegmentInput => ({
  phase: "stir", nowMs: (T0 + o.atS) * 1000, startedAt: T0, durationSec: 1200, mountedAtMs: (T0 + 1) * 1000, firstSeen: false,
  sinceRevealMs: -1, outcome: null, method: "boil", sessionId: "pot-1", ...o,
});

describe("method and outfit", () => {
  test("a method from the backend is used as is; missing or unknown = stir-fry", () => {
    expect(COOK_METHODS.map((m) => parseMethod(m))).toEqual([...COOK_METHODS]);
    expect([parseMethod(undefined), parseMethod("微波"), parseMethod(3), parseMethod("炒")]).toEqual(["stirfry", "stirfry", "stirfry", "stirfry"]);
  });
  test("the outfit comes from the pot id: one pot never changes, both outfits turn up", () => {
    expect(outfitFor("pot-1")).toBe(outfitFor("pot-1"));
    const seen = new Set(Array.from({ length: 40 }, (_, n) => outfitFor(`pot-${n}`)));
    expect([...seen].sort()).toEqual(["scarf", "toque"]);
  });
});

describe("progress through the cooking time", () => {
  test("a pot just started and seen for the first time: wash for 3 s, then chop", () => {
    const fresh = { firstSeen: true, mountedAtMs: (T0 + 2) * 1000 };
    expect(cookSegment(base({ atS: 2.5, phase: "enter", ...fresh }))).toBe("wash");
    expect(cookSegment(base({ atS: 4.9, ...fresh }))).toBe("wash");
    expect(cookSegment(base({ atS: 2 + CLIP_MS / 1000 + 0.1, ...fresh }))).toBe("chop");
  });
  test("mounted again or reopened (not first seen), or first seen long after the start: no wash, straight to the right segment", () => {
    expect(cookSegment(base({ atS: 2.5, firstSeen: false, mountedAtMs: (T0 + 2) * 1000 }))).toBe("chop");
    expect(cookSegment(base({ atS: 601, firstSeen: true, mountedAtMs: (T0 + 600) * 1000 }))).toMatch(/^boil_/);
  });
  test("chop = first 20%, at most 5 minutes; taste = last 10%, at most 2 minutes", () => {
    expect(cookSegment(base({ atS: 239 }))).toBe("chop");                    // a 20 minute dish: 4 minutes of chopping
    expect(cookSegment(base({ atS: 241 }))).not.toBe("chop");
    expect(cookSegment(base({ atS: 1079 }))).not.toBe("boil_taste");         // tasting only in the last 2 minutes
    expect(cookSegment(base({ atS: 1081 }))).toBe("boil_taste");
    const stew = { durationSec: 7200 };                                      // a two hour stew: chop capped at 5 min, taste at 2 min
    expect(cookSegment(base({ atS: CHOP_MAX_S - 1, ...stew }))).toBe("chop");
    expect(cookSegment(base({ atS: CHOP_MAX_S + 1, ...stew }))).not.toBe("chop");
    expect(cookSegment(base({ atS: 7200 - TASTE_MAX_S - 1, ...stew }))).not.toBe("boil_taste");
    expect(cookSegment(base({ atS: 7200 - TASTE_MAX_S + 1, ...stew }))).toBe("boil_taste");
  });
  test("a quick dish (1 minute): no wash, a few seconds of chopping, tasting in the last seconds", () => {
    const quick = { durationSec: 60, firstSeen: true, mountedAtMs: (T0 + 1) * 1000 };
    expect(cookSegment(base({ atS: 1.5, ...quick }))).toBe("chop");
    expect(cookSegment(base({ atS: 13, ...quick }))).toBe("boil_main");
    expect(cookSegment(base({ atS: 55, ...quick }))).toBe("boil_taste");
  });
  test("small actions in the main part: seconds 12-15 of every 30; the same moment gives the same one; another pot or slot differs", () => {
    const at = (slot: number, s: number, id = "pot-1") => cookSegment(base({ atS: 300 + slot * SLOT_S + s, sessionId: id }));
    const kinds = new Set<string>();
    for (let slot = 0; slot < 20; slot++) {
      expect(at(slot, 5)).toBe("boil_main");
      expect(at(slot, IDLE_AT_S + 4)).toBe("boil_main");
      const k = at(slot, IDLE_AT_S + 1)!;
      expect(at(slot, IDLE_AT_S + 2)).toBe(k);                               // unchanged inside the 3 s window
      expect(at(slot, IDLE_AT_S + 1)).toBe(k);                               // unchanged when computed again
      expect(["boil_main", "boil_wipe", "boil_look", "boil_hot"]).toContain(k);
      kinds.add(k);
    }
    expect(kinds.size).toBe(4);                                              // all four (including "nothing this slot") turn up
    const other = Array.from({ length: 20 }, (_, slot) => at(slot, IDLE_AT_S + 1, "pot-2"));
    expect(other).not.toEqual(Array.from({ length: 20 }, (_, slot) => at(slot, IDLE_AT_S + 1)));
  });
  test("every method uses its own set", () => {
    for (const m of COOK_METHODS) {
      expect(cookSegment(base({ atS: 305, method: m }))).toBe(`${m}_main`);
      expect(cookSegment(base({ atS: 1190, method: m }))).toBe(`${m}_taste`);
    }
  });
});

describe("the outcome", () => {
  test("due, outcome not here yet: keep cooking (never serve first and then flip to burnt)", () => {
    expect(cookSegment(base({ atS: 1203 }))).toBe("boil_main");
  });
  test("done well: serve -> still frame once the clip has played; leaves holding the plate", () => {
    expect(cookSegment(base({ atS: 1205, phase: "serve", sinceRevealMs: 100, outcome: "great" }))).toBe("boil_serve");
    expect(cookSegment(base({ atS: 1209, phase: "serve", sinceRevealMs: 3200, outcome: "ok" }))).toBe("boil_serve_last");
    expect(cookSegment(base({ atS: 1211, phase: "exit", sinceRevealMs: 5200, outcome: null }))).toBe("boil_serve_last");
  });
  test("burnt / spoiled: the fail clip -> still frame", () => {
    for (const o of ["burnt", "spoiled"] as const) {
      expect(cookSegment(base({ atS: 1205, phase: "serve", sinceRevealMs: 100, outcome: o, method: "bake" }))).toBe("bake_fail");
      expect(cookSegment(base({ atS: 1209, phase: "serve", sinceRevealMs: 3200, outcome: o, method: "bake" }))).toBe("bake_fail_last");
      expect(cookSegment(base({ atS: 1211, phase: "exit", sinceRevealMs: 5200, outcome: o, method: "bake" }))).toBe("bake_fail_last");
    }
  });
  test("cancelled midway: leaves doing the main action, carries nothing out; done / cancelled are off stage", () => {
    expect(cookSegment(base({ atS: 400, phase: "exit", sinceRevealMs: -800_000 }))).toBe("boil_main");
    expect(cookSegment(base({ atS: 9999, phase: "done" }))).toBeNull();
    expect(cookSegment(base({ atS: 400, phase: "cancelled" }))).toBeNull();
  });
});

test("assets: both outfits x (wash + chop + seven parts for each of seven methods + serve / fail stills + the base still) are registered", () => {
  const segs = ["wash", "chop", "base"];
  for (const m of COOK_METHODS) {
    for (const k of ["main", "wipe", "look", "hot", "taste", "serve", "fail", "serve_last", "fail_last"]) segs.push(`${m}_${k}`);
  }
  const missing: string[] = [];
  for (const o of ["toque", "scarf"] as const) for (const s of segs) if (CLAWD_MANIFEST.files[assetKey(o, s)] === undefined) missing.push(`${o}/${s}`);
  expect(missing).toEqual([]);
  expect(Object.keys(CLAWD_MANIFEST.files)).toHaveLength(2 * segs.length);
  expect(hashStr("a")).toBe(hashStr("a"));
});
