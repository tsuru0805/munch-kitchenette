// Start-up: find the kitchen server, get past its token if it has one, learn who lives there, then
// show the page.
//
// Opened on its own, the page talks to the server it was loaded from (or the one named in ?api=).
// If that server wants a token, the page asks for it once and keeps it in this browser's local
// storage; "换口令" at the bottom of the page forgets it. Embedded in another page or an app
// (docs/PAGE.md), the host hands over the address and the token in an `init` message instead, and
// nothing is stored. Either way the token is only ever sent as an Authorization header.
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { FridgeHttpError } from "./kitchen/fridgeApi";
import { fetchAbout, type About } from "./kitchen/kitchenApi";
import { KC, KF } from "./kitchen/kitchenTheme";
import { Label, Paper, SheetBtn, SheetFoot, sh } from "./kitchen/sheetParts";
import { KitchenPage } from "./KitchenPage";
import { startHost, type Host } from "./runtime/host";
import { usePageWidth } from "./runtime/layout";
import { getConn, saved, setConn } from "./runtime/session";
import { StoreProvider } from "./runtime/store";

type Phase = "boot" | "host" | "gate" | "offline" | "ready";
type Reach = "ok" | "unauthorized" | "offline";
/** What a framed page says while it has no kitchen to show: waiting for its host, or why the host's init failed */
type HostWait = "waiting" | "refused" | "unreachable";

/** ?who= and ?api= of the address (neither is a secret); api must be an http(s) origin */
export function readQuery(search: string): { who: string | null; api: string } {
  const q = new URLSearchParams(search);
  let api = "";
  try {
    const u = new URL(q.get("api") ?? "");
    if (u.protocol === "http:" || u.protocol === "https:") api = u.origin;
  } catch {
    api = "";
  }
  return { who: q.get("who") || null, api };
}

/**
 * Whose kitchen opens first. Only roles the server lists can be opened.
 * A role that was asked for and is listed: that one. Asked for but not listed: the default role, and
 * `unknown` carries the name so the page can say so. Nothing asked for: the one opened last time in
 * this browser if it is still listed, else the default.
 */
export function firstRole(about: About, wanted: string | null, last: string): { role: string; unknown: string | null } {
  if (wanted) return about.roles.includes(wanted) ? { role: wanted, unknown: null } : { role: about.defaultRole, unknown: wanted };
  if (last && about.roles.includes(last)) return { role: last, unknown: null };
  return { role: about.defaultRole, unknown: null };
}

/** The sentence a host gets back for a role the server does not list */
export function unknownRoleError(who: string, about: About): string {
  return `unknown role "${who}": the kitchen server lists ${about.roles.map((r) => `"${r}"`).join(", ")}`;
}

const HOST_WAIT_TEXT: Record<HostWait, string> = {
  waiting: "在等嵌入它的页面给口令…",
  refused: "口令不对 · 在等嵌入它的页面重新给",
  unreachable: "厨房没连上 · 在等嵌入它的页面重试",
};

export default function App() {
  const [phase, setPhase] = useState<Phase>("boot");
  const [about, setAbout] = useState<About | null>(null);
  const [role, setRoleState] = useState("");
  const [unknown, setUnknown] = useState("");
  const [session, setSession] = useState(0); // goes up on every new connection: the page starts over
  const [gateErr, setGateErr] = useState("");
  const [hostWait, setHostWait] = useState<HostWait>("waiting");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const host = useRef<Host | null>(null);
  const wanted = useRef<string | null>(null);
  const aboutRef = useRef<About | null>(null);
  const width = usePageWidth();

  const keepAbout = useCallback((a: About | null) => {
    aboutRef.current = a;
    // the same answer as before changes nothing (the page asks again on every re-read)
    setAbout((cur) => (cur && a && JSON.stringify(cur) === JSON.stringify(a) ? cur : a));
  }, []);

  const setRole = useCallback((r: string) => {
    saved.setRole(r);
    setRoleState(r);
    setUnknown("");
  }, []);

  /** Connect. `unknown` = a role that was asked for and that the server does not list (the default is opened instead). */
  const reach = useCallback(async (): Promise<{ r: Reach; unknown: string | null }> => {
    try {
      const a = await fetchAbout();
      const first = firstRole(a, wanted.current, saved.role());
      keepAbout(a);
      setRoleState(first.role);
      setUnknown(first.unknown ?? "");
      setSession((n) => n + 1);
      setPhase("ready");
      return { r: "ok", unknown: first.unknown };
    } catch (e) {
      return { r: e instanceof FridgeHttpError && e.status === 401 ? "unauthorized" : "offline", unknown: null };
    }
  }, [keepAbout]);

  /** With every re-read of the page: who lives here and what is switched on may have changed. A failure keeps what is known. */
  const refreshAbout = useCallback(() => {
    fetchAbout().then((a) => aboutRef.current && keepAbout(a), () => {});
  }, [keepAbout]);

  const bootAlone = useCallback(async () => {
    setPhase("boot");
    const { r } = await reach();
    if (r === "unauthorized") {
      if (getConn().token) saved.setToken(""); // the token kept from last time no longer opens the door
      setConn({ token: "" });
      setGateErr("");
      setPhase("gate");
    } else if (r === "offline") {
      setPhase("offline");
    }
  }, [reach]);

  useEffect(() => {
    const q = readQuery(typeof window === "undefined" ? "" : window.location.search);
    wanted.current = q.who;
    const h = startHost({
      init: async (i) => {
        wanted.current = i.who ?? wanted.current;
        setConn({ base: i.base, token: i.token });
        const got = await reach();
        if (got.r === "ok") {
          // the kitchen is open on the default role; the host still learns that the one it named does not exist
          return got.unknown && aboutRef.current ? `${unknownRoleError(got.unknown, aboutRef.current)}; showing "${aboutRef.current.defaultRole}"` : null;
        }
        setConn({ token: "" });
        keepAbout(null);
        setHostWait(got.r === "unauthorized" ? "refused" : "unreachable");
        setPhase("host");
        return got.r === "unauthorized" ? "the kitchen server refused the credential" : "the kitchen server cannot be reached";
      },
      role: async (who) => {
        if (!aboutRef.current) return "not connected: send init first";
        if (!aboutRef.current.roles.includes(who)) {
          // a role may have come into being since the page connected: ask the server once more before refusing
          await fetchAbout().then((a) => aboutRef.current && keepAbout(a), () => {});
        }
        const a = aboutRef.current;
        if (!a) return "not connected: send init first";
        if (!a.roles.includes(who)) {
          setUnknown(who);
          return unknownRoleError(who, a);
        }
        setRole(who);
        return null;
      },
      logout: () => {
        setConn({ token: "" });
        keepAbout(null);
        setHostWait("waiting");
        setPhase("host");
      },
    });
    host.current = h;
    if (h.mode === "standalone") {
      setConn({ base: q.api, token: saved.token() });
      void bootAlone();
    } else {
      setHostWait("waiting");
      setPhase("host");
    }
    return () => h.stop();
  }, [bootAlone, keepAbout, reach, setRole]);

  const enter = async () => {
    const token = draft.trim();
    if (!token || busy) return;
    setBusy(true);
    setGateErr("");
    setConn({ token });
    const { r } = await reach();
    setBusy(false);
    if (r === "ok") {
      saved.setToken(token);
      setDraft("");
      return;
    }
    setConn({ token: "" });
    setGateErr(r === "unauthorized" ? "口令不对" : "厨房没连上");
  };

  const forget = () => {
    saved.setToken("");
    setConn({ token: "" });
    keepAbout(null);
    setGateErr("");
    setPhase("gate");
  };
  const dismissUnknown = useCallback(() => setUnknown(""), []);

  if (phase === "ready" && about) {
    const embedded = host.current !== null && host.current.mode !== "standalone";
    return (
      <StoreProvider
        key={session}
        about={about}
        role={about.roles.includes(role) ? role : about.defaultRole}
        setRole={setRole}
        unknownRole={unknown}
        dismissUnknownRole={dismissUnknown}
        onReload={refreshAbout}
      >
        <KitchenPage
          onBack={embedded ? () => void host.current?.close() : undefined}
          onForgetToken={!embedded && getConn().token ? forget : undefined}
        />
      </StoreProvider>
    );
  }

  return (
    <View style={st.root}>
      <View style={[st.col, { width }]}>
        {phase === "gate" ? (
          <Paper testID="token-gate">
            <Label first>口令</Label>
            <Text style={st.hint} testID="token-hint">这间厨房的服务设了口令：填服务设置里 [server] 那一段的 token。</Text>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              onSubmitEditing={enter}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="口令"
              placeholderTextColor="#c4b5a8"
              style={[sh.field, st.input]}
              testID="token-input"
            />
            {gateErr ? <Text style={sh.err} testID="token-err">{gateErr}</Text> : null}
            <SheetFoot>
              <SheetBtn label={busy ? "稍等…" : "进厨房"} onPress={enter} disabled={!draft.trim() || busy} testID="token-enter" />
            </SheetFoot>
          </Paper>
        ) : phase === "offline" ? (
          <Pressable onPress={bootAlone} accessibilityRole="button" testID="offline-retry">
            <Text style={st.status}>厨房没连上 · 点一下重试</Text>
          </Pressable>
        ) : phase === "host" ? (
          // embedded: there is nothing to tap here, the page that embeds this one has to act
          <Text style={st.status} testID="host-wait">{HOST_WAIT_TEXT[hostWait]}</Text>
        ) : (
          <Text style={st.status} testID="booting">读取中…</Text>
        )}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: KC.bg, alignItems: "center" },
  col: { flex: 1, paddingTop: 96 },
  status: { fontFamily: KF, fontSize: 13, lineHeight: 20, color: KC.soft, paddingVertical: 22, textAlign: "center" },
  hint: { fontFamily: KF, fontSize: 11, lineHeight: 17, letterSpacing: 0.5, color: KC.soft, marginBottom: 6 },
  input: { fontFamily: KF, fontSize: 15, lineHeight: 22, color: KC.ink, outlineWidth: 0 },
});
