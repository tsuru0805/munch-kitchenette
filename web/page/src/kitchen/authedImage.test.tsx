// Pictures fetched with the token: each fetch belongs to one run of the effect; a URL that was released
// is never shown again (going A → B → A, or A → nothing → A, fetches A again), and a failure belongs to
// the picture it happened to, so a later fetch of the same picture that works is shown.
import TestRenderer, { act } from "react-test-renderer";
import { Image, Text } from "react-native";
import { _fetchHeadedPictures } from "./authedImage";
import type { ArtRef } from "./kindArt";
import { ArtImage } from "./panelParts";

const H = { Authorization: "Bearer tok" };
const art = (name: string): ArtRef => ({ src: { uri: `http://kitchen.test/api/dex/art?page_key=${name}&version=1`, headers: H }, w: 10, h: 10 });

let made = 0;
let released: string[] = [];
let asked: string[] = [];
const waiting = new Map<string, ((ok: boolean) => void)[]>();
const mockFetch = jest.fn((uri: string) => {
  asked.push(uri);
  return new Promise((res) => {
    const list = waiting.get(uri) ?? [];
    list.push((ok) => res(ok ? { ok: true, status: 200, blob: async () => ({ size: 1 }) } : { ok: false, status: 401, blob: async () => null }));
    waiting.set(uri, list);
  });
});
/** let the oldest request for this picture answer */
async function answer(a: ArtRef, ok = true) {
  const uri = (a.src as { uri: string }).uri;
  const list = waiting.get(uri) ?? [];
  const next = list.shift();
  if (!next) throw new Error(`nothing asked for ${uri}`);
  await act(async () => next(ok));
  await act(async () => {});
}

beforeAll(() => {
  Object.defineProperty(globalThis, "fetch", { value: (...a: unknown[]) => mockFetch(...(a as [string])), configurable: true, writable: true });
  _fetchHeadedPictures(true);
});
afterAll(() => _fetchHeadedPictures(false));
let spies: jest.SpyInstance[] = [];
beforeEach(() => {
  made = 0;
  released = [];
  asked = [];
  waiting.clear();
  mockFetch.mockClear();
  spies = [
    jest.spyOn(URL, "createObjectURL" as never).mockImplementation((() => `blob:${++made}`) as never),
    jest.spyOn(URL, "revokeObjectURL" as never).mockImplementation(((u: string) => { released.push(u); }) as never),
  ];
});
afterEach(() => spies.forEach((s) => s.mockRestore()));

const view = (a: ArtRef | null) => <ArtImage art={a} style={{ width: 10, height: 10 }} fallback={<Text>占位</Text>} />;
/** the address the <Image> shows, or null while the fallback stands */
const shown = (r: TestRenderer.ReactTestRenderer): string | null => {
  const imgs = r.root.findAllByType(Image);
  return imgs.length ? String((imgs[0].props.source as { uri: string }).uri) : null;
};
const neverReleased = (r: TestRenderer.ReactTestRenderer) => {
  const s = shown(r);
  if (s) expect(released).not.toContain(s);
};

test("A → B → A before B answers: A is fetched again, the released URL is never shown, B's late answer is dropped", async () => {
  const A = art("a");
  const B = art("b");
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => { r = TestRenderer.create(view(A)); });
  expect(shown(r)).toBeNull();
  await answer(A);
  expect(shown(r)).toBe("blob:1");
  await act(async () => r.update(view(B)));
  expect(released).toEqual(["blob:1"]);
  expect(shown(r)).toBeNull();
  await act(async () => r.update(view(A)));
  neverReleased(r);
  expect(shown(r)).toBeNull();                       // loading again, not the released blob:1
  await answer(A);
  expect(shown(r)).toBe("blob:2");
  await answer(B);                                   // B answers after it is no longer wanted
  expect(shown(r)).toBe("blob:2");
  expect(made).toBe(2);                              // no URL made for the dropped answer
  expect(asked.filter((u) => u.includes("page_key=a"))).toHaveLength(2);
  act(() => r.unmount());
  expect(released).toEqual(["blob:1", "blob:2"]);
});

test("A → nothing → A: fetched again", async () => {
  const A = art("a");
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => { r = TestRenderer.create(view(A)); });
  await answer(A);
  expect(shown(r)).toBe("blob:1");
  await act(async () => r.update(view(null)));
  expect(shown(r)).toBeNull();
  expect(released).toEqual(["blob:1"]);
  await act(async () => r.update(view(A)));
  neverReleased(r);
  expect(shown(r)).toBeNull();
  await answer(A);
  expect(shown(r)).toBe("blob:2");
});

test("a picture that failed to show is shown once a later fetch of it works (same address, fetched again)", async () => {
  const A = art("a");
  const B = art("b");
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => { r = TestRenderer.create(view(A)); });
  await answer(A);
  await act(async () => r.root.findByType(Image).props.onError());    // the bytes were no picture
  expect(shown(r)).toBeNull();
  // the same address asked for again (a new token): the new answer is shown, the old failure does not stick
  const A2: ArtRef = { ...A, src: { uri: (A.src as { uri: string }).uri, headers: { Authorization: "Bearer new" } } };
  await act(async () => r.update(view(A2)));
  await answer(A2);
  expect(shown(r)).toBe("blob:2");
  // and by way of another picture and back
  await act(async () => r.root.findByType(Image).props.onError());
  await act(async () => r.update(view(B)));
  await act(async () => r.update(view(A2)));
  await answer(A2);
  expect(shown(r)).toBe("blob:3");
});

test("a refused fetch (401) leaves the fallback; asked again later and allowed, it shows", async () => {
  const A = art("a");
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => { r = TestRenderer.create(view(A)); });
  await answer(A, false);
  expect(shown(r)).toBeNull();
  expect(r.root.findAllByType(Text).map((t) => t.props.children)).toContain("占位");
  await act(async () => r.update(view(null)));
  await act(async () => r.update(view(A)));
  await answer(A, true);
  expect(shown(r)).toBe("blob:1");
});
