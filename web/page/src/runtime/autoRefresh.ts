// Keeping an open page up to date. The role cooks, eats and buys through its tools while the page
// sits open, so the page reads everything again
//   - every AUTO_REFRESH_MS while the page is visible, and
//   - at once when it becomes visible again (a tab switched back to, a phone unlocked).
// Nothing is read while the page is hidden. A turn is skipped while the person is in the middle of
// something (a sheet is open, a request is on its way): what they are typing or doing is not
// touched, and the next turn comes one interval later.

export const AUTO_REFRESH_MS = 30_000;

/** The part of `document` this needs (the real one in a browser, a stand-in in tests) */
export interface VisibilitySource {
  visibilityState: string;
  addEventListener: (type: "visibilitychange", fn: () => void) => void;
  removeEventListener: (type: "visibilitychange", fn: () => void) => void;
}

export interface AutoRefresh {
  /** read everything again */
  refresh: () => void;
  /** false while the person is in the middle of something */
  idle: () => boolean;
  everyMs?: number;
  doc?: VisibilitySource | null;
}

/** Starts the turns; returns the function that stops them. */
export function startAutoRefresh({ refresh, idle, everyMs = AUTO_REFRESH_MS, doc }: AutoRefresh): () => void {
  const source = doc === undefined ? (typeof document === "undefined" ? null : (document as unknown as VisibilitySource)) : doc;
  let timer: ReturnType<typeof setInterval> | null = null;
  const visible = () => !source || source.visibilityState === "visible";
  const turn = () => {
    if (visible() && idle()) refresh();
  };
  const run = () => {
    if (timer === null) timer = setInterval(turn, everyMs);
  };
  const pause = () => {
    if (timer !== null) clearInterval(timer);
    timer = null;
  };
  const onVisibility = () => {
    if (visible()) {
      turn(); // back in front: what is shown may be minutes old
      run();
    } else {
      pause();
    }
  };
  source?.addEventListener("visibilitychange", onVisibility);
  if (visible()) run();
  return () => {
    pause();
    source?.removeEventListener("visibilitychange", onVisibility);
  };
}
