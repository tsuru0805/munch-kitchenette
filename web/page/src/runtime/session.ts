// Where the kitchen server is and the token to talk to it. The token lives in memory; a page opened
// on its own may also keep it in this browser's local storage (see App.tsx). It is only ever sent
// as an Authorization header, never put in an address.

export interface Conn {
  /** Server origin, e.g. "https://kitchen.example.com"; "" = the origin this page was loaded from. */
  base: string;
  token: string;
}

let conn: Conn = { base: "", token: "" };
const listeners = new Set<() => void>();

export function getConn(): Conn {
  return conn;
}

export function setConn(next: Partial<Conn>): void {
  conn = { ...conn, ...next, base: (next.base ?? conn.base).replace(/\/+$/, "") };
  [...listeners].forEach((fn) => fn());
}

export function subscribeConn(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function authHeaders(): Record<string, string> {
  return conn.token ? { Authorization: `Bearer ${conn.token}` } : {};
}

const TOKEN_KEY = "kitchenette.token";
const ROLE_KEY = "kitchenette.role";

function store(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null; // storage can be blocked (private mode, a framed page): the page then asks again each time
  }
}

export const saved = {
  token: (): string => store()?.getItem(TOKEN_KEY) ?? "",
  setToken: (t: string): void => {
    try {
      if (t) store()?.setItem(TOKEN_KEY, t);
      else store()?.removeItem(TOKEN_KEY);
    } catch {
      /* not saved: asked again next time */
    }
  },
  role: (): string => store()?.getItem(ROLE_KEY) ?? "",
  setRole: (r: string): void => {
    try {
      store()?.setItem(ROLE_KEY, r);
    } catch {
      /* not remembered */
    }
  },
};
