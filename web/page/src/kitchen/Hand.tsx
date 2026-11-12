// "The hand": whatever was tapped in the picture is taken down here and shown large: an ingredient /
// the coupon / the staples / a dish or a potion on the counter / the "meals today" receipt / the
// recent notes on the wall. A snack has its own hand (SnackHand: it reads its own data).
// This file is only the look: handing out a coupon, buying, putting up / changing / feeding /
// removing are handled by the page (KitchenPage.tsx), and so are the role guard and the in-flight locks.
import { useEffect, useState, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { FRIDGE_ART } from "./art.generated";
import { COUPON_ART, COUPON_TEXT } from "./couponArt";
import { inflightKey, type ArtAuth, type FridgeItem, type FridgeState, type Viewer } from "./fridgeApi";
import {
  Act, Acts, Bar, BarBtn, BarNum, BarTx, Big, HERO, HandShell, HeroArt, Line, Name, Note, Sp, Status, Thumbs, Top, hp, lineInk,
  type ThumbItem,
} from "./handParts";
import { outcomeWord, type KitchenOutcome } from "./kitchenApi";
import { artOf } from "./kindArt";
import { couponRule, expiryText, fmtLeft, fmtMD, fmtStamp } from "./kitchenText";
import { FRESH_COLOR, FRESH_LABEL, KC, KF, bodoniFor, bodoniTight, shadow } from "./kitchenTheme";
import { ArtImage, RefreshFailed } from "./panelParts";
import { batchesOf, kindsOf, type Pick } from "./pick";
import { NOTE_SLOTS, STAPLE_SLOTS, dishArt } from "./sceneSlots";
import { useInflight } from "./useInflight";

export interface HandDish {
  id: string | null;
  /** how the picture and the bottom row know it (the id when it has one) */
  key: string;
  n: string;
  note: string;
  outcome: KitchenOutcome | null;
  potion: boolean;
  potionPct: number | null;
}
export interface MealLine {
  slot: string;
  meal: string;
}

export interface HandProps {
  pick: Pick;
  anchor: { x: number; y: number } | null;
  sceneH: number;
  state: FridgeState | null;
  failed: boolean;
  viewer: Viewer;
  auth: ArtAuth | null;
  nowMs: number;
  dishes: HandDish[];
  /** the menu: still being read / read / could not be read */
  menu: "loading" | "ok" | "failed";
  meals: MealLine[];
  /** how many kinds one coupon buys (printed on the coupon) */
  buyMaxItems: number;
  onPick: (p: Pick) => void;
  onReload: () => void;
  onReloadMenu: () => void;
  onCoupon: () => void;
  onOpenBuy: () => void;
  onOpenWrite: () => void;
  onFeed: (d: HandDish) => void;
  onStrike: (d: HandDish) => void;
  onEdit: (d: HandDish) => void;
  onRemove: (d: HandDish) => void;
  /** the snack's hand (SnackHand): the page passes it in, this only leaves room for it */
  snack: ReactNode;
}

/** Notes per page on the wall (two columns, three rows) */
export const WALL_PAGE = 6;
/** The result words the kitchen writes into a menu row's note: already shown next to the dish name, not repeated */
const RESULT_NOTES = new Set(["糊了", "坏了", "火候刚好"]);

export function Hand(p: HandProps) {
  const { pick, state, failed } = p;
  if (pick.k === "snack") return <>{p.snack}</>;
  const needsFridge = pick.k === "item" || pick.k === "coupon" || pick.k === "staple" || pick.k === "wall";
  return (
    <HandShell anchor={p.anchor} sceneH={p.sceneH} testID={`hand-${pick.k}`}>
      {state && failed ? <RefreshFailed onRetry={p.onReload} /> : null}
      {needsFridge && !state ? (
        failed ? <Status text="冰箱没拉到 · 点一下重试" onPress={p.onReload} /> : <Status text="读取中…" />
      ) : pick.k === "item" ? (
        <ItemHand {...p} id={pick.id} />
      ) : pick.k === "coupon" ? (
        <CouponHand {...p} />
      ) : pick.k === "staple" ? (
        <StapleHand {...p} />
      ) : pick.k === "dish" ? (
        <DishHand {...p} id={pick.id} />
      ) : pick.k === "receipt" ? (
        <ReceiptHand {...p} />
      ) : (
        <WallHand {...p} />
      )}
    </HandShell>
  );
}

// ── the fridge row: everything in the fridge (the server's order, the most urgent first) + the coupon + buy groceries ──
function FridgeRow({ state, auth, cur, onPick, onOpenBuy }: Pick_<HandProps, "state" | "auth" | "onPick" | "onOpenBuy"> & { cur?: string }) {
  const kinds = kindsOf(state?.items ?? []);
  const c = state?.coupons ?? { count: 0, max: 3 };
  const thumbs: ThumbItem[] = kinds.map((k) => ({ key: k.itemId, name: k.name, badge: k.qty, art: artOf(k.itemId, k.first.freshness, k.first.art, auth) }));
  return (
    <>
      <Bar
        left={<><BarTx>冰箱里</BarTx><BarNum>{String(kinds.length)}</BarNum><BarTx>样</BarTx></>}
        right={
          <>
            <BarBtn label={`买菜券 ${c.count}/${c.max}`} onPress={() => onPick({ k: "coupon" })} testID="row-coupon" />
            <BarBtn label="给他买菜" go onPress={onOpenBuy} testID="open-buy" />
          </>
        }
      />
      {kinds.length === 0 ? <Text style={st.empty} testID="fridge-empty">空的</Text> : <Thumbs items={thumbs} cur={cur} onPick={(id) => onPick({ k: "item", id })} idPrefix="row-item" />}
    </>
  );
}
/** In this file Pick is "the thing in the hand"; TypeScript's own Pick utility goes by Pick_ here */
type Pick_<T, K extends keyof T> = { [P in K]: T[P] };

const byWho = (it: FridgeItem) => (it.by === "her" ? "你买的" : it.by === "self" ? "他自己买的" : "");

function ItemHand(p: HandProps & { id: string }) {
  const batches = batchesOf(p.state?.items ?? [], p.id);
  const first = batches[0];
  if (!first) return <FridgeRow {...p} />;
  const total = batches.reduce((n, b) => n + b.qty, 0);
  return (
    <>
      <Top hero={<HeroArt art={artOf(first.itemId, first.freshness, first.art, p.auth)} name={first.name} />}>
        <Name>{first.name}</Name>
        <Big n={`×${total}`} />
        {batches.map((b) => {
          const tail = [expiryText(b), batches.length > 1 ? `×${b.qty}` : ""].filter(Boolean).join(" · ");
          const who = [byWho(b), b.boughtAtMs !== null ? fmtMD(b.boughtAtMs) : ""].filter(Boolean).join(" · ");
          return (
            <View key={b.batchId} testID={`batch-${b.freshness}`}>
              <Line dot={FRESH_COLOR[b.freshness]}>
                <Text style={lineInk}>{FRESH_LABEL[b.freshness]}</Text>
                {tail ? ` · ${tail}` : ""}
              </Line>
              {who ? <Line>{who}</Line> : null}
            </View>
          );
        })}
      </Top>
      <FridgeRow {...p} cur={p.id} />
    </>
  );
}

/** The enlarged coupon: the picture with 「买菜券」 and one small line printed on it */
function CouponHero({ rule }: { rule: string }) {
  // where the coupon really is inside the hero box once scaled to fit; the words are placed against that
  const a = FRIDGE_ART[COUPON_ART];
  const sc = Math.min(HERO.w / a.w, HERO.h / a.h);
  const w = a.w * sc;
  const h = a.h * sc;
  const f = h * 0.165;
  return (
    <HeroArt art={COUPON_ART}>
      <View style={{ position: "absolute", pointerEvents: "none", left: 10 + (HERO.w - w) / 2 + w * (COUPON_TEXT.cx - 0.5), top: (HERO.h - h) / 2 + h * COUPON_TEXT.cy - f * 0.9, width: w, alignItems: "center" }}>
        <Text style={{ fontFamily: KF, fontSize: f, lineHeight: f * 1.3, letterSpacing: f * 0.12, color: COUPON_TEXT.color }}>买菜券</Text>
        <Text style={{ fontFamily: KF, fontSize: f * 0.36, lineHeight: f * 0.7, color: COUPON_TEXT.color }}>{rule}</Text>
      </View>
    </HeroArt>
  );
}

function CouponHand(p: HandProps) {
  const c = p.state?.coupons ?? { count: 0, max: 3 };
  const busy = useInflight(inflightKey("coupon", p.viewer));
  const last = (p.state?.log ?? []).find((l) => l.kind === "coupon");
  return (
    <>
      <Top hero={<CouponHero rule={couponRule(p.buyMaxItems)} />}>
        <Name>买菜券</Name>
        <Big n={String(c.count)} tail={`/ ${c.max} 张`} />
        {last ? <Line>{`${last.atMs !== null ? `${fmtStamp(last.atMs)} ` : ""}${last.text}`}</Line> : null}
      </Top>
      <Acts>
        <Act label="发一张" tone="go" onPress={p.onCoupon} disabled={c.count >= c.max || busy} testID="send-coupon" />
        {c.count >= c.max ? <Act label="攒满了" tone="mute" /> : null}
        <Sp />
        <Act label="给他买菜" onPress={p.onOpenBuy} testID="coupon-open-buy" />
      </Acts>
      <FridgeRow {...p} />
    </>
  );
}

function StapleHand(p: HandProps) {
  // as many as the server lists; the known ones (油 / 酱油 / 盐 / 米) get a picture, the others only their name
  const list = (p.state?.staples ?? []).map((name) => ({ name, art: STAPLE_SLOTS.find((s) => s.name === name)?.art ?? null }));
  return (
    <>
      <Top>
        <Name>常备</Name>
        <View style={st.staples}>
          {list.map((s) => (
            <View key={s.name} style={st.staple} testID={`staple-${s.name}`}>
              <View style={st.stapleImg}><ArtImage art={s.art} style={hp.fill} fallback={<Text style={st.stapleCh}>{Array.from(s.name)[0]}</Text>} /></View>
              <Text style={st.stapleNm}>{s.name}</Text>
            </View>
          ))}
        </View>
      </Top>
      <FridgeRow {...p} />
    </>
  );
}

// ── the table row: every dish that is up + meals today + put a dish up ──
function TableRow({ dishes, meals, menu, cur, onPick, onOpenWrite, onReloadMenu }: Pick_<HandProps, "dishes" | "meals" | "menu" | "onPick" | "onOpenWrite" | "onReloadMenu"> & { cur?: string }) {
  const thumbs: ThumbItem[] = dishes.map((d) => ({
    key: d.key, art: dishArt(d.n, d.outcome),
    name: d.note ? `${d.n} ${Array.from(d.note).slice(0, 20).join("")}` : d.n,   // dishes / potions of the same name are told apart by the start of the note (a potion's note = its amount + the memo)
  }));
  return (
    <>
      <Bar
        left={
          <>
            <BarTx>桌上</BarTx><BarNum>{String(dishes.length)}</BarNum><BarTx>道</BarTx>
            <BarBtn label={meals.length ? `今天吃了 ${meals.length} 顿` : "今天还没吃"} onPress={() => onPick({ k: "receipt" })} testID="row-receipt" />
          </>
        }
        right={<BarBtn label="挂一道" go onPress={onOpenWrite} testID="open-write" />}
      />
      {dishes.length > 0 ? (
        <Thumbs items={thumbs} cur={cur} onPick={(id) => onPick({ k: "dish", id })} idPrefix="row-dish" />
      ) : menu === "failed" ? (
        <Status text="没读到 · 点一下重试" onPress={onReloadMenu} />
      ) : (
        <Text style={st.empty} testID="table-empty">{menu === "loading" ? "读取中…" : "今天还没点菜"}</Text>
      )}
    </>
  );
}

function DishHand(p: HandProps & { id: string }) {
  const d = p.dishes.find((x) => x.key === p.id);
  if (!d) return <TableRow {...p} />;
  const word = outcomeWord(d.outcome);
  const note = d.note && !RESULT_NOTES.has(d.note.trim()) ? d.note : "";
  return (
    <>
      <Top hero={<HeroArt art={dishArt(d.n, d.outcome)} />}>
        <Name small>{d.n}</Name>
        {word ? <Line style={{ color: d.outcome === "great" ? KC.fresh : KC.bad }}>{word}</Line> : null}
        {d.potion && d.potionPct !== null ? <Big n={String(d.potionPct)} tail="% 体力" /> : null}
      </Top>
      {note ? <Note>{note}</Note> : null}
      {d.id ? (
        <Acts>
          <Act label="喂给他" tone="go" onPress={() => p.onFeed(d)} testID="dish-feed" />
          <Act label="只划掉" onPress={() => p.onStrike(d)} testID="dish-strike" />
          <Sp />
          <Act label="改" onPress={() => p.onEdit(d)} testID="dish-edit" />
          <Act label="撤" onPress={() => p.onRemove(d)} testID="dish-remove" />
        </Acts>
      ) : null}
      <TableRow {...p} cur={d.key} />
    </>
  );
}

function ReceiptHand(p: HandProps) {
  const n = p.meals.length;
  return (
    <>
      <Top
        hero={
          <View style={st.receipt}>
            <Text style={st.rcTx}>今天</Text>
            <Text style={[st.rcNum, { fontFamily: bodoniFor(40) }, bodoniTight(40, 44)]}>{n}</Text>
            <Text style={st.rcTx}>顿</Text>
          </View>
        }
      >
        <Name small>用餐记录</Name>
        <Line>{n ? `今天 ${n} 顿` : "今天还没吃"}</Line>
        {p.meals.map((m, i) => (
          <Line key={i}>
            <Text style={lineInk}>{m.meal}</Text>
            {`　${m.slot}`}
          </Line>
        ))}
      </Top>
      <TableRow {...p} />
    </>
  );
}

function WallHand(p: HandProps) {
  const [page, setPage] = useState(0);
  const log = p.state?.log ?? [];
  const pages = Math.max(1, Math.ceil(log.length / WALL_PAGE));
  useEffect(() => {
    if (page > pages - 1) setPage(pages - 1);
  }, [page, pages]);
  const shown = log.slice(page * WALL_PAGE, (page + 1) * WALL_PAGE);
  const dizzy = p.state?.dizzy && p.state.dizzy.untilMs > p.nowMs ? p.state.dizzy : null;
  return (
    <>
      {dizzy ? (
        <View style={st.dizzy} testID="wall-dizzy">
          <Text style={st.dizzyTx}>{`晕乎乎${dizzy.dish ? ` · 吃了坏掉的『${dizzy.dish}』` : ""}`}</Text>
          <Text style={st.dizzyLeft}>{`还有 ${fmtLeft(dizzy.untilMs - p.nowMs)}`}</Text>
        </View>
      ) : null}
      {log.length === 0 ? <Status text="还没有记录" /> : null}
      <View style={st.notes}>
        {shown.map((l, i) => (
          <View key={`${page}-${i}`} testID="wall-note" style={[st.note, { backgroundColor: NOTE_SLOTS[i % 3].color, transform: [{ rotate: `${NOTE_ROT[i % NOTE_ROT.length]}deg` }] }]}>
            <View style={st.pin} />
            {l.atMs !== null ? <Text style={[st.noteAt, { fontFamily: bodoniFor(10) }]}>{fmtStamp(l.atMs)}</Text> : null}
            <Text style={st.noteTx}>{l.text}</Text>
          </View>
        ))}
      </View>
      <Bar
        left={<BarTx>墙上 · 最近的事</BarTx>}
        right={
          pages > 1 ? (
            <>
              <BarBtn label="新一些" onPress={() => setPage((x) => Math.max(0, x - 1))} disabled={page === 0} testID="wall-newer" />
              <BarNum>{`${page + 1} / ${pages}`}</BarNum>
              <BarBtn label="更早的" onPress={() => setPage((x) => Math.min(pages - 1, x + 1))} disabled={page >= pages - 1} testID="wall-older" />
            </>
          ) : undefined
        }
      />
    </>
  );
}
const NOTE_ROT = [-1.5, 1, 1.2, -1, -1, 1.5];

const st = StyleSheet.create({
  empty: { fontFamily: KF, fontSize: 12, lineHeight: 20, letterSpacing: 1, color: KC.soft, marginTop: 10, minHeight: 34 },
  staples: { flexDirection: "row", flexWrap: "wrap", columnGap: 18, rowGap: 8, marginTop: 14 },
  staple: { alignItems: "center" },
  stapleImg: { width: 56, height: 88 },
  stapleCh: { width: 56, lineHeight: 88, textAlign: "center", fontFamily: KF, fontSize: 26, color: KC.soft },
  stapleNm: { fontFamily: KF, fontSize: 12, lineHeight: 20, letterSpacing: 1, color: KC.ink, marginTop: 4 },
  receipt: {
    marginLeft: 44, marginTop: 6, width: 74, height: 124, backgroundColor: "#fffef9", alignItems: "center", justifyContent: "center",
    ...shadow(0.28, 3, 2),
  },
  rcTx: { fontFamily: KF, fontSize: 13, lineHeight: 20, letterSpacing: 2, color: KC.ink },
  rcNum: { color: KC.ink },
  dizzy: { marginHorizontal: 4, marginBottom: 12, paddingVertical: 8, paddingHorizontal: 12, borderWidth: 1, borderColor: KC.bad, backgroundColor: KC.tix },
  dizzyTx: { fontFamily: KF, fontSize: 14, lineHeight: 20, letterSpacing: 1, color: KC.bad },
  dizzyLeft: { fontFamily: KF, fontSize: 12, lineHeight: 18, color: KC.soft },
  notes: { flexDirection: "row", flexWrap: "wrap", columnGap: 10, rowGap: 12, justifyContent: "space-between" },
  note: {
    width: "48%", minHeight: 76, paddingTop: 11, paddingHorizontal: 10, paddingBottom: 8,
    ...shadow(0.28, 1.5, 1),
  },
  pin: { position: "absolute", top: 3, alignSelf: "center", width: 6, height: 6, borderRadius: 3, backgroundColor: KC.tomato },
  noteAt: { fontSize: 9.5, lineHeight: 15, color: KC.soft },
  noteTx: { fontFamily: KF, fontSize: 11, lineHeight: 16, color: KC.ink },
});
