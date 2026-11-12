// Reading a pot from the backend: what the answer carries, and what each kind of failure is called.
import { KitchenFetchError, _resetApiCache, apiProbe, fetchKitchen, parseAnswer } from "./api";

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
  expect(parseAnswer({ now: 1, session: pot, timezone: "Asia/Tokyo" })).toEqual({ session: pot, timezone: "Asia/Tokyo" });
  expect(parseAnswer({ now: 1, session: pot, timezone: "" })).toEqual({ session: pot, timezone: "" });
  expect(parseAnswer({ now: 1, session: pot })).toEqual({ session: pot, timezone: "" });
  expect(parseAnswer({ session: null, timezone: 9 })).toEqual({ session: null, timezone: "" });
  expect(parseAnswer(null)).toEqual({ session: null, timezone: "" });
});

test("a good answer is asked for with the bearer token and comes back whole", async () => {
  const fetchMock = vi.fn(async () => json(200, { now: 1, session: pot, timezone: "Europe/Paris" }));
  vi.stubGlobal("fetch", fetchMock);
  expect(await fetchKitchen("https://k.example/", "ck 1", "tok")).toEqual({ session: pot, timezone: "Europe/Paris" });
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
