// Reading a pot from the backend: what the answer carries, and what each kind of failure is called.
import { KitchenFetchError, _resetApiCache, apiProbe, fetchKitchen, parseAnswer, parseSettlement, parseSettleMissing, probeFromSession } from "./api";

const pot = { id: "ck_1", dish: "soup", duration_seconds: 600, started_at: 1_800_000_000, status: "served", outcome: "great" };
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.unstubAllGlobals();
  _resetApiCache();
});

async function failure(run: () => Promise<unknown>): Promise<KitchenFetchError> {
  try {
    await run();
  } catch (e) {
    return e as KitchenFetchError;
  }
  throw new Error("expected a failure");
}

test("the answer: the pot and the server's time zone ('' when it has none or does not say)", () => {
  expect(parseAnswer({ now: 1, session: pot, timezone: "Asia/Tokyo" })).toEqual({ session: pot, timezone: "Asia/Tokyo", settlement: null, settleMissing: null });
  expect(parseAnswer({ now: 1, session: pot, timezone: "" })).toEqual({ session: pot, timezone: "", settlement: null, settleMissing: null });
  expect(parseAnswer({ now: 1, session: pot })).toEqual({ session: pot, timezone: "", settlement: null, settleMissing: null });
  expect(parseAnswer({ session: null, timezone: 9 })).toEqual({ session: null, timezone: "", settlement: null, settleMissing: null });
  expect(parseAnswer(null)).toEqual({ session: null, timezone: "", settlement: null, settleMissing: null });
});

test("a good answer is asked for with the bearer token and comes back whole", async () => {
  const fetchMock = vi.fn(async () => json(200, { now: 1, session: pot, timezone: "Europe/Paris" }));
  vi.stubGlobal("fetch", fetchMock);
  expect(await fetchKitchen("https://k.example/", "ck 1", "tok")).toEqual({ session: pot, timezone: "Europe/Paris", settlement: null, settleMissing: null });
  expect(fetchMock).toHaveBeenCalledWith("https://k.example/api/kitchen?session_id=ck%201", { headers: { Authorization: "Bearer tok" } });
  const probe = await apiProbe("https://k.example", "tok")("ck_1", true);
  expect(probe).toMatchObject({ status: "served", outcome: "great", timezone: "Europe/Paris" });
});

test("refused, missing, broken: each failure says which it is and carries the status", async () => {
  for (const [status, kind] of [[401, "unauthorized"], [403, "unauthorized"], [404, "not_found"], [500, "server"], [502, "server"]] as const) {
    vi.stubGlobal("fetch", vi.fn(async () => json(status, { detail: "x" })));
    const e = await failure(() => fetchKitchen("https://k.example", "ck_1"));
    expect(e).toBeInstanceOf(KitchenFetchError);
    expect([e.kind, e.status]).toEqual([kind, status]);
    expect(e.message).toContain(`status ${status}`);
  }
  vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>", { status: 200 })));
  expect((await failure(() => fetchKitchen("https://k.example", "ck_1"))).kind).toBe("bad_response");
});

test("no readable answer: 'blocked' when the server does answer a request the page cannot read, 'unreachable' when nothing answers", async () => {
  // the browser refuses the normal request; the second, unreadable one gets through = the server is up
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.mode === "no-cors") return new Response(null);
    throw new TypeError("Failed to fetch");
  }));
  const blocked = await failure(() => fetchKitchen("https://k.example", "ck_1", "tok"));
  expect([blocked.kind, blocked.status]).toEqual(["blocked", null]);

  vi.stubGlobal("fetch", vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  }));
  const down = await failure(() => fetchKitchen("https://k.example", "ck_1"));
  expect([down.kind, down.status]).toEqual(["unreachable", null]);
});

describe("the settled card", () => {
  it("is read only when the answer says it has one", () => {
    expect(parseSettlement(null)).toBeNull();
    expect(parseSettlement({ has: false, why: "legacy" })).toBeNull();
    const s = parseSettlement({
      has: true, outcome: "great", link: "follow", proficiency: { tier: "拿手", n: 3, to_next: 5 },
      mishap: { state: "none", text: "一路顺利" }, stamps: [{ key: "follow", text: "照谱做成" }],
    })!;
    expect(s.proficiency).toEqual({ tier: "拿手", n: 3, toNext: 5, nextTier: null, tierFrom: null });
    expect(parseSettlement({ has: true, proficiency: { tier: "拿手", n: 5, to_next: 3, next_tier: "招牌", tier_from: 3 } })!.proficiency)
      .toEqual({ tier: "拿手", n: 5, toNext: 3, nextTier: "招牌", tierFrom: 3 });
    expect(s.mishap).toEqual({ state: "none", text: "一路顺利" });
    expect(s.stamps).toEqual(["照谱做成"]);
    expect(parseAnswer({ session: null, timezone: "", settlement: { has: true, proficiency: null, mishap: null, stamps: [] } }).settlement)
      .toEqual({ outcome: "", link: "free", proficiency: null, mishap: null, icon: "", stamps: [] });
  });

  it("tells why there is none: an old pot keeps the outcome it had, if it is still known", () => {
    expect(parseSettleMissing({ has: false, why: "legacy", legacy_outcome: "burnt" })).toEqual({ why: "legacy", legacyOutcome: "burnt" });
    expect(parseSettleMissing({ has: false, why: "legacy", legacy_outcome: null })).toEqual({ why: "legacy", legacyOutcome: null });
    expect(parseSettleMissing({ has: false, why: "legacy", legacy_outcome: "raw" })).toEqual({ why: "legacy", legacyOutcome: null });
    expect(parseSettleMissing({ has: true })).toBeNull();
    expect(parseSettleMissing(undefined)).toBeNull();
    expect(parseAnswer({ session: null, settlement: { has: false, why: "feature_off" } }).settleMissing).toEqual({ why: "feature_off", legacyOutcome: null });
  });

  it("a ruined pot is its own status", () => {
    expect(probeFromSession({ id: "x", dish: "d", duration_seconds: 60, started_at: 1, status: "ruined", outcome: null }).status).toBe("ruined");
  });
});
