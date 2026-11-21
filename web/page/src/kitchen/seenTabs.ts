// The small 「新」 next to an entrance of the upgrade: shown until that entrance has been opened once on
// this device (remembered in localStorage; storage blocked = it shows each time, nothing breaks).
// Only on the row of entrances under the hand, never on the kitchen picture.
import type { PlayTab } from "./playApi";

export const SEEN_KEY = "kitchenette.seenTabs";

function store(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

/** The entrances already opened on this device */
export function loadSeen(): Set<string> {
  try {
    const raw = store()?.getItem(SEEN_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(list) ? list.filter((x): x is string => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

/** Remember that an entrance was opened; returns the new set (the same set when it was already in) */
export function markSeen(seen: Set<string>, tab: PlayTab): Set<string> {
  if (seen.has(tab)) return seen;
  const next = new Set(seen);
  next.add(tab);
  try {
    store()?.setItem(SEEN_KEY, JSON.stringify([...next].sort()));
  } catch {
    /* not remembered: shown again next time */
  }
  return next;
}
