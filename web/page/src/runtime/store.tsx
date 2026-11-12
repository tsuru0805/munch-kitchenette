// What every part of the page shares: whose kitchen is open, the list of roles, what the server
// has switched on, a one-line toast, a yes/no question, and a "read everything again" signal.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import type { About } from "../kitchen/kitchenApi";
import { KC, KF } from "../kitchen/kitchenTheme";
import { ConfirmSheet, type ConfirmAsk } from "./ConfirmSheet";

export interface Store {
  /** the role whose kitchen is open */
  role: string;
  roles: string[];
  setRole: (r: string) => void;
  about: About;
  toast: (msg: string) => void;
  /** ask before doing something that cannot be taken back */
  confirm: (ask: ConfirmAsk) => void;
  /** goes up by one whenever everything should be read again (time was fast-forwarded, the page came back to the front) */
  tick: number;
  reloadAll: () => void;
}

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore outside StoreProvider");
  return s;
}

const TOAST_MS = 2600;

export function StoreProvider({
  about, role, setRole, children,
}: { about: About; role: string; setRole: (r: string) => void; children: ReactNode }) {
  const [msg, setMsg] = useState("");
  const [on, setOn] = useState(false);
  const [ask, setAsk] = useState<ConfirmAsk | null>(null);
  const [tick, setTick] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const op = useRef(new Animated.Value(0)).current;

  const toast = useCallback((m: string) => {
    if (!m) return;
    setMsg(m);
    setOn(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setOn(false), TOAST_MS);
  }, []);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);
  useEffect(() => {
    const anim = Animated.timing(op, { toValue: on ? 1 : 0, duration: 220, useNativeDriver: false });
    anim.start();
    return () => anim.stop();
  }, [on, op]);

  const confirm = useCallback((a: ConfirmAsk) => setAsk(a), []);
  const reloadAll = useCallback(() => setTick((n) => n + 1), []);
  const value = useMemo<Store>(
    () => ({ role, roles: about.roles, setRole, about, toast, confirm, tick, reloadAll }),
    [role, about, setRole, toast, confirm, tick, reloadAll],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <View style={st.wrap}>
        <Animated.View style={[st.toast, { opacity: op }]} testID="toast" aria-live="polite">
          <Text style={st.text}>{msg}</Text>
        </Animated.View>
      </View>
      <ConfirmSheet ask={ask} onDone={() => setAsk(null)} />
    </Ctx.Provider>
  );
}

const st = StyleSheet.create({
  wrap: { position: "absolute", left: 0, right: 0, bottom: 34, alignItems: "center", pointerEvents: "none" },
  toast: { backgroundColor: KC.ink, paddingVertical: 9, paddingHorizontal: 16, borderRadius: 8, maxWidth: 320 },
  text: { color: "#fffdf8", fontSize: 12, lineHeight: 18, fontFamily: KF, textAlign: "center" },
});
