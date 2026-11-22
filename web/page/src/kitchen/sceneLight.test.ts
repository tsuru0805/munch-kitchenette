// The light of the picture and the pieces put back onto it: by the hour; the flowers by kind and look;
// the jars by what is sealed in them; the rack and the sink by the plates; a play that is off adds nothing.
import { SCENE_BASE, SCENE_PIECES, LIGHTS } from "./sceneArt.generated";
import { FLOWER_PIECE, RACK_HOURS, fullness, jarLook, lightAt, rackCount, scenePieces, sinkLook } from "./sceneLight";

const none = { flower: null, jars: null, plates: null };

describe("the light", () => {
  test("day 06:00–17:00, dusk 17:00–19:00, night the rest", () => {
    expect([lightAt(5, 59), lightAt(6), lightAt(12), lightAt(16, 59), lightAt(17), lightAt(18, 59), lightAt(19), lightAt(0)])
      .toEqual(["night", "day", "day", "day", "dusk", "dusk", "night", "night"]);
  });
  test("every light has its picture and the same set of pieces", () => {
    for (const l of LIGHTS) expect(SCENE_BASE[l]).toBeTruthy();
    const names = (l: string) => Object.keys(SCENE_PIECES).filter((k) => k.startsWith(`${l}_`)).map((k) => k.slice(l.length + 1)).sort();
    expect(names("day")).toHaveLength(34);   // 18 flowers + 9 jars + 3 rack + 4 sink
    expect(names("dusk")).toEqual(names("day"));
    expect(names("night")).toEqual(names("day"));
  });
});

describe("the pieces", () => {
  test("nothing switched on: the empty picture with the three jars standing empty (no flowers, no plates)", () => {
    expect(scenePieces("day", none)).toEqual(["day_jars_1", "day_jars_4", "day_jars_7"]);
    expect(scenePieces("night", none)).toEqual(["night_jars_1", "night_jars_4", "night_jars_7"]);
  });
  test("one bunch on the sill: its kind and how it looks, in the light of the hour; a kind without a picture leaves the sill empty", () => {
    const fl = (light: "day" | "dusk" | "night", f: { variety: string; state: string }) => scenePieces(light, { ...none, flower: f }).filter((k) => !k.includes("_jars_"));
    expect(fl("day", { variety: "sunflower", state: "fresh" })).toEqual(["day_fl1_1"]);
    expect(fl("dusk", { variety: "rose", state: "droopy" })).toEqual(["dusk_fl1_5"]);
    expect(fl("night", { variety: "narcissus", state: "wilted" })).toEqual(["night_fl2_9"]);
    expect(fl("day", { variety: "lily", state: "fresh" })).toEqual([]);
    for (const v of Object.keys(FLOWER_PIECE)) for (const s of ["fresh", "droopy", "wilted"]) {
      expect(fl("day", { variety: v, state: s })).toHaveLength(1);
    }
  });
  test("the jars: empty, fruit (sugar / honey), pickles (salt), by slot from the left", () => {
    expect([undefined, { slot: 1, state: "empty", how: "" }, { slot: 1, state: "sealed", how: "sugar" }, { slot: 1, state: "sealed", how: "honey" }, { slot: 1, state: "sealed", how: "salt" }].map(jarLook))
      .toEqual([0, 0, 1, 1, 2]);
    expect(scenePieces("day", { ...none, jars: [{ slot: 2, state: "sealed", how: "salt" }, { slot: 1, state: "sealed", how: "honey" }] }))
      .toEqual(["day_jars_2", "day_jars_6", "day_jars_7"]);
    expect(scenePieces("day", { ...none, jars: [] })).toEqual(["day_jars_1", "day_jars_4", "day_jars_7"]);
  });
  test("the rack and the sink: none / a few / many, foam while washing", () => {
    expect([0, 1, 3, 4, 20].map(fullness)).toEqual([0, 1, 1, 2, 2]);
    expect(sinkLook({ sink: 5, washing: 2, rack: 0 })).toBe(3);
    const pl = (light: "day" | "night", p: { sink: number; washing: number; rack: number }) => scenePieces(light, { ...none, plates: p }).filter((k) => k.includes("_dish_"));
    expect(pl("night", { sink: 0, washing: 0, rack: 0 })).toEqual(["night_dish_1", "night_dish_4"]);
    expect(pl("day", { sink: 2, washing: 0, rack: 6 })).toEqual(["day_dish_3", "day_dish_5"]);
    expect(pl("day", { sink: 9, washing: 0, rack: 1 })).toEqual(["day_dish_2", "day_dish_6"]);
    expect(pl("day", { sink: 0, washing: 1, rack: 0 })).toEqual(["day_dish_1", "day_dish_7"]);
  });
  test("plates on the rack come from the last washing: so far while it runs, all of it for a while after, none later", () => {
    expect(rackCount(null, 1000)).toBe(0);
    const run = { state: "running", startedAt: 1000, perS: 60, n: 5, endedAt: null };
    expect(rackCount(run, 1000 + 150)).toBe(2);
    expect(rackCount(run, 1000 + 9999)).toBe(5);
    const done = { state: "done", startedAt: 1000, perS: 60, n: 5, endedAt: 1300 };
    expect(rackCount(done, 1300 + 60)).toBe(5);
    expect(rackCount(done, 1300 + RACK_HOURS * 3600 + 1)).toBe(0);
    expect(rackCount({ state: "stopped", startedAt: 1000, perS: 60, n: 5, endedAt: 1130 }, 1200)).toBe(2);
  });
});
