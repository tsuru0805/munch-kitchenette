// The upgrade's entrances: one row of small words under the hand (only what is switched on), and the
// sheet each of them opens (the same paper sheet as buying and writing, with a tab per entrance).
// Nothing is drawn onto the kitchen picture.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Image, Platform, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { GrowingInput } from "../runtime/GrowingInput";
import { useStore } from "../runtime/store";
import {
  FridgeHttpError, artAuth, fetchCatalog, fridgeErrText, inflightKey, withInflight, type ArtAuth, type CatalogItem,
} from "./fridgeApi";
import { useInflight } from "./useInflight";
import { cellScale, dishIcon } from "./dishIcons";
import { fmtMD } from "./kitchenText";
import { ArtImage } from "./panelParts";
import { KC, KF } from "./kitchenTheme";
import {
  BEST_WORD, FLOWER_STATE, KIND_WORD, LEDGER_STATE, ORDER_WORD, TAB_LABEL, chooseDexArt, decideFlower, dexArtSource, feedJar, fetchBook, fetchCode,
  fetchDex, fetchDislikes, addDislike, removeDislike, buyMissing, fetchJars, fetchLedger, fetchMissing, fetchOrders, fetchPlates, fetchStopped, fetchToday, fetchVendor, fetchWallet,
  grantPocket, importCode, mergeDex, methodWord, missingToBuy, orderDish, previewCode, redrawDex, saveDexNote, searchRecipes,
  setJarCap, setPlates, stopRecipe, treat, unsortedDish, withdrawOrder, type BookPage, type Dex, type DexPage, type Features, type Jar,
  type JarGood, type LedgerLine, type Missing, type Order, type Plates, type PlayTab, type RecipeEntry, type StoppedRecipe, type VendorView,
} from "./playApi";
import { HeadBtn, Label, Paper, SheetBtn, SheetFoot, SheetFrame, SheetHead, sh } from "./sheetParts";
import { ChoreStage } from "./ChoreStage";
import { platesClip, vendorPanelClip } from "./choreAnim";

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
    case "recipes": return <RecipesTab f={features} say={say} onChanged={onChanged} />;
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

function Act({ label, onPress, testID, disabled }: { label: string; onPress: () => void; testID?: string; disabled?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} hitSlop={6} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} testID={testID}>
      <Text style={[st.act, disabled && st.actOff]}>{label}</Text>
    </Pressable>
  );
}

const field = { fontFamily: KF, fontSize: 15, lineHeight: 22, color: KC.ink, placeholderTextColor: "#c4b5a8", maxHeight: 96 };

// ── recipes: today / search / the role's book / orders / codes / what not to recommend ─────────
export function RecipesTab({ f, say, onChanged }: { f: Features; say: (m: string) => void; onChanged: () => void }) {
  const { role, confirm } = useStore();
  const [qText, setQText] = useState("");
  const [hits, setHits] = useState<{ total: number; recipes: RecipeEntry[] } | null>(null);
  const [today, reloadToday] = useLoad((r) => (f.recipes_today ? fetchToday(r) : Promise.resolve("")), say);
  const [pages, reloadPages] = useLoad<BookPage[]>((r) => (f.recipe_book ? fetchBook(r) : Promise.resolve([])), say);
  const [orders, reloadOrders] = useLoad<Order[]>((r) => (f.orders ? fetchOrders(r) : Promise.resolve([])), say);
  const [code, setCode] = useState("");
  const [shown, setShown] = useState<{ page: string; code: string } | null>(null);
  // what the fridge lacks for one recipe (or a page of the book), opened under its row
  const [lack, setLack] = useState<{ ref: string; missing: Missing[] } | null>(null);
  // a recipe was just stopped here: the list of stopped ones below reads again
  const [settingsTick, setSettingsTick] = useState(0);
  const bumpSettings = () => setSettingsTick((n) => n + 1);
  const search = (text = qText) => {
    if (!f.recipes_public) return;
    searchRecipes(role, text.trim()).then(setHits, (e) => say(fridgeErrText(e, "没找成 · 网络?")));
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
  const showLack = (ref: string) => {
    if (lack?.ref === ref) return setLack(null);
    fetchMissing(role, ref).then((m) => setLack({ ref, missing: m.missing }), (e) => say(fridgeErrText(e, "没查到")));
  };
  // the same lock as the buying sheet (one buying for the role at a time): a second tap while one is on its way sends nothing
  const buyKey = inflightKey("buy", role);
  // The server works out what is missing and buys it in one go, and answers what is still missing: the lock
  // is held until that answer is on the panel, so the old list can never be bought from twice.
  // One op_id per buying, kept until the server has answered: a retry after a timeout or a dropped
  // connection is the same buying, and the server answers it from its receipt without buying again.
  const keys = useRetryKeys();
  const buyLack = (ref: string) => {
    const what = `buy-missing:${role}:${ref}`;
    return withInflight(buyKey, () => buyMissing(role, ref, keys.key(what)).then((r) => {
      keys.settle(what);
      setLack((cur) => (cur?.ref === ref ? { ref, missing: r.missing } : cur));
      return r;
    }, (e) => {
      keys.settle(what, e);
      throw e;
    })).then((r) => {
      if (r === null) return;                       // already on its way
      say(r.bought ? r.text || "买齐了 · 他会知道" : "冰箱里已经够了,没再买");
      if (r.bought) onChanged();
    }, (e) => say(fridgeErrText(e, "没买成")));
  };
  const lackPanel = (ref: string) => (lack?.ref === ref ? <LackPanel missing={lack.missing} buyKey={buyKey} onBuy={() => buyLack(ref)} /> : null);
  const stop = (r: RecipeEntry) => confirm({
    title: `『${r.name}』写错了,停推?`,
    message: "推荐和翻食谱里都不再出现它;做过的锅、他食谱本里的页和图鉴都不变。下面「停推的食谱」里随时能恢复。", yes: "停推",
    onYes: () => stopRecipe(r.id, true).then(() => { say(`停推了 ${r.name}`); search(); bumpSettings(); reloadToday(); }, (e) => say(fridgeErrText(e, "没停成"))),
  });
  return (
    <View testID="tab-body-recipes">
      {f.recipes_today && today ? <Line testID="today">{today}</Line> : null}
      {f.recipes_public ? (
        <>
          <Label first={!today}>翻公共食谱</Label>
          <View style={st.searchRow}>
            <GrowingInput value={qText} onChangeText={setQText} placeholder="菜名、食材或分类" {...field} style={[sh.field, { flex: 1 }]} testID="recipe-q" />
            <Act label="找" onPress={() => search()} testID="recipe-search" />
          </View>
          {hits ? (
            hits.recipes.length ? hits.recipes.map((r) => (
              <View key={r.id} style={st.row}>
                <View style={st.rowMain}>
                  <Text style={st.name}>{r.name}</Text>
                  <Text style={st.soft}>{`${r.itemsText || "常备就够"} · ${methodWord(r.method)} · 约 ${r.minutes} 分钟 · ${r.id}`}</Text>
                  {lackPanel(r.id)}
                </View>
                <View style={st.side}>
                  {f.orders ? <Act label="想吃这个" onPress={() => order(r)} testID={`order-${r.id}`} /> : null}
                  {f.recipe_cook ? <Act label={lack?.ref === r.id ? "收起" : "缺什么"} onPress={() => showLack(r.id)} testID={`lack-${r.id}`} /> : null}
                  <Act label="写错了" onPress={() => stop(r)} testID={`stop-${r.id}`} />
                </View>
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
                {lackPanel(p.id)}
              </View>
              <View style={st.side}>
                {f.recipe_codes && p.kind !== "menu" ? <Act label="码" onPress={() => showCode(p)} testID={`code-${p.id}`} /> : null}
                {f.recipe_cook && p.kind !== "menu" ? <Act label={lack?.ref === p.id ? "收起" : "缺什么"} onPress={() => showLack(p.id)} testID={`lack-${p.id}`} /> : null}
              </View>
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
      {f.recipes_public ? (
        <RecipeSettings say={say} tick={settingsTick} onChanged={() => {
          if (hits) search();
          reloadToday();     // 「今天可以试试」 must not keep a recipe just stopped or an ingredient just ruled out
        }} />
      ) : null}
    </View>
  );
}

/** What the fridge lacks for a recipe, and buying all of it for the role in one go (the human's usual buying: no coupon) */
function LackPanel({ missing, buyKey, onBuy }: { missing: Missing[]; buyKey: string; onBuy: () => void }) {
  const busy = useInflight(buyKey);
  if (!missing.length) return <Text style={st.soft} testID="lack-none">冰箱里的料够了</Text>;
  const buyable = missingToBuy(missing);
  return (
    <View testID="lack-panel">
      {missing.map((m) => (
        <Text key={m.itemId} style={st.soft}>{`缺 ${m.name} ${m.short} · ${m.sold ? `买 ${m.packs} 份` : "超市没有"}`}</Text>
      ))}
      {buyable.length ? <Act label={busy ? "在买…" : "替他买齐"} onPress={() => { if (!busy) onBuy(); }} disabled={busy} testID="lack-buy" /> : null}
    </View>
  );
}

/** Things not to recommend to the role (ingredients), and recipes taken out because they had a mistake; both can be undone */
function RecipeSettings({ say, tick, onChanged }: { say: (m: string) => void; tick: number; onChanged: () => void }) {
  const { role } = useStore();
  const [loadedDislikes] = useLoad<string[]>(fetchDislikes, say);
  const [stopped, reloadStopped] = useLoad<StoppedRecipe[]>(() => fetchStopped(), say);
  const [catalog] = useLoad<CatalogItem[]>(() => fetchCatalog(), say);
  const [text, setText] = useState("");
  useEffect(() => {
    if (tick) reloadStopped();
  }, [tick, reloadStopped]);
  const nameOf = (id: string) => catalog?.find((c) => c.id === id)?.name ?? id;
  // One ingredient at a time (the server adds or takes off that one and answers the whole list, so another
  // page open at the same time loses nothing). Nothing can be changed before the list was read, and changes
  // go one after another; the list shown is the one the last answer gave.
  const [dislikes, setDislikes] = useState<string[] | null>(null);
  const newest = useRef<string[] | null>(null);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const [pending, setPending] = useState(0);
  useEffect(() => {
    if (loadedDislikes === null) {            // another role, or read again: nothing can be changed until it is in
      newest.current = null;
      setDislikes(null);
    } else if (!pending) {
      newest.current = loadedDislikes;
      setDislikes(loadedDislikes);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a fresh read counts; a save answers for itself
  }, [loadedDislikes]);
  const change = (make: (cur: string[]) => { run: () => Promise<string[]>; done: string } | string) => {
    setPending((n) => n + 1);
    queue.current = queue.current.then(async () => {
      const cur = newest.current;
      if (!cur) return;
      const next = make(cur);
      if (typeof next === "string") return say(next);
      try {
        const saved = await next.run();
        newest.current = saved;
        setDislikes(saved);
        say(next.done);
        onChanged();
      } catch (e) {
        say(fridgeErrText(e, "没改上"));
      }
    }).finally(() => setPending((n) => n - 1));
  };
  const ready = dislikes !== null && catalog !== null;
  const add = () => {
    if (!ready) return;
    const hit = findIngredient(catalog ?? [], text);
    if (!hit) return say(`厨房里没有『${text.trim()}』这样食材`);
    setText("");
    change((cur) => (cur.includes(hit.id) ? `${hit.name}已经在里面了` : { run: () => addDislike(role, hit.id), done: `以后不推带${hit.name}的菜` }));
  };
  const drop = (id: string) => change(() => ({ run: () => removeDislike(role, id), done: `${nameOf(id)}又能推了` }));
  const unstop = (r: StoppedRecipe) => stopRecipe(r.id, false).then(() => { say(`${r.name}恢复了`); reloadStopped(); onChanged(); }, (e) => say(fridgeErrText(e, "没恢复成")));
  return (
    <View testID="recipe-settings">
      <Label>不让推的食材</Label>
      {dislikes === null ? <Line soft>…</Line> : dislikes.length === 0 ? <Line soft>没有 · 什么都可以推</Line> : dislikes.map((id) => (
        <View key={id} style={st.row}>
          <View style={st.rowMain}><Text style={st.name}>{nameOf(id)}</Text></View>
          <Act label="撤掉" onPress={() => drop(id)} testID={`dislike-off-${id}`} />
        </View>
      ))}
      <View style={st.searchRow}>
        <GrowingInput value={text} onChangeText={setText} placeholder="食材名,比如 香菜" {...field} style={[sh.field, { flex: 1 }]} testID="dislike-in" />
        <Act label="加" onPress={add} disabled={!ready} testID="dislike-add" />
      </View>
      {stopped && stopped.length ? (
        <>
          <Label>停推的食谱</Label>
          {stopped.map((r) => (
            <View key={r.id} style={st.row}>
              <View style={st.rowMain}>
                <Text style={st.name}>{r.name}</Text>
                <Text style={st.soft}>{`${r.id}${r.why ? ` · ${r.why}` : ""}`}</Text>
              </View>
              <Act label="恢复" onPress={() => unstop(r)} testID={`unstop-${r.id}`} />
            </View>
          ))}
        </>
      ) : null}
    </View>
  );
}

/** The catalog kind a typed name means: the same name, else the only one whose name contains it */
export function findIngredient(catalog: CatalogItem[], typed: string): CatalogItem | null {
  const t = typed.trim();
  if (!t) return null;
  const same = catalog.find((c) => c.name === t);
  if (same) return same;
  const part = catalog.filter((c) => c.name.includes(t));
  return part.length === 1 ? part[0] : null;
}

// ── the dish book ───────────────────────────────────────────────────────
/** The side of a page's picture box (the drawn picture is fitted into it; a pixel dish keeps whole cells) */
export const DEX_PIC = 64;

/** One of the fourteen small pixel dishes: in colour for a dish made, a grey silhouette for one only collected */
export function PixelDish({ icon, ghost, box, testID }: { icon: string; ghost?: boolean; box: number; testID?: string }) {
  const ic = dishIcon(icon);
  const k = cellScale(ic.w, ic.h, box - 12);
  return (
    <View style={[st.pic, { width: box, height: box }, PIXELATED]} testID={testID}>
      <Image source={ic.src} accessible={false} style={{ width: ic.w * k, height: ic.h * k, ...(ghost ? { tintColor: GHOST } : null) }} />
    </View>
  );
}

/** A page's picture: the chosen drawn version when there is one, otherwise (or when it cannot be fetched) its pixel dish */
export function DexPicture({ page, auth, version, box = DEX_PIC }: { page: DexPage; auth: ArtAuth; version?: number | null; box?: number }) {
  const v = version === undefined ? page.art.chosen : version;
  const placeholder = <PixelDish icon={page.icon} box={box} testID={`dex-placeholder-${page.key}`} />;
  if (v === null) return placeholder;
  return (
    <View style={[st.pic, { width: box, height: box }]} testID={`dex-art-${page.key}-${v}`}>
      <ArtImage art={{ src: dexArtSource(auth, page.key, v), w: box, h: box }} style={st.fill} fallback={placeholder} />
    </View>
  );
}

export function DexTab({ say }: { say: (m: string) => void }) {
  const { role, confirm } = useStore();
  const [dex, reload] = useLoad<Dex>(fetchDex, say);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  // the page whose pictures (switch back) or merge targets are open
  const [open, setOpen] = useState<{ key: string; what: "art" | "merge" } | null>(null);
  const auth = artAuth();
  if (!dex) return <Line soft>…</Line>;
  const save = (key: string) => saveDexNote(role, key, draft.trim()).then(() => { setEditing(null); reload(); }, (e) => say(fridgeErrText(e, "没存上")));
  const toggle = (key: string, what: "art" | "merge") => setOpen((o) => (o?.key === key && o.what === what ? null : { key, what }));
  const redraw = (p: DexPage) => confirm({
    title: `重画『${p.name}』?`, message: "画好之前还是现在这张;旧的每一张都留着,随时能换回去。", yes: "重画",
    onYes: () => redrawDex(p.key).then(() => { say("排上了 · 画好会换上"); reload(); }, (e) => say(fridgeErrText(e, "没排上"))),
  });
  const choose = (p: DexPage, v: number) => chooseDexArt(p.key, v).then(() => { say(`换成第 ${v} 版`); reload(); }, (e) => say(fridgeErrText(e, "没换成")));
  const merge = (p: DexPage, to: DexPage) => confirm({
    title: `把『${p.name}』并到『${to.name}』?`, message: "以后这个名字做的锅都记在那一页。并错了在那一页上能拆回来。", yes: "并",
    onYes: () => mergeDex(role, unsortedDish(p.key), to.key).then(() => { setOpen(null); say("并好了"); reload(); }, (e) => say(fridgeErrText(e, "没并成"))),
  });
  const unmerge = (dish: string) => mergeDex(role, dish, `d:${dish}`).then(() => { say(`『${dish}』拆回去了`); reload(); }, (e) => say(fridgeErrText(e, "没拆成")));
  // an unsorted dish goes onto a sorted page only (a recipe's, or one of his own): merging into another
  // unsorted page would leave a chain (B merged on, then B itself merged away) that cannot be undone cleanly
  const targetsFor = (p: DexPage) => dex.pages.filter((t) => t.key !== p.key && !t.pending);
  return (
    <View testID="tab-body-dex">
      <Line soft>{`公共食谱 ${dex.total ?? "—"} 道 · 做过其中 ${dex.madePublic} 道 · 图鉴 ${dex.pages.length} 页${dex.drawing && dex.artMissing ? ` · 还差 ${dex.artMissing} 张图` : ""}`}</Line>
      {dex.pages.length === 0 ? <Line soft>还没有做过的菜</Line> : dex.pages.map((p) => {
        const artOpen = open?.key === p.key && open.what === "art";
        const mergeOpen = open?.key === p.key && open.what === "merge";
        const picLine = p.art.drawing ? "新图在画" : p.art.failed ? `没画成:${p.art.failed}` : "";
        return (
          <View key={p.key} style={st.dexRow} testID={`dex-page-${p.key}`}>
            <DexPicture page={p} auth={auth} />
            <View style={st.rowMain}>
              <Text style={st.name}>{p.name}{p.pending ? <Text style={st.soft}>  待归类</Text> : null}</Text>
              <Text style={st.soft}>{`${p.firstAt ? `${fmtMD(p.firstAt * 1000)} 第一次 · ` : ""}做过 ${p.made} · 做好 ${p.good} · 吃过 ${p.eaten}${p.best ? ` · 最好 ${BEST_WORD[p.best] ?? p.best}` : ""} · ${methodWord(p.method)}`}</Text>
              {p.ingredients.length ? <Text style={st.soft}>{p.ingredients.join("、")}</Text> : null}
              {p.roleNote ? <Text style={st.soft}>{`他:「${p.roleNote}」`}</Text> : null}
              {editing === p.key ? (
                <View style={st.searchRow}>
                  <GrowingInput value={draft} onChangeText={setDraft} placeholder="评语" {...field} style={[sh.field, { flex: 1 }]} testID="dex-note-in" />
                  <Act label="存" onPress={() => save(p.key)} testID="dex-note-save" />
                </View>
              ) : p.humanNote ? <Text style={st.soft}>{`评语:${p.humanNote}`}</Text> : null}
              {picLine ? <Text style={[st.soft, p.art.failed && !p.art.drawing ? st.bad : null]} testID={`dex-pic-state-${p.key}`}>{picLine}</Text> : null}
              {p.mergedIn.map((d) => (
                <View key={d} style={st.inline}>
                  <Text style={st.soft}>{`并进来的:${d}`}</Text>
                  <Act label="拆回" onPress={() => unmerge(d)} testID={`dex-unmerge-${d}`} />
                </View>
              ))}
              <View style={st.acts}>
                {editing !== p.key ? <Act label="评语" onPress={() => { setEditing(p.key); setDraft(p.humanNote); }} testID={`dex-note-${p.key}`} /> : null}
                {dex.drawing && !p.art.drawing && (p.art.ready.length || p.art.failed) ? <Act label="重画" onPress={() => redraw(p)} testID={`dex-redraw-${p.key}`} /> : null}
                {p.art.ready.length > 1 ? <Act label={artOpen ? "收起旧图" : "换回旧图"} onPress={() => toggle(p.key, "art")} testID={`dex-versions-${p.key}`} /> : null}
                {p.pending && targetsFor(p).length ? <Act label={mergeOpen ? "收起" : "并页"} onPress={() => toggle(p.key, "merge")} testID={`dex-merge-${p.key}`} /> : null}
              </View>
              {artOpen ? (
                <View style={st.versions} testID={`dex-version-list-${p.key}`}>
                  {p.art.ready.map((v) => (
                    <Pressable key={v} onPress={() => choose(p, v)} accessibilityRole="button" accessibilityLabel={`第 ${v} 版`} accessibilityState={{ selected: v === p.art.chosen }} testID={`dex-version-${p.key}-${v}`} style={st.version}>
                      <View style={[st.versionPic, v === p.art.chosen && st.versionOn]}><DexPicture page={p} auth={auth} version={v} box={44} /></View>
                      <Text style={[st.soft, v === p.art.chosen && st.tabOn]}>{`第 ${v} 版`}</Text>
                    </Pressable>
                  ))}
                </View>
              ) : null}
              {mergeOpen ? (
                <View testID={`dex-merge-list-${p.key}`}>
                  <Text style={st.soft}>并到哪一页:</Text>
                  <View style={st.acts}>
                    {targetsFor(p).map((t) => <Act key={t.key} label={t.name} onPress={() => merge(p, t)} testID={`dex-merge-to-${t.key}`} />)}
                  </View>
                </View>
              ) : null}
            </View>
          </View>
        );
      })}
      {dex.silhouettes.length ? (
        <>
          <Label>收藏了还没做</Label>
          <View style={st.ghosts}>
            {dex.silhouettes.map((g) => (
              <View key={g.recipeId || g.name} style={st.ghost} testID={`dex-ghost-${g.recipeId || g.name}`}>
                <PixelDish icon={g.icon} ghost box={48} />
                <Text style={st.ghostName} numberOfLines={2}>{g.name}</Text>
              </View>
            ))}
          </View>
        </>
      ) : null}
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
export function VendorTab({ say, onChanged }: { say: (m: string) => void; onChanged: () => void }) {
  const { role, confirm } = useStore();
  const [v, reload] = useLoad<VendorView>(fetchVendor, say);
  const [ledger, reloadLedger] = useLoad<LedgerLine[]>(fetchLedger, say);
  const keys = useRetryKeys();
  // the role buys through its tools while this is open
  // (and, for a short while after the vendor has gone, so the panel can finish what it was showing)
  useEvery(VENDOR_POLL_MS, !!(v?.visit || v?.ended), () => {
    reload();
    reloadLedger();
  });
  if (!v) return <Line soft>…</Line>;
  const buyFor = (id: string, name: string) => confirm({
    title: `替他买一份『${name}』?`, message: "不花他的零花钱。", yes: "买",
    onYes: () => {
      const what = `treat:${role}:${id}`;
      treat(role, id, keys.key(what)).then((ok) => { keys.settle(what); say(ok ? "买好了 · 他会知道" : "还在办"); reload(); reloadLedger(); onChanged(); },
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
      ) : (
        <>
          <Line soft>楼下现在没有小贩</Line>
          {/* the visit that just ended (or, once the server no longer says, what this device last knew) finishes here */}
          <ChoreStage pick={(ms) => vendorPanelClip(v, ms)} testID="vendor-cook" />
        </>
      )}
      <Label>{`他今天在小贩这儿花了 ${v.spent} / ${v.cap}`}</Label>
      <LedgerList lines={ledger} />
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

/** One line per order with the vendors, newest first (who paid, what, how many, how much): read only */
function LedgerList({ lines }: { lines: LedgerLine[] | null }) {
  if (!lines || !lines.length) return null;
  return (
    <View testID="vendor-ledger">
      {lines.slice(0, 10).map((o) => (
        <Text key={o.id} style={st.soft}>
          {`${fmtMD(o.at * 1000)} · ${o.name}×${o.qty} · ${o.total} · ${o.payer === "her" ? "你请的" : "他自己买的"} · ${LEDGER_STATE[o.state] ?? o.state}`}
        </Text>
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
  actOff: { color: KC.tixOff },
  searchRow: { flexDirection: "row", alignItems: "flex-end", columnGap: 12, marginTop: 4 },
  code: { fontFamily: KF, fontSize: 11, lineHeight: 16, color: KC.ink, marginTop: 4 },
  pocketNum: { fontFamily: KF, fontSize: 30, lineHeight: 40, color: KC.ink, marginTop: 10 },
  bad: { color: KC.bad },
  fill: { width: "100%", height: "100%" },
  // the dish book: a picture box on the left of each page (the same paper tone as the thumbnails)
  dexRow: { flexDirection: "row", alignItems: "flex-start", columnGap: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: KC.line },
  pic: { borderRadius: 10, backgroundColor: KC.thumb, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  acts: { flexDirection: "row", flexWrap: "wrap", columnGap: 14, rowGap: 2, marginTop: 4 },
  inline: { flexDirection: "row", alignItems: "center", columnGap: 10 },
  versions: { flexDirection: "row", flexWrap: "wrap", columnGap: 10, rowGap: 6, marginTop: 6 },
  version: { alignItems: "center" },
  versionPic: { borderRadius: 12, borderWidth: 1.5, borderColor: "transparent", padding: 1 },
  versionOn: { borderColor: KC.tomato },
  ghosts: { flexDirection: "row", flexWrap: "wrap", columnGap: 12, rowGap: 10, paddingTop: 6 },
  ghost: { width: 56, alignItems: "center" },
  ghostName: { fontFamily: KF, fontSize: 10, lineHeight: 14, color: KC.soft, textAlign: "center", marginTop: 3 },
  side: { alignItems: "flex-end", rowGap: 4 },
});

/** Pixel art is scaled by whole cells without smoothing (inherited by the image inside) */
const PIXELATED = Platform.OS === "web" ? ({ imageRendering: "pixelated" } as object) : null;
/** A dish collected and not made yet: its pixel dish in one flat grey */
const GHOST = "#cdbfb2";
