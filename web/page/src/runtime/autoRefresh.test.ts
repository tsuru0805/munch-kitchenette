// When an open page reads everything again: on a timer while visible, at once when it comes back to
// the front, never while hidden, and not in the middle of what the person is doing.
import { AUTO_REFRESH_MS, startAutoRefresh, type VisibilitySource } from "./autoRefresh";

function fakeDoc(state = "visible") {
  const listeners = new Set<() => void>();
  const doc: VisibilitySource & { set: (s: string) => void; count: () => number } = {
    visibilityState: state,
    addEventListener: (_t, fn) => void listeners.add(fn),
    removeEventListener: (_t, fn) => void listeners.delete(fn),
    set: (s) => {
      doc.visibilityState = s;
      [...listeners].forEach((fn) => fn());
    },
    count: () => listeners.size,
  };
  return doc;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test("a visible page reads again every 30 seconds", () => {
  const refresh = jest.fn();
  const stop = startAutoRefresh({ refresh, idle: () => true, doc: fakeDoc() });
  expect(AUTO_REFRESH_MS).toBe(30_000);
  jest.advanceTimersByTime(29_999);
  expect(refresh).toHaveBeenCalledTimes(0);
  jest.advanceTimersByTime(1);
  expect(refresh).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(60_000);
  expect(refresh).toHaveBeenCalledTimes(3);
  stop();
});

test("a hidden page reads nothing; coming back to the front reads at once and the turns start again", () => {
  const refresh = jest.fn();
  const doc = fakeDoc();
  const stop = startAutoRefresh({ refresh, idle: () => true, doc });
  doc.set("hidden");
  jest.advanceTimersByTime(5 * 60_000);
  expect(refresh).toHaveBeenCalledTimes(0);
  doc.set("visible");
  expect(refresh).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(30_000);
  expect(refresh).toHaveBeenCalledTimes(2);
  stop();
});

test("a page opened in the background waits until it is shown", () => {
  const refresh = jest.fn();
  const doc = fakeDoc("hidden");
  const stop = startAutoRefresh({ refresh, idle: () => true, doc });
  jest.advanceTimersByTime(120_000);
  expect(refresh).toHaveBeenCalledTimes(0);
  doc.set("visible");
  expect(refresh).toHaveBeenCalledTimes(1);
  stop();
});

test("a turn is skipped while the person is in the middle of something, and the next one comes an interval later", () => {
  const refresh = jest.fn();
  let busy = true;
  const doc = fakeDoc();
  const stop = startAutoRefresh({ refresh, idle: () => !busy, doc });
  jest.advanceTimersByTime(90_000);
  expect(refresh).toHaveBeenCalledTimes(0);
  doc.set("hidden");
  doc.set("visible"); // coming back to the front does not interrupt either
  expect(refresh).toHaveBeenCalledTimes(0);
  busy = false;
  jest.advanceTimersByTime(30_000);
  expect(refresh).toHaveBeenCalledTimes(1);
  stop();
});

test("stopping ends the turns and lets go of the page", () => {
  const refresh = jest.fn();
  const doc = fakeDoc();
  const stop = startAutoRefresh({ refresh, idle: () => true, doc });
  expect(doc.count()).toBe(1);
  stop();
  expect(doc.count()).toBe(0);
  jest.advanceTimersByTime(120_000);
  doc.set("visible");
  expect(refresh).toHaveBeenCalledTimes(0);
});

test("the interval can be set", () => {
  const refresh = jest.fn();
  const stop = startAutoRefresh({ refresh, idle: () => true, doc: fakeDoc(), everyMs: 1000 });
  jest.advanceTimersByTime(3500);
  expect(refresh).toHaveBeenCalledTimes(3);
  stop();
});
