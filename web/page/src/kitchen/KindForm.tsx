// "添种类": the human adds ingredient kinds of their own. The upper half adds one (name / which
// category / can it be eaten as it is / how many in a pack / how many days it keeps); the lower half
// lists the ones already added (how its picture is coming along, draw again, remove).
// The rules and numbers are the server's (a name that breaks them, a duplicate: the server's own
// sentence is shown right here). The picture is drawn by the server in the background; this only
// shows its state.
import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { GrowingInput } from "../runtime/GrowingInput";
import {
  addKind, fridgeErrText, inflightKey, redrawKind, removeKind, withInflight,
  type ArtAuth, type CatalogItem, type FridgeCategory, type NewKind,
} from "./fridgeApi";
import { artOf } from "./kindArt";
import { CATEGORY_ORDER } from "./kitchenText";
import { KC, KF } from "./kitchenTheme";
import { Ring } from "./handParts";
import { Thumb, ps } from "./panelParts";
import { HeadBtn, Label, SheetBtn, SheetFoot, sh } from "./sheetParts";
import { useInflight } from "./useInflight";

export const PACK_CHOICES = [1, 2, 3, 4, 6];
/** null = the default number of days for the category (the number is the server's) */
export const DAYS_CHOICES: (number | null)[] = [null, 3, 7, 14, 30];
const KIND_LOCK = inflightKey("kind", "all");

/** The form -> the request body; an empty name = null ("添上" is dimmed). "Can be eaten as it is" left untouched = yes for fruit, no for the rest */
export function draftToKind(d: { name: string; category: FridgeCategory | null; raw: boolean | null; pack: number; days: number | null }): NewKind | null {
  const name = d.name.trim();
  if (!name || !d.category) return null;
  return { name, category: d.category, rawEdible: d.raw ?? d.category === "fruit", packQty: d.pack, shelfDays: d.days };
}

/** The small words on the right of an added kind's row: being drawn / failed (why); nothing once it is drawn or when the server draws no pictures */
export function artStatusText(it: CatalogItem): string {
  if (!it.art || it.art.state === "ready" || it.art.state === "none") return "";
  if (it.art.state === "pending") return it.art.v > 0 ? "重画中…" : "小图画着…";
  return it.art.err ? `没画成:${it.art.err}` : "没画成";
}

function Chip({ label, on, onPress, testID }: { label: string; on: boolean; onPress: () => void; testID?: string }) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={6}
      style={st.chip}
      accessibilityRole="radio"
      accessibilityState={{ selected: on }}
      accessibilityLabel={label}
      testID={testID}
    >
      <Text style={[st.chipTx, on && st.chipTxOn]}>{label}</Text>
      {on ? <Ring style={st.ring} /> : null}
    </Pressable>
  );
}

export function KindForm({
  items, auth, onChanged, onOrphanError,
}: {
  items: CatalogItem[];
  auth: ArtAuth | null;
  onChanged: () => void;
  /** the answer arrived after this form was left / the sheet was closed: the failure sentence goes to the page to show */
  onOrphanError: (message: string) => void;
}) {
  const here = useRef(true);
  useEffect(() => {
    here.current = true;
    return () => {
      here.current = false;
    };
  }, []);
  const [name, setName] = useState("");
  const [category, setCategory] = useState<FridgeCategory | null>(null);
  const [raw, setRaw] = useState<boolean | null>(null);
  const [pack, setPack] = useState(1);
  const [days, setDays] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const busy = useInflight(KIND_LOCK);
  const draft = draftToKind({ name, category, raw, pack, days });
  const rawOn = raw ?? category === "fruit";
  const mine = items.filter((i) => i.custom);

  const run = async (fn: () => Promise<void>, fallback: string) => {
    setErr("");
    try {
      const r = await withInflight(KIND_LOCK, async () => {
        await fn();
        return true;
      });
      if (r) onChanged();
      return !!r;
    } catch (e) {
      const msg = fridgeErrText(e, fallback);
      if (here.current) setErr(msg);
      else onOrphanError(msg);
      return false;
    }
  };

  const add = async () => {
    if (!draft || busy) return;
    if ((await run(() => addKind(draft), "没添上")) && here.current) {
      setName("");
      setRaw(null);
      setPack(1);
      setDays(null);
    }
  };

  return (
    <View testID="kind-form">
      <Label first>名字</Label>
      <GrowingInput
        value={name}
        onChangeText={setName}
        placeholder="名字"
        maxLength={8}
        enterKeyHint="done"
        {...field}
        style={sh.field}
        testID="kind-name"
      />
      <Label>哪一类</Label>
      <View style={st.chips}>
        {CATEGORY_ORDER.map((c) => (
          <Chip key={c.key} label={c.label} on={category === c.key} onPress={() => setCategory(c.key as FridgeCategory)} testID={`kind-cat-${c.key}`} />
        ))}
      </View>
      <Label>拿出来就能吃</Label>
      <View style={st.chips}>
        <Chip label="能" on={rawOn} onPress={() => setRaw(true)} testID="kind-raw-yes" />
        <Chip label="不能" on={!rawOn} onPress={() => setRaw(false)} testID="kind-raw-no" />
      </View>
      <Label>一份几个</Label>
      <View style={st.chips}>
        {PACK_CHOICES.map((n) => (
          <Chip key={n} label={String(n)} on={pack === n} onPress={() => setPack(n)} testID={`kind-pack-${n}`} />
        ))}
      </View>
      <Label>能放几天</Label>
      <View style={st.chips}>
        {DAYS_CHOICES.map((n) => (
          <Chip key={String(n)} label={n === null ? "跟这一类" : `${n} 天`} on={days === n} onPress={() => setDays(n)} testID={`kind-days-${n ?? "auto"}`} />
        ))}
      </View>
      {err ? <Text style={sh.err} testID="kind-err">{err}</Text> : null}
      <SheetFoot>
        <SheetBtn label={busy ? "稍等…" : "添上"} onPress={add} disabled={!draft || busy} testID="kind-add" />
      </SheetFoot>
      {mine.length ? (
        <View style={st.mine}>
          <Label first>自己添的</Label>
          {mine.map((it, i) => {
            const status = artStatusText(it);
            return (
              <View key={it.id} style={[ps.row, i === mine.length - 1 && ps.rowLast]} testID={`kind-row-${it.id}`}>
                <Thumb art={artOf(it.id, "fresh", it.art, auth)} name={it.name} />
                <View style={ps.nm}>
                  <Text style={ps.nmTx} numberOfLines={1}>{it.name}</Text>
                  {status ? <Text style={[ps.nmSmall, it.art?.state === "failed" && { color: KC.bad }]}>{status}</Text> : null}
                </View>
                {/* drawing again only makes sense on a server that draws pictures */}
                {it.art && it.art.state !== "none" ? (
                  <HeadBtn label="重画" disabled={busy || it.art.state === "pending"} onPress={() => run(() => redrawKind(it.id), "没发出去")} testID={`kind-redraw-${it.id}`} />
                ) : null}
                <HeadBtn label="撤掉" disabled={busy} onPress={() => run(() => removeKind(it.id), "没撤成")} testID={`kind-remove-${it.id}`} />
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

const field = { fontFamily: KF, fontSize: 15, lineHeight: 20, color: KC.ink, placeholderTextColor: "#c4b5a8", maxHeight: 44 };

const st = StyleSheet.create({
  chips: { flexDirection: "row", flexWrap: "wrap", columnGap: 16, rowGap: 2 },
  chip: { paddingVertical: 1 },
  chipTx: { fontFamily: KF, fontSize: 13, lineHeight: 24, letterSpacing: 1, color: KC.soft },
  chipTxOn: { color: KC.ink },
  ring: { left: -8, right: -8, top: 0, bottom: 0 },
  mine: { marginTop: 4 },
});
