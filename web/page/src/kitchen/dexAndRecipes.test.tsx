// The dish book with pictures (a drawn picture, the pixel dish standing in, the grey silhouette of a dish
// only collected, redrawing, switching back to an older picture, merging an unsorted dish and taking it
// back out), and the recipe settings (ingredients not to recommend, a recipe with a mistake stopped and
// put back, what a recipe lacks bought in one go), plus the answers they read (contract fixture).
import { readFileSync } from "node:fs";
import { join } from "node:path";

const mockConfirm = jest.fn((a: { onYes: () => void }) => a.onYes());
jest.mock("../runtime/store", () => ({ useStore: () => ({ role: "aster", tick: 0, confirm: mockConfirm }) }));
jest.mock("../runtime/session", () => ({
  getConn: () => ({ base: "http://kitchen.test", token: "tok" }),
  authHeaders: () => ({ Authorization: "Bearer tok" }),
}));
const mockFetch = jest.fn();
beforeAll(() => Object.defineProperty(globalThis, "fetch", { value: (...a: unknown[]) => mockFetch(...a), configurable: true, writable: true }));

import TestRenderer, { act } from "react-test-renderer";
import { _fetchHeadedPictures } from "./authedImage";
import { _resetInflight } from "./fridgeApi";
import { Image, Text } from "react-native";
import fixture from "./__fixtures__/server_contract.json";
import { DISH_ICON, DISH_ICON_KINDS, cellScale, dishIcon } from "./dishIcons";
import { DexTab, RecipesTab, VendorTab, findIngredient } from "./PlaySheet";
import {
  NO_FEATURES, missingToBuy, parseDex, parseDexArt, parseLedger, parseMissing, parseStopped, unsortedDish, type Features,
} from "./playApi";

const repo = join(__dirname, "..", "..", "..", "..");

const texts = (r: TestRenderer.ReactTestRenderer) =>
  r.root.findAllByType(Text).map((t) => [t.props.children].flat(9).filter((x) => typeof x === "string" || typeof x === "number").join(""));
const byId = (r: TestRenderer.ReactTestRenderer, id: string) => r.root.findAll((n) => n.props.testID === id && typeof n.type === "string");
const press = async (r: TestRenderer.ReactTestRenderer, id: string) => {
  const n = r.root.find((x) => x.props.testID === id && typeof x.props.onPress === "function");
  await act(async () => {
    n.props.onPress();
  });
};

/** A server in memory: answers by method and path, records the writes */
/** Every request seen: method, path, headers */
let calls: { m: string; path: string; headers: Record<string, string> }[] = [];
/** A route answering a picture (bytes) or a bare status */
const PICTURE = { __picture: true };
const STATUS = (n: number) => ({ __status: n });

function serve(routes: Record<string, (body?: Record<string, unknown>) => unknown>) {
  const writes: [string, string, unknown][] = [];
  mockFetch.mockImplementation(async (url: string, init?: { method?: string; body?: string; headers?: Record<string, string> }) => {
    const path = url.replace("http://kitchen.test", "");
    const m = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    calls.push({ m, path, headers: { ...(init?.headers ?? {}) } });
    if (m !== "GET") writes.push([m, path, body]);
    const key = Object.keys(routes).find((k) => {
      const [km, kp] = k.split(" ");
      return km === m && path.startsWith(kp);
    });
    if (!key) return { ok: false, status: 404, json: async () => ({ detail: `no route for ${m} ${path}` }) };
    const out = await routes[key](body);
    if (out && typeof out === "object" && "__status" in out) {
      const n = (out as { __status: number }).__status;
      return { ok: false, status: n, json: async () => ({ detail: "no" }), blob: async () => null };
    }
    if (out === PICTURE) return { ok: true, status: 200, json: async () => null, blob: async () => ({ size: 3, type: "image/png" }) };
    return { ok: true, status: 200, json: async () => out };
  });
  return writes;
}

/** An answer held back until the test lets it go */
function later<T>(value: T): { promise: Promise<T>; go: () => void } {
  let go!: () => void;
  const promise = new Promise<T>((res) => {
    go = () => res(value);
  });
  return { promise, go };
}

beforeEach(() => {
  calls = [];
  _resetInflight();
  mockFetch.mockReset();
  mockConfirm.mockClear();
});

describe("the answers (contract fixture)", () => {
  test("dish book pages name their pixel dish; no picture drawn yet = none chosen; silhouettes carry theirs", () => {
    const d = parseDex(fixture.dex);
    expect(d.pages.map((p) => [p.name, p.icon])).toEqual([["煎蛋", "friedegg"], ["蒸水蛋", "steamer"]]);
    expect(d.pages.every((p) => p.art.chosen === null && p.art.ready.length === 0 && !p.art.drawing && p.art.failed === null)).toBe(true);
    expect(d.pages.every((p) => p.mergedIn.length === 0)).toBe(true);
    expect(d.pages[0].firstAt).toBeGreaterThan(1e9);
  });
  test("a page's pictures: ready versions, the chosen one, one being drawn, a failure and why", () => {
    expect(parseDexArt({ versions: [{ version: 1, state: "ready" }, { version: 2, state: "ready" }, { version: 3, state: "pending" }], chosen: 1 }))
      .toEqual({ chosen: 1, ready: [1, 2], drawing: true, failed: null });
    expect(parseDexArt({ versions: [{ version: 1, state: "failed", err: "ValueError: no" }], chosen: null }))
      .toEqual({ chosen: null, ready: [], drawing: false, failed: "ValueError: no" });
    expect(parseDexArt(null)).toEqual({ chosen: null, ready: [], drawing: false, failed: null });
  });
  test("merged dishes are listed on the page they went to", () => {
    const d = parseDex({ pages: [{ key: "r:x", name: "蒸水蛋" }], merges: [{ dish: "我家的蛋", page_key: "r:x" }, { dish: "别的", page_key: "r:y" }] });
    expect(d.pages[0].mergedIn).toEqual(["我家的蛋"]);
    expect(unsortedDish("d:我家的蛋")).toBe("我家的蛋");
  });
  test("stopped recipes, what a recipe lacks, the vendor ledger", () => {
    expect(parseStopped(fixture.stopped)).toEqual([{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", why: "写错了" }]);
    const m = parseMissing(fixture.missing);
    expect(m.missing).toEqual([{ itemId: "tomato", name: "番茄", short: 1, sold: true, packs: 1 }]);
    expect(missingToBuy([...m.missing, { itemId: "v_x", name: "小贩才有", short: 1, sold: false, packs: 1 }, { itemId: "egg", name: "鸡蛋", short: 7, sold: true, packs: 2 }]))
      .toEqual(["tomato", "egg", "egg"]);
    const l = parseLedger(fixture.ledger);
    expect(l).toHaveLength(1);
    expect(l[0]).toMatchObject({ name: "山楂糖葫芦", qty: 1, total: 5, payer: "her", state: "delivered" });
    expect(fixture.prefs.dislike).toEqual(["spinach"]);
    expect(fixture.prefs_add.dislike).toEqual(["egg", "spinach"]);          // one at a time, the whole list back
    expect(fixture.prefs_remove.dislike).toEqual(["egg"]);
    expect(new Set([fixture.prefs.version, fixture.prefs_add.version, fixture.prefs_remove.version]).size).toBe(3);
    expect(fixture.buy_missing.replayed).toBe(false);
    expect(parseMissing(fixture.buy_missing).missing).toEqual([]);          // what is still missing after buying
    expect(fixture.buy_missing.added.length).toBeGreaterThan(0);
  });
});

describe("the pixel dishes", () => {
  test("the same fourteen kinds as the server's rules, each file the size written here", () => {
    const rules = JSON.parse(readFileSync(join(repo, "src", "kitchenette", "data", "dish_icons.json"), "utf8"));
    expect([...DISH_ICON_KINDS].sort()).toEqual([...rules.kinds].sort());
    for (const k of DISH_ICON_KINDS) {
      const png = readFileSync(join(repo, "assets", "clawd", "dishes", `${k}_cells.png`));
      expect([k, png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([k, DISH_ICON[k].w, DISH_ICON[k].h]);
    }
  });
  test("an unknown kind is the plain bowl; whole cells only", () => {
    expect(dishIcon("nonsense")).toBe(DISH_ICON.bowl);
    expect(dishIcon(undefined)).toBe(DISH_ICON.bowl);
    expect(cellScale(13, 8, 52)).toBe(4);
    expect(cellScale(12, 12, 50)).toBe(4);
    expect(cellScale(40, 40, 10)).toBe(1);
  });
});

const page = (key: string, name: string, over: Record<string, unknown> = {}) => ({
  key, name, first_at: 1795309615, made: 1, good: 1, eaten: 0, best: "great", method: "steam", ingredients: ["鸡蛋"],
  pending: false, human_note: "", role_note: "", icon: "steamer", art: null, ...over,
});

describe("the dish book", () => {
  const book = (drawing: boolean, pages: unknown[], extra: Record<string, unknown> = {}) => ({
    pages, silhouettes: [{ recipe_id: "hc-wings", name: "可乐鸡翅", icon: "meat" }],
    totals: { public: 320, made_public: 1, art_missing: 1 }, drawing, merges: [], ...extra,
  });

  test("a drawn picture, a pixel dish where there is none, a grey one for a dish only collected", async () => {
    serve({
      "GET /api/dex": () => book(true, [
        page("r:egg", "蒸水蛋", { art: { versions: [{ version: 1, state: "ready" }, { version: 2, state: "ready" }], chosen: 2 }, role_note: "嫩", human_note: "好吃" }),
        page("d:我家的蛋", "我家的蛋", { pending: true, icon: "friedegg" }),
      ]),
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<DexTab say={() => {}} />);
    });
    const imgs = r.root.findAllByType(Image);
    const drawn = imgs.find((i) => typeof i.props.source === "object" && String((i.props.source as { uri?: string }).uri).includes("/api/dex/art"));
    expect((drawn!.props.source as { uri: string; headers: Record<string, string> })).toEqual({
      uri: "http://kitchen.test/api/dex/art?page_key=r%3Aegg&version=2", headers: { Authorization: "Bearer tok" },
    });
    expect(byId(r, "dex-placeholder-d:我家的蛋")).toHaveLength(1);
    const ghost = byId(r, "dex-ghost-hc-wings");
    expect(ghost).toHaveLength(1);
    const ghostImg = r.root.findAllByType(Image).find((i) => [i.props.style].flat().some((s) => s && (s as { tintColor?: string }).tintColor));
    expect(ghostImg).toBeTruthy();
    const t = texts(r).join("\n");
    expect(t).toContain("收藏了还没做");
    expect(t).toContain("可乐鸡翅");
    expect(t).toContain("第一次");
    expect(t).toContain("他:「嫩」");
    expect(t).toContain("评语:好吃");
    expect(t).toContain("还差 1 张图");
  });

  test("with a token, the picture is fetched with it and shown from an object URL (released after); a refused one leaves the pixel dish", async () => {
    _fetchHeadedPictures(true);
    const made: string[] = [];
    const released: string[] = [];
    const urlSpy = jest.spyOn(URL, "createObjectURL" as never).mockImplementation((() => {
      made.push(`blob:pic-${made.length + 1}`);
      return made[made.length - 1];
    }) as never);
    const revSpy = jest.spyOn(URL, "revokeObjectURL" as never).mockImplementation(((u: string) => released.push(u)) as never);
    try {
      serve({
        "GET /api/dex/art?page_key=r%3Aegg": () => PICTURE,
        "GET /api/dex/art?page_key=r%3Abad": () => STATUS(401),
        "GET /api/dex": () => book(true, [
          page("r:egg", "蒸水蛋", { art: { versions: [{ version: 1, state: "ready" }], chosen: 1 } }),
          page("r:bad", "坏图", { art: { versions: [{ version: 1, state: "ready" }], chosen: 1 } }),
        ]),
      });
      let r!: TestRenderer.ReactTestRenderer;
      await act(async () => {
        r = TestRenderer.create(<DexTab say={() => {}} />);
      });
      await act(async () => {});
      const art = calls.filter((c) => c.path.startsWith("/api/dex/art"));
      expect(art.map((c) => c.headers.Authorization)).toEqual(["Bearer tok", "Bearer tok"]);
      const shown = r.root.findAllByType(Image).map((i) => (i.props.source as { uri?: string }).uri).filter(Boolean);
      expect(shown).toEqual(["blob:pic-1"]);                         // no address with the token-less request in it
      expect(byId(r, "dex-placeholder-r:bad")).toHaveLength(1);      // 401: the pixel dish stays
      expect(byId(r, "dex-placeholder-r:egg")).toHaveLength(0);
      act(() => r.unmount());
      expect(released).toEqual(["blob:pic-1"]);
    } finally {
      _fetchHeadedPictures(false);
      urlSpy.mockRestore();
      revSpy.mockRestore();
    }
  });

  test("a page never drawn is drawn by itself (no redraw); a failed one can be redrawn", async () => {
    serve({
      "GET /api/dex": () => book(true, [
        page("r:a", "甲"),
        page("r:b", "乙", { art: { versions: [{ version: 1, state: "failed", err: "超时" }], chosen: null } }),
      ]),
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<DexTab say={() => {}} />);
    });
    expect(byId(r, "dex-redraw-r:a")).toHaveLength(0);
    expect(byId(r, "dex-redraw-r:b").length).toBeGreaterThan(0);
  });

  test("redraw asks for a new version; switching back chooses an older one", async () => {
    const writes = serve({
      "GET /api/dex": () => book(true, [page("r:egg", "蒸水蛋", { art: { versions: [{ version: 1, state: "ready" }, { version: 2, state: "ready" }], chosen: 2 } })]),
      "POST /api/dex/art/redraw": () => ({ version: 3 }),
      "PUT /api/dex/art/choice": () => ({ ok: true }),
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<DexTab say={() => {}} />);
    });
    await press(r, "dex-redraw-r:egg");
    await press(r, "dex-versions-r:egg");
    expect(byId(r, "dex-art-r:egg-1")).toHaveLength(1);       // the older picture is shown to pick from
    await press(r, "dex-version-r:egg-1");
    expect(writes).toEqual([
      ["POST", "/api/dex/art/redraw", { page_key: "r:egg" }],
      ["PUT", "/api/dex/art/choice", { page_key: "r:egg", version: 1 }],
    ]);
  });

  test("with no picture drawer: no redraw, the being-drawn and failed lines when there are", async () => {
    serve({
      "GET /api/dex": () => book(false, [
        page("r:a", "甲", { art: { versions: [{ version: 1, state: "failed", err: "超时" }], chosen: null } }),
      ]),
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<DexTab say={() => {}} />);
    });
    expect(byId(r, "dex-redraw-r:a")).toHaveLength(0);         // nothing draws here: no redraw
    expect(byId(r, "dex-placeholder-r:a")).toHaveLength(1);
    expect(texts(r)).toContain("没画成:超时");
    expect(texts(r).join("")).not.toContain("还差");
  });

  test("an unsorted dish is merged into a page, and taken back out from that page", async () => {
    let merged = false;
    const writes = serve({
      "GET /api/dex": () => (merged
        ? book(false, [page("r:egg", "蒸水蛋", { made: 2 })], { merges: [{ dish: "我家的蛋", page_key: "r:egg" }] })
        : book(false, [page("r:egg", "蒸水蛋"), page("d:我家的蛋", "我家的蛋", { pending: true })])),
      "PUT /api/dex/merge": (b) => {
        merged = b!.page_key === "r:egg";
        return { ok: true };
      },
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<DexTab say={() => {}} />);
    });
    expect(byId(r, "dex-merge-r:egg")).toHaveLength(0);       // only an unsorted page can be merged
    await press(r, "dex-merge-d:我家的蛋");
    await press(r, "dex-merge-to-r:egg");
    expect(texts(r)).toContain("并进来的:我家的蛋");
    await press(r, "dex-unmerge-我家的蛋");
    expect(writes).toEqual([
      ["PUT", "/api/dex/merge", { who: "aster", dish: "我家的蛋", page_key: "r:egg" }],
      ["PUT", "/api/dex/merge", { who: "aster", dish: "我家的蛋", page_key: "d:我家的蛋" }],
    ]);
  });
});

describe("merging one unsorted dish after another", () => {
  test("only sorted pages are offered; two unsorted dishes merged one after the other both land there and both can be taken back", async () => {
    const merges = new Map<string, string>();
    const pages = () => {
      const all = [
        { key: "r:c", name: "蒸水蛋", pending: false },
        { key: "d:甲", name: "甲", pending: true },
        { key: "d:乙", name: "乙", pending: true },
      ];
      return all.filter((p) => !merges.has(p.name)).map((p) => page(p.key, p.name, { pending: p.pending }));
    };
    const writes = serve({
      "GET /api/dex": () => ({ pages: pages(), silhouettes: [], totals: {}, drawing: false,
        merges: [...merges].filter(([d, k]) => k !== `d:${d}`).map(([dish, page_key]) => ({ dish, page_key })) }),
      "PUT /api/dex/merge": (b) => {
        merges.set(String(b!.dish), String(b!.page_key));
        if (b!.page_key === `d:${b!.dish}`) merges.delete(String(b!.dish));
        return { ok: true };
      },
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<DexTab say={() => {}} />);
    });
    await press(r, "dex-merge-d:甲");
    expect(byId(r, "dex-merge-to-d:乙")).toHaveLength(0);           // never onto another unsorted page
    await press(r, "dex-merge-to-r:c");
    await press(r, "dex-merge-d:乙");
    expect(byId(r, "dex-merge-to-d:甲")).toHaveLength(0);
    await press(r, "dex-merge-to-r:c");
    expect(texts(r)).toEqual(expect.arrayContaining(["并进来的:甲", "并进来的:乙"]));
    await press(r, "dex-unmerge-甲");
    expect(byId(r, "dex-page-d:甲")).toHaveLength(1);
    expect(texts(r)).toContain("并进来的:乙");
    expect(writes.map((w) => (w[2] as { page_key: string }).page_key)).toEqual(["r:c", "r:c", "d:甲"]);
  });
});

describe("the recipe settings", () => {
  const on = (...keys: (keyof Features)[]): Features => ({ ...NO_FEATURES, ...Object.fromEntries(keys.map((k) => [k, true])) });
  const catalog = { items: [{ id: "cilantro", name: "香菜", category: "leafy" }, { id: "egg", name: "鸡蛋", category: "dairy" }, { id: "tomato", name: "番茄", category: "veg" }] };

  test("a typed ingredient is found by its name, or by the only name that contains it", () => {
    const c = [{ id: "a", name: "小葱" }, { id: "b", name: "葱头" }, { id: "c", name: "鸡蛋" }] as never[];
    expect(findIngredient(c, " 鸡蛋 ")).toMatchObject({ id: "c" });
    expect(findIngredient(c, "蛋")).toMatchObject({ id: "c" });
    expect(findIngredient(c, "葱")).toBeNull();            // two contain it: say so rather than guess
    expect(findIngredient(c, "")).toBeNull();
  });

  test("dislikes are added and taken off one at a time (the server answers the whole list)", async () => {
    let dis: string[] = ["egg"];
    const writes = serve({
      "GET /api/prefs": () => ({ dislike: dis }),
      "POST /api/prefs/dislike": (b) => {
        dis = [...new Set([...dis, String(b!.item)])];
        return { dislike: dis };
      },
      "DELETE /api/prefs/dislike/": () => {
        dis = dis.filter((x) => x !== "egg");
        return { dislike: dis };
      },
      "GET /api/recipes/stopped": () => ({ recipes: [] }),
      "GET /api/fridge/catalog": () => catalog,
    });
    const said: string[] = [];
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public")} say={(m) => said.push(m)} onChanged={() => {}} />);
    });
    expect(texts(r)).toContain("鸡蛋");
    const input = r.root.find((n) => n.props.testID === "dislike-in" && typeof n.props.onChangeText === "function");
    await act(async () => input.props.onChangeText("香菜"));
    await press(r, "dislike-add");
    await press(r, "dislike-off-egg");
    await act(async () => input.props.onChangeText("榴莲"));
    await press(r, "dislike-add");
    expect(writes).toEqual([
      ["POST", "/api/prefs/dislike", { who: "aster", item: "cilantro" }],
      ["DELETE", "/api/prefs/dislike/egg?who=aster", undefined],
    ]);
    expect(said.at(-1)).toBe("厨房里没有『榴莲』这样食材");
    expect(texts(r)).toContain("香菜");
    expect(texts(r)).not.toContain("鸡蛋");
  });

  test("nothing can be added before the list was read; quick changes go one after another and the list shown is the last answer", async () => {
    const first = later({ dislike: ["egg"] });
    const held: ReturnType<typeof later<{ dislike: string[] }>>[] = [];
    // another page added 「番茄」 meanwhile: the server's answers carry it, the page never writes it away
    let server = ["egg", "tomato"];
    const writes = serve({
      "GET /api/prefs": () => first.promise,
      "POST /api/prefs/dislike": (b) => {
        server = [...new Set([...server, String(b!.item)])];
        const h = later({ dislike: [...server] });
        held.push(h);
        return h.promise;
      },
      "DELETE /api/prefs/dislike/": () => {
        server = server.filter((x) => x !== "egg");
        const h = later({ dislike: [...server] });
        held.push(h);
        return h.promise;
      },
      "GET /api/recipes/stopped": () => ({ recipes: [] }),
      "GET /api/fridge/catalog": () => catalog,
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public")} say={() => {}} onChanged={() => {}} />);
    });
    const addBtn = () => r.root.find((n) => n.props.testID === "dislike-add" && typeof n.props.onPress === "function");
    const input = () => r.root.find((n) => n.props.testID === "dislike-in" && typeof n.props.onChangeText === "function");
    expect(addBtn().props.disabled).toBe(true);
    await act(async () => input().props.onChangeText("香菜"));
    await press(r, "dislike-add");
    expect(writes).toEqual([]);                                     // the list is not in yet: nothing written
    await act(async () => first.go());
    expect(addBtn().props.disabled).toBe(false);
    await act(async () => input().props.onChangeText("香菜"));
    await press(r, "dislike-add");
    await press(r, "dislike-off-egg");
    expect(writes).toHaveLength(1);                                 // the second waits for the first answer
    await act(async () => held[0].go());
    await act(async () => {});
    expect(writes).toHaveLength(2);
    await act(async () => held[1].go());
    expect(writes.map((w) => [w[0], w[1]])).toEqual([["POST", "/api/prefs/dislike"], ["DELETE", "/api/prefs/dislike/egg?who=aster"]]);
    expect(texts(r)).toEqual(expect.arrayContaining(["番茄", "香菜"]));
    expect(texts(r)).not.toContain("鸡蛋");
    expect(server).toEqual(["tomato", "cilantro"]);                 // what the other page added is still there
  });

  test("「today you could try」 is read again after a recipe is stopped or put back and after a dislike changes", async () => {
    let todayText = "今天可以试试:西红柿炒鸡蛋";
    serve({
      "GET /api/recipes/today": () => ({ text: todayText }),
      "GET /api/prefs": () => ({ dislike: [] }),
      "POST /api/prefs/dislike": (b) => ({ dislike: [b!.item] }),
      "GET /api/fridge/catalog": () => catalog,
      "GET /api/recipes/stopped": () => ({ recipes: todayText.includes("蒸水蛋") ? [{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", why: "" }] : [] }),
      "GET /api/recipes?": () => ({ total: 320, recipes: [{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", method: "stirfry", minutes: 15 }] }),
      "PUT /api/recipes/": () => {
        todayText = "今天可以试试:蒸水蛋";
        return {};
      },
    });
    const todays = () => calls.filter((c) => c.path.startsWith("/api/recipes/today")).length;
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public", "recipes_today")} say={() => {}} onChanged={() => {}} />);
    });
    expect(todays()).toBe(1);
    await press(r, "recipe-search");
    await press(r, "stop-hc-d9b1068d");
    expect(todays()).toBe(2);
    expect(texts(r)).toContain("今天可以试试:蒸水蛋");
    expect(texts(r)).not.toContain("今天可以试试:西红柿炒鸡蛋");
    const input = r.root.find((n) => n.props.testID === "dislike-in" && typeof n.props.onChangeText === "function");
    await act(async () => input.props.onChangeText("鸡蛋"));
    await press(r, "dislike-add");
    expect(todays()).toBe(3);
    await press(r, "unstop-hc-d9b1068d");
    expect(todays()).toBe(4);
  });

  test("a recipe with a mistake is stopped from the search, listed, and put back", async () => {
    const stopped = new Set<string>();
    const writes = serve({
      "GET /api/prefs": () => ({ dislike: [] }),
      "GET /api/fridge/catalog": () => catalog,
      "GET /api/recipes/stopped": () => ({ recipes: [...stopped].map((id) => ({ id, name: "西红柿炒鸡蛋", why: "" })) }),
      "GET /api/recipes?": () => ({ total: 320, recipes: stopped.size ? [] : [{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", method: "stirfry", minutes: 15, items_text: "番茄、鸡蛋" }] }),
      "PUT /api/recipes/": (b) => {
        if (b!.stopped) stopped.add("hc-d9b1068d");
        else stopped.delete("hc-d9b1068d");
        return {};
      },
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public")} say={() => {}} onChanged={() => {}} />);
    });
    const q = r.root.find((n) => n.props.testID === "recipe-q" && typeof n.props.onChangeText === "function");
    await act(async () => q.props.onChangeText("番茄"));
    await press(r, "recipe-search");
    await press(r, "stop-hc-d9b1068d");
    expect(byId(r, "stop-hc-d9b1068d")).toHaveLength(0);          // gone from the search
    expect(byId(r, "unstop-hc-d9b1068d").length).toBeGreaterThan(0);
    await press(r, "unstop-hc-d9b1068d");
    expect(byId(r, "unstop-hc-d9b1068d")).toHaveLength(0);
    expect(byId(r, "stop-hc-d9b1068d").length).toBeGreaterThan(0);  // back in the search
    expect(writes).toEqual([
      ["PUT", "/api/recipes/hc-d9b1068d/stop", { stopped: true, why: "" }],
      ["PUT", "/api/recipes/hc-d9b1068d/stop", { stopped: false, why: "" }],
    ]);
  });

  test("what a recipe lacks, bought for the role in one go by the server; the panel then shows what is still missing", async () => {
    const writes = serve({
      "GET /api/prefs": () => ({ dislike: [] }),
      "GET /api/fridge/catalog": () => catalog,
      "GET /api/recipes/stopped": () => ({ recipes: [] }),
      "GET /api/recipes/missing": () => ({ name: "西红柿炒鸡蛋", missing: [
        { item_id: "tomato", name: "番茄", short: 1, sold: true, packs: 1 },
        { item_id: "egg", name: "鸡蛋", short: 8, sold: true, packs: 2 },
        { item_id: "v_hawthorn", name: "山楂", short: 1, sold: false, packs: 1 },
      ] }),
      "GET /api/recipes?": () => ({ total: 320, recipes: [{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", method: "stirfry", minutes: 15 }] }),
      "POST /api/recipes/buy_missing": () => ({ ok: true, text: "放进冰箱了", added: [{ name: "番茄", qty: 1 }],
        missing: [{ item_id: "v_hawthorn", name: "山楂", short: 1, sold: false, packs: 1 }] }),
    });
    const changed = jest.fn();
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public", "recipe_cook")} say={() => {}} onChanged={changed} />);
    });
    await press(r, "recipe-search");
    await press(r, "lack-hc-d9b1068d");
    expect(texts(r)).toEqual(expect.arrayContaining(["缺 番茄 1 · 买 1 份", "缺 鸡蛋 8 · 买 2 份", "缺 山楂 1 · 超市没有"]));
    await press(r, "lack-buy");
    expect(writes).toHaveLength(1);
    expect(writes[0][0]).toBe("POST");
    expect(writes[0][1]).toBe("/api/recipes/buy_missing");
    expect(writes[0][2]).toMatchObject({ who: "aster", recipe: "hc-d9b1068d", op_id: expect.any(String) });
    expect(changed).toHaveBeenCalled();
    expect(texts(r)).toContain("缺 山楂 1 · 超市没有");
    expect(texts(r)).not.toContain("缺 番茄 1 · 买 1 份");
    expect(byId(r, "lack-buy")).toHaveLength(0);                    // nothing left the shop sells
  });

  test("a retry after the connection dropped is the same buying (same op_id); the next buying is a new one", async () => {
    let drop = true;
    const writes = serve({
      "GET /api/prefs": () => ({ dislike: [] }),
      "GET /api/fridge/catalog": () => catalog,
      "GET /api/recipes/stopped": () => ({ recipes: [] }),
      "GET /api/recipes/missing": () => ({ name: "西红柿炒鸡蛋", missing: [{ item_id: "tomato", name: "番茄", short: 1, sold: true, packs: 1 }] }),
      "GET /api/recipes?": () => ({ total: 320, recipes: [{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", method: "stirfry", minutes: 15 }] }),
      "POST /api/recipes/buy_missing": () => {
        if (drop) {
          drop = false;
          throw new TypeError("network down");                    // no answer reached the page
        }
        return { ok: true, text: "放进冰箱了", added: [{ name: "番茄", qty: 1 }], missing: [{ item_id: "tomato", name: "番茄", short: 1, sold: true, packs: 1 }] };
      },
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public", "recipe_cook")} say={() => {}} onChanged={() => {}} />);
    });
    await press(r, "recipe-search");
    await press(r, "lack-hc-d9b1068d");
    await press(r, "lack-buy");                                     // dropped
    await press(r, "lack-buy");                                     // retried: answered
    await press(r, "lack-buy");                                     // a new buying
    const ops = writes.map((w) => (w[2] as { op_id: string }).op_id);
    expect(ops).toHaveLength(3);
    expect(ops[0]).toBe(ops[1]);
    expect(ops[2]).not.toBe(ops[1]);
  });

  test("while buying (and until the new list is on the panel) the old list cannot be bought from again", async () => {
    const held = later({ ok: true, text: "放进冰箱了", added: [{ name: "番茄", qty: 1 }], missing: [] });
    const writes = serve({
      "GET /api/prefs": () => ({ dislike: [] }),
      "GET /api/fridge/catalog": () => catalog,
      "GET /api/recipes/stopped": () => ({ recipes: [] }),
      "GET /api/recipes/missing": () => ({ name: "西红柿炒鸡蛋", missing: [{ item_id: "tomato", name: "番茄", short: 1, sold: true, packs: 1 }] }),
      "GET /api/recipes?": () => ({ total: 320, recipes: [{ id: "hc-d9b1068d", name: "西红柿炒鸡蛋", method: "stirfry", minutes: 15 }] }),
      "POST /api/recipes/buy_missing": () => held.promise,
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<RecipesTab f={on("recipes_public", "recipe_cook")} say={() => {}} onChanged={() => {}} />);
    });
    await press(r, "recipe-search");
    await press(r, "lack-hc-d9b1068d");
    await press(r, "lack-buy");
    const btn = () => r.root.find((n) => n.props.testID === "lack-buy" && typeof n.props.onPress === "function");
    expect(btn().props.disabled).toBe(true);
    expect(texts(r)).toContain("在买…");
    expect(texts(r)).toContain("缺 番茄 1 · 买 1 份");             // the old list is still shown, but locked
    await press(r, "lack-buy");
    await press(r, "lack-buy");
    expect(writes).toHaveLength(1);
    await act(async () => held.go());
    await act(async () => {});
    expect(writes).toHaveLength(1);
    expect(byId(r, "lack-none")).toHaveLength(1);                   // the answer's list is on the panel
  });
});

describe("the vendor ledger", () => {
  test("one line per order: what, how many, how much, who paid, how it stands", async () => {
    serve({
      "GET /api/vendor/ledger": () => fixture.ledger,
      "GET /api/vendor": () => ({ ...fixture.vendor, visit: null }),
    });
    let r!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      r = TestRenderer.create(<VendorTab say={() => {}} onChanged={() => {}} />);
    });
    expect(byId(r, "vendor-ledger")).toHaveLength(1);
    expect(texts(r).some((t) => t.includes("山楂糖葫芦×1 · 5 · 你请的 · 到手了"))).toBe(true);
  });
});
