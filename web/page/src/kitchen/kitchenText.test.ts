// Words and merges of the kitchen page + reading the server's answers.
import { parseCatalog, parseFridgeState, toMs } from "./fridgeApi";
import { couponRule, dishOutcome, expiryText, fmtLeft, fmtStamp, groupCatalog, mealSlot, toggleSelect } from "./kitchenText";
import { setZone } from "../runtime/zone";
import type { KitchenSessionWire } from "./kitchenApi";

describe("ticking things on the grocery sheet", () => {
  test("tap to tick, tap again to untick, the order of ticking kept", () => {
    let sel: string[] = [];
    sel = toggleSelect(sel, "tomato");
    sel = toggleSelect(sel, "egg");
    expect(sel).toEqual(["tomato", "egg"]);
    sel = toggleSelect(sel, "tomato");
    expect(sel).toEqual(["egg"]);
    sel = toggleSelect(sel, "tomato");
    expect(sel).toEqual(["egg", "tomato"]);
  });

  test("the catalog by category: fixed order, no empty groups, unknown categories last", () => {
    const g = groupCatalog([
      { id: "egg", name: "鸡蛋", category: "dairy", packQty: 6, shelfDays: 5, custom: false, rawEdible: false, art: null },
      { id: "spinach", name: "菠菜", category: "leafy", packQty: 1, shelfDays: 2, custom: false, rawEdible: false, art: null },
      { id: "x", name: "怪东西", category: "weird", packQty: 1, shelfDays: 5, custom: false, rawEdible: false, art: null },
      { id: "tofu", name: "豆腐", category: "dairy", packQty: 1, shelfDays: 5, custom: false, rawEdible: false, art: null },
    ]);
    expect(g.map((x) => x.label)).toEqual(["叶菜", "蛋奶豆", "其他"]);
    expect(g[1].items.map((i) => i.id)).toEqual(["egg", "tofu"]);
  });
});

describe("how a dish on the table turned out", () => {
  const row = (dish: string, outcome: KitchenSessionWire["outcome"], served_at: number, menu_row_id: string | null): KitchenSessionWire => ({
    id: `${dish}-${served_at}`, dish, outcome, menu_row_id,
  });
  test("the menu row id is matched against a pot's menu_row_id", () => {
    const recent = [row("番茄炒蛋", "great", 100, "m1"), row("番茄炒蛋", "burnt", 200, "m2")];
    expect(dishOutcome("m1", "", recent)).toBe("great");
    expect(dishOutcome("m2", "火候刚好", recent)).toBe("burnt");
  });
  test("a dish put up by hand with the name of a pot that burnt is not marked burnt (a past pot is never matched by name)", () => {
    const recent = [row("照烧鸡腿", "burnt", 200, "m1"), row("照烧鸡腿", "spoiled", 300, null)];
    expect(dishOutcome("m9", "饭后吃", recent)).toBeNull();
    expect(dishOutcome(null, "", recent)).toBeNull();
  });
  test("no match = only the row's own note is read", () => {
    expect(dishOutcome("m3", "糊了", [])).toBe("burnt");
    expect(dishOutcome("m3", "坏了", [])).toBe("spoiled");
    expect(dishOutcome("m3", "火候刚好", [row("葱油拌面", null, 1, "m3")])).toBe("great");
    expect(dishOutcome("m3", "饭后吃", [])).toBeNull();
  });
});

describe("words", () => {
  test("expiry: spoiled = that day; otherwise the day it keeps until; none given = empty", () => {
    const ms = new Date(2026, 9, 25, 12).getTime();
    expect(expiryText({ freshness: "bad", expiresAtMs: ms })).toBe("10.25");
    expect(expiryText({ freshness: "meh", expiresAtMs: ms })).toBe("到 10.25");
    expect(expiryText({ freshness: "fresh", expiresAtMs: null })).toBe("");
  });
  test("how much longer the role is dizzy", () => {
    expect(fmtLeft(30_000)).toBe("1 分钟");
    expect(fmtLeft(20 * 60_000)).toBe("20 分钟");
    expect(fmtLeft(80 * 60_000)).toBe("1 小时 20 分");
    expect(fmtLeft(120 * 60_000)).toBe("2 小时");
  });
  test("dates follow the kitchen's time zone when the server names one", () => {
    const ms = Date.UTC(2026, 9, 25, 16, 5);          // 01:05 on the 26th in Tokyo, 12:05 on the 25th in New York
    try {
      setZone("Asia/Tokyo");
      expect(fmtStamp(ms)).toBe("10.26 01:05");
      expect(mealSlot(ms)).toBe("夜");
      setZone("America/New_York");
      expect(fmtStamp(ms)).toBe("10.25 12:05");
      expect(mealSlot(ms)).toBe("午");
      setZone("Not/A_Zone");                            // unknown name: the visitor's own zone
      expect(fmtStamp(ms)).toBe(fmtStamp(ms));
    } finally {
      setZone("");
    }
  });
  test("the line on the coupon follows the server's limit", () => {
    expect(couponRule(5)).toBe("一张买一次 · 最多五样");
    expect(couponRule(3)).toBe("一张买一次 · 最多三样");
    expect(couponRule(12)).toBe("一张买一次 · 最多 12 样");
  });
  test("the part of the day a meal fell in", () => {
    const at = (h: number) => new Date(2026, 9, 25, h).getTime();
    expect([7, 12, 18, 23, 2].map((h) => mealSlot(at(h)))).toEqual(["早", "午", "晚", "夜", "夜"]);
  });
});

describe("reading answers", () => {
  test("times: seconds / milliseconds / ISO all become milliseconds", () => {
    expect(toMs(1_800_000_000)).toBe(1_800_000_000_000);
    expect(toMs(1_800_000_000_000)).toBe(1_800_000_000_000);
    expect(toMs("2026-10-25T00:00:00Z")).toBe(Date.UTC(2026, 9, 25));
    expect(toMs(null)).toBeNull();
  });
  test("the fridge answer is read field by field; a wrong shape = null", () => {
    const st = parseFridgeState(
      {
        now: 1_800_000_000, who: "birch",
        items: [{ batch_id: 3, item_id: "egg", name: "鸡蛋", category: "dairy", qty: 6, bought_at: 1_799_990_000, by: "her", expires_at: 1_800_100_000, freshness: "meh" }, { name: "坏行" }],
        staples: ["米", "油", "盐", "酱油"], coupons: { count: 2, max: 3 },
        log: [{ at: 1_799_999_000, kind: "bought", text: "用户买了鸡蛋" }, { at: 1, kind: "x" }],
        satiety: { value: 80.4, updated_at: 1_800_000_000 }, dizzy: { until: 1_800_005_000, dish: "番茄炒蛋" },
      },
      "aster",
    );
    expect(st?.viewer).toBe("birch");
    expect(st?.items).toHaveLength(1);
    expect(st?.items[0]).toMatchObject({ batchId: "3", itemId: "egg", qty: 6, freshness: "meh", expiresAtMs: 1_800_100_000_000 });
    expect(st?.coupons).toEqual({ count: 2, max: 3 });
    expect(st?.log).toEqual([{ atMs: 1_799_999_000_000, kind: "bought", text: "用户买了鸡蛋" }]);
    expect(st?.satiety).toBe(80);
    expect(st?.dizzy).toEqual({ untilMs: 1_800_005_000_000, dish: "番茄炒蛋" });
    expect(parseFridgeState({ detail: "Not Found" }, "aster")).toBeNull();
    expect(parseFridgeState({ items: [], satiety: null, dizzy: null }, "aster")).toMatchObject({ viewer: "aster", satiety: null, dizzy: null, coupons: { count: 0, max: 3 } });
    // satiety switched off on the server: no number at all
    expect(parseFridgeState({ items: [], satiety: { value: 55, enabled: false } }, "aster")?.satiety).toBeNull();
  });
  test("the catalog", () => {
    expect(parseCatalog([{ id: "egg", name: "鸡蛋", category: "dairy", pack_qty: 6, shelf_days: 5 }, { name: "无 id" }])).toEqual([
      { id: "egg", name: "鸡蛋", category: "dairy", packQty: 6, shelfDays: 5, custom: false, rawEdible: false, art: null },
    ]);
    expect(parseCatalog({ nope: 1 })).toBeNull();
  });
});
