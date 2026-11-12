// Talking to the page that embeds this one (docs/PAGE.md, "Embedding"). Protocol v1, a handful of messages:
//
//   page -> host   ready {v: 1}              the page can take `init` now
//                  close                     the person pressed "back"
//   host -> page   init {apiBase?, credential?, who?}
//                  role {who}                show this role's kitchen
//                  logout                    forget the credential, wait for a new `init`
//
// Every host message is answered with {id, ok: true, result} or {id, ok: false, error}.
// The credential only ever travels in `init`: never in an address, so it reaches no server log.
//
// In an <iframe> the page talks to exactly one registered origin: the one named in ?host=, which must
// also be the real parent where the browser can tell (location.ancestorOrigins). A framed page without
// ?host= sends and accepts nothing and behaves as if opened on its own.

export type Mode = "standalone" | "iframe" | "native";

export interface Msg {
  v: 1;
  id: string;
  type: string;
  payload: Record<string, unknown>;
}

export interface Env {
  search: string;
  framed: boolean;
  /** location.ancestorOrigins as a list, or null where the browser has none (Firefox) */
  ancestors: string[] | null;
  nativeBridge: boolean;
}

function originOf(value: string | null): string | null {
  if (!value) return null;
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:" ? u.origin : null;
  } catch {
    return null;
  }
}

/** Which way the page was opened, and (in a frame) the one origin it may talk to. */
export function detect(env: Env): { mode: Mode; hostOrigin: string | null } {
  const q = new URLSearchParams(env.search);
  if (q.get("embed") === "native" || env.nativeBridge) return { mode: "native", hostOrigin: null };
  if (!env.framed) return { mode: "standalone", hostOrigin: null };
  const named = originOf(q.get("host"));
  if (!named) return { mode: "standalone", hostOrigin: null };
  // a page that frames this one cannot pass itself off as another origin
  if (env.ancestors && env.ancestors.length && env.ancestors[0] !== named) return { mode: "standalone", hostOrigin: null };
  return { mode: "iframe", hostOrigin: named };
}

/** A host message, or null for anything that is not one (other scripts post messages too). */
export function parseMsg(raw: unknown): Msg | null {
  let m: unknown = raw;
  if (typeof raw === "string") {
    try {
      m = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!m || typeof m !== "object") return null;
  const r = m as Record<string, unknown>;
  if (r.v !== 1 || typeof r.type !== "string" || !r.type) return null;
  const payload = r.payload && typeof r.payload === "object" ? (r.payload as Record<string, unknown>) : {};
  return { v: 1, id: typeof r.id === "string" ? r.id : "", type: r.type, payload };
}

export type InitCheck = { ok: true; base: string; token: string; who: string | null } | { ok: false; error: string };

/** What `init` carries. apiBase "" or missing = the server the page came from. */
export function checkInit(p: Record<string, unknown>): InitCheck {
  const base = typeof p.apiBase === "string" ? p.apiBase.trim().replace(/\/+$/, "") : "";
  if (base && !/^https?:\/\//.test(base)) return { ok: false, error: "apiBase must start with http:// or https://" };
  const token = typeof p.credential === "string" ? p.credential : "";
  const who = typeof p.who === "string" && p.who ? p.who : null;
  return { ok: true, base, token, who };
}

export interface HostHandlers {
  init: (i: { base: string; token: string; who: string | null }) => Promise<string | null>; // an error sentence, or null
  role: (who: string) => void;
  logout: () => void;
}

export interface Host {
  mode: Mode;
  /** tell the host the person wants to leave; false = nobody to tell */
  close: () => boolean;
  stop: () => void;
}

type Bridge = { postMessage: (m: string) => void };
type W = Window & {
  webkit?: { messageHandlers?: { kitchenette?: Bridge } };
  ReactNativeWebView?: Bridge;
  KitchenetteHost?: Bridge;
  kitchenette?: { receive: (m: unknown) => void };
};

function nativeOut(w: W): Bridge | null {
  return w.webkit?.messageHandlers?.kitchenette ?? w.ReactNativeWebView ?? w.KitchenetteHost ?? null;
}

/** Read the environment once, wire the messages, and say `ready`. */
export function startHost(handlers: HostHandlers): Host {
  if (typeof window === "undefined") return { mode: "standalone", close: () => false, stop: () => {} };
  const w = window as W;
  const anc = (w.location as Location & { ancestorOrigins?: DOMStringList }).ancestorOrigins;
  const { mode, hostOrigin } = detect({
    search: w.location.search,
    framed: w.parent !== w,
    ancestors: anc ? Array.from(anc) : null,
    nativeBridge: nativeOut(w) !== null,
  });
  if (mode === "standalone") return { mode, close: () => false, stop: () => {} };

  let seq = 0;
  const send = (m: Record<string, unknown>) => {
    if (mode === "iframe" && hostOrigin) w.parent.postMessage(m, hostOrigin);
    else nativeOut(w)?.postMessage(JSON.stringify(m));
  };
  const handle = async (raw: unknown) => {
    const m = parseMsg(raw);
    if (!m) return;
    const reply = (ok: boolean, extra: Record<string, unknown>) => send({ v: 1, id: m.id, ok, ...extra });
    if (m.type === "init") {
      const c = checkInit(m.payload);
      if (!c.ok) return reply(false, { error: c.error });
      const err = await handlers.init(c);
      return err ? reply(false, { error: err }) : reply(true, { result: { v: 1 } });
    }
    if (m.type === "role") {
      const who = typeof m.payload.who === "string" ? m.payload.who : "";
      if (!who) return reply(false, { error: "role needs who" });
      handlers.role(who);
      return reply(true, { result: {} });
    }
    if (m.type === "logout") {
      handlers.logout();
      return reply(true, { result: {} });
    }
    // unknown types are dropped without an answer
  };
  const onMessage = (e: MessageEvent) => {
    if (e.origin !== hostOrigin || e.source !== w.parent) return;
    void handle(e.data);
  };
  if (mode === "iframe") w.addEventListener("message", onMessage);
  else w.kitchenette = { receive: (m) => void handle(m) };
  send({ v: 1, id: `p${++seq}`, type: "ready", payload: { v: 1 } });
  return {
    mode,
    close: () => {
      send({ v: 1, id: `p${++seq}`, type: "close", payload: {} });
      return true;
    },
    stop: () => {
      if (mode === "iframe") w.removeEventListener("message", onMessage);
      else delete w.kitchenette;
    },
  };
}
