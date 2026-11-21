import {
  BREAK_SHOW_MS, CARRY_MS, RESULT_WAIT_S, CLIP_MS, WASHER_RUN_MS, nextPlateDue, WASH_PARTS, hashStr, outfitFor, platesClip, serverNow, stillFor, vendorClip, vendorPanelClip, washClip,
  washerClip, type VendorOrderFacts, type WashJobFacts,
} from "./choreAnim";
import { CHORE_ART, CHORE_SEGMENTS } from "./choreArt.generated";
import { parsePlates, parseVendor } from "./playApi";
import contract from "./__fixtures__/server_contract.json";

const job = (over: Partial<WashJobFacts> = {}): WashJobFacts => ({ id: "job1", startedAt: 1000, perS: 70, n: 3, endedAt: null, breaks: [], ...over });
const seg = (j: WashJobFacts, t: number) => washClip(j, t)?.segment ?? null;

describe("washing up", () => {
  test("each plate's time in seven equal parts, in order; the sleeves only at the start of the washing", () => {
    const j = job(); // 70 s a plate: 10 s a part
    expect([0, 10, 20, 30, 40, 50, 60].map((s) => seg(j, 1000 + s + 1))).toEqual([...WASH_PARTS]);
    // the second plate: soap takes the first two parts, then the same order
    expect([0, 10, 20, 30, 40, 50, 60].map((s) => seg(j, 1070 + s + 1))).toEqual(
      ["dish_soap", "dish_soap", "dish_scrub", "dish_rinse", "dish_shake", "dish_dry", "dish_stack"]);
    // soap on the second plate is one run across both parts (it does not restart in the middle)
    expect(washClip(j, 1071)!.run).toBe(washClip(j, 1081)!.run);
    expect(washClip(j, 1001)!.run).not.toBe(washClip(j, 1011)!.run);
  });

  test("a plate that broke: told once its time is up; the dropped plate once, then its last frame, then the next plate", () => {
    const j = job({ breaks: [1] }); // plate 1 (1070-1140) broke: the page only learns it at 1140
    expect(seg(j, 1060 + 1)).toBe("dish_stack");
    expect(seg(j, 1130 + 1)).toBe("dish_stack"); // its own last part: stacking, nothing told yet
    expect(seg(j, 1140)).toBe("dish_break");
    expect(seg(j, 1140 + CLIP_MS / 1000 + 0.1)).toBe("dish_break_last");
    expect(seg(j, 1140 + BREAK_SHOW_MS / 1000)).toBe("dish_soap"); // the next plate goes on
    expect(washClip(j, 1140)!.run).not.toBe(washClip(j, 1139)!.run);
  });

  test("the last plate broke: shown after the washing is over, then nothing", () => {
    const j = job({ breaks: [2] });
    expect(seg(j, 1210)).toBe("dish_break");
    expect(seg(j, 1210 + 4)).toBe("dish_break_last");
    expect(seg(j, 1210 + BREAK_SHOW_MS / 1000)).toBeNull();
    // stopped midway: only a plate whose time was up before the stop
    expect(seg(job({ endedAt: 1100, breaks: [0] }), 1071)).toBe("dish_break");
    expect(seg(job({ endedAt: 1100, breaks: [0] }), 1101)).toBeNull();
  });

  test("a plate due after the answer was read: its last step goes on a moment while the page reads again", () => {
    const j = job({ breaks: [] }); // read at 1139, plate 1 due at 1140, its result not known yet
    expect(washClip(j, 1140.5, 1139)!.segment).toBe("dish_stack");
    expect(washClip(j, 1140.5, 1139)!.run).toBe(washClip(j, 1139.5, 1139)!.run); // the same run: no restart
    expect(washClip(j, 1140 + RESULT_WAIT_S, 1139)!.segment).toBe("dish_soap"); // nothing came: go on
    expect(washClip(j, 1140.5, 1140.2)!.segment).toBe("dish_soap"); // read after it was due: it did not break
    expect(washClip(job({ breaks: [1] }), 1140.5, 1140.2)!.segment).toBe("dish_break");
    expect(washClip(j, 1210.5, 1209)!.segment).toBe("dish_stack"); // the last plate too
    expect(washClip(j, 1210.5, 1210.1)).toBeNull();
  });

  test("when to read again for the next plate's result", () => {
    expect(nextPlateDue(job(), 1001)).toBe(1070);
    expect(nextPlateDue(job(), 1150)).toBe(1210);
    expect(nextPlateDue(job(), 1210)).toBeNull();
    expect(nextPlateDue(job({ endedAt: 1100 }), 1080)).toBeNull();
    expect(nextPlateDue(null, 0)).toBeNull();
  });

  test("nothing before the start, after the end, or after the washing was stopped", () => {
    expect(seg(job(), 999)).toBeNull();
    expect(seg(job(), 1000 + 3 * 70)).toBeNull();
    expect(seg(job({ endedAt: 1100 }), 1100)).toBeNull();
    expect(seg(job({ endedAt: 1100 }), 1099)).not.toBeNull();
    expect(washClip(null, 1000)).toBeNull();
    expect(washClip(job({ perS: 0 }), 1001)).toBeNull();
  });

  test("the outfit follows the washing's id, the card's rule", () => {
    expect(washClip(job({ id: "a" }), 1001)!.outfit).toBe(outfitFor("a"));
    expect(washClip(job({ id: "a" }), 1201)!.outfit).toBe(outfitFor("a"));
  });
});

describe("the dishwasher", () => {
  test("load -> close -> start -> running for 8 s -> done once, then its last frame", () => {
    const at = 500;
    const s = (ms: number) => washerClip(at, 2, at + ms / 1000)!.segment;
    expect([0, 3000, 6000, 9000, 9000 + WASHER_RUN_MS - 1, 9000 + WASHER_RUN_MS].map(s)).toEqual(
      ["machine_load", "machine_close", "machine_start", "machine_run", "machine_run", "machine_done"]);
    expect(s(9000 + WASHER_RUN_MS + CLIP_MS)).toBe("machine_done_last");
    expect(s(86_400_000)).toBe("machine_done_last");
  });
  test("nothing when no plate is in it", () => {
    expect(washerClip(null, 2, 1)).toBeNull();
    expect(washerClip(500, 0, 501)).toBeNull();
  });
});

describe("the vendor", () => {
  const o = (over: Partial<VendorOrderFacts>): VendorOrderFacts => ({ id: "o1", payer: "self", state: "delivered", createdAt: 100, updatedAt: 100, ...over });
  const s = (mine: VendorOrderFacts[], t: number) => vendorClip("v1", mine, t)?.segment ?? null;

  test("no vendor downstairs: nothing; a vendor and no order yet: calling him over", () => {
    expect(vendorClip(null, [], 0)).toBeNull();
    expect(vendorClip("v1", [], 0)).toEqual({ segment: "vendor_call", outfit: outfitFor("v1"), run: "v1:call" });
  });
  test("paying while it is paid; taking the bag once, then carrying it back, then at the window again", () => {
    for (const state of ["created", "debiting", "paid"]) expect(s([o({ state })], 101)).toBe("vendor_pay");
    expect(s([o({ updatedAt: 200 })], 200)).toBe("vendor_take");
    expect(s([o({ updatedAt: 200 })], 200 + CLIP_MS / 1000)).toBe("vendor_carry");
    expect(s([o({ updatedAt: 200 })], 200 + (CLIP_MS + CARRY_MS) / 1000)).toBe("vendor_call");
    expect(vendorClip("v1", [o({ id: "abc", state: "debiting" })], 101)!.outfit).toBe(outfitFor("abc"));
  });
  test("the human treating: no paying", () => {
    expect(s([o({ payer: "her", state: "created" })], 101)).toBe("vendor_call");
    expect(s([o({ payer: "her", updatedAt: 200 })], 201)).toBe("vendor_take");
  });
  test("refunded or failed: nothing is taken", () => {
    for (const state of ["refunding", "refunded", "debit_failed"]) expect(s([o({ state, updatedAt: 200 })], 200.5)).toBe("vendor_call");
  });
  test("the latest order counts", () => {
    expect(s([o({ id: "a", createdAt: 300, state: "debiting" }), o({ id: "b", createdAt: 100, updatedAt: 299 })], 300)).toBe("vendor_pay");
  });
});

test("reduce motion: the last frame of a clip that plays once, otherwise the still base pose", () => {
  expect(stillFor("dish_break")).toBe("dish_break_last");
  expect(stillFor("dish_break_last")).toBe("dish_break_last");
  expect(stillFor("machine_done")).toBe("machine_done_last");
  expect(stillFor("vendor_take")).toBe("vendor_take_last");
  expect(stillFor("dish_scrub")).toBe("base");
  expect(stillFor("vendor_carry")).toBe("base");
  expect(stillFor("machine_run")).toBe("base");
});

test("every segment these name, and every still, is in the art for both outfits", () => {
  const named = new Set<string>(["base"]);
  for (const j of [job(), job({ breaks: [0, 1, 2] })]) for (let t = 1000; t < 1220; t += 0.5) { const c = washClip(j, t); if (c) named.add(c.segment); }
  for (let t = 0; t < 30; t += 0.25) named.add(washerClip(0, 1, t)!.segment);
  for (const st of ["created", "delivered"]) for (let t = 100; t < 120; t += 0.5) named.add(vendorClip("v", [{ id: "o", payer: "self", state: st, createdAt: 100, updatedAt: 100 }], t)!.segment);
  for (const n of [...named]) named.add(stillFor(n));
  expect([...named].sort()).toEqual([...CHORE_SEGMENTS].sort());
  for (const outfit of ["toque", "scarf"] as const) for (const k of CHORE_SEGMENTS) expect(CHORE_ART[outfit][k]).toBeDefined();
});

test("the outfit hash is the card's (FNV-1a), so a washing or an order wears the same as the card would pick", () => {
  // values from web/src/cookSegments.ts hashStr
  expect(hashStr("a")).toBe(0xe40c292c);
  expect(hashStr("")).toBe(0x811c9dc5);
});

describe("from what the server answers", () => {
  test("plates: the washing, which plates break, when plates went into the dishwasher", () => {
    const p = parsePlates({ now: 1100, counts: { machine: 2 }, machine_at: 900,
      job: { id: "j", state: "running", started_at: 1000, per_s: 70, n: 2, ended_at: null, breaks: [0] } });
    expect(p.job).toMatchObject({ id: "j", breaks: [0] });
    expect(p.machineAt).toBe(900);
    const read = p.readAt;
    expect(platesClip(p, read)!.segment).toBe("dish_rinse"); // second plate, 30 s in (the first broke 30 s ago)
    expect(platesClip({ ...p, now: 1072 }, read)!.segment).toBe("dish_break");
    expect(platesClip({ ...p, job: null }, read)!.segment).toBe("machine_done_last");
    expect(platesClip({ ...p, now: 1000 + 140 }, read)!.segment).toBe("machine_done_last"); // the washing is over
  });
  test("vendor: the visit's id and the role's orders", () => {
    const v = parseVendor({ now: 50, visit: { id: "v9", name: "x", who: "y", left_s: 60, goods: [] },
      mine: [{ id: "o1", item_name: "栗子", qty: 1, total: 7, payer: "self", state: "delivered", created_at: 40, updated_at: 49 }] });
    expect(v.visit!.id).toBe("v9");
    expect(v.mine).toEqual([{ id: "o1", name: "栗子", payer: "self", state: "delivered", createdAt: 40, updatedAt: 49 }]);
    expect(vendorPanelClip(v, v.readAt)!.segment).toBe("vendor_take");
    expect(vendorPanelClip(v, v.readAt + 3000)!.segment).toBe("vendor_carry");
  });
  test("the server's own answers carry the fields", () => {
    const c = contract as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
    expect(c.dishes).toHaveProperty("machine_at");
    expect(c.vendor.visit).toHaveProperty("id");
    expect(Array.isArray(c.vendor.mine)).toBe(true);
  });
  test("server time moves on with this device's clock", () => {
    expect(serverNow(100, 5000, 7000)).toBe(102);
    expect(serverNow(100, 5000, 4000)).toBe(100);
  });
});
