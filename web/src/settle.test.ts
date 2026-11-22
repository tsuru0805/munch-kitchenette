// The settled still: which pictures it needs, and where the dish goes on the cook's grid.
import { CLAWD_MANIFEST } from "./manifest.generated";
import { readFileSync, readdirSync } from "node:fs";
import { SRC_LINE_Y } from "./manifest";
import { CELL, PIC_FRAME, PIC_SCALE, PIC_SCALE_NARROW, PLATES, StillCache, picBox, placeDish, poseFor, settleKeys } from "./settle";

test("every picture a settled still can ask for is in the built-in pack", () => {
  for (const o of CLAWD_MANIFEST.outfits) {
    for (const pose of ["great", "ok", "burnt", "spoiled", "ruined"] as const) {
      for (const icon of ["stirfry", "soup", "bowl", "nonsense", ""]) {
        for (const k of settleKeys(o, pose, icon)) expect(CLAWD_MANIFEST.files[k]).toBeDefined();
      }
    }
  }
  expect(settleKeys("toque", "ruined", "soup")).toEqual(["toque/settle_ruined"]);
  expect(settleKeys("toque", "burnt", "soup")[2]).toBe("dishes/soup_burnt_cells");
  expect(settleKeys("toque", "ok", "nonsense")[2]).toBe("dishes/bowl_cells");
  expect(poseFor("great")).toBe("great");
  expect(poseFor("raw")).toBeNull();
});

test("the dish sits on the grid with its bottom where the plate goes; spoiled tips away from the hand", () => {
  const p = placeDish(PLATES.toque.ok, 12, 8);
  expect((p.x - 6) % CELL).toBe(0);
  expect(p.y + 8 * CELL).toBe(510);
  expect(p.drop(5)).toBe(0);
  const s = placeDish(PLATES.toque.spoiled, 12, 8);
  expect(s.drop(11)).toBe(0);          // the column by the hand stays up
  expect(s.drop(0)).toBe(3);           // the far one is three cells lower
});

test("one frame for every still: on the cell grid, its bottom on the feet line, the column sized from it", () => {
  expect((PIC_FRAME.x - 6) % CELL).toBe(0);
  expect(PIC_FRAME.y % CELL).toBe(0);
  expect(PIC_FRAME.y + PIC_FRAME.h).toBe(SRC_LINE_Y);
  // one scale for all five, on whole CSS pixels a cell; the body (24 cells) about 96 px; the column at most ~190 px
  for (const k of [PIC_SCALE, PIC_SCALE_NARROW]) expect(Number.isInteger(CELL * k)).toBe(true);
  expect(24 * CELL * PIC_SCALE).toBe(96);
  expect(picBox(PIC_SCALE).col).toBeLessThanOrEqual(192);
  expect(picBox(PIC_SCALE_NARROW).col).toBeLessThan(picBox(PIC_SCALE).col);
});

test("every dish of the built-in pack, in every pose and outfit, lands inside the frame", () => {
  const dir = new URL("../../assets/clawd/dishes/", import.meta.url);
  const files = readdirSync(dir).filter((f) => f.endsWith("_cells.png"));
  expect(files.length).toBe(28);
  for (const f of files) {
    const png = readFileSync(new URL(f, dir));
    const cols = png.readUInt32BE(16);   // IHDR width
    const rows = png.readUInt32BE(20);   // IHDR height
    for (const outfit of Object.keys(PLATES)) {
      for (const [pose, spot] of Object.entries(PLATES[outfit])) {
        if (f.includes("_burnt_") !== (pose === "burnt")) continue; // the burnt dish is only held when burnt
        const at = placeDish(spot, cols, rows);
        const drops = Array.from({ length: cols }, (_, c) => at.drop(c));
        const where = `${f} ${outfit}/${pose}`;
        expect(at.x, where).toBeGreaterThanOrEqual(PIC_FRAME.x);
        expect(at.x + cols * CELL, where).toBeLessThanOrEqual(PIC_FRAME.x + PIC_FRAME.w);
        expect(at.y, where).toBeGreaterThanOrEqual(PIC_FRAME.y);
        expect(at.y + rows * CELL + Math.max(...drops) * CELL, where).toBeLessThanOrEqual(PIC_FRAME.y + PIC_FRAME.h);
      }
    }
  }
});

describe("the drawn stills", () => {
  const flush = () => new Promise((r) => setTimeout(r, 0));

  it("are drawn once and shared; a card asking while one is being drawn waits for it", async () => {
    const cache = new StillCache<string>();
    let calls = 0;
    const load = async () => (calls++, "still");
    const done = vi.fn();
    expect(cache.get("k", new Set(), load, done)).toBeNull();
    expect(cache.state("k")).toBe("loading");
    expect(cache.get("k", new Set(), load, done)).toBeNull(); // another card, same pictures
    await flush();
    expect(calls).toBe(1);
    expect(done).toHaveBeenCalledTimes(1);
    expect(cache.get("k", new Set(), load, done)).toBe("still");
  });

  it("two cards waiting for the same pictures are both told when they are drawn, or when that failed", async () => {
    const cache = new StillCache<string>();
    let calls = 0;
    let finish!: (v: string | null) => void;
    const load = () => (calls++, new Promise<string | null>((r) => (finish = r)));
    const first = vi.fn();
    const second = vi.fn();
    expect(cache.get("k", new Set(), load, first)).toBeNull();
    expect(cache.get("k", new Set(), load, second)).toBeNull();   // the other card, while the first is loading
    expect(cache.get("k", new Set(), load, second)).toBeNull();   // re-rendered meanwhile: still told once
    finish("still");
    await flush();
    expect(calls).toBe(1);
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
    expect(cache.get("k", new Set(), load, second)).toBe("still");

    const bad = new StillCache<string>();
    let fail!: (e: Error) => void;
    const a = vi.fn();
    const b = vi.fn();
    bad.get("k", new Set(), () => new Promise((_, no) => (fail = no)), a);
    bad.get("k", new Set(), () => Promise.resolve("never asked"), b);
    fail(new Error("picture did not load"));
    await flush();
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    expect(bad.state("k")).toBe("failed");
  });

  it("a failed one is asked again once, the next time a card is put on the page, not on every render", async () => {
    const cache = new StillCache<string>();
    let calls = 0;
    let ok = false;
    const load = async () => {
      calls++;
      if (!ok) throw new Error("picture did not load");
      return "still";
    };
    const done = () => {};
    let tried = new Set<string>();                 // this appearance of the card
    cache.get("k", tried, load, done);
    await flush();
    expect(cache.state("k")).toBe("failed");
    expect(cache.get("k", tried, load, done)).toBeNull(); // re-rendered: not again
    await flush();
    expect(calls).toBe(1);
    ok = true;
    tried = new Set();                             // the card comes back on the page
    expect(cache.get("k", tried, load, done)).toBeNull();
    await flush();
    expect(calls).toBe(2);
    expect(cache.get("k", tried, load, done)).toBe("still");
  });

  it("a load that gives nothing counts as failed", async () => {
    const cache = new StillCache<string>();
    cache.get("k", new Set(), async () => null, () => {});
    await flush();
    expect(cache.state("k")).toBe("failed");
  });
});
