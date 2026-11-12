// The embedding protocol's pure parts: how the page decides where it is, and what it accepts from a host.
import { checkInit, detect, parseMsg } from "./host";

const env = (over: Partial<Parameters<typeof detect>[0]> = {}) => ({ search: "", framed: false, ancestors: null, nativeBridge: false, ...over });

describe("where the page is", () => {
  test("opened on its own", () => {
    expect(detect(env())).toEqual({ mode: "standalone", hostOrigin: null });
    expect(detect(env({ search: "?host=https%3A%2F%2Fhost.example" }))).toEqual({ mode: "standalone", hostOrigin: null });   // not framed: ?host= means nothing
  });
  test("in a frame: only with ?host=, and only when it is the real parent", () => {
    const search = "?host=https%3A%2F%2Fhost.example%2Fsome%2Fpath";
    expect(detect(env({ framed: true, search }))).toEqual({ mode: "iframe", hostOrigin: "https://host.example" });
    expect(detect(env({ framed: true, search, ancestors: ["https://host.example"] }))).toEqual({ mode: "iframe", hostOrigin: "https://host.example" });
    // a page that frames this one cannot pass itself off as another origin
    expect(detect(env({ framed: true, search, ancestors: ["https://evil.example"] }))).toEqual({ mode: "standalone", hostOrigin: null });
    // framed without ?host=: the page talks to nobody
    expect(detect(env({ framed: true, ancestors: ["https://host.example"] }))).toEqual({ mode: "standalone", hostOrigin: null });
    expect(detect(env({ framed: true, search: "?host=javascript:alert(1)" })).mode).toBe("standalone");
  });
  test("in an app's web view", () => {
    expect(detect(env({ nativeBridge: true })).mode).toBe("native");
    expect(detect(env({ search: "?embed=native" })).mode).toBe("native");
  });
});

describe("messages from a host", () => {
  test("an object or a JSON string, version 1, with a type", () => {
    expect(parseMsg({ v: 1, id: "a", type: "init", payload: { who: "x" } })).toEqual({ v: 1, id: "a", type: "init", payload: { who: "x" } });
    expect(parseMsg('{"v":1,"type":"logout"}')).toEqual({ v: 1, id: "", type: "logout", payload: {} });
    for (const bad of [null, 3, "nope", "{", { v: 2, type: "init" }, { v: 1 }, { v: 1, type: "" }, { type: "init" }]) expect(parseMsg(bad)).toBeNull();
  });
  test("init: the server address is optional and must be http(s); the credential and the role are passed on", () => {
    expect(checkInit({})).toEqual({ ok: true, base: "", token: "", who: null });
    expect(checkInit({ apiBase: "https://kitchen.example.com/", credential: "s3cret", who: "aster" })).toEqual({ ok: true, base: "https://kitchen.example.com", token: "s3cret", who: "aster" });
    expect(checkInit({ apiBase: "ftp://x" }).ok).toBe(false);
    expect(checkInit({ apiBase: 5, credential: 7, who: "" })).toEqual({ ok: true, base: "", token: "", who: null });
  });
});
