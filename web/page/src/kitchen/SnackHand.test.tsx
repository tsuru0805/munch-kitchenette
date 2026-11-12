// What the snack hand shows and does: the counts and the tier of the snack being held, what a serving
// restores (only while stamina is on), a server without snacks, feeding (coffee needs a flavour first),
// the sentence past the daily cap, and changing one snack's cap.
const mockToast = jest.fn();
let mockRoles = ["aster", "birch"];
jest.mock("../runtime/store", () => ({ useStore: () => ({ toast: mockToast, role: "aster", roles: mockRoles, tick: 0 }) }));
const mockFetch = jest.fn();
const mockFeed = jest.fn();
const mockSave = jest.fn();
jest.mock("./snacksApi", () => {
  const actual = jest.requireActual("./snacksApi");
  return {
    ...actual,
    fetchSnacks: (...a: unknown[]) => mockFetch(...a),
    feedSnack: (...a: unknown[]) => mockFeed(...a),
    saveSnackCaps: (...a: unknown[]) => mockSave(...a),
  };
});

import TestRenderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { SnackHand, snackArt } from "./SnackHand";
import { SnackCapError, SnacksUnsupportedError, parseSnackState, resetText } from "./snacksApi";
import { setZone } from "../runtime/zone";

const wire = (who: string, energy: boolean, over: Record<string, number> = {}) => ({
  who,
  day: "2026-10-13",
  resets_at: Date.UTC(2026, 9, 13, 19, 0, 0) / 1000,
  energy_enabled: energy,
  cap_min: 0,
  cap_max: 20,
  snacks: [
    {
      id: "coffee", name: "咖啡", tier: "mid", tier_label: "中档", default_cap: 3, cap: over.coffee ?? 3, eaten: 1, gain: null,
      variants: [{ id: "espresso", name: "浓缩", gain: 0.08 }, { id: "latte", name: "拿铁", gain: 0.05 }],
    },
    { id: "jelly", name: "即时元气果冻", tier: "high", tier_label: "高档", default_cap: 2, cap: 2, eaten: 2, gain: 0.15, variants: [] },
    { id: "cookie", name: "曲奇", tier: "low", tier_label: "低档", default_cap: 5, cap: 5, eaten: 0, gain: 0.02, variants: [] },
  ],
});

const texts = (r: TestRenderer.ReactTestRenderer) =>
  r.root.findAllByType(Text).map((t) => [t.props.children].flat(9).filter((x) => typeof x === "string" || typeof x === "number").join(""));
const press = (r: TestRenderer.ReactTestRenderer, label: string) =>
  r.root.find((n) => n.props.accessibilityLabel === label && typeof n.props.onPress === "function").props.onPress();

async function mount(snackId: string) {
  let r!: TestRenderer.ReactTestRenderer;
  const onPick = jest.fn();
  await act(async () => {
    r = TestRenderer.create(<SnackHand snackId={snackId} anchor={null} sceneH={390} onPick={onPick} />);
  });
  return { r, onPick };
}

beforeAll(() => setZone("Asia/Tokyo"));      // the reset time below is written in the kitchen's zone
afterAll(() => setZone(""));
beforeEach(() => {
  mockRoles = ["aster", "birch"];
  mockToast.mockReset();
  mockFetch.mockReset();
  mockFeed.mockReset();
  mockSave.mockReset();
});

it("the snack being held: its count, tier and reset time; what a serving restores while stamina is on; full = \"今日已满\", not tappable", async () => {
  mockFetch.mockResolvedValue(parseSnackState(wire("aster", true)));
  const { r } = await mount("jelly");
  expect(mockFetch).toHaveBeenCalledWith("aster");
  const t = texts(r);
  expect(t).toEqual(expect.arrayContaining(["即时元气果冻", "2", "/ 2 今天 · 04:00 重置", "高档", " · 体力 +0.15 / 份", "今日已满", "柜子上"]));
  expect(r.root.find((n) => n.props.accessibilityLabel === "即时元气果冻今日已满" && typeof n.props.onPress === "function").props.disabled).toBe(true);
});

it("the bottom row is the whole shelf; tapping one holds that one", async () => {
  mockFetch.mockResolvedValue(parseSnackState(wire("aster", true)));
  const { r, onPick } = await mount("jelly");
  await act(async () => r.root.findByProps({ testID: "row-snack-cookie" }).props.onPress());
  expect(onPick).toHaveBeenCalledWith("cookie");
});

it("feeding another role reads that role's shelf; with stamina off nothing about stamina is shown", async () => {
  mockFetch.mockImplementation(async (v: string) => parseSnackState(wire(v, v === "aster")));
  const { r } = await mount("cookie");
  await act(async () => press(r, "喂给birch"));
  expect(mockFetch).toHaveBeenLastCalledWith("birch");
  expect(texts(r).some((x) => x.includes("体力"))).toBe(false);
  expect(texts(r)).toContain("低档");
});

it("a server without snacks: one plain sentence", async () => {
  mockFetch.mockRejectedValue(new SnacksUnsupportedError());
  const { r } = await mount("coffee");
  expect(texts(r)).toContain("常驻零食还没接上 · 服务端这一件尚未装载");
});

it("coffee without a flavour sends nothing; with one it is fed (and the picture is that flavour's)", async () => {
  mockFetch.mockResolvedValue(parseSnackState(wire("aster", true)));
  mockFeed.mockResolvedValue({
    result: { name: "拿铁咖啡", energyDelta: 0.05, energy: 0.5, eaten: 2, cap: 3 }, notified: true, state: parseSnackState(wire("aster", true)),
  });
  const { r } = await mount("coffee");
  expect(texts(r)).toEqual(expect.arrayContaining(["中档", " · 体力 +0.08 · +0.05"]));
  await act(async () => press(r, "喂一份咖啡"));
  expect(mockFeed).not.toHaveBeenCalled();
  expect(mockToast).toHaveBeenLastCalledWith("先选咖啡的口味");
  await act(async () => press(r, "拿铁咖啡"));
  expect(texts(r)).toContain(" · 体力 +0.05 / 份");
  await act(async () => press(r, "喂一份咖啡"));
  expect(mockFeed).toHaveBeenCalledWith("aster", "coffee", "latte");
  expect(mockToast).toHaveBeenLastCalledWith("喂了aster一份拿铁咖啡 · 体力 +0.05 · 他下轮会知道");
  expect(snackArt("coffee", "latte")).toBe("snack_coffee_latte");
  expect(snackArt("coffee", null)).toBe("snack_coffee_americano");
});

it("past the cap: the server's sentence is shown and the shelf is read again", async () => {
  mockFetch.mockResolvedValue(parseSnackState(wire("aster", true)));
  mockFeed.mockRejectedValue(new SnackCapError("今天的曲奇已经 5/5 份了,04:00 重置", 5, 5));
  const { r } = await mount("cookie");
  await act(async () => press(r, "喂一份曲奇"));
  expect(mockToast).toHaveBeenLastCalledWith("今天的曲奇已经 5/5 份了,04:00 重置");
  expect(mockFetch).toHaveBeenCalledTimes(2);
});

it("changing the cap of this one snack: \"存 / 算了\" only appear after stepping; saving sends this snack only; backing out sends nothing", async () => {
  mockFetch.mockResolvedValue(parseSnackState(wire("aster", true)));
  mockSave.mockResolvedValue(parseSnackState(wire("aster", true, { coffee: 4 })));
  const { r } = await mount("coffee");
  const has = (label: string) => r.root.findAll((n) => n.props.accessibilityLabel === label && typeof n.props.onPress === "function").length > 0;
  expect(has("存上限")).toBe(false);
  await act(async () => press(r, "咖啡上限加一"));
  await act(async () => press(r, "咖啡上限加一"));
  await act(async () => press(r, "咖啡上限减一"));
  expect(has("存上限")).toBe(true);
  await act(async () => press(r, "不改了"));
  expect(has("存上限")).toBe(false);
  expect(mockSave).not.toHaveBeenCalled();
  await act(async () => press(r, "咖啡上限加一"));
  await act(async () => press(r, "存上限"));
  expect(mockSave).toHaveBeenCalledWith("aster", { coffee: 4 });
  expect(mockToast).toHaveBeenLastCalledWith("上限改好了");
  expect(texts(r)).toContain("/ 4 今天 · 04:00 重置");
});

it("with a single role there is nobody to choose between: no \"喂给\" row", async () => {
  mockRoles = ["aster"];
  mockFetch.mockResolvedValue(parseSnackState(wire("aster", true)));
  const { r } = await mount("cookie");
  expect(texts(r)).not.toContain("喂给");
  expect(texts(r)).toContain("喂一份");
});

it("the reset time is written in the kitchen's time zone", () => {
  const at = Date.UTC(2026, 9, 13, 19, 0, 0) / 1000;      // 04:00 on the 14th in Tokyo
  expect(resetText(at)).toBe("04:00");
  setZone("America/New_York");
  expect(resetText(at)).toBe("15:00");
  setZone("Asia/Tokyo");
});
