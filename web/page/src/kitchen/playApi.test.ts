// The upgrade's answers as the real server writes them (scripts/contract_fixture.py), and which
// entrances the page shows for which switches.
jest.mock("../runtime/session", () => ({
  getConn: () => ({ base: "http://kitchen.test", token: "tok" }),
  authHeaders: () => ({ Authorization: "Bearer tok" }),
}));

import fixture from "./__fixtures__/server_contract.json";
import { NO_FEATURES, parseBook, parseDex, parseFeatures, parseRecipes, parseVendor, visibleTabs } from "./playApi";

describe("the upgrade's answers (contract fixture)", () => {
  test("out of the box: ten on, seven off, and the entrances that follow", () => {
    const f = parseFeatures(fixture.features_default);
    expect(Object.values(f).filter(Boolean).length).toBe(10);
    expect(f.vendor || f.dishwash || f.seal_jars).toBe(false);
    expect(visibleTabs(f)).toEqual(["recipes", "dex", "achievements"]);   // no vendors, so no pocket money either
  });

  test("everything off: no entrance at all", () => {
    expect(visibleTabs(NO_FEATURES)).toEqual([]);
    expect(visibleTabs(parseFeatures({ features: "nonsense" }))).toEqual([]);
  });

  test("everything on", () => {
    expect(visibleTabs(parseFeatures(fixture.features))).toEqual(["recipes", "dex", "achievements", "vendor", "pocket", "plates", "jars"]);
  });

  test("recipes, the book, the dish book and the vendor parse", () => {
    const r = parseRecipes(fixture.recipes);
    expect(r.total).toBeGreaterThan(300);
    expect(r.recipes.length).toBe(3);
    expect(r.recipes.every((x) => x.id.startsWith("hc-") && x.minutes > 0)).toBe(true);
    const book = parseBook(fixture.book);
    expect(book.map((p) => p.kind).sort()).toEqual(["fav", "own"]);
    expect(book.find((p) => p.kind === "own")!.note).toBe("夏天吃");
    expect(book.find((p) => p.kind === "own")!.itemsText).toBe("黄瓜");          // names, not catalog ids
    const dex = parseDex(fixture.dex);
    expect(dex.pages.map((p) => p.name)).toEqual(["煎蛋", "蒸水蛋"]);   // a pot from before the upgrade is read too
    expect(dex.pages[1].made).toBe(1);
    expect(dex.achievements.length).toBeGreaterThanOrEqual(10);
    const v = parseVendor(fixture.vendor);
    expect(v.visit!.who).toBe("卖糖葫芦的");
    expect(v.visit!.goods.some((g) => g.kind === "snack" && g.price > 0)).toBe(true);
    expect(v.localWallet).toBe(true);
  });
});
