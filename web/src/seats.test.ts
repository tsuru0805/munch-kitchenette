// Animation seats are "newest first": a card mounted later takes the oldest holder's seat; the one
// pushed out goes still and comes back when a seat is released.
import { MAX_ANIMATED, _resetSeats, acquireSeat, onSeatFree, releaseSeat, seatFree } from "./seats";

beforeEach(() => _resetSeats());

it("newest card preempts the oldest when seats are full", () => {
  expect(MAX_ANIMATED).toBe(2);
  const revoked: string[] = [];
  const a = acquireSeat(() => revoked.push("a"));
  acquireSeat(() => revoked.push("b"));
  expect(seatFree()).toBe(false);
  acquireSeat(() => revoked.push("c"));     // the third (newest) takes a's seat
  expect(revoked).toEqual(["a"]);
  releaseSeat(a);                            // releasing a handle that was already taken away does nothing
  expect(seatFree()).toBe(false);
});

it("a released seat wakes waiters so the preempted card can come back", () => {
  const wake = vi.fn();
  onSeatFree(wake);
  const a = acquireSeat(() => {});
  acquireSeat(() => {});
  releaseSeat(a);
  expect(wake).toHaveBeenCalledTimes(1);
  expect(seatFree()).toBe(true);
});
