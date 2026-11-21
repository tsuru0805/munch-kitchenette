// "Tap a thing, hold that thing": which things can be tapped, their tap areas, what is held by default, where the leader line starts.
import type { FridgeItem } from "./fridgeApi";
import { anchorOf, batchesOf, defaultPick, hitBoxes, kindsOf, pickAlive, sceneObjects, tapKey, zonePick, MIN_HIT, type Box } from "./pick";
import { SCENE_SRC } from "./sceneSlots";

const it = (itemId: string, over: Partial<FridgeItem> = {}): FridgeItem => ({
  batchId: `${itemId}-${over.qty ?? 1}`, itemId, name: itemId, category: "veg", qty: 1, boughtAtMs: 0, by: "her", expiresAtMs: 0, freshness: "fresh", ...over,
});
const K = 390 / SCENE_SRC;
const scene = (over: Partial<Parameters<typeof sceneObjects>[0]> = {}) =>
  sceneObjects({ items: [it("egg", { category: "dairy" }), it("tomato")], staples: ["油", "盐"], coupons: 2, dishes: [], auth: null, ...over });

describe("what can be tapped in the picture", () => {
  test("each thing is there: one coupon per coupon held, the grocery memo, the ingredients placed in the fridge, five snacks, staples, the cork board, the receipt, the empty strip", () => {
    const keys = scene().map((o) => tapKey(o.tap));
    expect(keys.filter((x) => x === "coupon")).toHaveLength(2);
    expect(keys.slice(0, 2)).toEqual(["fridge", "table"]);   // the two ground zones lie at the very bottom
    expect(keys).toEqual(expect.arrayContaining(["buy", "item-egg", "item-tomato", "snack-coffee", "snack-jelly", "snack-pudding", "snack-chocolate", "snack-cookie", "wall", "receipt", "write"]));
    expect(keys.filter((x) => x === "staple")).toHaveLength(2);
    expect(keys.some((x) => x.startsWith("dish-"))).toBe(false);
  });
  test("dishes: one strip each (four at most) + a bowl on the counter for the first three; the empty strip comes after the last one, under the shelf, below the cork board", () => {
    const dishes = ["a", "b", "c", "d", "e", "f"].map((x) => ({ key: x, name: `菜${x}`, outcome: null }));
    const objs = scene({ dishes });
    const strips = objs.filter((o) => o.paper === "strip");
    expect(strips.map((o) => tapKey(o.tap))).toEqual(["dish-a", "dish-b", "dish-c", "dish-d"]);
    expect(objs.filter((o) => o.art && o.tap.k === "dish").map((o) => tapKey(o.tap))).toEqual(["dish-a", "dish-b", "dish-c"]);
    const blank = objs.find((o) => o.paper === "blank")!;
    expect(blank.box.x).toBeGreaterThan(strips[3].box.x);
    const cork = objs.find((o) => o.paper === "cork")!;
    expect(blank.box.y).toBeGreaterThanOrEqual(cork.box.y + cork.box.h);   // the cork board hangs above the lower shelf, the strips under it
    expect(blank.box.x + blank.box.w).toBeLessThanOrEqual(1015);           // the lower shelf ends at the window
  });
  test("the things of the plays in the picture: only those switched on; the flowers only with a bunch on the sill; each opens its sheet", () => {
    expect(scene().some((o) => o.scenery)).toBe(false);
    const all = scene({ scenery: { flower: true, jars: true, plates: true } });
    const sc = all.filter((o) => o.scenery);
    expect(sc.map((o) => tapKey(o.tap))).toEqual(["sheet-vendor", "sheet-jars", "sheet-jars", "sheet-jars", "sheet-plates", "sheet-plates"]);
    expect(scene({ scenery: { flower: false, jars: true, plates: false } }).filter((o) => o.scenery).map((o) => tapKey(o.tap))).toEqual(["sheet-jars", "sheet-jars", "sheet-jars"]);
    // they lie right above the ground zones: everything else (a dish in front of the jars) is drawn and tapped over them
    expect(all.findIndex((o) => o.scenery)).toBe(2);
  });
  test("no coupons: none in the picture (handing one out starts from the row under the picture)", () => {
    expect(scene({ coupons: 0 }).some((o) => o.tap.k === "coupon")).toBe(false);
  });
});

describe("tap areas", () => {
  const objs = scene();
  const hits = hitBoxes(objs, K);
  const at = (key: string) => hits[objs.findIndex((o) => tapKey(o.tap) === key)];
  test("a small picture grows until a finger can hit it", () => {
    const coffee = at("snack-coffee");
    expect(coffee.h).toBeGreaterThanOrEqual(MIN_HIT - 0.01);
  });
  test("two snacks next to each other: the areas do not overlap; left of the midline belongs to the left one, right of it to the right one", () => {
    const a = at("snack-coffee"), b = at("snack-jelly");
    expect(a.x + a.w).toBeLessThanOrEqual(b.x + 0.01);
    const boxA = objs.find((o) => tapKey(o.tap) === "snack-coffee")!.box, boxB = objs.find((o) => tapKey(o.tap) === "snack-jelly")!.box;
    const mid = ((boxA.x + boxA.w + boxB.x) / 2) * K;
    expect(a.x + a.w).toBeCloseTo(mid, 3);
    expect(b.x).toBeCloseTo(mid, 3);
  });
  test("every area covers the centre of its own picture (the side next to a neighbour gives up three tenths at most)", () => {
    objs.forEach((o, i) => {
      const cx = (o.box.x + o.box.w / 2) * K, cy = (o.box.y + o.box.h / 2) * K;
      expect(hits[i].x).toBeLessThan(cx);
      expect(hits[i].x + hits[i].w).toBeGreaterThan(cx);
      expect(hits[i].y).toBeLessThan(cy);
      expect(hits[i].y + hits[i].h).toBeGreaterThan(cy);
    });
  });
  const overlap = (a: Box, b: Box) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  test.each([
    ["a full fridge (wide ingredients side by side, milk in the door rack)", { items: ["cucumber", "potato", "onion", "egg", "tofu", "salmon", "spinach", "scallion", "lettuce", "milk", "carrot", "tomato"].map((x) => it(x, { category: x === "milk" || x === "egg" || x === "tofu" ? "dairy" : x === "salmon" ? "meat" : x === "spinach" || x === "scallion" || x === "lettuce" ? "leafy" : "veg" })), coupons: 3 }],
    ["six dishes + three coupons", { dishes: ["a", "b", "c", "d", "e", "f"].map((x) => ({ key: x, name: `菜${x}`, outcome: null })), coupons: 3 }],
    ["an empty fridge", { items: [], coupons: 0, staples: [] }],
    ["every play on: flowers, jars, sink and rack, with three dishes in front of the jars and all four staples", {
      scenery: { flower: true, jars: true, plates: true }, staples: ["油", "酱油", "盐", "米"],
      dishes: ["a", "b", "c", "d"].map((x) => ({ key: x, name: `菜${x}`, outcome: null })),
    }],
  ])("%s: the tap areas of any two different things do not overlap (ground zones aside)", (_n, over) => {
    const o3 = scene(over as Parameters<typeof scene>[0]);
    const h3 = hitBoxes(o3, K);
    const bad: string[] = [];
    o3.forEach((a, i) => o3.forEach((b, j) => {
      if (j <= i || a.zone || b.zone || tapKey(a.tap) === tapKey(b.tap)) return;
      if (overlap(h3[i], h3[j]) > 0.01) bad.push(`${tapKey(a.tap)} × ${tapKey(b.tap)}`);   // things that touch or overlap in the picture must not overlap either (split at the midline)
    }));
    expect(bad).toEqual([]);
    // once split, every area still covers the centre of its own picture
    o3.forEach((o, i) => {
      if (o.zone) return;
      const cx = (o.box.x + o.box.w / 2) * K, cy = (o.box.y + o.box.h / 2) * K;
      expect([tapKey(o.tap), h3[i].x < cx && h3[i].x + h3[i].w > cx && h3[i].y < cy && h3[i].y + h3[i].h > cy]).toEqual([tapKey(o.tap), true]);
    });
  });
  test("the strip and the bowl of one dish do not give way to each other (either one is that dish)", () => {
    const o2 = scene({ dishes: [{ key: "a", name: "菜", outcome: null }] });
    const h2 = hitBoxes(o2, K);
    const strip = h2[o2.findIndex((o) => o.paper === "strip")];
    expect(strip.h).toBeGreaterThanOrEqual(MIN_HIT - 0.01);
  });
});

describe("the thing in the hand", () => {
  test("on arriving: the first thing in the fridge (the server sorts by urgency); empty fridge = the coupon", () => {
    expect(defaultPick([it("spinach", { freshness: "bad" }), it("egg")])).toEqual({ k: "item", id: "spinach" });
    expect(defaultPick([])).toEqual({ k: "coupon" });
  });
  test("a thing that is gone no longer counts: the ingredient was used up / the dish was taken off", () => {
    expect(pickAlive({ k: "item", id: "egg" }, [it("egg")], [])).toBe(true);
    expect(pickAlive({ k: "item", id: "egg" }, [], [])).toBe(false);
    expect(pickAlive({ k: "dish", id: "m1" }, [], ["m2"])).toBe(false);
    expect(pickAlive({ k: "wall" }, [], [])).toBe(true);
  });
  test("where the leader line starts: the middle of the bottom edge of the thing in the picture; not in the picture = no line", () => {
    const objs = scene();
    const egg = objs.find((o) => tapKey(o.tap) === "item-egg")!;
    expect(anchorOf(objs, { k: "item", id: "egg" }, K)).toEqual({ x: (egg.box.x + egg.box.w / 2) * K, y: (egg.box.y + egg.box.h) * K });
    expect(anchorOf(objs, { k: "item", id: "nope" }, K)).toBeNull();
    expect(anchorOf(objs, null, K)).toBeNull();
  });
  test("a group (the four staples / the coupons): the line starts at the middle of the group's bottom edge; a dish: at its bowl", () => {
    const objs = scene({ staples: ["油", "酱油", "盐", "米"], dishes: [{ key: "a", name: "菜", outcome: null }] });
    const st = objs.filter((o) => o.tap.k === "staple");
    const x0 = Math.min(...st.map((o) => o.box.x)), x1 = Math.max(...st.map((o) => o.box.x + o.box.w));
    expect(anchorOf(objs, { k: "staple" }, K)!.x).toBeCloseTo(((x0 + x1) / 2) * K, 4);
    const bowl = objs.find((o) => o.art && o.tap.k === "dish")!;
    expect(anchorOf(objs, { k: "dish", id: "a" }, K)).toEqual({ x: (bowl.box.x + bowl.box.w / 2) * K, y: (bowl.box.y + bowl.box.h) * K });
  });
  test("a tap on an empty spot: fridge = the most urgent thing (empty = the coupon), counter = the receipt (which brings the table row)", () => {
    expect(zonePick("fridge", [it("egg")])).toEqual({ k: "item", id: "egg" });
    expect(zonePick("fridge", [])).toEqual({ k: "coupon" });
    expect(zonePick("table", [])).toEqual({ k: "receipt" });
  });
  test("the batches of one kind are listed apart; the row is by kind, with counts added up and the order kept", () => {
    const items = [it("egg", { qty: 2, freshness: "meh" }), it("tomato", { qty: 3 }), it("egg", { qty: 6 })];
    expect(batchesOf(items, "egg").map((b) => b.qty)).toEqual([2, 6]);
    expect(kindsOf(items).map((x) => [x.itemId, x.qty])).toEqual([["egg", 8], ["tomato", 3]]);
    expect(kindsOf(items)[0].first.freshness).toBe("meh");
  });
});
