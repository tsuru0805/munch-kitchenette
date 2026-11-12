// Ingredient kinds the human adds: which picture is used (bundled / drawn by the server / none yet = the
// first character of the name), where they go in the fridge, and the "添种类" form on the grocery sheet
// (add / the server's own sentence on failure / redraw / remove / quietly re-reading the catalog while a
// picture is being drawn). The server is a fake fetch throughout.
jest.mock("../runtime/session", () => ({
  getConn: () => ({ base: "http://kitchen.test", token: "tok" }),
  authHeaders: () => ({ Authorization: "Bearer tok" }),
}));

import TestRenderer, { act } from "react-test-renderer";
import { Image, Text } from "react-native";
import { ART_POLL_MS, BuySheet } from "./BuySheet";
import { _resetInflight, type ArtAuth, type FridgeItem, type KindArt } from "./fridgeApi";
import { artStatusText, draftToKind } from "./KindForm";
import { artOf, remoteArt } from "./kindArt";
import { FRIDGE_SLOTS, fridgePlacements } from "./sceneSlots";

const AUTH: ArtAuth = { base: "http://kitchen.test", headers: { Authorization: "Bearer tok" } };
const READY: KindArt = { state: "ready", v: 2, sizes: { fresh: { w: 256, h: 234 }, meh: { w: 256, h: 235 }, bad: { w: 256, h: 233 } }, err: "" };
const PENDING: KindArt = { state: "pending", v: 0, sizes: {}, err: "" };

describe("which picture", () => {
  test("a bundled one when there is one; an added kind from the server (with the token and the version); never drawn = none", () => {
    expect(artOf("tomato", "meh", null, AUTH)).toBe("tomato_meh");
    expect(artOf("u_kaki", "bad", READY, AUTH)).toEqual({
      src: { uri: "http://kitchen.test/api/fridge/art/u_kaki/bad.png?v=2", headers: { Authorization: "Bearer tok" } },
      w: 256,
      h: 233,
    });
    expect(artOf("u_kaki", "fresh", PENDING, AUTH)).toBeNull();
    expect(remoteArt("u_kaki", "fresh", READY, null)).toBeNull();
    // being redrawn: the old picture is still there (v > 0) and stands in
    expect(artOf("u_kaki", "fresh", { ...READY, state: "pending" }, AUTH)).not.toBeNull();
  });

  test("in the fridge: an added fruit goes on the middle shelf once it is drawn, and is not placed before", () => {
    const it = (itemId: string, art: KindArt | null): FridgeItem => ({
      batchId: itemId, itemId, name: itemId, category: "fruit", qty: 1, boughtAtMs: null, by: "her", expiresAtMs: null, freshness: "fresh", art,
    });
    const { placed, hidden } = fridgePlacements([it("u_kaki", READY), it("u_nashi", PENDING), it("apple", null)], AUTH);
    expect(placed.map((p) => p.key)).toEqual(["u_kaki", "apple"]);
    expect(placed[0].slot).toEqual(FRIDGE_SLOTS.veg[0]);
    expect(placed[1].art).toBe("apple_fresh");
    expect(hidden).toEqual(["u_nashi"]);
    expect(fridgePlacements([it("u_kaki", READY)]).hidden).toEqual(["u_kaki"]);     // no address / token to fetch with
  });
});

describe("the form's pure functions", () => {
  test("\"can be eaten as it is\" left untouched: yes for fruit, no for the rest; touched: as chosen", () => {
    const base = { name: " 柿子 ", pack: 1, days: null };
    expect(draftToKind({ ...base, category: "fruit", raw: null })).toEqual({ name: "柿子", category: "fruit", rawEdible: true, packQty: 1, shelfDays: null });
    expect(draftToKind({ ...base, category: "root", raw: null })!.rawEdible).toBe(false);
    expect(draftToKind({ ...base, category: "fruit", raw: false })!.rawEdible).toBe(false);
    expect(draftToKind({ ...base, name: "  ", category: "fruit", raw: null })).toBeNull();
    expect(draftToKind({ ...base, category: null, raw: null })).toBeNull();
  });

  test("the small words about the picture", () => {
    const row = (art: KindArt | null) => ({ id: "u", name: "柿子", category: "fruit", packQty: 1, shelfDays: 7, custom: true, rawEdible: true, art });
    expect(artStatusText(row(READY))).toBe("");
    expect(artStatusText(row(PENDING))).toBe("小图画着…");
    expect(artStatusText(row({ ...READY, state: "pending" }))).toBe("重画中…");
    expect(artStatusText(row({ state: "failed", v: 0, sizes: {}, err: "画了太久没画完" }))).toBe("没画成:画了太久没画完");
    expect(artStatusText(row({ state: "none", v: 0, sizes: {}, err: "" }))).toBe("");      // a server that draws no pictures: nothing to say
  });
});

// ── the sheet ────────────────────────────────────────────────────────

const fetchMock = jest.fn();
global.fetch = fetchMock as unknown as typeof fetch;
const resp = (status: number, body?: unknown) =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body ?? {} }) as Response;

const TOMATO = { id: "tomato", name: "番茄", category: "veg", pack_qty: 3, shelf_days: 5, raw_edible: true, custom: false };
const kaki = (art: unknown) => ({ id: "u_kaki", name: "柿子", category: "fruit", pack_qty: 1, shelf_days: 7, raw_edible: true, custom: true, art });
const ART_READY = { state: "ready", v: 1, sizes: { fresh: [256, 234], meh: [256, 235], bad: [256, 233] }, err: "" };
const ART_PENDING = { state: "pending", v: 0, sizes: {}, err: "" };

let catalog: unknown[] = [];
let kindReply: () => Response = () => resp(200, { ok: true });
const calls = (frag: string, method?: string) =>
  fetchMock.mock.calls.filter(([u, o]) => String(u).includes(frag) && (!method || (o as RequestInit | undefined)?.method === method));

beforeEach(() => {
  _resetInflight();
  fetchMock.mockReset();
  catalog = [TOMATO];
  kindReply = () => resp(200, { ok: true });
  fetchMock.mockImplementation(async (url: string) => {
    const u = String(url);
    if (u.includes("/api/fridge/kinds")) return kindReply();
    if (u.includes("/api/fridge/catalog")) return resp(200, catalog);
    return resp(404, {});
  });
});

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
};
async function mount() {
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    r = TestRenderer.create(
      <BuySheet open viewer="aster" auth={AUTH} onClose={() => {}} onBuy={async () => ({ kind: "done" })} onOrphanError={() => {}} />,
    );
  });
  await flush();
  return r;
}
const press = async (r: TestRenderer.ReactTestRenderer, testID: string) => {
  await act(async () => {
    r.root.findByProps({ testID }).props.onPress();
  });
  await flush();
};
const texts = (r: TestRenderer.ReactTestRenderer) => r.root.findAllByType(Text).map((t) => [t.props.children].flat(9).join(""));
const has = (r: TestRenderer.ReactTestRenderer, testID: string) => r.root.findAllByProps({ testID }).length > 0;

test("a tile on the grocery sheet: an added kind that is drawn = the server's picture; not drawn = the first character of its name", async () => {
  catalog = [TOMATO, kaki(ART_READY), { ...kaki(ART_PENDING), id: "u_nashi", name: "梨" }];
  const r = await mount();
  const uris = r.root.findAllByType(Image).map((i) => (i.props.source as { uri?: string }).uri).filter(Boolean);
  expect(uris).toEqual(["http://kitchen.test/api/fridge/art/u_kaki/fresh.png?v=1"]);
  expect(texts(r)).toContain("梨");
  await act(async () => r.unmount());
});

test("adding a kind: a name and \"fruit\" -> added (the right request body) -> the form is cleared and the catalog read again; back to buying", async () => {
  const r = await mount();
  expect(has(r, "kind-form")).toBe(false);
  await press(r, "buy-mode");
  expect(has(r, "kind-form")).toBe(true);
  expect(has(r, "buy-confirm")).toBe(false);
  expect(r.root.findByProps({ testID: "kind-add" }).props.disabled).toBe(true);
  await act(async () => {
    r.root.findByProps({ testID: "kind-name" }).props.onChangeText("柿子");
  });
  await press(r, "kind-cat-fruit");
  await press(r, "kind-pack-2");
  await press(r, "kind-days-14");
  catalog = [TOMATO, kaki(ART_PENDING)];
  await press(r, "kind-add");
  const post = calls("/api/fridge/kinds", "POST");
  expect(post).toHaveLength(1);
  expect(JSON.parse((post[0][1] as RequestInit).body as string)).toEqual({ name: "柿子", category: "fruit", raw_edible: true, pack_qty: 2, shelf_days: 14 });
  expect(r.root.findByProps({ testID: "kind-name" }).props.value).toBe("");
  expect(has(r, "kind-row-u_kaki")).toBe(true);
  expect(texts(r)).toContain("小图画着…");
  await press(r, "buy-mode");
  expect(has(r, "kind-form")).toBe(false);
  expect(has(r, "buy-u_kaki")).toBe(true);
  await act(async () => r.unmount());
});

test("it could not be added: the server's own sentence is shown right there and what was typed stays", async () => {
  kindReply = () => resp(409, { detail: "已经有苹果了。" });
  const r = await mount();
  await press(r, "buy-mode");
  await act(async () => {
    r.root.findByProps({ testID: "kind-name" }).props.onChangeText("苹果");
  });
  await press(r, "kind-cat-fruit");
  await press(r, "kind-add");
  expect(r.root.findByProps({ testID: "kind-err" }).props.children).toBe("已经有苹果了。");
  expect(r.root.findByProps({ testID: "kind-name" }).props.value).toBe("苹果");
  await act(async () => r.unmount());
});

test("added kinds: a failed picture says why; redraw and remove each send their request; a picture being drawn cannot be redrawn", async () => {
  catalog = [TOMATO, kaki({ state: "failed", v: 0, sizes: {}, err: "画了太久没画完" })];
  const r = await mount();
  await press(r, "buy-mode");
  expect(texts(r)).toContain("没画成:画了太久没画完");
  catalog = [TOMATO, kaki(ART_PENDING)];
  await press(r, "kind-redraw-u_kaki");
  expect(calls("/api/fridge/kinds/u_kaki/redraw", "POST")).toHaveLength(1);
  expect(r.root.findByProps({ testID: "kind-redraw-u_kaki" }).props.disabled).toBe(true);
  catalog = [TOMATO];
  await press(r, "kind-remove-u_kaki");
  expect(calls("/api/fridge/kinds/u_kaki", "DELETE")).toHaveLength(1);
  expect(has(r, "kind-row-u_kaki")).toBe(false);
  await act(async () => r.unmount());
});

test("the server's picture could not be fetched: the tile falls back to the first character, never an empty box", async () => {
  catalog = [TOMATO, kaki(ART_READY)];
  const r = await mount();
  const img = r.root.findAllByType(Image).find((i) => (i.props.source as { uri?: string }).uri?.includes("/art/u_kaki/"))!;
  expect(texts(r)).not.toContain("柿");
  await act(async () => {
    img.props.onError();
  });
  expect(texts(r)).toContain("柿");
  expect(r.root.findAllByType(Image).some((i) => (i.props.source as { uri?: string }).uri?.includes("/art/u_kaki/"))).toBe(false);
  await act(async () => r.unmount());
});

test("a slow, older catalog answer does not put back a kind that was just removed", async () => {
  catalog = [TOMATO, kaki(ART_READY)];
  const r = await mount();
  await press(r, "buy-mode");
  // the re-read after removing hangs; adding a kind then triggers a second re-read, which answers first. The first one must not count when it arrives late
  let release!: (v: Response) => void;
  const slow = new Promise<Response>((res) => {
    release = res;
  });
  let n = 0;
  fetchMock.mockImplementation(async (url: string) => {
    const u = String(url);
    if (u.includes("/api/fridge/kinds")) return resp(200, { ok: true });
    if (u.includes("/api/fridge/catalog")) return ++n === 1 ? slow : resp(200, [TOMATO]);
    return resp(404, {});
  });
  await press(r, "kind-remove-u_kaki");     // re-read no. 1 (hangs; when it arrives it carries the catalog from before the removal)
  await act(async () => {
    r.root.findByProps({ testID: "kind-name" }).props.onChangeText("梨");
  });
  await press(r, "kind-cat-fruit");
  await press(r, "kind-add");               // re-read no. 2, answers [tomato] at once
  expect(has(r, "kind-row-u_kaki")).toBe(false);
  await act(async () => {
    release(resp(200, [TOMATO, kaki(ART_READY)]));
  });
  await flush();
  expect(has(r, "kind-row-u_kaki")).toBe(false);
  await act(async () => r.unmount());
});

test("the answer to \"add\" arrives after switching back to buying: the failure sentence goes to the page", async () => {
  let release!: (v: Response) => void;
  kindReply = () => new Promise<Response>((res) => {
    release = res;
  }) as unknown as Response;
  const orphan = jest.fn();
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    r = TestRenderer.create(<BuySheet open viewer="aster" auth={AUTH} onClose={() => {}} onBuy={async () => ({ kind: "done" })} onOrphanError={orphan} />);
  });
  await flush();
  await press(r, "buy-mode");
  await act(async () => {
    r.root.findByProps({ testID: "kind-name" }).props.onChangeText("苹果");
  });
  await press(r, "kind-cat-fruit");
  await press(r, "kind-add");
  await press(r, "buy-mode");               // back to buying: the form is unmounted
  await act(async () => {
    release(resp(409, { detail: "已经有苹果了。" }));
  });
  await flush();
  expect(orphan).toHaveBeenCalledWith("已经有苹果了。");
  await act(async () => r.unmount());
});

test("while a picture is being drawn the open sheet quietly re-reads the catalog every few seconds, and stops once it is drawn", async () => {
  jest.useFakeTimers();
  try {
    catalog = [TOMATO, kaki(ART_PENDING)];
    const r = await mount();
    const n0 = calls("/api/fridge/catalog").length;
    catalog = [TOMATO, kaki(ART_READY)];
    await act(async () => {
      jest.advanceTimersByTime(ART_POLL_MS + 10);
    });
    await flush();
    expect(calls("/api/fridge/catalog").length).toBe(n0 + 1);
    expect(r.root.findAllByType(Image).some((i) => (i.props.source as { uri?: string }).uri?.includes("/art/u_kaki/fresh.png?v=1"))).toBe(true);
    await act(async () => {
      jest.advanceTimersByTime(ART_POLL_MS * 3);
    });
    await flush();
    expect(calls("/api/fridge/catalog").length).toBe(n0 + 1);
    await act(async () => r.unmount());
  } finally {
    jest.useRealTimers();
  }
});
