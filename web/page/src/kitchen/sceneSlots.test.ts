// Placing things in slots: by shelf, one picture per kind (the most urgent batch's freshness), the drawer when a shelf is full, nothing when that is full too.
import type { FridgeItem } from "./fridgeApi";
import {
  FRIDGE_SLOTS, NOTE_SLOTS, STAPLE_SLOTS, TICKET_SLOTS, dishArt, fitInSlot, fridgePlacements, hashName, noteCount,
  shelfFor, staplePlacements, ticketCount,
} from "./sceneSlots";
import { FRIDGE_ART } from "./art.generated";

let seq = 0;
function it_(itemId: string, category: string, freshness: FridgeItem["freshness"] = "fresh"): FridgeItem {
  seq += 1;
  return {
    batchId: `b${seq}`, itemId, name: itemId, category, qty: 1, boughtAtMs: null, by: "her", expiresAtMs: null, freshness,
  };
}

describe("shelfFor", () => {
  test("milk goes in the door rack; spoiled things and leafy greens on the bottom shelf; eggs, dairy, tofu and meat on top; the rest in the middle", () => {
    expect(shelfFor(it_("milk", "dairy"))).toBe("door");
    expect(shelfFor(it_("milk", "dairy", "bad"))).toBe("door");
    expect(shelfFor(it_("spinach", "leafy"))).toBe("leafyBad");
    expect(shelfFor(it_("tomato", "veg", "bad"))).toBe("leafyBad");
    expect(shelfFor(it_("egg", "dairy"))).toBe("dairyMeat");
    expect(shelfFor(it_("beef", "meat", "meh"))).toBe("dairyMeat");
    expect(shelfFor(it_("tomato", "veg"))).toBe("veg");
    expect(shelfFor(it_("udon", "staple_food"))).toBe("veg");
    expect(shelfFor(it_("apple", "fruit"))).toBe("veg");
  });
});

describe("fridgePlacements", () => {
  test("freshness picks the picture: fresh / meh / bad each have their own", () => {
    const { placed } = fridgePlacements([it_("spinach", "leafy", "bad"), it_("tomato", "veg", "meh"), it_("egg", "dairy")]);
    expect(placed.map((p) => p.art)).toEqual(["spinach_bad", "tomato_meh", "egg_fresh"]);
  });

  test("several batches of one kind are drawn once, as the first (most urgent) batch", () => {
    const { placed } = fridgePlacements([it_("egg", "dairy", "meh"), it_("egg", "dairy", "fresh")]);
    expect(placed).toHaveLength(1);
    expect(placed[0].art).toBe("egg_meh");
  });

  test("things go to their shelf, to the drawer when it is full, and are not drawn when the drawer is full too", () => {
    const meats = ["beef", "pork", "chicken", "shrimp", "salmon", "egg", "tofu", "butter"].map((x) => it_(x, x === "egg" || x === "tofu" || x === "butter" ? "dairy" : "meat"));
    const { placed, hidden } = fridgePlacements(meats);
    expect(placed.slice(0, 3).map((p) => p.slot)).toEqual(FRIDGE_SLOTS.dairyMeat);
    expect(placed.slice(3, 6).map((p) => p.slot)).toEqual(FRIDGE_SLOTS.drawer);
    expect(placed).toHaveLength(6);
    expect(hidden).toEqual(["tofu", "butter"]);
  });

  test("milk in the door rack; a kind with no picture is not drawn", () => {
    const { placed, hidden } = fridgePlacements([it_("milk", "dairy", "meh"), it_("durian", "fruit")]);
    expect(placed).toEqual([{ key: "milk", art: "milk_meh", slot: FRIDGE_SLOTS.door[0] }]);
    expect(hidden).toEqual(["durian"]);
  });

  test("an empty fridge draws nothing", () => {
    expect(fridgePlacements([])).toEqual({ placed: [], hidden: [] });
  });
});

describe("wall and counter", () => {
  test("only the staples the server lists are drawn", () => {
    expect(staplePlacements(["米", "盐"]).map((p) => p.art)).toEqual(["staple_salt", "staple_rice"]);
    expect(staplePlacements([])).toEqual([]);
    expect(STAPLE_SLOTS.every((s) => s.art in FRIDGE_ART)).toBe(true);
  });

  test("0–3 coupons, 0–3 notes", () => {
    expect([0, 1, 3, 7, -1].map(ticketCount)).toEqual([0, 1, 3, 3, 0]);
    expect([0, 2, 30].map(noteCount)).toEqual([0, 2, 3]);
    expect(TICKET_SLOTS).toHaveLength(3);
    expect(NOTE_SLOTS).toHaveLength(3);
  });

  test("a dish keeps its vessel (a hash of its name); burnt or spoiled uses the burnt picture", () => {
    expect(hashName("番茄炒蛋")).toBe(hashName("番茄炒蛋"));
    const a = dishArt("番茄炒蛋", null);
    expect(dishArt("番茄炒蛋", "great")).toBe(a);
    expect(dishArt("番茄炒蛋", "burnt")).toBe(`${a}_burnt`);
    expect(dishArt("番茄炒蛋", "spoiled")).toBe(`${a}_burnt`);
    const vessels = new Set(["葱油拌面", "草莓大福", "味噌汤", "番茄炖牛腩", "冰镇酸梅汤", "蛋包饭"].map((n) => dishArt(n, null)));
    expect(vessels.size).toBeGreaterThan(1);
    for (const v of vessels) expect(v in FRIDGE_ART).toBe(true);
  });

  test("scaled to fit, on the bottom line, centred", () => {
    const box = fitInSlot({ x: 100, y: 200, w: 50, h: 100 }, { w: 100, h: 100 }, 0.5);
    expect(box).toEqual({ left: 37.5, top: 75, width: 25, height: 25 });
  });
});
