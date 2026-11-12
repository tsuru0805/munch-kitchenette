// A cap on how many cooks animate at once on one page (decoding several animated images while a
// chat is streaming is expensive). A mounted card whose cook is on stage takes a seat; without a
// seat it shows the still base pose. Newest first: when the seats are full, the card mounted last
// takes the seat of the oldest holder, which goes back to the still pose and waits; it gets a seat
// again when one is released. In a chat this means the most recent pot is always the one moving.
export const MAX_ANIMATED = 2;

type Holder = { revoke: () => void };
const holders: Holder[] = []; // in the order the seats were taken
const waiters = new Set<() => void>();

/** Take a seat; when full, take the oldest holder's seat (its revoke is called). Returns the handle to release with. */
export function acquireSeat(revoke: () => void): Holder {
  const h: Holder = { revoke };
  if (holders.length >= MAX_ANIMATED) {
    const oldest = holders.shift()!;
    oldest.revoke();
  }
  holders.push(h);
  return h;
}

export function releaseSeat(h: Holder): void {
  const i = holders.indexOf(h);
  if (i < 0) return; // already taken away: do not release twice
  holders.splice(i, 1);
  // Notify a copy: callbacks add and remove subscriptions
  [...waiters].forEach((fn) => fn());
}

/** Is a seat free (a card that lost its seat uses this to come back without pushing anyone out) */
export function seatFree(): boolean {
  return holders.length < MAX_ANIMATED;
}

export function onSeatFree(fn: () => void): () => void {
  waiters.add(fn);
  return () => {
    waiters.delete(fn);
  };
}

/** For tests: clear the seats */
export function _resetSeats(): void {
  holders.length = 0;
  waiters.clear();
}
