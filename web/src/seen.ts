// "This page has seen this pot" (module-level memory, lives as long as the page).
// The entrance and the hand-washing are only for a pot that has not been seen yet; a card that
// leaves the document and comes back (a virtualised list mounting it again) counts as seen.
// A pot is marked as seen only once its entrance has finished (or when the card never needed one),
// not after a grace period: if a card is removed while the entrance is still playing (a streaming
// message being re-keyed, for example), the next mount plays it from the start instead of losing it.
const seen = new Set<string>();

export function isFirstSeen(sessionId: string): boolean {
  return !seen.has(sessionId);
}

export function markSeen(sessionId: string): void {
  seen.add(sessionId);
}

/** For tests */
export function _resetSeen(): void {
  seen.clear();
}
