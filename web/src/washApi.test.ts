// Reading one washing back: what the answer carries, the attachment, and what each failure is called.
import { KitchenFetchError } from "./api";
import { factsFromAttachment, fetchWashing, parseWashRead, washApiProbe } from "./washApi";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const job = {
  now: 1_800_000_300, id: "j1", who: "aster", state: "running", started_at: 1_800_000_000, per_s: 120, n: 3, ended_at: null,
  counts: { washing: 2, clean: 0, broken: 1, machine: 0 },
  dishes: [{ i: 0, state: "broken", done_at: 1_800_000_120 }, { i: 1, state: "washing", done_at: null }, { i: 2, state: "washing", done_at: null }],
  timezone: "Asia/Tokyo",
};

afterEach(() => vi.unstubAllGlobals());

test("the attachment a [刷盘子] hands the chat", () => {
  expect(factsFromAttachment({ kind: "kitchen_washing", job_id: "j1", who: "aster", n: 3, per_s: 120, started_at: 1_800_000_000 }))
    .toEqual({ jobId: "j1", startedAt: 1_800_000_000, perS: 120, n: 3 });
  expect(factsFromAttachment({ job_id: "j1" })).toBeNull(); // no start time: nothing to count from
  expect(factsFromAttachment(null)).toBeNull();
});

test("the answer: state, counts and each plate", () => {
  const r = parseWashRead(job)!;
  expect(r).toMatchObject({ state: "running", startedAt: 1_800_000_000, perS: 120, n: 3, endedAt: null, timezone: "Asia/Tokyo" });
  expect(r.counts).toEqual({ washing: 2, clean: 0, broken: 1, machine: 0 });
  expect(r.dishes[0]).toEqual({ i: 0, state: "broken", doneAt: 1_800_000_120 });
  expect(parseWashRead({ detail: "no" })).toBeNull();
  expect(parseWashRead(null)).toBeNull();
});

test("read with the bearer token from /api/dishes/jobs/<id>", async () => {
  const fetchMock = vi.fn(async () => json(200, job));
  vi.stubGlobal("fetch", fetchMock);
  expect((await fetchWashing("https://k.example/", "j 1", "tok")).state).toBe("running");
  expect(fetchMock).toHaveBeenCalledWith("https://k.example/api/dishes/jobs/j%201", { headers: { Authorization: "Bearer tok" } });
});

test("failures say which they are; a washing the backend does not know reads as null through the probe", async () => {
  for (const [status, kind] of [[401, "unauthorized"], [404, "not_found"], [500, "server"]] as const) {
    vi.stubGlobal("fetch", vi.fn(async () => json(status, { detail: "x" })));
    const e = (await fetchWashing("https://k.example", "j1").catch((x: unknown) => x)) as KitchenFetchError;
    expect(e).toBeInstanceOf(KitchenFetchError);
    expect([e.kind, e.status]).toEqual([kind, status]);
  }
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { something: "else" })));
  expect(((await fetchWashing("https://k.example", "j1").catch((x: unknown) => x)) as KitchenFetchError).kind).toBe("bad_response");
  vi.stubGlobal("fetch", vi.fn(async () => json(404, { detail: "no such washing" })));
  expect(await washApiProbe("https://k.example")("j1")).toBeNull();
  vi.stubGlobal("fetch", vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  }));
  await expect(washApiProbe("https://k.example")("j1")).rejects.toMatchObject({ kind: "unreachable" });
});
