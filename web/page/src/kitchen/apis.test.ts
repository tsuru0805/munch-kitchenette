// The data layer against the server: reading its answers (a fixture written by the real server code,
// see scripts/contract_fixture.py), request deadlines, and the potion's small rules.
jest.mock("../runtime/session", () => ({
  getConn: () => ({ base: "http://kitchen.test", token: "tok" }),
  authHeaders: () => ({ Authorization: "Bearer tok" }),
}));

import fixture from "./__fixtures__/server_contract.json";
import { FRIDGE_TIMEOUT_MS, TIMEOUT_TEXT, buyItems, parseCatalog, parseFridgeState } from "./fridgeApi";
import { parseAbout, parseMeals, parseOutcome, parseRecent } from "./kitchenApi";
import { cleanMemo, isPotionName, parsePct, parsePotionBook, potionNote } from "./potionApi";
import { parseSnackState } from "./snacksApi";
import { FRIDGE_ART } from "./art.generated";

describe("the server's answers (contract fixture)", () => {
  test("the fridge parses with every field", () => {
    const s = parseFridgeState(fixture.fridge, "other")!;
    expect(s.viewer).toBe("aster");
    expect(s.items.map((i) => i.itemId).sort()).toEqual(["egg", "spinach", "udon"]);
    expect(s.items.find((i) => i.itemId === "egg")!.qty).toBe(6);
    expect(s.items.every((i) => i.boughtAtMs! > 1e12 && i.expiresAtMs! > i.boughtAtMs!)).toBe(true);
    expect(s.items.every((i) => i.by === "her")).toBe(true);
    expect(s.coupons).toEqual({ count: 1, max: 3 });
    expect(s.staples).toEqual(["米", "油", "盐", "酱油"]);
    expect(s.satiety).toBe(60);
    expect(s.dizzy?.dish).toBe("坏汤");
    expect(s.log.length).toBeGreaterThan(0);
    expect(s.log.some((l) => l.kind === "coupon")).toBe(true);
  });

  test("every built-in ingredient has its three pictures", () => {
    const c = parseCatalog(fixture.catalog)!;
    expect(c.length).toBeGreaterThan(30);
    expect(c.every((x) => !x.custom && x.art === null)).toBe(true);
    const missing = c.flatMap((x) => ["fresh", "meh", "bad"].map((f) => `${x.id}_${f}`)).filter((k) => !(k in FRIDGE_ART));
    expect(missing).toEqual([]);
    expect(c.find((x) => x.id === "apple")!.rawEdible).toBe(true);
    expect(c.find((x) => x.id === "lemon")!.rawEdible).toBe(false);
  });

  test("kinds the human added say so, with the state of their picture", () => {
    const c = parseCatalog(fixture.catalog_kinds)!;
    const kaki = c.find((x) => x.name === "柿子")!;
    expect(kaki).toMatchObject({ category: "fruit", custom: true, rawEdible: true, packQty: 1 });
    expect(kaki.art).toEqual({ state: "none", v: 0, sizes: {}, err: "" });       // no art provider configured: a text card
    const s = parseFridgeState(fixture.fridge_kinds, "aster")!;
    expect(s.items.find((i) => i.name === "柿子")!.art!.state).toBe("none");
    expect(s.items.find((i) => i.name === "鸡蛋")!.art).toBeNull();
  });

  test("every snack on the default shelf has a picture, coffee one per flavour", () => {
    const s = parseSnackState(fixture.snacks)!;
    expect(s.viewer).toBe("aster");
    expect(s.energyEnabled).toBe(true);
    for (const sn of s.snacks) {
      const keys = sn.variants.length ? sn.variants.map((v) => `snack_${sn.id}_${v.id}`) : [`snack_${sn.id}`];
      expect(keys.filter((k) => !(k in FRIDGE_ART))).toEqual([]);
    }
  });

  test("potions, about, meals, and how a pot turned out", () => {
    const book = parsePotionBook(fixture.potions)!;
    expect(book.enabled).toBe(true);
    expect(Object.values(book.byRow)).toEqual([30]);
    expect(isPotionName(book.name)).toBe(true);
    expect(potionNote(book, 30, "困了就喝")).toBe(fixture.potion_row_note);
    const about = parseAbout(fixture.about)!;
    expect(about).toMatchObject({ defaultRole: "companion", stamina: true, satiety: true, devClock: false, hungryBelow: 30, buyMaxItems: 5 });
    expect(about.roles).toEqual(expect.arrayContaining(["aster", "companion"]));
    expect(parseMeals(fixture.meals).map((m) => m.meal)).toEqual(["茄汁滑蛋"]);
    const pot = parseRecent(fixture.kitchen)[0];
    expect(pot.outcome).toBe(parseOutcome(fixture.kitchen.recent[0].outcome));
    expect(pot.menu_row_id).toBe(String(fixture.kitchen.recent[0].menu_row_id));
  });

  test("switched off on the server", () => {
    expect(parseAbout(fixture.about_off)).toMatchObject({ stamina: false, satiety: false, devClock: true });
    expect(parseFridgeState(fixture.fridge_off, "aster")!.satiety).toBeNull();
    expect(parsePotionBook(fixture.potions_off)!.enabled).toBe(false);
    expect(parseSnackState(fixture.snacks_off)!.energyEnabled).toBe(false);
  });
});

describe("the potion's rules", () => {
  const book = parsePotionBook({ name: "精力补充药剂", note_fmt: "回 {pct}% 体力", memo_sep: " · ", memo_max: 10, pct_min: 1, enabled: true, items: [] })!;
  test("the reserved name, blanks and case ignored", () => {
    expect(isPotionName(" 精力 补充药剂\n")).toBe(true);
    expect(isPotionName("精力补充药剂 加强版")).toBe(false);
  });
  test("the amount: a whole number from the minimum up; a slip of a million or more is refused", () => {
    expect(parsePct(" 30 ", book)).toBe(30);
    for (const bad of ["", "0", "-5", "3.5", "abc", "1000001", "12345678"]) expect(parsePct(bad, book)).toBeNull();
    expect(parsePct("1000000", book)).toBe(1_000_000);
  });
  test("the memo: one line, trimmed, cut to the limit", () => {
    expect(cleanMemo(book, "  困了\n就喝  ")).toBe("困了 就喝");
    expect(cleanMemo(book, "一二三四五六七八九十多出来的")).toBe("一二三四五六七八九十");
    expect(potionNote(book, 20)).toBe("回 20% 体力");
  });
});

test("a body cut off by the deadline is a timeout, not a success", async () => {
  jest.useFakeTimers();
  try {
    let jsonCalled!: () => void;
    const reading = new Promise<void>((res) => (jsonCalled = res));
    (global as { fetch: unknown }).fetch = jest.fn(async (_u: string, opts: { signal: AbortSignal }) => ({
      ok: true,
      status: 200,
      json: () => {
        jsonCalled();   // the headers are in and the body is being read
        return new Promise((_, reject) =>
          opts.signal.addEventListener("abort", () => reject(Object.assign(new Error("Aborted"), { name: "AbortError" }))),
        );
      },
    }));
    const settled = buyItems("aster", ["egg"]).then(() => "ok", (e: Error) => e.message);
    await reading;                              // only let the deadline pass once the body is really being read
    jest.advanceTimersByTime(FRIDGE_TIMEOUT_MS);
    expect(await settled).toBe(TIMEOUT_TEXT);
  } finally {
    jest.useRealTimers();
  }
});
