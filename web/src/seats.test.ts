// Animation seats are "newest first": a card mounted later takes the oldest holder's seat; the one
// pushed out goes still and comes back when a seat is released.
import { MAX_ANIMATED, SeatClaim, _resetSeats, acquireSeat, onSeatFree, releaseSeat, seatFree } from "./seats";

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

describe("cooking cards and washing cards share the two seats (both go through SeatClaim)", () => {
  // what each card does with its claim: want a seat while its cook is on stage, give it back when he leaves
  // or the card is taken off the page; onChange = the card draws itself again (still pose <-> moving)
  function card(name: string, log: string[]) {
    return new SeatClaim(() => log.push(name));
  }

  it("taking, being pushed out by a newer card of either kind, and coming back when one is released", () => {
    const log: string[] = [];
    const pot = card("pot", log);
    const wash = card("wash", log);
    pot.want(true);
    wash.want(true);
    expect([pot.held, wash.held, seatFree()]).toEqual([true, true, false]);

    // a second pot arrives in the chat: the oldest (the first pot) goes still
    const pot2 = card("pot2", log);
    pot2.want(true);
    expect([pot.held, wash.held, pot2.held]).toEqual([false, true, true]);
    expect(log).toEqual(["pot"]);

    // a second washing: the washing card that was there is now the oldest holder
    const wash2 = card("wash2", log);
    wash2.want(true);
    expect([pot.held, wash.held, pot2.held, wash2.held]).toEqual([false, false, true, true]);
    expect(log).toEqual(["pot", "wash"]);

    // the newest washing ends (he sinks below the card): its seat goes to a card still waiting, nobody is pushed
    wash2.want(false);
    expect(wash2.held).toBe(false);
    expect([pot.held, wash.held].filter(Boolean)).toHaveLength(1);
    expect(pot2.held).toBe(true);
    expect(log.length).toBe(3);

    // every card taken off the page: every seat is free again, and nothing is called any more
    for (const c of [pot, wash, pot2, wash2]) c.want(false);
    expect(seatFree()).toBe(true);
    const before = log.length;
    const fresh = card("fresh", log);
    fresh.want(true);
    expect(fresh.held).toBe(true);
    expect(log.length).toBe(before);
  });

  it("wanting twice takes one seat; a card that no longer wants one is not woken", () => {
    const log: string[] = [];
    const a = card("a", log);
    a.want(true);
    a.want(true);
    const b = card("b", log);
    b.want(true);
    expect(seatFree()).toBe(false);
    const c = card("c", log);
    c.want(true);           // pushes a out
    a.want(false);          // a leaves while waiting
    c.want(false);          // a seat comes free: a is not woken
    expect(a.held).toBe(false);
    expect(log).toEqual(["a"]);
  });
});
