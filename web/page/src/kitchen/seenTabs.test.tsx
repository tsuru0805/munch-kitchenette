// The small 「新」 on the row of entrances: shown until an entrance has been opened once on this device;
// remembered in localStorage; blocked storage changes nothing but the memory.
import TestRenderer, { act } from "react-test-renderer";
import { PlayShelf } from "./PlaySheet";
import { SEEN_KEY, loadSeen, markSeen } from "./seenTabs";
import type { PlayTab } from "./playApi";

// a plain in-memory localStorage (the test environment has none of its own)
class MemStorage {
  private m = new Map<string, string>();
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
  removeItem(k: string) { this.m.delete(k); }
  clear() { this.m.clear(); }
}
const mem = new MemStorage();
beforeAll(() => Object.defineProperty(globalThis, "localStorage", { value: mem, configurable: true, writable: true }));
beforeEach(() => mem.clear());

describe("remembering opened entrances", () => {
  test("nothing opened yet: an empty set; opening one is remembered, once", () => {
    expect(loadSeen().size).toBe(0);
    const a = markSeen(loadSeen(), "dex");
    expect([...a]).toEqual(["dex"]);
    expect(markSeen(a, "dex")).toBe(a);
    expect([...loadSeen()]).toEqual(["dex"]);
    expect(JSON.parse(localStorage.getItem(SEEN_KEY)!)).toEqual(["dex"]);
  });
  test("whatever else is in the key counts as nothing opened", () => {
    localStorage.setItem(SEEN_KEY, "{not json");
    expect(loadSeen().size).toBe(0);
    localStorage.setItem(SEEN_KEY, JSON.stringify([1, "jars", null]));
    expect([...loadSeen()]).toEqual(["jars"]);
  });
  test("storage that refuses to write: the set still changes for this visit", () => {
    const spy = jest.spyOn(mem, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect([...markSeen(new Set(), "vendor")]).toEqual(["vendor"]);
    spy.mockRestore();
  });
});

describe("the row of entrances", () => {
  const marks = (r: TestRenderer.ReactTestRenderer) => r.root.findAll((n) => typeof n.props.testID === "string" && n.props.testID.startsWith("play-new-") && typeof n.type === "string").map((n) => n.props.testID);
  test("each entrance not opened yet carries 「新」; opened ones do not; without a set nothing is marked", () => {
    let r!: TestRenderer.ReactTestRenderer;
    act(() => { r = TestRenderer.create(<PlayShelf tabs={["recipes", "dex", "jars"]} seen={new Set(["dex"])} onOpen={() => {}} />); });
    expect(marks(r)).toEqual(["play-new-recipes", "play-new-jars"]);
    act(() => { r.update(<PlayShelf tabs={["recipes", "dex", "jars"]} onOpen={() => {}} />); });
    expect(marks(r)).toEqual([]);
  });
  test("a dot between two entrances on one line; none at the start of a wrapped line; none before the layout is known", () => {
    const tabs: PlayTab[] = ["recipes", "dex", "jars", "vendor"];
    let r!: TestRenderer.ReactTestRenderer;
    act(() => { r = TestRenderer.create(<PlayShelf tabs={tabs} onOpen={() => {}} />); });
    const dots = () => r.root.findAll((n) => typeof n.props.testID === "string" && n.props.testID.startsWith("play-dot-") && typeof n.type === "string").map((n) => n.props.testID);
    expect(dots()).toEqual([]);
    const boxes = r.root.findAll((n) => typeof n.props.onLayout === "function" && typeof n.type === "string");
    act(() => { [0, 0, 24, 24].forEach((y, i) => boxes[i].props.onLayout({ nativeEvent: { layout: { x: 0, y, width: 40, height: 20 } } })); });
    expect(dots()).toEqual(["play-dot-dex", "play-dot-vendor"]);
  });
  test("opening one marks it seen and its 「新」 goes away", () => {
    let seen = loadSeen();
    let r!: TestRenderer.ReactTestRenderer;
    const open = (t: PlayTab) => {
      seen = markSeen(seen, t);
      r.update(<PlayShelf tabs={["recipes", "jars"]} seen={seen} onOpen={open} />);
    };
    act(() => { r = TestRenderer.create(<PlayShelf tabs={["recipes", "jars"]} seen={seen} onOpen={open} />); });
    act(() => { r.root.find((n) => n.props.testID === "play-jars" && typeof n.props.onPress === "function").props.onPress(); });
    expect(marks(r)).toEqual(["play-new-recipes"]);
    expect([...loadSeen()]).toEqual(["jars"]);
  });
});
