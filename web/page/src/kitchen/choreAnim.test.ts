import {
  CALL_EVERY_MS, CLIP_MS, MAX_SHOWS, STALE_S, VendorShow, WASHER_RUN_MS, forgetShows, hashStr, outfitFor, platesClip,
  serverNow, showCount, cachedOrderCount, stillFor, vendorPanelClip, vendorPrefix, washerClip, type VendorOrderFacts, type VendorVisitFacts,
} from "./choreAnim";
import { CHORE_ART, CHORE_SEGMENTS } from "./choreArt.generated";
import { parsePlates, parseVendor, type VendorView } from "./playApi";
import contract from "./__fixtures__/server_contract.json";

describe("the dishwasher", () => {
  test("load -> close -> start -> running for 8 s -> done once, then its last frame", () => {
    const at = 500;
    const s = (ms: number) => washerClip(at, 2, at + ms / 1000)!.segment;
    expect([0, 3000, 6000, 9000, 9000 + WASHER_RUN_MS - 1, 9000 + WASHER_RUN_MS].map(s)).toEqual(
      ["machine_load", "machine_close", "machine_start", "machine_run", "machine_run", "machine_done"]);
    expect(s(9000 + WASHER_RUN_MS + CLIP_MS)).toBe("machine_done_last");
    expect(s(86_400_000)).toBe("machine_done_last");
  });
  test("nothing when no plate is in it", () => {
    expect(washerClip(null, 2, 1)).toBeNull();
    expect(washerClip(500, 0, 501)).toBeNull();
  });
});

// ── the vendor: whole runs, not single picks ────────────────────────────
// `play` asks the show every quarter second from `from` to `to`, with the facts as they are at that moment,
// and returns the clips it showed, each once in the order shown (a clip that starts again, like the next
// call, counts again), plus every pick. The facts are a timeline: (t) => the role's orders at server time t.
type Facts = (t: number) => VendorOrderFacts[];
const VISIT: VendorVisitFacts = { id: "v1", vendor: "chestnut", leaveAt: 10_000 };
function play(facts: Facts, from: number, to: number, visit: (t: number) => VendorVisitFacts = () => VISIT, show = new VendorShow("v1")) {
  const seq: string[] = [], all: string[] = [];
  let last = "";
  for (let k = 0; from + k * 0.25 <= to + 1e-9; k++) {
    const t = from + k * 0.25;
    const c = show.pick(visit(t), facts(t), t);
    all.push(c.segment);
    const key = `${c.segment}|${c.run}`;
    if (key !== last) seq.push(c.segment.replace(/^vendor_(th_)?/, ""));
    last = key;
  }
  return { seq, all, show, at: (t: number) => all[Math.round((t - from) * 4)] };
}
const order = (over: Partial<VendorOrderFacts>): VendorOrderFacts => ({ id: "o1", payer: "self", state: "created", createdAt: 10, updatedAt: 10, kind: "snack", ...over });
// an order placed at `createdAt` (10 unless given) that moves on as `steps` says: [[from t, state], ...]
const moving = (steps: [number, string][], over: Partial<VendorOrderFacts> = {}): Facts => (t) => {
  const created = over.createdAt ?? 10;
  if (t < created) return [];
  let st = steps[0][1], at = created;
  for (const [from, state] of steps) if (t >= from) { st = state; at = from; }
  return [order({ ...over, state: st, updatedAt: at })];
};

describe("the vendor's show", () => {
  test("first shown: he pushes the cart in, then calls for one clip every 15 s and waits in between", () => {
    const r = play(() => [], 0, 35);
    expect(r.seq).toEqual(["arrive", "call", "wait", "call", "wait", "call"]);
    expect(r.at(CLIP_MS / 1000 + CALL_EVERY_MS / 1000)).toBe("vendor_call");
  });

  test("a quick deal (paid and delivered within half a second) still plays every step, in order, once", () => {
    const { seq } = play(moving([[10, "created"], [10.25, "paid"], [10.5, "delivered"]]), 0, 30);
    expect(seq).toEqual(["arrive", "call", "wait", "walkin", "pay", "give", "eat", "walkout", "call", "wait"]);
  });

  test("paying lasts as long as the charge, and at least one clip", () => {
    const r = play(moving([[10, "created"], [12, "debiting"], [21, "paid"], [22, "delivered"]]), 0, 40);
    // walks over 10–13, pays from 13 until the delivery at 22, then hands it over
    expect(r.at(21.75)).toBe("vendor_pay");
    expect(r.at(22.25)).toBe("vendor_give");
  });

  test("the page opened with an order already under way: his arrival first, then the order from the start", () => {
    const { seq } = play(moving([[0, "paid"], [104, "delivered"]], { createdAt: 0 }), 100, 118);
    expect(seq).toEqual(["arrive", "walkin", "pay", "give", "eat", "walkout", "call"]);
  });

  test("the page opened long after an order was done: it is not played again", () => {
    const facts: Facts = () => [order({ createdAt: 0, updatedAt: 5, state: "delivered" })];
    const { seq } = play(facts, 5 + STALE_S + 1, 5 + STALE_S + 15);
    expect(seq).toEqual(["arrive", "call", "wait"]);
  });

  test("a treat: no paying; the cook walks over and stands there until it comes", () => {
    const { seq } = play(moving([[10, "created"], [20, "delivered"]], { payer: "her" }), 0, 31);
    expect(seq).toEqual(["arrive", "call", "wait", "walkin", "walkin_last", "give", "eat", "walkout", "call"]);
  });

  test("an ingredient or flowers: handed over, held, carried back out; nothing eaten", () => {
    const { seq } = play(moving([[10, "created"], [10.5, "delivered"]], { kind: "ingredient" }), 0, 30);
    expect(seq).toEqual(["arrive", "call", "wait", "walkin", "pay", "give", "give_last", "walkout_hold", "call", "wait"]);
  });

  test("refunding, then refunded: the cook walks back out empty-handed once, not again when it is refunded", () => {
    const { seq } = play(moving([[10, "created"], [11, "paid"], [14, "refunding"], [18, "refunded"]]), 0, 45);
    // walk 10–13, pay 13–16, back out 16–19, then call 19–22, wait, call again at 34
    expect(seq).toEqual(["arrive", "call", "wait", "walkin", "pay", "walkout_empty", "call", "wait", "call", "wait"]);
    expect(seq.filter((x) => x === "walkout_empty")).toHaveLength(1);
  });

  test("a failed charge: walked over, nothing paid, nothing handed over, back out empty-handed", () => {
    const { seq } = play(moving([[10, "created"], [10.5, "debit_failed"]]), 0, 30);
    expect(seq).toEqual(["arrive", "call", "wait", "walkin", "walkout_empty", "call", "wait"]);
  });

  test("two orders one after the other: each played through, in the order they were placed", () => {
    const facts: Facts = (t) => [
      ...(t >= 10 ? [order({ id: "a", createdAt: 10, updatedAt: 10.5, state: t >= 10.5 ? "delivered" : "created" })] : []),
      ...(t >= 12 ? [order({ id: "b", createdAt: 12, updatedAt: 12.5, state: t >= 12.5 ? "delivered" : "created", kind: "ingredient" })] : []),
    ];
    const { seq } = play(facts, 0, 50);
    expect(seq).toEqual(["arrive", "call", "wait", "walkin", "pay", "give", "eat", "walkout",
      "walkin", "pay", "give", "give_last", "walkout_hold", "call", "wait"]);
  });

  test("an order placed at the very end of the visit is played to its end before he leaves; then the roadside stays empty", () => {
    const visit = (t: number): VendorVisitFacts => ({ ...VISIT, leaveAt: 30, ended: t >= 30 });
    const r = play(moving([[26, "created"], [26.5, "delivered"]], { createdAt: 26 }), 0, 60, visit);
    // (he calls at 3 and again at 18 before the order is placed at 26)
    expect(r.seq).toEqual(["arrive", "call", "wait", "call", "wait", "walkin", "pay", "give", "eat", "walkout", "leave", "leave_last"]);
    expect(r.all.at(-1)).toBe("vendor_leave_last");
  });

  test("no order: he leaves in the last 3 s of the visit", () => {
    const visit = (t: number): VendorVisitFacts => ({ ...VISIT, leaveAt: 20, ended: t >= 20 });
    const r = play(() => [], 0, 30, visit);
    expect(r.at(16.75)).not.toBe("vendor_leave");
    expect(r.at(17)).toBe("vendor_leave");
    expect(r.at(20)).toBe("vendor_leave_last");
  });

  test("the page asleep for a while: nothing that was not played is skipped, nothing played twice", () => {
    const show = new VendorShow("v1");
    const f = moving([[10, "created"], [10.5, "delivered"]]);
    expect(show.pick(VISIT, f(0), 0).segment).toBe("vendor_arrive");
    const { seq } = play(f, 11, 26, () => VISIT, show);
    expect(seq).toEqual(["walkin", "pay", "give", "eat", "walkout", "call"]);
  });

  test("the tanghulu seller's cart, and every other vendor's", () => {
    expect(vendorPrefix("tanghulu")).toBe("vendor_th_");
    expect(vendorPrefix("chestnut")).toBe("vendor_");
    expect(play(() => [], 0, 4, () => ({ ...VISIT, vendor: "tanghulu" })).all.at(-1)).toBe("vendor_th_call");
  });

  test("reduce motion: every clip of a whole run stands still on something that is in the art", () => {
    const runs = [
      play(moving([[10, "created"], [10.5, "delivered"]]), 0, 40),
      play(moving([[10, "created"], [20, "delivered"]], { payer: "her", kind: "ingredient" }), 0, 40),
      play(moving([[10, "created"], [11, "paid"], [14, "refunding"], [18, "refunded"]]), 0, 40),
    ];
    for (const r of runs) for (const seg of r.all) {
      const still = stillFor(seg);
      expect(/_last$|_still$/.test(still)).toBe(true);
      expect(CHORE_SEGMENTS as readonly string[]).toContain(still);
    }
  });
});

// ── the panel: the page's own view of the server's answers, stepped like the page does ─────────────
// `panel` builds the view the page would hold at server time t and asks the panel every quarter second.
function panel(view: (t: number) => VendorView, from: number, to: number) {
  const seq: string[] = [], all: (string | null)[] = [];
  let last = "";
  for (let k = 0; from + k * 0.25 <= to + 1e-9; k++) {
    const t = from + k * 0.25;
    const c = vendorPanelClip(view(t), 0);
    all.push(c ? c.segment : null);
    const key = c ? `${c.segment}|${c.run}` : "-";
    if (key !== last) seq.push(c ? c.segment.replace(/^vendor_(th_)?/, "") : "-");
    last = key;
  }
  return { seq, all };
}
const RAW_VISIT = { id: "v1", vendor: "chestnut", name: "栗子", who: "卖炒栗子的", left_s: 0, goods: [] as unknown[] };
const rawOrder = (o: VendorOrderFacts) => ({ id: o.id, item_name: "x", kind: o.kind, payer: o.payer, state: o.state, created_at: o.createdAt, updated_at: o.updatedAt });
// a view at t: the visit live until leaveAt, `ended` until leaveAt + endedFor, nothing after; the orders as `facts` says
function view(facts: Facts, { leaveAt = 10_000, endedFor = 120, scope = "s|aster", visitId = "v1" } = {}) {
  return (t: number): VendorView => {
    const v = { ...RAW_VISIT, id: visitId, leave_at: leaveAt };
    const live = t < leaveAt, ended = !live && t < leaveAt + endedFor;
    return { ...parseVendor({ now: t, visit: live ? v : null, ended: ended ? v : null, mine: live || ended ? facts(t).map(rawOrder) : [] }), readAt: 0, scope };
  };
}

describe("the vendor's show, from the review's cases", () => {
  afterEach(() => forgetShows());

  test("an order read late (placed at 10.1, delivered at 10.2, first seen at 15): the walk over still plays, from 15", () => {
    const f = moving([[10.1, "created"], [10.2, "delivered"]], { createdAt: 10.1 });
    const late: Facts = (t) => (t < 15 ? [] : f(t));
    const r = play(late, 0, 32);
    expect(r.seq).toEqual(["arrive", "call", "wait", "walkin", "pay", "give", "eat", "walkout", "call"]);
    expect(r.at(15)).toBe("vendor_walkin");
    expect(r.at(14.75)).toBe("vendor_wait");
  });

  test("the page waking at 30 after showing the arrival at 0, with an order of 10–11: the whole order plays from 30", () => {
    const show = new VendorShow("v1");
    const f = moving([[10, "created"], [11, "delivered"]]);
    expect(show.pick(VISIT, f(0), 0).segment).toBe("vendor_arrive");
    const r = play(f, 30, 46, () => VISIT, show);
    expect(r.seq).toEqual(["walkin", "pay", "give", "eat", "walkout", "call"]);
    expect(r.at(30)).toBe("vendor_walkin");
  });

  test("an order placed while he is leaving: he finishes leaving, comes back with his cart, plays it, and leaves again", () => {
    const visit = (t: number): VendorVisitFacts => ({ ...VISIT, leaveAt: 30, ended: t >= 30 });
    const r = play(moving([[28.5, "created"], [29, "delivered"]], { createdAt: 28.5 }), 0, 60, visit);
    expect(r.seq).toEqual(["arrive", "call", "wait", "call", "wait", "leave", "arrive", "walkin", "pay", "give", "eat", "walkout", "leave", "leave_last"]);
  });

  test("an order read only after he has gone: he comes back for it", () => {
    const visit = (t: number): VendorVisitFacts => ({ ...VISIT, leaveAt: 30, ended: t >= 30 });
    const f = moving([[29.9, "created"], [30, "delivered"]], { createdAt: 29.9 });
    const r = play((t) => (t < 35 ? [] : f(t)), 0, 60, visit);
    expect(r.seq.slice(-10)).toEqual(["leave", "leave_last", "arrive", "walkin", "pay", "give", "eat", "walkout", "leave", "leave_last"]);
  });

  test("a hundred orders in one visit: each played once; the show keeps none of the finished ones", () => {
    const facts: Facts = (t) => {
      const out: VendorOrderFacts[] = [];
      for (let k = 0; k < 100 && 10 + 20 * k <= t; k++) {
        const c = 10 + 20 * k;
        out.push(order({ id: `o${k}`, createdAt: c, updatedAt: t >= c + 0.5 ? c + 0.5 : c, state: t >= c + 0.5 ? "delivered" : "created" }));
      }
      return out;
    };
    const r = play(facts, 0, 10 + 20 * 100 + 20);
    expect(r.seq.filter((x) => x === "walkin")).toHaveLength(100);
    expect(r.show.sizes()).toEqual({ pending: 0 });
  });

  test("the panel keeps a few shows only: finished ones go, and never more than MAX_SHOWS", () => {
    for (let k = 0; k < 20; k++) panel(view(() => [], { visitId: `v${k}` }), 0, 1);
    expect(showCount()).toBeLessThanOrEqual(MAX_SHOWS);
    forgetShows();
    // a visit played to its end and then another one: the finished show is let go
    panel(view(() => [], { leaveAt: 10, endedFor: 120, visitId: "a" }), 0, 20);
    panel(view(() => [], { visitId: "b" }), 20, 21);
    expect(showCount()).toBe(1);
  });

  test("two roles on the same visit: each its own show; switching back goes on where it was", () => {
    const aster = view(moving([[10, "created"], [10.5, "delivered"]]), { scope: "s|aster" });
    const basil = view(() => [], { scope: "s|basil" });
    expect(panel(aster, 0, 11).seq).toEqual(["arrive", "call", "wait", "walkin"]);
    expect(panel(basil, 11, 14).seq).toEqual(["arrive", "call"]);
    // back to aster at 14: the same show, mid-order (no second arrival)
    expect(panel(aster, 14, 30).seq).toEqual(["pay", "give", "eat", "walkout", "call", "wait"]);
  });

  test("the server stops answering about the visit mid-order: the show finishes from what it last knew, then the panel is empty", () => {
    // paid at 26, the visit ends at 30 and its `ended` window is cut short at 31; nothing is delivered as far as we know
    const r = panel(view(moving([[26, "created"], [26.5, "paid"]], { createdAt: 26 }), { leaveAt: 30, endedFor: 1 }), 0, 50);
    expect(r.seq.slice(-5)).toEqual(["walkin", "pay", "walkout_empty", "leave", "-"]);
    expect(r.all.at(-1)).toBeNull();
  });

  test("a new visit right after the old one, mid-order: the old order and the old vendor's leaving finish first, then the new vendor arrives", () => {
    // visit A until 30 (order walked over at 26, delivered at 29), visit B live from 31 (so A is never `ended`)
    const a = { ...RAW_VISIT, id: "A", leave_at: 30 }, b = { ...RAW_VISIT, id: "B", vendor: "tanghulu", leave_at: 10_000 };
    const f = moving([[26, "created"], [29, "delivered"]], { createdAt: 26 });
    const v = (t: number): VendorView => ({ ...parseVendor({ now: t, visit: t < 30 ? a : t >= 31 ? b : null, ended: t >= 30 && t < 31 ? a : null,
      mine: t < 31 ? f(t).map(rawOrder) : [] }), readAt: 0, scope: "s|aster" });
    const r = panel(v, 0, 49);
    expect(r.seq).toEqual(["arrive", "call", "wait", "call", "wait", "walkin", "pay", "give", "eat", "walkout", "leave", "arrive", "call"]);
    // the old vendor's clips up to his leaving, the new one's (tanghulu cart) after
    expect(r.all[Math.round(43.75 * 4)]).toBe("vendor_leave");
    expect(r.all[Math.round(44 * 4)]).toBe("vendor_th_arrive");
  });

  test("the new visit's orders read while the old show is still finishing are noted then, and played after his arrival", () => {
    // visit A until 30 with four orders backed up from 20; visit B (tanghulu) live from 31, its order read at 31.5, delivered at 32
    const a = { ...RAW_VISIT, id: "A", leave_at: 30 }, b = { ...RAW_VISIT, id: "B", vendor: "tanghulu", leave_at: 10_000 };
    const aOrders = (t: number) => (t < 20 ? [] : [0, 1, 2, 3].map((k) => rawOrder(order({ id: `a${k}`, createdAt: 20 + k / 10, updatedAt: 20.5, state: t >= 20.5 ? "delivered" : "created" }))));
    const bOrders = (t: number) => (t < 31.5 ? [] : [rawOrder(order({ id: "b0", createdAt: 31.5, updatedAt: t >= 32 ? 32 : 31.5, state: t >= 32 ? "delivered" : "created" }))]);
    const v = (t: number): VendorView => ({ ...parseVendor({ now: t, visit: t < 30 ? a : t >= 31 ? b : null, ended: t >= 30 && t < 31 ? a : null,
      mine: t < 31 ? aOrders(t) : bOrders(t) }), readAt: 0, scope: "s|aster" });
    const r = panel(v, 0, 110);
    // the old show: four orders, then that vendor leaves (it runs far past 31.5 + 30 s)
    const firstNew = r.all.indexOf("vendor_th_arrive");
    expect(firstNew / 4).toBeGreaterThan(31.5 + STALE_S);
    expect(r.seq.filter((x) => x === "walkin")).toHaveLength(5);
    // then the new vendor arrives and the order read at 31.5 plays, in order, once
    const after: string[] = [];
    let last = "";
    for (const seg of r.all.slice(firstNew)) if (seg && seg !== last) { after.push(seg); last = seg; }
    expect(after.slice(0, 7)).toEqual(["vendor_th_arrive", "vendor_th_walkin", "vendor_th_pay", "vendor_th_give", "vendor_th_eat", "vendor_th_walkout", "vendor_th_call"]);
  });

  test("a hundred orders through the panel: once they are all played, it keeps no order's facts", () => {
    const facts: Facts = (t) => {
      const out: VendorOrderFacts[] = [];
      for (let k = 0; k < 100 && 10 + 20 * k <= t; k++) {
        const c = 10 + 20 * k;
        out.push(order({ id: `o${k}`, createdAt: c, updatedAt: t >= c + 0.5 ? c + 0.5 : c, state: t >= c + 0.5 ? "delivered" : "created" }));
      }
      return out;
    };
    const r = panel(view(facts), 0, 10 + 20 * 100 + 20);
    expect(r.seq.filter((x) => x === "walkin")).toHaveLength(100);
    expect(cachedOrderCount()).toBe(0);
    // and mid-order it keeps only that one
    forgetShows();
    panel(view(facts), 0, 10 + 20 * 50 + 1);
    expect(cachedOrderCount()).toBe(1);
  });

  test("an ended visit this device never showed: nothing", () => {
    expect(panel(view(() => [], { leaveAt: 0 }), 1, 3).seq).toEqual(["-"]);
  });
});

test("reduce motion: the last frame of a clip that plays once; the vendor otherwise standing by his cart; otherwise the base pose", () => {
  expect(stillFor("machine_done")).toBe("machine_done_last");
  expect(stillFor("machine_run")).toBe("base");
  expect(stillFor("vendor_give")).toBe("vendor_give_last");
  expect(stillFor("vendor_th_eat")).toBe("vendor_th_eat_last");
  expect(stillFor("vendor_th_leave")).toBe("vendor_th_leave_last");
  expect(stillFor("vendor_walkin")).toBe("vendor_walkin_last");
  for (const p of ["arrive", "call", "wait", "pay", "walkout", "walkout_hold", "walkout_empty"]) {
    expect(stillFor(`vendor_${p}`)).toBe("vendor_still");
    expect(stillFor(`vendor_th_${p}`)).toBe("vendor_th_still");
  }
  expect(stillFor("vendor_th_still")).toBe("vendor_th_still");
});

test("every segment these name, and every still, is in the art for both outfits", () => {
  const named = new Set<string>(["base"]);
  for (let t = 0; t < 30; t += 0.25) named.add(washerClip(0, 1, t)!.segment);
  for (const vendor of ["tanghulu", "chestnut"]) {
    const visit = (t: number): VendorVisitFacts => ({ id: "v", vendor, leaveAt: 60, ended: t >= 60 });
    for (const f of [
      moving([[10, "created"], [10.5, "delivered"]]),
      moving([[10, "created"], [20, "delivered"]], { payer: "her", kind: "ingredient" }),
      moving([[10, "created"], [11, "paid"], [14, "refunded"]]),
    ]) for (const seg of play(f, 0, 70, visit).all) named.add(seg);
  }
  for (const n of [...named]) named.add(stillFor(n));
  expect([...named].sort()).toEqual([...CHORE_SEGMENTS].sort());
  for (const outfit of ["toque", "scarf"] as const) for (const k of CHORE_SEGMENTS) expect(CHORE_ART[outfit][k]).toBeDefined();
});

test("the outfit hash is the card's (FNV-1a), so an order wears the same as the card would pick", () => {
  // values from web/src/cookSegments.ts hashStr
  expect(hashStr("a")).toBe(0xe40c292c);
  expect(hashStr("")).toBe(0x811c9dc5);
});

describe("from what the server answers", () => {
  test("plates: only the dishwasher; a washing going on plays on its card in the chat, not here", () => {
    const p = parsePlates({ now: 1100, counts: { machine: 2 }, machine_at: 900,
      job: { id: "j", state: "running", started_at: 1000, per_s: 70, n: 2, ended_at: null, breaks: [0] } });
    expect(p.machineAt).toBe(900);
    const read = p.readAt;
    expect(platesClip(p, read)!.segment).toBe("machine_done_last"); // washing by hand right now: still the dishwasher's state
    expect(platesClip({ ...p, now: 905 }, read)!.segment).toBe("machine_close");
    expect(platesClip({ ...p, machineAt: null }, read)).toBeNull();
    expect(platesClip({ ...p, machine: 0 }, read)).toBeNull();
  });
  test("vendor: the visit, the role's orders and what each is (the order's own kind first, else the goods by name)", () => {
    forgetShows();
    const v = parseVendor({ now: 50, visit: { id: "v9", vendor: "chestnut", name: "x", who: "y", left_s: 60, leave_at: 110,
      goods: [{ id: "g1", name: "糖炒栗子", kind: "snack", unit: "袋", price: 6, left: 2 }, { id: "g2", name: "栗子", kind: "ingredient", unit: "份", price: 9, left: 1 }] },
      mine: [{ id: "o1", item_name: "栗子", kind: "ingredient", qty: 1, total: 9, payer: "self", state: "delivered", created_at: 49, updated_at: 49.5 }] });
    expect(v.visit!.vendor).toBe("chestnut");
    expect(v.visit!.leaveAt).toBe(110);
    expect(v.ended).toBeNull();
    expect(v.mine[0].kind).toBe("ingredient");
    expect(panel((t) => ({ ...v, now: t, readAt: 0 }), 50, 70).seq).toEqual(["arrive", "walkin", "pay", "give", "give_last", "walkout_hold", "call"]);
    forgetShows();
    const w = { ...v, mine: [{ ...v.mine[0], kind: undefined, name: "糖炒栗子" }] };
    expect(panel((t) => ({ ...w, now: t, readAt: 0 }), 50, 70).seq).toContain("eat");
    forgetShows();
  });
  test("the server's own answers carry the fields", () => {
    const c = contract as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
    expect(c.dishes).toHaveProperty("machine_at");
    expect(c.vendor.visit).toHaveProperty("id");
    expect(c.vendor.visit).toHaveProperty("vendor");
    expect(c.vendor.visit).toHaveProperty("leave_at");
    expect(c.vendor).toHaveProperty("ended");
    expect(c.vendor.visit.goods[0]).toHaveProperty("kind");
    expect(Array.isArray(c.vendor.mine)).toBe(true);
  });
  test("server time moves on with this device's clock", () => {
    expect(serverNow(100, 5000, 7000)).toBe(102);
    expect(serverNow(100, 5000, 4000)).toBe(100);
  });
});
