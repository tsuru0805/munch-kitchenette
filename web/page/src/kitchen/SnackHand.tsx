// The snacks on the upper shelf: tap one and it is the one in the hand.
// Whom it is fed to (the list of roles) -> a flavour for coffee -> feed one serving; eaten today /
// the daily cap; the cap is changed per snack. Counts and caps are the same book the role's own
// snack tool writes to (on the server), which refuses past the cap with 409; the server's sentence
// is shown. What a serving restores is only shown while stamina is switched on.
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useStore } from "../runtime/store";
import { FRIDGE_ART, type FridgeArtId } from "./art.generated";
import type { Viewer } from "./fridgeApi";
import { Act, Acts, Bar, BarTx, Big, HandShell, HeroArt, Line, Name, Ring, Sp, Status, Thumbs, Top, lineInk } from "./handParts";
import { KC, KF, bodoniFor } from "./kitchenTheme";
import {
  SnackCapError, SnacksUnsupportedError, feedSnack, fetchSnacks, gainText, resetText, saveSnackCaps, stepCap,
  type Snack, type SnackState,
} from "./snacksApi";

type Load = { kind: "loading" } | { kind: "ok"; st: SnackState } | { kind: "unsupported" } | { kind: "error" };

/** Which picture a snack is drawn with (coffee by the chosen flavour; none chosen / no such picture = the americano) */
export function snackArt(id: string, variant?: string | null): FridgeArtId | null {
  const key = id === "coffee" ? `snack_coffee_${variant || "americano"}` : `snack_${id}`;
  if (key in FRIDGE_ART) return key as FridgeArtId;
  return id === "coffee" ? "snack_coffee_americano" : null;
}

export function SnackHand({
  snackId, anchor, sceneH, onPick,
}: { snackId: string; anchor: { x: number; y: number } | null; sceneH: number; onPick: (id: string) => void }) {
  const { toast, role, roles, tick } = useStore();
  const [viewer, setViewer] = useState<Viewer>(role);
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [variantPick, setVariantPick] = useState<Record<string, string>>({});
  const [capDraft, setCapDraft] = useState<number | null>(null); // the cap being changed for this snack; null = not changing
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false); // in-flight lock for feeding / saving (only read and written in event handlers)
  const seq = useRef(0); // answers that arrive after a switch or a retry are dropped

  useEffect(() => {
    setViewer(role);
  }, [role]);

  const reload = useCallback((v: Viewer) => {
    const my = ++seq.current;
    setLoad({ kind: "loading" });
    fetchSnacks(v)
      .then((st) => {
        if (my === seq.current) setLoad({ kind: "ok", st });
      })
      .catch((e) => {
        if (my !== seq.current) return;
        setLoad(e instanceof SnacksUnsupportedError ? { kind: "unsupported" } : { kind: "error" });
      });
  }, []);

  useEffect(() => {
    reload(viewer);
  }, [viewer, reload, tick]);
  // another snack / another role to feed: an unsaved cap is not carried over
  useEffect(() => {
    setCapDraft(null);
  }, [snackId, viewer]);

  const lock = (): boolean => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    return true;
  };
  const unlock = () => {
    busyRef.current = false;
    setBusy(false);
  };

  const feed = async (s: Snack) => {
    let variant: string | null = null;
    if (s.variants.length) {
      variant = variantPick[s.id] ?? null;
      if (!variant) return toast(`先选${s.name}的口味`);
    }
    if (!lock()) return;
    const v = viewer;
    try {
      const r = await feedSnack(v, s.id, variant);
      setLoad({ kind: "ok", st: r.state }); // the "feed to" choice is locked while feeding: the answer belongs to this role
      const energy = r.state.energyEnabled && r.result.energyDelta > 0 ? ` · 体力 ${gainText(r.result.energyDelta)}` : "";
      toast(`喂了${v}一份${r.result.name}${energy}${r.notified ? " · 他下轮会知道" : ""}`);
    } catch (e) {
      if (e instanceof SnackCapError) {
        toast(e.message);
        reload(v);
      } else if (e instanceof SnacksUnsupportedError) {
        setLoad({ kind: "unsupported" });
      } else {
        toast("没喂成 · 网络?");
      }
    } finally {
      unlock();
    }
  };

  const saveCap = async (st: SnackState, s: Snack) => {
    if (capDraft === null || capDraft === s.cap) return setCapDraft(null);
    if (!lock()) return;
    try {
      const next = await saveSnackCaps(st.viewer, { [s.id]: capDraft });
      setLoad({ kind: "ok", st: next });
      setCapDraft(null);
      toast("上限改好了");
    } catch (e) {
      toast(e instanceof Error && e.message && !(e instanceof SnacksUnsupportedError) ? e.message : "没改成 · 网络?");
    } finally {
      unlock();
    }
  };

  const st = load.kind === "ok" ? load.st : null;
  const sn = st?.snacks.find((x) => x.id === snackId) ?? null;
  const pick = variantPick[snackId];
  // with a single role there is nobody to choose between
  const whoRow = roles.length > 1 ? (
    <>
      <Act label="喂给" tone="mute" />
      {roles.map((w) => (
        <Act key={w} label={w} tone={viewer === w ? "ink" : "mute"} onPress={() => setViewer(w)} disabled={busy} a11y={`喂给${w}`} selected={viewer === w} testID={`snack-who-${w}`} />
      ))}
    </>
  ) : null;

  return (
    <HandShell anchor={anchor} sceneH={sceneH} testID="hand-snack">
      {load.kind === "loading" ? <Status text="读取中…" /> : null}
      {load.kind === "unsupported" ? <Status text="常驻零食还没接上 · 服务端这一件尚未装载" /> : null}
      {load.kind === "error" ? <Status text="没读到 · 点一下重试" onPress={() => reload(viewer)} /> : null}
      {st && !sn ? <Status text="这一款现在没有了" /> : null}
      {st && sn ? (
        <>
          <Top hero={<HeroArt art={snackArt(sn.id, pick)} name={sn.name} />}>
            <Name small={sn.name.length > 3}>{sn.name}</Name>
            <Big n={String(sn.eaten)} tail={`/ ${sn.cap} 今天 · ${resetText(st.resetsAt)} 重置`} />
            {sn.variants.length ? (
              <View style={s.variants}>
                {sn.variants.map((x) => {
                  const on = pick === x.id;
                  return (
                    <Pressable
                      key={x.id}
                      onPress={() => setVariantPick((p) => ({ ...p, [sn.id]: x.id }))}
                      hitSlop={6}
                      accessibilityRole="button"
                      accessibilityState={{ selected: on }}
                      accessibilityLabel={`${x.name}${sn.name}`}
                      testID={`snack-variant-${x.id}`}
                    >
                      <Text style={[s.variant, on && lineInk]}>{x.name}</Text>
                      {on ? <Ring style={s.ring} /> : null}
                    </Pressable>
                  );
                })}
              </View>
            ) : null}
            <Line>
              <Text style={[lineInk, sn.tier === "high" && { color: KC.tomato }]}>{sn.tierLabel}</Text>
              {st.energyEnabled
                ? ` · ${(sn.gain ?? sn.variants.find((x) => x.id === pick)?.gain) != null
                  ? `体力 ${gainText((sn.gain ?? sn.variants.find((x) => x.id === pick)?.gain) as number)} / 份`
                  : `体力 ${sn.variants.map((x) => gainText(x.gain)).join(" · ")}`}`
                : ""}
            </Line>
          </Top>
          <Acts>
            <Act
              label={sn.eaten >= sn.cap ? "今日已满" : "喂一份"}
              tone={sn.eaten >= sn.cap ? "mute" : "go"}
              onPress={() => feed(sn)}
              disabled={busy || sn.eaten >= sn.cap}
              a11y={sn.eaten >= sn.cap ? `${sn.name}今日已满` : `喂一份${sn.name}`}
              testID="snack-feed"
            />
            <Act label="上限" tone="mute" />
            <Act label="−" onPress={() => setCapDraft(stepCap(capDraft ?? sn.cap, -1, st.capMin, st.capMax))} disabled={busy} a11y={`${sn.name}上限减一`} testID="snack-cap-minus" />
            <Text style={[s.capNum, { fontFamily: bodoniFor(15) }]} testID="snack-cap">{capDraft ?? sn.cap}</Text>
            <Act label="+" onPress={() => setCapDraft(stepCap(capDraft ?? sn.cap, 1, st.capMin, st.capMax))} disabled={busy} a11y={`${sn.name}上限加一`} testID="snack-cap-plus" />
            {capDraft !== null && capDraft !== sn.cap ? (
              <>
                <Act label="存" tone="go" onPress={() => saveCap(st, sn)} disabled={busy} a11y="存上限" testID="snack-cap-save" />
                <Act label="算了" tone="mute" onPress={() => setCapDraft(null)} disabled={busy} a11y="不改了" testID="snack-cap-cancel" />
              </>
            ) : null}
            <Sp />
            {whoRow}
          </Acts>
          <Bar left={<BarTx>柜子上</BarTx>} />
          <Thumbs
            items={st.snacks.map((x) => ({ key: x.id, name: x.name, badge: x.eaten, art: snackArt(x.id, variantPick[x.id]) }))}
            cur={sn.id}
            onPick={onPick}
            idPrefix="row-snack"
          />
        </>
      ) : null}
      {(!st || !sn) && whoRow ? <Acts>{whoRow}</Acts> : null}
    </HandShell>
  );
}

const s = StyleSheet.create({
  variants: { flexDirection: "row", flexWrap: "wrap", columnGap: 12, rowGap: 2, marginTop: 4 },
  variant: { fontFamily: KF, fontSize: 12.5, lineHeight: 22, letterSpacing: 1, color: KC.soft },
  ring: { left: -8, right: -8, top: -1, bottom: -1 },
  capNum: { fontSize: 15, lineHeight: 23, color: KC.ink },
});
