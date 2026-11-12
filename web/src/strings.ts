// The words on the card. `zh` is the original wording; `en` is provided for English chats.
// Set the element's `lang` attribute to pick one, or assign `strings` to override any entry.
import type { KitchenErrorKind } from "./api";
import { fmtMinutes, outcomeWord, type KitchenOutcome } from "./cookPhase";

export interface CardStrings {
  /** The glyph in the coloured block on the left */
  symbol: string;
  /** The small caps under the glyph */
  symbolLabel: string;
  /** The small line above the dish name */
  eyebrow: string;
  cancelled: string;
  /** "served", with the outcome word when there is one */
  served: (outcome: KitchenOutcome | null) => string;
  /** A duration in words */
  minutes: (durationSec: number) => string;
  footCooking: (start: string, duration: string, due: string) => string;
  footServed: (start: string, duration: string, due: string) => string;
  footCancelled: (start: string) => string;
  ariaCooking: (dish: string, remaining: string) => string;
  ariaServed: (dish: string, served: string) => string;
  ariaCancelled: (dish: string) => string;
  /** The one line shown when the card was asked to fetch a pot and could not (status = HTTP status, if any) */
  loadFailed: (kind: KitchenErrorKind, status: number | null) => string;
}

const zh: CardStrings = {
  symbol: "火",
  symbolLabel: "KITCHEN",
  eyebrow: "小厨房",
  cancelled: "关火了",
  served: (o) => {
    const w = outcomeWord(o);
    return w ? `出锅了 · ${w}` : "出锅了";
  },
  minutes: fmtMinutes,
  footCooking: (start, duration, due) => `${start} 下锅 · 做 ${duration} · ${due} 出锅`,
  footServed: (start, duration, due) => `${start} 下锅 · 做了 ${duration} · ${due} 出锅`,
  footCancelled: (start) => `${start} 下锅 · 没做完`,
  ariaCooking: (dish, remaining) => `${dish},在火上,还剩 ${remaining}`,
  ariaServed: (dish, served) => `${dish},${served}`,
  ariaCancelled: (dish) => `${dish},关火了`,
  loadFailed: (kind, status) =>
    `取不到这一锅：${
      {
        unreachable: "连不上厨房服务。",
        blocked: "浏览器拦下了这次读取，厨房服务的跨站名单里没有这个页面。",
        unauthorized: "厨房服务拒绝了，口令没带或不对。",
        not_found: "厨房服务里没有这一锅。",
        server: `厨房服务出错了${status ? `（状态码 ${status}）` : ""}。`,
        bad_response: "厨房服务的回答看不懂。",
      }[kind]
    }`,
};

const EN_OUTCOME: Record<KitchenOutcome, string | null> = { great: "great", ok: null, burnt: "burnt", spoiled: "spoiled" };

const en: CardStrings = {
  symbol: "火",
  symbolLabel: "KITCHEN",
  eyebrow: "KITCHENETTE",
  cancelled: "Heat off",
  served: (o) => {
    const w = o ? EN_OUTCOME[o] : null;
    return w ? `Served · ${w}` : "Served";
  },
  minutes: (sec) => {
    const m = Math.round(sec / 60);
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    const r = m % 60;
    return r === 0 ? `${h} h` : `${h} h ${r} min`;
  },
  footCooking: (start, duration, due) => `On at ${start} · ${duration} · ready ${due}`,
  footServed: (start, duration, due) => `On at ${start} · cooked ${duration} · served ${due}`,
  footCancelled: (start) => `On at ${start} · not finished`,
  ariaCooking: (dish, remaining) => `${dish}, on the stove, ${remaining} left`,
  ariaServed: (dish, served) => `${dish}, ${served}`,
  ariaCancelled: (dish) => `${dish}, heat off`,
  loadFailed: (kind, status) =>
    `Can't load this pot: ${
      {
        unreachable: "the kitchen server can't be reached.",
        blocked: "the browser blocked the request. This page is not on the kitchen server's list of allowed sites.",
        unauthorized: "the kitchen server refused it. The token is missing or wrong.",
        not_found: "the kitchen server has no pot with this id.",
        server: `the kitchen server answered with an error${status ? ` (status ${status})` : ""}.`,
        bad_response: "the kitchen server's answer was not understood.",
      }[kind]
    }`,
};

export const STRINGS: Record<string, CardStrings> = { zh, en };

/** `lang` may be "en", "en-GB", "zh-CN"...; anything that is not English gets the original wording */
export function stringsFor(lang: string | null | undefined): CardStrings {
  return (lang ?? "").toLowerCase().startsWith("en") ? en : zh;
}
