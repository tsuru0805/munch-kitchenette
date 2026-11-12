// The kitchen page.
// At the top: whose kitchen it is, satiety (red when low), and how much longer the role is dizzy.
// In the middle: the whole kitchen in one square picture, in which every thing can be tapped.
// Below ("the hand"): whatever was tapped is taken down and shown large, with what can be done with
// it and a row of the other things from the same place.
// What needs typing or choosing among many things is done on a sheet that drops from the top
// (BuySheet / WriteSheet); a yes/no question is asked on a slip (runtime/ConfirmSheet).
// The state and the handlers for putting up / changing / feeding / removing a dish, potions,
// coupons and groceries all live in this file; the parts under kitchen/ are only the look.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { BuySheet, type BuyResult } from "./kitchen/BuySheet";
import {
  FridgeHttpError, artAuth, buyItems, fetchFridge, fridgeErrText, inflightKey, sendCoupon, withInflight, type FridgeState,
} from "./kitchen/fridgeApi";
import { Hand, type HandDish } from "./kitchen/Hand";
import { HAND_TOP } from "./kitchen/handParts";
import {
  advanceClock, deleteMenu, feedMenu, fetchMeals, fetchMenu, fetchRecentPots, patchMenu, postMenu, type KitchenSessionWire, type Meal,
} from "./kitchen/kitchenApi";
import { KitchenScene } from "./kitchen/KitchenScene";
import { dishOutcome, fmtLeft, mealSlot } from "./kitchen/kitchenText";
import { KC, KF, bodoniFor, bodoniTight } from "./kitchen/kitchenTheme";
import { anchorOf, defaultPick, pickAlive, sceneObjects, zonePick, type Pick, type Tap } from "./kitchen/pick";
import {
  POTION_NAME, cleanMemo, dropPotion, feedPotion, fetchPotions, hangPotion, isPotionName, parsePct, potionNote, updatePotion,
  type PotionBook,
} from "./kitchen/potionApi";
import { SnackHand } from "./kitchen/SnackHand";
import { WriteSheet } from "./kitchen/WriteSheet";
import { usePageWidth } from "./runtime/layout";
import { useStore } from "./runtime/store";
import { nowMs as kitchenNow } from "./runtime/zone";

/** Horizontal padding of the page */
const PAD_H = 18;

interface Dish { id: string | null; n: string; note: string; /** the key of a dish just put up, until its real id comes back (does not depend on its place in the list) */ tmp?: string }
type Ticket = { epoch: number; role: string };

export function KitchenPage({ onBack, onForgetToken }: {
  /** set when the page is embedded and the host can be told the person wants to leave */
  onBack?: () => void;
  /** set when a token kept in this browser is in use: forget it and ask again */
  onForgetToken?: () => void;
}) {
  const { toast: rawToast, confirm, role, roles, setRole, about, tick, reloadAll } = useStore();
  // The "put a dish up / change" sheet is a layer of its own and a toast is hidden behind it: while
  // the sheet is open, what the toast says is written on the sheet too
  const [sheetMsg, setSheetMsg] = useState("");
  const sheetUp = useRef(false);
  const toast = useCallback((m: string) => {
    rawToast(m);
    if (sheetUp.current) setSheetMsg(m);
  }, [rawToast]);

  const width = usePageWidth();
  const viewer = role;
  // which thing is held (null = the default: the thing in the fridge that most needs using up); whether the two sheets are open
  const [pick, setPick] = useState<Pick | null>(null);
  const [buyOpen, setBuyOpen] = useState(false);
  const [writeOpen, setWriteOpen] = useState(false);
  const auth = useMemo(() => artAuth(), []);
  const [fridge, setFridge] = useState<FridgeState | null>(null);
  const [fridgeFailed, setFridgeFailed] = useState(false);
  const [recent, setRecent] = useState<KitchenSessionWire[]>([]);
  const [nowMs, setNowMs] = useState(() => kitchenNow());
  const fridgeSeq = useRef(0); // an answer overtaken by a later reload is dropped (the later one decides)
  const [todayMeals, setTodayMeals] = useState<Meal[]>([]);
  const [dishes, setDishes] = useState<Dish[]>([]);
  const [menuState, setMenuState] = useState<"loading" | "ok" | "failed">("loading");
  const [dishDraft, setDishDraft] = useState("");
  const [dishNoteDraft, setDishNoteDraft] = useState("");
  // Potions: which menu rows are potions and how much each restores; null = not read yet (no potion can be hung then)
  const [potionBook, setPotionBook] = useState<PotionBook | null>(null);
  const [potionDraft, setPotionDraft] = useState("");
  const [potionMemoDraft, setPotionMemoDraft] = useState("");
  const addDishRef = useRef(false); // in-flight lock for putting a dish up (against a double tap)
  const tmpSeq = useRef(0); // counter for the temporary keys of dishes put up optimistically
  const writeRound = useRef(0); // the round of the "put up / change" sheet: +1 on every open / close; an answer from an older round must not touch the newer sheet
  const actRef = useRef(false); // one in-flight lock shared by change / feed / remove (they exclude each other on this page)
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editNote, setEditNote] = useState("");

  // The role guard: every asynchronous action takes a "ticket" (role + life-cycle number) when it
  // starts and checks it when it comes back. If the role was switched or the page was left, the
  // result is dropped: nothing is refreshed and nothing is written into the lists of the role now
  // shown. The number goes up when the role changes or the page unmounts (in the cleanup), so this
  // effect must come before the ones below that load by role.
  const life = useRef({ epoch: 0, role });
  useEffect(() => {
    life.current.role = role;
    return () => {
      life.current.epoch += 1;
    };
  }, [role]);
  const ticket = useCallback((): Ticket => ({ epoch: life.current.epoch, role: life.current.role }), []);
  const valid = useCallback((t: Ticket) => t.epoch === life.current.epoch && t.role === life.current.role, []);

  // The fridge (with satiety / dizzy / coupons / the log) and the recently served pots (how a dish on
  // the table turned out): two requests, each with its own fallback. Read for the role at the moment
  // of the call; an answer has to pass three checks: the latest request, a ticket that still holds,
  // and an answer that names the role that was asked for.
  const reloadFridge = useCallback(() => {
    const t = ticket();
    const v = t.role;
    const my = ++fridgeSeq.current;
    setFridgeFailed(false);
    fetchFridge(v)
      .then((st) => {
        if (my !== fridgeSeq.current || !valid(t) || st.viewer !== v) return;
        setFridge(st);
        setNowMs(kitchenNow());
      })
      .catch(() => {
        if (my === fridgeSeq.current && valid(t)) setFridgeFailed(true);
      });
    fetchRecentPots(v)
      .then((pots) => {
        if (my === fridgeSeq.current && valid(t)) setRecent(pots);
      })
      .catch(() => {});
  }, [ticket, valid]);

  useEffect(() => {
    setFridge(null);
    setRecent([]);
    setPick(null);
    setBuyOpen(false); // what was ticked was for the previous role
    setWriteOpen(false);
    reloadFridge();
  }, [role, reloadFridge]);

  /** An answer for a role that was switched away from: only say whose it was, do not touch what is on the page */
  const staleToast = (t: Ticket, text: string) => {
    if (text) toast(`${t.role}那边 · ${text}`);
  };

  // Handing out a coupon / buying groceries: the in-flight lock is kept in the request layer by "action:role"
  const couponAct = async () => {
    const t = ticket();
    const v = t.role;
    try {
      const r = await withInflight(inflightKey("coupon", v), () => sendCoupon(v));
      if (r === null) return;
      if (!valid(t)) return staleToast(t, r.text);
      if (r.text) toast(r.text);
      reloadFridge();
    } catch (e) {
      const msg = fridgeErrText(e, "没发成 · 网络?");
      if (!valid(t)) return staleToast(t, msg);
      toast(msg);
      if (e instanceof FridgeHttpError && e.status === 409) reloadFridge();
    }
  };

  const buyAct = async (items: string[]): Promise<BuyResult> => {
    const t = ticket();
    const v = t.role;
    try {
      const r = await withInflight(inflightKey("buy", v), () => buyItems(v, items));
      if (r === null) return { kind: "busy" };
      if (!valid(t)) {
        staleToast(t, r.text);
        return { kind: "stale" };
      }
      toast(r.text || "放进冰箱了");
      reloadFridge();
      return { kind: "done" };
    } catch (e) {
      const msg = fridgeErrText(e, "没买成 · 网络?");
      if (!valid(t)) {
        staleToast(t, msg);
        return { kind: "stale" };
      }
      return { kind: "error", message: msg };
    }
  };

  // "Dizzy for another …" moves once a minute (only while dizzy)
  const dizzyUntil = fridge?.dizzy?.untilMs ?? 0;
  useEffect(() => {
    if (dizzyUntil <= kitchenNow()) return;
    const id = setInterval(() => setNowMs(kitchenNow()), 60_000);
    return () => clearInterval(id);
  }, [dizzyUntil]);

  // The menu, today's meals and the potions, read for the role shown
  const tableSeq = useRef(0);
  const reloadTable = useCallback(() => {
    const t = ticket();
    const my = ++tableSeq.current;
    const live = () => my === tableSeq.current && valid(t);
    setMenuState((s) => (s === "ok" ? s : "loading"));
    fetchMenu(t.role).then(
      (menu) => {
        if (!live()) return;
        setDishes(menu.map((d) => ({ id: d.id, n: d.dish, note: d.note ?? "" })));
        setMenuState("ok");
      },
      () => live() && setMenuState("failed"),
    );
    fetchMeals(t.role).then((meals) => live() && setTodayMeals(meals), () => {});
    fetchPotions(t.role).then((book) => live() && setPotionBook(book), () => live() && setPotionBook(null));
  }, [ticket, valid]);
  const reloadMeals = useCallback(() => {
    const t = ticket();
    fetchMeals(t.role).then((meals) => valid(t) && setTodayMeals(meals), () => {});
  }, [ticket, valid]);

  useEffect(() => {
    setEditingId(null); // half-way through a change when the role was switched: the row belongs to the previous role
    setDishes([]);
    setMenuState("loading");
    setTodayMeals([]);
    setPotionBook(null);
    setPotionDraft("");
    setPotionMemoDraft("");
    reloadTable();
  }, [role, reloadTable]);

  // Read everything again when asked to (time was fast-forwarded, the page came back to the front)
  const firstTick = useRef(tick);
  useEffect(() => {
    if (tick === firstTick.current) return;
    reloadFridge();
    reloadTable();
  }, [tick, reloadFridge, reloadTable]);
  useEffect(() => {
    if (typeof document === "undefined") return;
    const onShow = () => {
      if (document.visibilityState === "visible") reloadAll();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [reloadAll]);

  const sp = fridge?.satiety ?? null;
  const dizzyLeftMs = fridge?.dizzy ? fridge.dizzy.untilMs - nowMs : 0;

  const addDish = () => {
    const v = dishDraft.trim();
    if (!v) return toast("空盘子不上桌");
    if (isPotionName(v)) return toast(potionBook?.enabled ? `「${POTION_NAME}」这个名字留给药剂了 · 用下面的「挂药剂」` : `「${POTION_NAME}」这个名字留给药剂了`);
    if (addDishRef.current) return;
    addDishRef.current = true;
    const noteDraft = dishNoteDraft.trim();
    const noteV = noteDraft || "刚挂的";
    const tmp = `new-${++tmpSeq.current}`;
    const optimistic: Dish = { id: null, n: v, note: noteV, tmp };
    setDishes((d) => [...d, optimistic]);
    setPick({ k: "dish", id: tmp }); // the new dish is the one held (its real id replaces the key when it comes back)
    setDishDraft("");
    setDishNoteDraft("");
    setWriteOpen(false);
    toast("挂上了 · 他下次 eat() 会读到");
    const t = ticket();
    const round = writeRound.current;
    postMenu(v, t.role, noteDraft || undefined)
      .then((row) => {
        if (!valid(t)) return; // the role was switched: this row belongs to the previous role and is not filled into this list
        // the real id is filled in, so the dish can be changed / fed / removed at once
        setDishes((d) => d.map((x) => (x === optimistic ? { ...x, id: row.id, note: row.note ?? "" } : x)));
        setPick((cur) => (cur && cur.k === "dish" && cur.id === tmp ? { k: "dish", id: row.id } : cur));
      })
      .catch(() => {
        if (!valid(t)) return staleToast(t, "挂不上");
        setDishes((d) => d.filter((x) => x !== optimistic));
        if (writeRound.current !== round) return toast(`『${v}』挂不上`); // the sheet was reopened for the next dish: this one's draft is not pushed into the new sheet
        setDishDraft((curr) => curr || v);
        setDishNoteDraft((curr) => curr || noteDraft);
        toast("挂不上 · 退回草稿");
      })
      .finally(() => {
        addDishRef.current = false;
      });
  };

  // ── The stamina potion: put up like a dish, plus the amount of stamina it restores; not a meal ──
  // A row is known as a potion by its reserved name (also when the potion list could not be read, so
  // a potion is never fed as an ordinary dish); the amount is the one registered on the server, and
  // null when that was not read or not registered
  const isPotion = (d: Dish): boolean => isPotionName(d.n);
  const potionPct = (d: Dish): number | null => (isPotion(d) && d.id && potionBook ? potionBook.byRow[d.id] ?? null : null);
  const potionUnknown = () => toast(potionBook ? "这一瓶没登记上回多少 · 撤掉重挂一瓶" : "药剂这会儿动不了 · 厨房没连上");
  const setPotionRow = (rowId: string, pct: number | null, memo = "") =>
    setPotionBook((b) => {
      if (!b) return b;
      const byRow = { ...b.byRow };
      const memoByRow = { ...b.memoByRow };
      if (pct === null) {
        delete byRow[rowId];
        delete memoByRow[rowId];
      } else {
        byRow[rowId] = pct;
        memoByRow[rowId] = memo;
      }
      return { ...b, byRow, memoByRow };
    });

  const addPotion = () => {
    const book = potionBook;
    if (!book) return toast("药剂这会儿挂不了 · 厨房没连上");
    const pct = parsePct(potionDraft, book);
    if (pct === null) return toast("回多少体力填大于 0 的整数");
    if (addDishRef.current) return;
    addDishRef.current = true;
    const t = ticket();
    const round = writeRound.current;
    const memo = cleanMemo(book, potionMemoDraft);
    (async () => {
      let row: { id: string; note: string };
      try {
        row = await hangPotion(t.role, pct, memo); // the menu row and its amount in one step: both or neither
      } catch (e) {
        const msg = `药剂没挂上 · ${fridgeErrText(e, "网络?")}`;
        return valid(t) ? toast(msg) : staleToast(t, msg);
      }
      if (valid(t)) {
        setDishes((d) => [...d, { id: row.id, n: book.name, note: row.note || potionNote(book, pct, memo) }]);
        setPotionRow(row.id, pct, memo);
        setPick({ k: "dish", id: row.id });
        if (writeRound.current === round) {
          // only the round it was submitted in is closed: if the sheet was closed and reopened and the
          // next bottle is being written, what was newly typed is not cleared and the new sheet stays open
          setPotionDraft("");
          setPotionMemoDraft("");
          setWriteOpen(false);
        }
        toast("药剂挂上了");
      } else {
        staleToast(t, "药剂挂上了");
      }
    })().finally(() => {
      addDishRef.current = false;
    });
  };

  const savePotion = async (d: Dish) => {
    const book = potionBook;
    if (!d.id || !book || actRef.current) return;
    const pct = parsePct(editNote, book);
    if (pct === null) return toast("回多少体力填大于 0 的整数");
    actRef.current = true;
    const t = ticket();
    const round = writeRound.current;
    const memo = cleanMemo(book, editName); // while a potion row is being changed, the second field (editName) holds the memo
    const note = potionNote(book, pct, memo);
    try {
      await updatePotion(t.role, d.id, pct, memo);
      const noteOk = await patchMenu(d.id, { note }).then(() => true, () => false);
      if (!valid(t)) return staleToast(t, "改好了");
      setPotionRow(d.id, pct, memo);
      if (noteOk) setDishes((list) => list.map((x) => (x.id === d.id ? { ...x, note } : x)));
      if (writeRound.current === round) setEditingId(null); // only the round it was submitted in: a reopened sheet (even for this same bottle) stays open
      toast(noteOk ? "改好了" : "数值改了 · 菜单上那行的字没改上");
    } catch (e) {
      const why = fridgeErrText(e, "网络?");
      toast(valid(t) ? `没改成 · ${why}` : `${t.role}那边 · 没改成`);
    } finally {
      actRef.current = false;
    }
  };

  const doFeedPotion = async (d: Dish, real: boolean, t: Ticket) => {
    if (!d.id || actRef.current || !valid(t)) return;
    actRef.current = true;
    const id = d.id;
    const gone = () => {
      if (!valid(t)) return;
      setDishes((list) => list.filter((x) => x.id !== id));
      setPotionRow(id, null);
    };
    const strike = () => patchMenu(id, { eaten_at: kitchenNow() / 1000, if_pending: true }).then(() => true, () => false);
    try {
      let msg = "划掉了";
      if (real) {
        msg = (await feedPotion(t.role, id)).text || "喂好了"; // the server adds the stamina, marks the bottle drunk and crosses the row off
      } else {
        if (!(await strike())) throw new Error("row");
        dropPotion(id).catch(() => {}); // only crossed off: this bottle is void
      }
      gone();
      if (valid(t)) toast(msg);
      else staleToast(t, msg);
    } catch (e) {
      if (e instanceof FridgeHttpError && e.code === "gone") {
        // It is confirmed drunk (the role just drank it): the row left on the menu is crossed off as well.
        // "Being drunk right now" (busy) and "not registered" are not handled here: in both the bottle is
        // still there and its row stays (a sip that added no stamina is put back).
        const rowOk = await strike();
        gone();
        const why = fridgeErrText(e, "这一瓶已经喝掉了");
        const done = rowOk ? why : `${why} · 菜单上那行没划掉`;
        toast(valid(t) ? done : `${t.role}那边 · ${done}`);
      } else {
        // the server's own sentence when it gave one (e.g. the stamina could not be added and the bottle is still there)
        const said = e instanceof FridgeHttpError && e.status > 0 ? fridgeErrText(e, "") : "";
        const msg = said || `${real ? "没喂成" : "没划成"} · 网络?`;
        toast(valid(t) ? msg : `${t.role}那边 · ${msg}`);
      }
    } finally {
      actRef.current = false;
    }
  };

  const startEdit = (d: Dish) => {
    if (!d.id) return;
    if (isPotion(d) && potionPct(d) === null) return potionUnknown();
    const pct = potionPct(d);
    writeRound.current += 1;
    setSheetMsg("");
    setEditingId(d.id);
    // a potion: what changes is the amount and the memo (the name is reserved and cannot change; the second field is borrowed for the memo)
    setEditName(pct !== null ? potionBook?.memoByRow[d.id] ?? "" : d.n);
    setEditNote(pct !== null ? String(pct) : d.note);
  };

  const saveEdit = async (d: Dish) => {
    if (isPotion(d)) return savePotion(d);
    const name = editName.trim();
    if (isPotionName(name)) return toast(`「${POTION_NAME}」这个名字留给药剂了`);
    if (!name) return toast("菜名不能空");
    if (!d.id || actRef.current) return;
    actRef.current = true;
    const note = editNote.trim();
    const t = ticket();
    const round = writeRound.current;
    try {
      await patchMenu(d.id, { dish: name, note: note || null });
      if (!valid(t)) return staleToast(t, "改好了");
      setDishes((list) => list.map((x) => (x.id === d.id ? { ...x, n: name, note } : x)));
      if (writeRound.current === round) setEditingId(null); // only the round it was submitted in: a reopened sheet (even for this same dish) stays open
      toast("改好了");
    } catch (e) {
      toast(valid(t) ? fridgeErrText(e, "没改成 · 网络?") : `${t.role}那边 · 没改成`);
    } finally {
      actRef.current = false;
    }
  };

  // Feeding: the ticket is bound when the question is asked. If the role is switched while the
  // question is open, the answer checks the ticket first and does nothing when it no longer holds.
  const switchedAway = (t: Ticket) => toast(`已切到另一个人,${t.role}的这道没动`);

  /** "喂给他": really fed. An ordinary dish counts as a meal and the role is told; a potion restores its stamina at once and is not a meal */
  const feedDish = (d: Dish) => {
    if (!d.id || actRef.current) return; // the lock is checked first: no second question is queued while something is in flight
    const t = ticket();
    const pct = potionPct(d);
    if (isPotion(d) && pct === null) return potionUnknown();
    if (pct !== null) {
      return confirm({
        title: `喂他喝『${d.n}』?`, message: `会回 ${pct}% 体力,他也会知道。`, yes: "喂给他",
        onYes: () => (valid(t) ? void doFeedPotion(d, true, t) : switchedAway(t)),
      });
    }
    confirm({
      title: `喂他『${d.n}』?`, message: "会替他记一餐,他也会知道。", yes: "喂给他",
      onYes: () => (valid(t) ? void doFeed(d, true, t) : switchedAway(t)),
    });
  };
  /** "只划掉": the role already ate it and it was only not crossed off / this bottle is not wanted. No meal is counted and the role is not told */
  const strikeDish = (d: Dish) => {
    if (!d.id || actRef.current) return;
    const t = ticket();
    const potion = isPotion(d);
    if (potion && potionPct(d) === null) return potionUnknown();
    confirm({
      title: `只划掉『${d.n}』?`, message: potion ? "这一瓶就不要了。" : "他吃过了只是没划掉;不记餐,也不告诉他。", yes: "只划掉",
      onYes: () => (valid(t) ? void (potion ? doFeedPotion(d, false, t) : doFeed(d, false, t)) : switchedAway(t)),
    });
  };

  const doFeed = async (d: Dish, real: boolean, t: Ticket) => {
    if (!d.id || actRef.current || !valid(t)) return;
    actRef.current = true;
    const id = d.id;
    const drop = () => valid(t) && setDishes((list) => list.filter((x) => x.id !== id));
    try {
      if (!real) {
        // if_pending guards against doing it twice (the role just crossed it off by eating -> 409: nothing is overwritten)
        await patchMenu(id, { eaten_at: kitchenNow() / 1000, if_pending: true });
        drop();
        return valid(t) ? toast("划掉了") : staleToast(t, "划掉了");
      }
      const r = await feedMenu(id); // crossed off, counted as a meal, and the role is told, in one request
      drop();
      if (valid(t)) {
        // what this page shows follows at once: one more meal today; satiety is the server's, so the fridge is read again
        reloadMeals();
        reloadFridge();
      }
      const done = r.notified ? "喂进去了 · 他下轮会知道" : "喂进去了 · 餐已记";
      if (valid(t)) toast(done);
      else staleToast(t, done);
    } catch (e) {
      if (!valid(t)) {
        staleToast(t, "没划成");
      } else if (e instanceof FridgeHttpError && e.status === 409) {
        // the role got there first and ate it: the row is no longer pending, so it is taken off and no meal is counted
        drop();
        toast("这道他刚自己吃过了");
      } else {
        toast(fridgeErrText(e, "没划成 · 网络?"));
      }
    } finally {
      actRef.current = false;
    }
  };

  const removeDish = (d: Dish) => {
    if (!d.id || actRef.current) return; // the lock is checked first, as for feeding
    const t = ticket(); // as for feeding: the ticket is bound when the question is asked
    const id = d.id;
    confirm({
      title: `撤掉『${d.n}』?`, yes: "撤了",
      onYes: async () => {
        if (actRef.current) return;
        if (!valid(t)) return switchedAway(t);
        actRef.current = true;
        try {
          await deleteMenu(id); // a potion's bottle is voided by the server with its row
          if (!valid(t)) return staleToast(t, "撤了");
          setPotionRow(id, null);
          setDishes((list) => list.filter((x) => x.id !== id));
          toast("撤了");
        } catch (e) {
          toast(valid(t) ? fridgeErrText(e, "没撤成 · 网络?") : `${t.role}那边 · 没撤成`);
        } finally {
          actRef.current = false;
        }
      },
    });
  };

  // How a dish on the table turned out: the menu row's id against a pot's menu_row_id; when nothing
  // matches, only this row's own note is read (never a past pot of the same name). Whether the bowl
  // in the picture is the burnt one follows the same rule.
  const handDishes: HandDish[] = dishes.map((d, i) => ({
    ...d, key: d.id ?? d.tmp ?? `row-${i}`, outcome: dishOutcome(d.id, d.note, recent), potion: isPotion(d), potionPct: potionPct(d),
  }));
  const sceneDishes = handDishes.map((d) => ({ key: d.key, name: d.n, outcome: d.outcome }));
  const low = sp !== null && sp < about.hungryBelow;

  // The things in the picture that can be tapped (which, and where) = the pure functions in pick.ts;
  // the scene draws from them and the leader line takes its position from them
  const items = fridge?.items;
  const staples = fridge?.staples;
  const coupons = fridge?.coupons.count ?? 0;
  const sceneKey = sceneDishes.map((d) => `${d.key}:${d.name}:${d.outcome ?? ""}`).join("|");
  const objs = useMemo(
    () => sceneObjects({ items: items ?? [], staples: staples ?? [], coupons, dishes: sceneDishes, auth }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sceneDishes is rebuilt on every render; its content as a string is the dependency
    [items, staples, coupons, sceneKey, auth],
  );
  // The thing in the hand: the one that was tapped while it still exists; never tapped / gone (the
  // ingredient was used up, the dish was taken off) = the thing in the fridge that most needs using up
  const held: Pick = pick && pickAlive(pick, items ?? [], handDishes.map((d) => d.key)) ? pick : defaultPick(items ?? []);
  const k = width / 1254;
  const onTap = (t: Tap) => {
    if (t.k === "buy") return setBuyOpen(true);
    if (t.k === "write") return openWrite();
    if (t.k === "fridge" || t.k === "table") return setPick(zonePick(t.k, items ?? []));
    setPick(t);
  };
  const openWrite = () => {
    writeRound.current += 1;
    setEditingId(null);
    setSheetMsg("");
    setWriteOpen(true);
  };
  const editing = editingId !== null ? handDishes.find((d) => d.id === editingId) ?? null : null;
  sheetUp.current = writeOpen || editing !== null;

  // Fast-forward (only on a server that switched it on): move the kitchen's clock, then read everything again
  const [skipping, setSkipping] = useState(false);
  const skip = async (seconds: number) => {
    if (skipping) return;
    setSkipping(true);
    try {
      await advanceClock(seconds);
      reloadAll();
    } catch (e) {
      toast(fridgeErrText(e, "没快进成 · 网络?"));
    } finally {
      setSkipping(false);
    }
  };

  return (
    <View style={kit.root}>
      <ScrollView style={kit.flex} contentContainerStyle={[kit.content, { width }]} keyboardShouldPersistTaps="handled">
        <View style={kit.backRow}>
          <View style={kit.backSide}>
            {onBack ? (
              <Pressable onPress={onBack} hitSlop={10} accessibilityRole="button" accessibilityLabel="返回" style={kit.back} testID="back">
                <Text style={kit.backTx}>← 返回</Text>
              </Pressable>
            ) : null}
            {/* fast-forward for demos: only on a server that switched it on. Not part of the design, so it is kept as small as it goes, in the corner. */}
            {about.devClock ? (
              <View style={kit.clock} testID="dev-clock">
                <Pressable onPress={() => skip(3600)} disabled={skipping} hitSlop={6} accessibilityRole="button" testID="skip-hour">
                  <Text style={kit.clockTx}>过一小时</Text>
                </Pressable>
                <Text style={kit.clockTx}>/</Text>
                <Pressable onPress={() => skip(86400)} disabled={skipping} hitSlop={6} accessibilityRole="button" testID="skip-day">
                  <Text style={kit.clockTx}>过一天</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
          {roles.length > 1 ? (
            <View style={kit.roles} testID="roles">
              {roles.map((r) => (
                <Pressable key={r} onPress={() => setRole(r)} hitSlop={8} accessibilityRole="button" accessibilityLabel={`${r}的厨房`} accessibilityState={{ selected: r === role }} testID={`role-${r}`}>
                  <Text style={[kit.backTx, r === role && { color: KC.ink }]}>{r}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </View>
        <View style={kit.top}>
          <Text style={kit.h1} testID="title">{`${role}的厨房`}</Text>
          {about.satiety ? (
            <View style={kit.sat} testID="satiety">
              <Text style={kit.full}>饱食度</Text>
              <Text style={[kit.satNum, { fontFamily: bodoniFor(34) }, bodoniTight(34, 36), low && { color: KC.tomato }]}>{sp === null ? "—" : String(sp)}</Text>
              {sp === null ? null : <Text style={[kit.satPct, { fontFamily: bodoniFor(13) }]}>%</Text>}
            </View>
          ) : null}
        </View>
        {dizzyLeftMs > 0 ? (
          <Text style={kit.dizzy} testID="dizzy-line">{`晕乎乎的 · 还有 ${fmtLeft(dizzyLeftMs)}`}</Text>
        ) : null}
        <View style={kit.bleed}>
          <KitchenScene width={width} objs={objs} pick={held} logCount={fridge?.log.length ?? 0} onTap={onTap} />
          {/* the bottom edge of the picture fades into the colour of the hand, so the two read as one */}
          <LinearGradient colors={["rgba(239,223,200,0)", HAND_TOP]} style={[kit.fade, { top: width - 40 }]} />
          <Hand
            pick={held}
            anchor={anchorOf(objs, held, k)}
            sceneH={width}
            state={fridge}
            failed={fridgeFailed}
            viewer={viewer}
            auth={auth}
            nowMs={nowMs}
            dishes={handDishes}
            menu={menuState}
            meals={todayMeals.map((m) => ({ slot: mealSlot(m.atMs), meal: m.meal }))}
            buyMaxItems={about.buyMaxItems}
            onPick={setPick}
            onReload={reloadFridge}
            onReloadMenu={reloadTable}
            onCoupon={couponAct}
            onOpenBuy={() => setBuyOpen(true)}
            onOpenWrite={openWrite}
            onFeed={feedDish}
            onStrike={strikeDish}
            onEdit={startEdit}
            onRemove={removeDish}
            snack={
              <SnackHand
                snackId={held.k === "snack" ? held.id : ""}
                anchor={anchorOf(objs, held, k)}
                sceneH={width}
                onPick={(id) => setPick({ k: "snack", id })}
              />
            }
          />
        </View>
        {onForgetToken ? (
          <Pressable onPress={onForgetToken} accessibilityRole="button" style={kit.foot} testID="forget-token">
            <Text style={kit.footTx}>换口令 →</Text>
          </Pressable>
        ) : <View style={kit.footGap} />}
      </ScrollView>
      <BuySheet
        open={buyOpen}
        viewer={viewer}
        auth={auth}
        onClose={() => setBuyOpen(false)}
        onBuy={async (picked, isLive) => {
          const r = await buyAct(picked);
          // only the round it was submitted in: after closing and reopening, or unmounting, the new round's sheet is not closed (the success was already said)
          if (r.kind === "done" && isLive()) setBuyOpen(false);
          return r;
        }}
        onOrphanError={toast}
      />
      <WriteSheet
        open={writeOpen || editing !== null}
        onClose={() => {
          writeRound.current += 1;
          setWriteOpen(false);
          setEditingId(null);
          setSheetMsg("");
        }}
        msg={sheetMsg}
        edit={editing ? { potion: editing.potion, name: editing.n } : null}
        editName={editName}
        editNote={editNote}
        setEditName={setEditName}
        setEditNote={setEditNote}
        onSaveEdit={() => (editing ? void saveEdit(editing) : undefined)}
        dishDraft={dishDraft}
        dishNoteDraft={dishNoteDraft}
        setDishDraft={setDishDraft}
        setDishNoteDraft={setDishNoteDraft}
        onAdd={addDish}
        potionName={potionBook?.enabled ? potionBook.name : null}
        potionDraft={potionDraft}
        setPotionDraft={setPotionDraft}
        potionMemoDraft={potionMemoDraft}
        setPotionMemoDraft={setPotionMemoDraft}
        onAddPotion={addPotion}
      />
    </View>
  );
}

// The picture and the hand run the full width of the column (they cancel the page's horizontal padding)
const kit = StyleSheet.create({
  root: { flex: 1, backgroundColor: KC.bg },
  flex: { flex: 1 },
  content: { alignSelf: "center", paddingHorizontal: PAD_H, paddingTop: 8 },
  backRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", minHeight: 26 },
  back: { paddingVertical: 4 },
  backTx: { fontFamily: KF, fontSize: 12, lineHeight: 18, letterSpacing: 1, color: KC.soft },
  roles: { flexDirection: "row", columnGap: 14, flexShrink: 1, flexWrap: "wrap", justifyContent: "flex-end" },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", paddingTop: 8, paddingBottom: 10, paddingHorizontal: 20 - PAD_H },
  sat: { flexDirection: "row", alignItems: "flex-end" },
  satNum: { color: KC.ink, marginLeft: 6, fontVariant: ["tabular-nums"] },
  satPct: { fontSize: 13, lineHeight: 20, color: KC.ink, marginLeft: 1, marginBottom: 3 },
  h1: { fontFamily: KF, fontSize: 22, lineHeight: 30, letterSpacing: 4, color: KC.ink, flexShrink: 1 },
  full: { fontFamily: KF, fontSize: 11, lineHeight: 18, letterSpacing: 1, color: KC.soft, marginBottom: 5 },
  dizzy: { fontFamily: KF, fontSize: 11, letterSpacing: 1, color: KC.bad, marginTop: -6, marginBottom: 8, paddingHorizontal: 20 - PAD_H },
  bleed: { marginHorizontal: -PAD_H },
  fade: { position: "absolute", left: 0, right: 0, height: 40, pointerEvents: "none" },
  foot: { alignSelf: "center", paddingTop: 14, paddingBottom: 24 },
  footGap: { height: 24 },
  footTx: { fontFamily: KF, fontSize: 11, letterSpacing: 1, color: KC.soft },
  backSide: { flexDirection: "row", alignItems: "center", columnGap: 12 },
  clock: { flexDirection: "row", columnGap: 4, opacity: 0.75 },
  clockTx: { fontFamily: KF, fontSize: 9.5, lineHeight: 14, color: KC.soft },
});
