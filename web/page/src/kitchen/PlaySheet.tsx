// The upgrade's entrances: one row of small words under the hand (only what is switched on), and the
// sheet each of them opens (the same paper sheet as buying and writing, with a tab per entrance).
// Nothing is drawn onto the kitchen picture.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { GrowingInput } from "../runtime/GrowingInput";
import { useStore } from "../runtime/store";
import { FridgeHttpError, fridgeErrText } from "./fridgeApi";
import { KC, KF } from "./kitchenTheme";
import {
  BEST_WORD, FLOWER_STATE, KIND_WORD, ORDER_WORD, TAB_LABEL, decideFlower, feedJar, fetchBook, fetchCode, fetchDex, fetchJars, fetchWallet,
  fetchOrders, fetchPlates, fetchToday, fetchVendor, grantPocket, importCode, methodWord, orderDish, previewCode, saveDexNote,
  searchRecipes, setJarCap, setPlates, treat, withdrawOrder, type BookPage, type Dex, type Features, type Jar, type JarGood,
  type Order, type Plates, type PlayTab, type RecipeEntry, type VendorView,
} from "./playApi";
import { HeadBtn, Label, Paper, SheetBtn, SheetFoot, SheetFrame, SheetHead, sh } from "./sheetParts";
import { ChoreStage } from "./ChoreStage";
import { nextPlateDue, platesClip, serverNow, vendorPanelClip } from "./choreAnim";

/**
 * The row of entrances under the hand; an entrance not opened yet on this device carries a small 「新」.
 * A dot between two entrances on the same line; none at the start of a line when the row wraps. The
 * dot hangs in the gap outside the entrance's box, so showing or hiding it never moves anything.
 */
export function PlayShelf({ tabs, seen, onOpen }: { tabs: PlayTab[]; seen?: Set<string>; onOpen: (t: PlayTab) => void }) {
  // the line each entrance landed on (its top edge in the row), from its layout
  const [tops, setTops] = useState<Record<string, number>>({});
  if (!tabs.length) return null;
  return (
    <View style={st.shelf} testID="play-shelf">
      {tabs.map((t, i) => (
        <View
          key={t}
          style={[st.shelfItem, st.shelfGap]}
          onLayout={(e) => {
            const y = Math.round(e.nativeEvent.layout.y);
            setTops((p) => (p[t] === y ? p : { ...p, [t]: y }));
          }}
        >
          {i && tops[t] !== undefined && tops[t] === tops[tabs[i - 1]] ? <Text style={st.dot} testID={`play-dot-${t}`}>·</Text> : null}
          <Pressable onPress={() => onOpen(t)} hitSlop={8} accessibilityRole="button" accessibilityLabel={TAB_LABEL[t]} testID={`play-${t}`} style={st.shelfItem}>
            <Text style={st.shelfTx}>{TAB_LABEL[t]}</Text>
            {seen && !seen.has(t) ? <Text style={st.newMark} testID={`play-new-${t}`}>新</Text> : null}
          </Pressable>
        </View>
      ))}
    </View>
  );
}

/** One line at the top of the page while a vendor is downstairs (tapping it opens the vendor tab) */
export function VendorLine({ view, onOpen }: { view: VendorView | null; onOpen: () => void }) {
  if (!view?.visit) return null;
  const mins = Math.max(1, Math.round(view.visit.leftS / 60));
  return (
    <Pressable onPress={onOpen} accessibilityRole="button" testID="vendor-line">
      <Text style={st.vendorLine}>{`楼下有${view.visit.who} · 还待 ${mins} 分钟 →`}</Text>
    </Pressable>
  );
}

export function PlaySheet({ open, tab, tabs, features, onTab, onClose, onChanged }: {
  open: boolean; tab: PlayTab; tabs: PlayTab[]; features: Features;
  onTab: (t: PlayTab) => void; onClose: () => void;
  /** something changed in the kitchen (bought, fed): the page reads the fridge again */
  onChanged: () => void;
}) {
  const { height } = useWindowDimensions();
  const [msg, setMsg] = useState("");
  useEffect(() => setMsg(""), [tab, open]);
  return (
    <SheetFrame open={open} onClose={onClose}>
      <Paper style={{ maxHeight: height * 0.84 }} testID="play-sheet">
        <SheetHead title={TAB_LABEL[tab]}>
          <HeadBtn label="收起" onPress={onClose} testID="play-close" />
        </SheetHead>
        <View style={st.tabs}>
          {tabs.map((t) => (
            <Pressable key={t} onPress={() => onTab(t)} hitSlop={6} accessibilityRole="tab" accessibilityState={{ selected: t === tab }} testID={`tab-${t}`}>
              <Text style={[st.tab, t === tab && st.tabOn]}>{TAB_LABEL[t]}</Text>
            </Pressable>
          ))}
        </View>
        <ScrollView style={st.scroll} keyboardShouldPersistTaps="handled">
          {open ? <Body tab={tab} features={features} say={setMsg} onChanged={onChanged} /> : null}
        </ScrollView>
        {msg ? <Text style={sh.err} testID="play-msg">{msg}</Text> : null}
      </Paper>
    </SheetFrame>
  );
}

function Body({ tab, features, say, onChanged }: { tab: PlayTab; features: Features; say: (m: string) => void; onChanged: () => void }) {
  switch (tab) {
    case "recipes": return <RecipesTab f={features} say={say} />;
    case "dex": return <DexTab say={say} />;
    case "achievements": return <AchievementsTab say={say} />;
    case "vendor": return <VendorTab say={say} onChanged={onChanged} />;
    case "pocket": return <PocketTab say={say} />;
    case "plates": return <PlatesTab say={say} />;
    case "jars": return <JarsTab say={say} onChanged={onChanged} />;
  }
}

/** Load something for the role shown; a role switch or a closed tab drops a late answer */
function useLoad<T>(load: (role: string) => Promise<T>, say: (m: string) => void): [T | null, () => void, boolean] {
  const { role, tick } = useStore();
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const seq = useRef(0);
  const reload = useCallback(() => {
    const my = ++seq.current;
    setFailed(false);
    load(role).then((d) => my === seq.current && setData(d), (e) => {
      if (my !== seq.current) return;
      setFailed(true);
      say(fridgeErrText(e, "没读到 · 网络?"));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);
  useEffect(() => {
    setData(null);
    reload();
  }, [reload, tick]);
  useEffect(() => () => {
    seq.current += 1;
  }, []);
  return [data, reload, failed];
}

/** While a tab is open the page's own refresh waits (a sheet is open): these two read again on their own */
const VENDOR_POLL_MS = 5_000;
const PLATES_POLL_MS = 15_000;
function useEvery(ms: number, on: boolean, fn: () => void): void {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (!on) return;
    const t = setInterval(() => ref.current(), ms);
    return () => clearInterval(t);
  }, [ms, on]);
}

/**
 * Request keys for the things that must not happen twice (pocket money, feeding from a jar, buying for the
 * role): the same attempt keeps its key until the server has answered, so a retry after a timeout or a
 * dropped connection is recognised as the same request and does nothing twice.
 */
export function useRetryKeys() {
  const keys = useRef(new Map<string, string>());
  return {
    key: (what: string): string => {
      let k = keys.current.get(what);
      if (!k) {
        k = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
        keys.current.set(what, k);
      }
      return k;
    },
    /** the server answered (done or refused): the next attempt is a new request */
    settle: (what: string, e?: unknown) => {
      if (e === undefined || (e instanceof FridgeHttpError && e.status > 0)) keys.current.delete(what);
    },
  };
}

function Line({ children, soft, testID }: { children: ReactNode; soft?: boolean; testID?: string }) {
  return <Text style={soft ? st.soft : st.line} testID={testID}>{children}</Text>;
}

function Act({ label, onPress, testID }: { label: string; onPress: () => void; testID?: string }) {
  return (
    <Pressable onPress={onPress} hitSlop={6} accessibilityRole="button" accessibilityLabel={label} testID={testID}>
      <Text style={st.act}>{label}</Text>
    </Pressable>
  );
}

const field = { fontFamily: KF, fontSize: 15, lineHeight: 22, color: KC.ink, placeholderTextColor: "#c4b5a8", maxHeight: 96 };

// ── recipes: today / search / the role's book / orders / codes ─────────
function RecipesTab({ f, say }: { f: Features; say: (m: string) => void }) {
  const { role, confirm } = useStore();
  const [qText, setQText] = useState("");
  const [hits, setHits] = useState<{ total: number; recipes: RecipeEntry[] } | null>(null);
  const [today] = useLoad((r) => (f.recipes_today ? fetchToday(r) : Promise.resolve("")), say);
  const [pages, reloadPages] = useLoad<BookPage[]>((r) => (f.recipe_book ? fetchBook(r) : Promise.resolve([])), say);
  const [orders, reloadOrders] = useLoad<Order[]>((r) => (f.orders ? fetchOrders(r) : Promise.resolve([])), say);
  const [code, setCode] = useState("");
  const [shown, setShown] = useState<{ page: string; code: string } | null>(null);
  const search = () => {
    if (!f.recipes_public) return;
    searchRecipes(role, qText.trim()).then(setHits, (e) => say(fridgeErrText(e, "没找成 · 网络?")));
  };
  const order = (r: RecipeEntry) => confirm({
    title: `点『${r.name}』?`, message: "他看厨房时会看到。", yes: "点",
    onYes: () => orderDish(role, r.id).then(() => { say(`点了 ${r.name}`); reloadOrders(); }, (e) => say(fridgeErrText(e, "没点成"))),
  });
  const showCode = (p: BookPage) => fetchCode(role, p.kind === "fav" && p.refId ? p.refId : p.id).then(
    (c) => setShown({ page: p.id, code: c }), (e) => say(fridgeErrText(e, "没出成")));
  const take = async () => {
    try {
      const pv = await previewCode(code.trim());
      confirm({
        title: `收下『${pv.name}』?`, message: `${(pv.items ?? []).map((x: [string, number]) => x[0]).join("、")} · ${methodWord(pv.method)} · 约 ${pv.minutes} 分钟${pv.note ? `\n「${pv.note}」` : ""}`,
        yes: "收下",
        onYes: () => importCode(role, code.trim()).then((r) => { say(r.duplicate ? "已经收过这一页" : "收进他的食谱本了"); setCode(""); reloadPages(); },
          (e) => say(fridgeErrText(e, "没收成"))),
      });
    } catch (e) {
      say(fridgeErrText(e, "这串码认不出来"));
    }
  };
  return (
    <View testID="tab-body-recipes">
      {f.recipes_today && today ? <Line testID="today">{today}</Line> : null}
      {f.recipes_public ? (
        <>
          <Label first={!today}>翻公共食谱</Label>
          <View style={st.searchRow}>
            <GrowingInput value={qText} onChangeText={setQText} placeholder="菜名、食材或分类" {...field} style={[sh.field, { flex: 1 }]} testID="recipe-q" />
            <Act label="找" onPress={search} testID="recipe-search" />
          </View>
          {hits ? (
            hits.recipes.length ? hits.recipes.map((r) => (
              <View key={r.id} style={st.row}>
                <View style={st.rowMain}>
                  <Text style={st.name}>{r.name}</Text>
                  <Text style={st.soft}>{`${r.itemsText || "常备就够"} · ${methodWord(r.method)} · 约 ${r.minutes} 分钟 · ${r.id}`}</Text>
                </View>
                {f.orders ? <Act label="想吃这个" onPress={() => order(r)} testID={`order-${r.id}`} /> : null}
              </View>
            )) : <Line soft>没找到</Line>
          ) : null}
        </>
      ) : null}
      {f.orders && orders && orders.some((o) => o.state !== "withdrawn") ? (
        <>
          <Label>点的菜</Label>
          {orders.filter((o) => o.state !== "withdrawn").slice(0, 12).map((o) => (
            <View key={o.id} style={st.row}>
              <View style={st.rowMain}>
                <Text style={st.name}>{o.name}</Text>
                <Text style={st.soft}>{(ORDER_WORD[o.state] ?? o.state) + (o.note ? ` · ${o.note}` : "")}</Text>
              </View>
              {o.state === "received" || o.state === "planned" ? (
                <Act label="撤回" onPress={() => withdrawOrder(role, o.id).then(reloadOrders, (e) => say(fridgeErrText(e, "没撤成")))} />
              ) : null}
            </View>
          ))}
        </>
      ) : null}
      {f.recipe_book ? (
        <>
          <Label>{`${role}的食谱本`}</Label>
          {pages === null ? <Line soft>…</Line> : pages.length === 0 ? <Line soft>还是空的</Line> : pages.map((p) => (
            <View key={p.id} style={st.row}>
              <View style={st.rowMain}>
                <Text style={st.name}>{`${p.name}`}<Text style={st.soft}>{`  ${KIND_WORD[p.kind] ?? p.kind}`}</Text></Text>
                {p.kind !== "menu" ? <Text style={st.soft}>{`${p.itemsText} · ${methodWord(p.method)} · 约 ${p.minutes} 分钟`}</Text> : null}
                {p.note ? <Text style={st.soft}>{`「${p.note}」`}</Text> : null}
                {p.notes.map((n, i) => <Text key={i} style={st.soft}>{`札记 · ${n}`}</Text>)}
                {shown?.page === p.id ? <Text selectable style={st.code} testID="code-text">{shown.code}</Text> : null}
              </View>
              {f.recipe_codes && p.kind !== "menu" ? <Act label="码" onPress={() => showCode(p)} testID={`code-${p.id}`} /> : null}
            </View>
          ))}
          {f.recipe_codes ? (
            <>
              <Label>收别人的码</Label>
              <GrowingInput value={code} onChangeText={setCode} placeholder="KC1.…" {...field} style={sh.field} testID="code-in" />
              <SheetFoot><SheetBtn label="看看" onPress={take} disabled={!code.trim()} testID="code-preview" /></SheetFoot>
            </>
          ) : null}
        </>
      ) : null}
    </View>
  );
}

// ── the dish book ───────────────────────────────────────────────────────
function DexTab({ say }: { say: (m: string) => void }) {
  const { role } = useStore();
  const [dex, reload] = useLoad<Dex>(fetchDex, say);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  if (!dex) return <Line soft>…</Line>;
  const save = (key: string) => saveDexNote(role, key, draft.trim()).then(() => { setEditing(null); reload(); }, (e) => say(fridgeErrText(e, "没存上")));
  return (
    <View testID="tab-body-dex">
      <Line soft>{`公共食谱 ${dex.total ?? "—"} 道 · 做过其中 ${dex.madePublic} 道 · 图鉴 ${dex.pages.length} 页${dex.drawing && dex.artMissing ? ` · 还差 ${dex.artMissing} 张图` : ""}`}</Line>
      {dex.pages.length === 0 ? <Line soft>还没有做过的菜</Line> : dex.pages.map((p) => (
        <View key={p.key} style={st.row}>
          <View style={st.rowMain}>
            <Text style={st.name}>{p.name}{p.pending ? <Text style={st.soft}>  待归类</Text> : null}</Text>
            <Text style={st.soft}>{`做过 ${p.made} · 做好 ${p.good} · 吃过 ${p.eaten}${p.best ? ` · 最好 ${BEST_WORD[p.best] ?? p.best}` : ""} · ${methodWord(p.method)}`}</Text>
            {p.ingredients.length ? <Text style={st.soft}>{p.ingredients.join("、")}</Text> : null}
            {p.roleNote ? <Text style={st.soft}>{`他:「${p.roleNote}」`}</Text> : null}
            {editing === p.key ? (
              <View style={st.searchRow}>
                <GrowingInput value={draft} onChangeText={setDraft} placeholder="评语" {...field} style={[sh.field, { flex: 1 }]} testID="dex-note-in" />
                <Act label="存" onPress={() => save(p.key)} testID="dex-note-save" />
              </View>
            ) : p.humanNote ? <Text style={st.soft}>{`评语:${p.humanNote}`}</Text> : null}
          </View>
          {editing !== p.key ? <Act label="评语" onPress={() => { setEditing(p.key); setDraft(p.humanNote); }} testID={`dex-note-${p.key}`} /> : null}
        </View>
      ))}
      {dex.silhouettes.length ? (<><Label>收藏了还没做</Label><Line soft>{dex.silhouettes.join("、")}</Line></>) : null}
    </View>
  );
}

// ── achievements (all of them here; the role only ever reads the earned ones) ──
function AchievementsTab({ say }: { say: (m: string) => void }) {
  const [dex] = useLoad<Dex>(fetchDex, say);
  if (!dex) return <Line soft>…</Line>;
  return (
    <View testID="tab-body-achievements">
      {dex.achievements.map((a) => (
        <View key={a.key} style={st.row}>
          <View style={st.rowMain}>
            <Text style={[st.name, !a.earned && st.dim]}>{a.name}</Text>
            {a.earned ? <Text style={st.soft}>{a.why}</Text> : <Text style={st.soft}>还没拿到</Text>}
          </View>
        </View>
      ))}
    </View>
  );
}

// ── the vendor and the sill ─────────────────────────────────────────────
function VendorTab({ say, onChanged }: { say: (m: string) => void; onChanged: () => void }) {
  const { role, confirm } = useStore();
  const [v, reload] = useLoad<VendorView>(fetchVendor, say);
  const keys = useRetryKeys();
  useEvery(VENDOR_POLL_MS, !!v?.visit, reload); // the role buys through its tools while this is open
  if (!v) return <Line soft>…</Line>;
  const buyFor = (id: string, name: string) => confirm({
    title: `替他买一份『${name}』?`, message: "不花他的零花钱。", yes: "买",
    onYes: () => {
      const what = `treat:${role}:${id}`;
      treat(role, id, keys.key(what)).then((ok) => { keys.settle(what); say(ok ? "买好了 · 他会知道" : "还在办"); reload(); onChanged(); },
        (e) => { keys.settle(what, e); say(fridgeErrText(e, "没买成")); });
    },
  });

  return (
    <View testID="tab-body-vendor">
      {v.visit ? (
        <>
          <Line>{`楼下有${v.visit.who} · 还待 ${Math.max(1, Math.round(v.visit.leftS / 60))} 分钟`}</Line>
          <ChoreStage pick={(ms) => vendorPanelClip(v, ms)} testID="vendor-cook" />
          {v.visit.goods.map((g) => (
            <View key={g.id} style={st.row}>
              <View style={st.rowMain}>
                <Text style={st.name}>{g.name}</Text>
                <Text style={st.soft}>{`${g.price} 一${g.unit} · ${g.left > 0 ? `还有 ${g.left} ${g.unit}` : "卖完了"}`}</Text>
              </View>
              {g.left > 0 ? <Act label="替他买" onPress={() => buyFor(g.id, g.name)} testID={`treat-${g.id}`} /> : null}
            </View>
          ))}
        </>
      ) : <Line soft>楼下现在没有小贩</Line>}
      <Label>{`他今天在小贩这儿花了 ${v.spent} / ${v.cap}`}</Label>
      <PocketGive local={v.localWallet} balance={v.balance} say={say} onGiven={reload} />
      <Label>窗台</Label>
      <Line soft>{v.flower ? `${v.flower.name} · ${FLOWER_STATE[v.flower.state] ?? v.flower.state}${v.flower.gifted ? ` · 他送给你了:「${v.flower.note}」` : ""}` : "窗台上没有花"}</Line>
      {v.requests.filter((r) => r.state === "pending").map((r) => (
        <View key={r.id} style={st.row}>
          <View style={st.rowMain}><Text style={st.name}>{`他想要「${r.name}」`}</Text></View>
          <Act label="同意" onPress={() => decideFlower(r.id, true).then(reload, (e) => say(fridgeErrText(e, "没成")))} testID={`flower-yes-${r.id}`} />
          <Act label="不了" onPress={() => decideFlower(r.id, false).then(reload, (e) => say(fridgeErrText(e, "没成")))} testID={`flower-no-${r.id}`} />
        </View>
      ))}
    </View>
  );
}

// ── pocket money: the human decides, every time, how much ─────────────
function PocketGive({ local, balance, say, onGiven }: { local: boolean; balance: number | null; say: (m: string) => void; onGiven: () => void }) {
  const { role } = useStore();
  const [amount, setAmount] = useState("");
  const keys = useRetryKeys();
  const give = () => {
    const n = Number(amount);
    if (!Number.isInteger(n) || n <= 0) return say("填一个正整数");
    const what = `grant:${role}:${n}`;
    grantPocket(role, n, keys.key(what)).then((bal) => { keys.settle(what); setAmount(""); say(`给了 ${n} · 现在有 ${bal} · 他下一轮会知道`); onGiven(); },
      (e) => { keys.settle(what, e); say(fridgeErrText(e, "没给上")); });
  };
  return (
    <View testID="pocket">
      <Text style={st.pocketNum} testID="pocket-balance">{balance === null ? "—" : String(balance)}</Text>
      <Text style={st.soft}>{balance === null ? "零花钱读不到" : `${role}的零花钱`}</Text>
      {local ? (
        <>
          <Label>给他多少</Label>
          <GrowingInput value={amount} onChangeText={setAmount} placeholder="填个数" inputMode="numeric" {...field} style={sh.field} testID="pocket-in" />
          <SheetFoot left="给了以后他下一轮会知道">
            <SheetBtn label="给他" onPress={give} disabled={!amount.trim()} testID="pocket-give" />
          </SheetFoot>
        </>
      ) : <Line soft>零花钱在你们自家的系统里,从那边给。</Line>}
    </View>
  );
}

function PocketTab({ say }: { say: (m: string) => void }) {
  const [w, reload] = useLoad(fetchWallet, say);
  if (!w) return <Line soft>…</Line>;
  return <PocketGive local={w.local} balance={w.balance} say={say} onGiven={reload} />;
}

// ── plates ──────────────────────────────────────────────────────────────
function PlatesTab({ say }: { say: (m: string) => void }) {
  const { role } = useStore();
  const [p, reload] = useLoad<Plates>(fetchPlates, say);
  const [quota, setQuota] = useState("");
  useEvery(PLATES_POLL_MS, !!p, reload); // a washing the role starts while this is open
  // a plate's result is only told once its time is up: read again right then, to show a broken one
  useEffect(() => {
    if (!p) return;
    const due = nextPlateDue(p.job, serverNow(p.now, p.readAt, Date.now()));
    if (due === null) return;
    const t = setTimeout(reload, Math.max(0, (due - serverNow(p.now, p.readAt, Date.now())) * 1000) + 300);
    return () => clearTimeout(t);
  }, [p, reload]);
  if (!p) return <Line soft>…</Line>;
  const set = (change: { self_wash?: boolean; quota?: number | null }) => setPlates(role, change).then(reload, (e) => say(fridgeErrText(e, "没改上")));
  return (
    <View testID="tab-body-plates">
      <ChoreStage pick={(ms) => platesClip(p, ms)} testID="plates-cook" />
      <Line>{`水槽 ${p.sink} · 在刷 ${p.washing} · 刷干净 ${p.clean} · 碎了 ${p.broken} · 洗碗机 ${p.machine}`}</Line>
      <View style={st.row}>
        <View style={st.rowMain}>
          <Text style={st.name}>让他自己刷</Text>
          <Text style={st.soft}>{p.selfWash ? "开着:盘子留在水槽,等他写 [刷盘子]" : "关着:吃完就进洗碗机"}</Text>
        </View>
        <Act label={p.selfWash ? "关掉" : "打开"} onPress={() => set({ self_wash: !p.selfWash })} testID="self-wash" />
      </View>
      <Label>{`一次刷几只 · 现在 ${p.quota === null ? "有几只刷几只" : `${p.quota} 只`}`}</Label>
      <View style={st.searchRow}>
        <GrowingInput value={quota} onChangeText={setQuota} placeholder="几只" inputMode="numeric" {...field} style={[sh.field, { flex: 1 }]} testID="quota-in" />
        <Act label="定" onPress={() => { const n = Number(quota); if (!Number.isInteger(n) || n < 0) return say("填一个整数"); set({ quota: n }); setQuota(""); }} testID="quota-set" />
        <Act label="不限" onPress={() => set({ quota: null })} testID="quota-clear" />
      </View>
    </View>
  );
}

// ── jars ────────────────────────────────────────────────────────────────
function JarsTab({ say, onChanged }: { say: (m: string) => void; onChanged: () => void }) {
  const { role, confirm } = useStore();
  const [j, reload] = useLoad<{ jars: Jar[]; goods: JarGood[]; cap: number }>(fetchJars, say);
  const keys = useRetryKeys();
  if (!j) return <Line soft>…</Line>;
  const feed = (g: JarGood) => confirm({
    title: `喂他一份『${g.name}』?`, message: "和他自己取的共用每天的上限。", yes: "喂",
    onYes: () => {
      const what = `feed:${role}:${g.name}`;
      feedJar(role, g.name, keys.key(what)).then((t) => { keys.settle(what); say(t); reload(); onChanged(); },
        (e) => { keys.settle(what, e); say(fridgeErrText(e, "没喂成")); });
    },
  });
  return (
    <View testID="tab-body-jars">
      {j.jars.map((x) => (
        <Line key={x.slot} soft={x.state !== "sealed"}>
          {x.state === "sealed" ? `${x.itemName}、${x.howWord}${x.note ? ` · 纸条「${x.note}」` : ""}` : "空着一只"}
        </Line>
      ))}
      <Label>{`零食架上的罐子成品 · 每天最多 ${j.cap} 份`}</Label>
      {j.goods.filter((g) => g.ok && g.left > 0).map((g) => (
        <View key={g.id} style={st.row}>
          <View style={st.rowMain}>
            <Text style={st.name}>{g.name}</Text>
            <Text style={st.soft}>{`还剩 ${g.left}/${g.total}${g.note ? ` · 「${g.note}」` : ""}`}</Text>
          </View>
          <Act label="喂他" onPress={() => feed(g)} testID={`jar-feed-${g.id}`} />
        </View>
      ))}
      <View style={st.searchRow}>
        <Act label="上限 −1" onPress={() => setJarCap(role, Math.max(0, j.cap - 1)).then(reload)} testID="cap-down" />
        <Act label="上限 +1" onPress={() => setJarCap(role, j.cap + 1).then(reload)} testID="cap-up" />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  shelf: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", paddingTop: 14, rowGap: 6 },
  shelfItem: { flexDirection: "row", alignItems: "center" },
  shelfTx: { fontFamily: KF, fontSize: 13, lineHeight: 20, letterSpacing: 2, color: KC.ink },
  newMark: { fontFamily: KF, fontSize: 9, lineHeight: 12, color: KC.tomato, marginLeft: 1, marginTop: -8 },
  shelfGap: { marginHorizontal: 11 },
  dot: { position: "absolute", left: -16, width: 10, textAlign: "center", fontFamily: KF, fontSize: 13, lineHeight: 20, color: KC.soft },
  vendorLine: { fontFamily: KF, fontSize: 11, letterSpacing: 1, color: KC.soft, marginTop: -6, marginBottom: 8 },
  tabs: { flexDirection: "row", flexWrap: "wrap", columnGap: 14, rowGap: 4, paddingTop: 6, paddingBottom: 4 },
  tab: { fontFamily: KF, fontSize: 12, lineHeight: 18, letterSpacing: 1, color: KC.soft },
  tabOn: { color: KC.tomato, textDecorationLine: "underline" },
  scroll: { flexGrow: 0, flexShrink: 1 },
  line: { fontFamily: KF, fontSize: 13, lineHeight: 20, color: KC.ink, marginTop: 6 },
  soft: { fontFamily: KF, fontSize: 11, lineHeight: 17, color: KC.soft, marginTop: 2 },
  row: { flexDirection: "row", alignItems: "center", columnGap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: KC.line },
  rowMain: { flex: 1, minWidth: 0 },
  name: { fontFamily: KF, fontSize: 15, lineHeight: 22, letterSpacing: 1, color: KC.ink },
  dim: { color: KC.soft },
  act: { fontFamily: KF, fontSize: 12, lineHeight: 18, letterSpacing: 1, color: KC.tomato },
  searchRow: { flexDirection: "row", alignItems: "flex-end", columnGap: 12, marginTop: 4 },
  code: { fontFamily: KF, fontSize: 11, lineHeight: 16, color: KC.ink, marginTop: 4 },
  pocketNum: { fontFamily: KF, fontSize: 30, lineHeight: 40, color: KC.ink, marginTop: 10 },
});
