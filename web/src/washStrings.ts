// The words on the washing card. `zh` is the original wording; `en` is provided for English chats.
// Set the element's `lang` attribute to pick one, or assign `strings` to override any entry.
import type { KitchenErrorKind } from "./api";
import { fmtMinutes } from "./cookPhase";

export interface WashCounts {
  clean: number;
  broken: number;
  machine: number;
}

export interface WashCardStrings {
  /** The glyph in the coloured block on the left */
  symbol: string;
  /** The small caps under the glyph */
  symbolLabel: string;
  /** The small line above the title */
  eyebrow: string;
  title: string;
  /** Under the time left, while washing: which plate (0-based) of how many */
  plateOf: (index: number, n: number) => string;
  /** Instead, while the plate that broke is being dropped */
  plateBroke: (index: number, n: number) => string;
  /** The word on the right once it is over */
  done: string;
  stopped: string;
  /** The line under the title once it is over and the backend said how it went */
  result: (c: WashCounts, stopped: boolean) => string;
  /** A duration in words */
  minutes: (sec: number) => string;
  footWashing: (start: string, n: number, duration: string, due: string) => string;
  footDone: (start: string, n: number, end: string) => string;
  footStopped: (start: string, n: number, end: string) => string;
  ariaWashing: (index: number, n: number, remaining: string) => string;
  ariaDone: (word: string, result: string) => string;
  /** The one line shown when the card was asked to fetch a washing and could not (status = HTTP status, if any) */
  loadFailed: (kind: KitchenErrorKind, status: number | null) => string;
}

const zh: WashCardStrings = {
  symbol: "水",
  symbolLabel: "SINK",
  eyebrow: "小厨房",
  title: "刷盘子",
  plateOf: (i, n) => `第 ${Math.min(i + 1, n)} / ${n} 只`,
  plateBroke: (i, n) => `第 ${Math.min(i + 1, n)} / ${n} 只 · 碎了`,
  done: "刷完了",
  stopped: "停下了",
  result: (c, stopped) => {
    const washed = c.clean + c.broken;
    const parts = [`刷了 ${washed} 只`];
    if (c.broken) parts.push(`碎了 ${c.broken} 只`);
    else if (!stopped && washed) parts.push("一只都没碎");
    if (c.machine) parts.push(`${c.machine} 只进了洗碗机`);
    return parts.join(" · ");
  },
  minutes: fmtMinutes,
  footWashing: (start, n, duration, due) => `${start} 开刷 · ${n} 只 · 约 ${duration} · ${due} 刷完`,
  footDone: (start, n, end) => `${start} 开刷 · ${n} 只 · ${end} 刷完`,
  footStopped: (start, n, end) => `${start} 开刷 · ${n} 只 · ${end} 停下`,
  ariaWashing: (i, n, remaining) => `刷盘子,在刷第 ${Math.min(i + 1, n)} 只,共 ${n} 只,还剩 ${remaining}`,
  ariaDone: (word, result) => (result ? `刷盘子,${word},${result}` : `刷盘子,${word}`),
  loadFailed: (kind, status) =>
    `取不到这一趟刷盘子：${
      {
        unreachable: "连不上厨房服务。",
        blocked: "浏览器拦下了这次读取，厨房服务的跨站名单里没有这个页面。",
        unauthorized: "厨房服务拒绝了，口令没带或不对。",
        not_found: "厨房服务里没有这一趟。",
        server: `厨房服务出错了${status ? `（状态码 ${status}）` : ""}。`,
        bad_response: "厨房服务的回答看不懂。",
      }[kind]
    }`,
};

const en: WashCardStrings = {
  symbol: "水",
  symbolLabel: "SINK",
  eyebrow: "KITCHENETTE",
  title: "Washing up",
  plateOf: (i, n) => `plate ${Math.min(i + 1, n)} of ${n}`,
  plateBroke: (i, n) => `plate ${Math.min(i + 1, n)} of ${n} · broke`,
  done: "Done",
  stopped: "Stopped",
  result: (c, stopped) => {
    const washed = c.clean + c.broken;
    const parts = [`washed ${washed}`];
    if (c.broken) parts.push(`${c.broken} broke`);
    else if (!stopped && washed) parts.push("none broke");
    if (c.machine) parts.push(`${c.machine} into the dishwasher`);
    return parts.join(" · ");
  },
  minutes: (sec) => {
    const m = Math.round(sec / 60);
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    const r = m % 60;
    return r === 0 ? `${h} h` : `${h} h ${r} min`;
  },
  footWashing: (start, n, duration, due) => `Started ${start} · ${n} plates · about ${duration} · done ${due}`,
  footDone: (start, n, end) => `Started ${start} · ${n} plates · done ${end}`,
  footStopped: (start, n, end) => `Started ${start} · ${n} plates · stopped ${end}`,
  ariaWashing: (i, n, remaining) => `Washing up, plate ${Math.min(i + 1, n)} of ${n}, ${remaining} left`,
  ariaDone: (word, result) => (result ? `Washing up, ${word}, ${result}` : `Washing up, ${word}`),
  loadFailed: (kind, status) =>
    `Can't load this washing-up: ${
      {
        unreachable: "the kitchen server can't be reached.",
        blocked: "the browser blocked the request. This page is not on the kitchen server's list of allowed sites.",
        unauthorized: "the kitchen server refused it. The token is missing or wrong.",
        not_found: "the kitchen server has no washing-up with this id.",
        server: `the kitchen server answered with an error${status ? ` (status ${status})` : ""}.`,
        bad_response: "the kitchen server's answer was not understood.",
      }[kind]
    }`,
};

export const WASH_STRINGS: Record<string, WashCardStrings> = { zh, en };

/** `lang` may be "en", "en-GB", "zh-CN"...; anything that is not English gets the original wording */
export function washStringsFor(lang: string | null | undefined): WashCardStrings {
  return (lang ?? "").toLowerCase().startsWith("en") ? en : zh;
}
