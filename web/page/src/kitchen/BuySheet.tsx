// The "buy him groceries" sheet: the catalog (GET /api/fridge/catalog) as a grid of small pictures
// grouped by category; tick several (tap again to untick) and buy (POST /api/fridge/buy: the human
// buys without a coupon, as often as they like).
// Success = the sheet closes and the server's sentence is passed on; failure = the server's own
// sentence is shown right here and what was ticked stays, so it can be tried again.
// "添种类" in the head switches to KindForm (adding / removing ingredient kinds). The picture of an
// added kind is drawn by the server in the background (when an art provider is configured); until
// it is there the tile shows the first character of the name, and while the sheet is open the
// catalog is quietly read again every few seconds so the picture appears by itself.
// The purchase itself is carried out by the page: the role guard and the per-role in-flight lock
// live there and in the request layer. This sheet only hands over what was ticked and shows the
// answer; "in flight" is read from the request layer's lock, so closing and reopening does not lose it.
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { usePageWidth } from "../runtime/layout";
import { KindForm } from "./KindForm";
import { artOf } from "./kindArt";
import { fetchCatalog, inflightKey, type ArtAuth, type CatalogItem, type Viewer } from "./fridgeApi";
import { useInflight } from "./useInflight";
import { groupCatalog, toggleSelect } from "./kitchenText";
import { KC, KF } from "./kitchenTheme";
import { Ring } from "./handParts";
import { ArtImage, ps } from "./panelParts";
import { HeadBtn, Paper, SheetBtn, SheetFoot, SheetFrame, SheetHead, sh } from "./sheetParts";

type Load = { kind: "loading" } | { kind: "ok"; items: CatalogItem[] } | { kind: "error" };

/** What came of the purchase the page carried out: done = bought (the page already closed the sheet / said so); error = show the sentence here; busy = this role already has an order on its way; stale = the role was switched away */
export type BuyResult = { kind: "done" } | { kind: "error"; message: string } | { kind: "busy" } | { kind: "stale" };

const COLS = 6;
/** While a picture is still being drawn, how often the open sheet quietly reads the catalog again */
export const ART_POLL_MS = 6000;

export function BuySheet({
  open,
  viewer,
  auth,
  onClose,
  onBuy,
  onOrphanError,
}: {
  open: boolean;
  viewer: Viewer;
  auth: ArtAuth | null;
  onClose: () => void;
  /** isLive: this round of the sheet is still there (mounted, and not closed and reopened); the page only closes the sheet while it is true */
  onBuy: (items: string[], isLive: () => boolean) => Promise<BuyResult>;
  /** the answer arrived after this round of the sheet was gone: the failure sentence goes to the page to show */
  onOrphanError: (message: string) => void;
}) {
  const width = usePageWidth();
  const { height } = useWindowDimensions();
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [sel, setSel] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [late, setLate] = useState(""); // the failure sentence of the previous order (it arrived while this round of the sheet was open)
  const openRef = useRef(open);
  openRef.current = open;
  const [mode, setMode] = useState<"buy" | "kinds">("buy");
  const busy = useInflight(inflightKey("buy", viewer));

  // Catalog request number: only the last one sent counts. A slow answer from the polling must not
  // put back a kind that was just removed; nothing is written after unmounting either.
  const catSeq = useRef(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const reload = useCallback(() => {
    const mine = ++catSeq.current;
    const latest = () => alive.current && catSeq.current === mine;
    setLoad({ kind: "loading" });
    fetchCatalog()
      .then((items) => latest() && setLoad({ kind: "ok", items }))
      .catch(() => latest() && setLoad({ kind: "error" }));
  }, []);
  /** Read again quietly (no "loading" flash; a failure keeps what was there): after adding / removing / redrawing, and while waiting for a picture */
  const refresh = useCallback(() => {
    const mine = ++catSeq.current;
    fetchCatalog()
      .then((items) => {
        if (!alive.current || catSeq.current !== mine) return;
        setLoad({ kind: "ok", items });
        setSel((s) => s.filter((id) => items.some((i) => i.id === id)));   // a removed kind does not stay ticked
      })
      .catch(() => {});
  }, []);
  const drawing = open && load.kind === "ok" && load.items.some((i) => i.art?.state === "pending");
  useEffect(() => {
    if (!drawing) return;
    const t = setInterval(refresh, ART_POLL_MS);
    return () => clearInterval(t);
  }, [drawing, refresh]);

  // Rounds: every opening / closing of the sheet starts a new one. An answer is only written back to
  // the round it was submitted in; an unmounted sheet counts as expired too.
  const round = useRef(0);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    round.current += 1;
    if (!open) return setLate("");
    setSel([]);
    setErr("");
    setMode("buy");
    reload();
  }, [open, reload]);

  const buy = async () => {
    if (!sel.length || busy) return;
    setErr("");
    setLate("");
    const mine = round.current;
    const isLive = () => mounted.current && round.current === mine;
    const r = await onBuy(sel, isLive);
    if (r.kind !== "error") return;
    if (isLive()) return setErr(r.message);
    onOrphanError(r.message);
    // this round was closed and reopened: a toast is hidden behind the new sheet, so one line is written on the new sheet too
    if (mounted.current && openRef.current) setLate(r.message);
  };

  // A tile's width: 14 kept free on each side of the sheet, 16 of padding inside the paper, a 34 wide column of category names on the left, 7 between tiles, 6 in a row
  const tileW = Math.floor((width - 100 - (COLS - 1) * 7) / COLS);

  return (
    <SheetFrame open={open} onClose={onClose}>
      <Paper style={{ maxHeight: height * 0.8 }} testID="buy-sheet">
        <SheetHead title={mode === "kinds" ? "添种类" : `给${viewer}买菜`}>
          <HeadBtn label={mode === "kinds" ? "回去买菜" : "添种类"} onPress={() => setMode((m) => (m === "buy" ? "kinds" : "buy"))} testID="buy-mode" />
          <HeadBtn label="收起" onPress={onClose} testID="buy-close" />
        </SheetHead>
        <ScrollView style={st.scroll} contentContainerStyle={st.scrollIn} keyboardShouldPersistTaps="handled">
          {load.kind === "loading" ? <Text style={ps.status}>读取中…</Text> : null}
          {load.kind === "error" ? (
            <Pressable onPress={reload} accessibilityRole="button" accessibilityLabel="重新读取" testID="catalog-retry">
              <Text style={ps.status}>目录没拉到 · 点一下重试</Text>
            </Pressable>
          ) : null}
          {load.kind === "ok" && mode === "kinds" ? <KindForm items={load.items} auth={auth} onChanged={refresh} onOrphanError={onOrphanError} /> : null}
          {load.kind === "ok" && mode === "buy"
            ? groupCatalog(load.items).map((g) => (
                <View key={g.key} style={st.group}>
                  <Text style={st.groupLbl}>{g.label}</Text>
                  <View style={st.grid}>
                    {g.items.map((it) => {
                      const on = sel.includes(it.id);
                      const art = artOf(it.id, "fresh", it.art, auth);
                      return (
                        <Pressable
                          key={it.id}
                          onPress={() => setSel((s) => toggleSelect(s, it.id))}
                          style={[st.tile, { width: tileW }]}
                          accessibilityRole="checkbox"
                          accessibilityState={{ checked: on }}
                          accessibilityLabel={it.name}
                          testID={`buy-${it.id}`}
                        >
                          <View style={{ width: tileW, height: tileW - 8 }}>
                            <ArtImage
                              art={art}
                              style={st.img}
                              fallback={
                                <Text style={[st.tileCh, { fontSize: tileW * 0.4, lineHeight: tileW - 8 }]} testID={`buy-ch-${it.id}`}>{Array.from(it.name)[0]}</Text>
                              }
                            />
                            {on ? <Ring style={st.ring} /> : null}
                          </View>
                          <Text style={[st.tileNm, on && { color: KC.ink }]} numberOfLines={1}>
                            {it.packQty > 1 ? `${it.name} ×${it.packQty}` : it.name}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </View>
              ))
            : null}
        </ScrollView>
        {mode === "buy" && err ? <Text style={sh.err} testID="buy-err">{err}</Text> : null}
        {late ? <Text style={sh.err} testID="buy-late">{`上一单 · ${late}`}</Text> : null}
        {mode === "buy" ? (
          <SheetFoot left={sel.length ? `圈了 ${sel.length} 样` : ""}>
            <SheetBtn
              label={busy ? "买着…" : sel.length ? `买 ${sel.length} 样` : "买"}
              onPress={buy}
              disabled={!sel.length || busy}
              testID="buy-confirm"
            />
          </SheetFoot>
        ) : null}
      </Paper>
    </SheetFrame>
  );
}

const st = StyleSheet.create({
  // 8 let out on each side: the red circle is a little wider than the name, and the scroller's edge must not cut it
  scroll: { flexGrow: 0, flexShrink: 1, marginTop: 4, marginHorizontal: -8 },
  scrollIn: { paddingBottom: 4, paddingHorizontal: 8 },
  // one category per line: its name in a column on the left, its pictures on the right
  group: { flexDirection: "row", marginTop: 6 },
  groupLbl: { width: 34, fontFamily: KF, fontSize: 10, lineHeight: 14, letterSpacing: 1, color: KC.soft, paddingTop: 12 },
  grid: { flex: 1, flexDirection: "row", flexWrap: "wrap", columnGap: 7, rowGap: 2 },
  tile: { alignItems: "center" },
  tileCh: { fontFamily: KF, textAlign: "center", color: KC.soft },
  img: { width: "100%", height: "100%" },
  ring: { left: -1, right: -1, top: -3, bottom: -3 },
  tileNm: { fontFamily: KF, fontSize: 9.5, lineHeight: 14, color: KC.soft },
});
