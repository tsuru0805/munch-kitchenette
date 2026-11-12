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

/** Whose kitchen opens first: the one asked for, else the one opened last time, else the default (only roles the server lists) */
export function firstRole(about: About, wanted: string | null, last: string): string {
  if (wanted && about.roles.includes(wanted)) return wanted;
  if (last && about.roles.includes(last)) return last;
  return about.defaultRole;
}

export default function App() {
  const [phase, setPhase] = useState<Phase>("boot");
  const [about, setAbout] = useState<About | null>(null);
  const [role, setRoleState] = useState("");
  const [session, setSession] = useState(0); // goes up on every new connection: the page starts over
  const [gateErr, setGateErr] = useState("");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const host = useRef<Host | null>(null);
  const wanted = useRef<string | null>(null);
  const width = usePageWidth();

  const setRole = useCallback((r: string) => {
    saved.setRole(r);
    setRoleState(r);
  }, []);

  const reach = useCallback(async (): Promise<Reach> => {
    try {
      const a = await fetchAbout();
      setAbout(a);
      setRoleState(firstRole(a, wanted.current, saved.role()));
      setSession((n) => n + 1);
      setPhase("ready");
      return "ok";
    } catch (e) {
      return e instanceof FridgeHttpError && e.status === 401 ? "unauthorized" : "offline";
    }
  }, []);

  const bootAlone = useCallback(async () => {
    setPhase("boot");
    const r = await reach();
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
        const r = await reach();
        if (r === "ok") return null;
        setConn({ token: "" });
        return r === "unauthorized" ? "the kitchen server refused the credential" : "the kitchen server cannot be reached";
      },
      role: (who) => setRole(who),
      logout: () => {
        setConn({ token: "" });
        setAbout(null);
        setPhase("host");
      },
    });
    host.current = h;
    if (h.mode === "standalone") {
      setConn({ base: q.api, token: saved.token() });
      void bootAlone();
    } else {
      setPhase("host");
    }
    return () => h.stop();
  }, [bootAlone, reach, setRole]);

  const enter = async () => {
    const token = draft.trim();
    if (!token || busy) return;
    setBusy(true);
    setGateErr("");
    setConn({ token });
    const r = await reach();
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
    setAbout(null);
    setGateErr("");
    setPhase("gate");
  };

  if (phase === "ready" && about) {
    const embedded = host.current !== null && host.current.mode !== "standalone";
    return (
      <StoreProvider key={session} about={about} role={about.roles.includes(role) ? role : about.defaultRole} setRole={setRole}>
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
  input: { fontFamily: KF, fontSize: 15, lineHeight: 22, color: KC.ink, outlineWidth: 0 },
});
