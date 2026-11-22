// What the settled card shows, as a pure function of what the backend said. The element only draws it.
//
//   the card face once a pot is done        when
//   settled   picture + three lines          the backend sent a settlement (a ruined pot: only its outcome
//                                            line); or an old pot (served before the upgrade), with only the
//                                            outcome it had, when that is still known
//   pending   same layout, no lines          the read that tells which is still out (or failed: tried again
//                                            the next time the card is shown)
//   plain     the card as it always was      the backend has no settled cards (switched off, or older);
//                                            a ruined pot then says 毁了 in words, with no picture
//
// A line is left out when its fact is missing. "Not known" and "none" are different things: a mishap
// that was not recorded is not "no mishaps", and an outcome that is not known is not "ok".
import type { KitchenSettleMissing, KitchenSettlement } from "./api";
import type { CardStrings } from "./strings";

/** The three tiers in order (the backend's fixed ladder), used when an older backend does not name the next one */
export const TIER_LADDER = ["生疏", "拿手", "招牌"];

const OUTCOMES = new Set(["great", "ok", "burnt", "spoiled", "ruined"]);

export type SettleView =
  | { kind: "plain" }
  | { kind: "pending" }
  | { kind: "settled"; facts: SettleFacts };

/** What one settled card knows. Anything null is not shown. */
export interface SettleFacts {
  /** great | ok | burnt | spoiled | ruined; null = not known */
  outcome: string | null;
  proficiency: KitchenSettlement["proficiency"];
  mishap: KitchenSettlement["mishap"];
  stamps: string[];
  /** which dish picture the cook holds up ("" = the plain bowl) */
  icon: string;
}

export interface SettleInput {
  /** The pot is done (served, not cancelled) or was ruined */
  done: boolean;
  ruined: boolean;
  settlement: KitchenSettlement | null | undefined;
  missing: KitchenSettleMissing | null | undefined;
  /** A read with the pot's final state came back (it either carried settled-card facts or it did not) */
  answered: boolean;
  /** The card can read from a backend at all */
  canRead: boolean;
}

/** Reasons that mean "there will be a settled card, it is just not readable yet" */
const NOT_YET = new Set(["not_settled", "error"]);

export function settleView(i: SettleInput): SettleView {
  if (!i.done) return { kind: "plain" };
  const s = i.settlement;
  if (s) {
    return {
      kind: "settled",
      facts: {
        outcome: OUTCOMES.has(s.outcome) ? s.outcome : i.ruined ? "ruined" : null,
        proficiency: s.proficiency, mishap: s.mishap, stamps: s.stamps, icon: s.icon,
      },
    };
  }
  // A ruined pot goes the same way as any other: a backend with settled cards switched off (or without
  // them) gets the card as it always was, which says 毁了 in words; only its outcome is known from the pot
  const m = i.missing;
  if (m?.why === "legacy") {
    const outcome = i.ruined ? "ruined" : m.legacyOutcome;
    return { kind: "settled", facts: { outcome, proficiency: null, mishap: null, stamps: [], icon: "" } };
  }
  if (m && !NOT_YET.has(m.why)) return { kind: "plain" };
  if (m || (!i.answered && i.canRead)) return { kind: "pending" };
  return { kind: "plain" };
}

export interface SettleLine {
  key: "outcome" | "tier" | "mishap";
  label: string;
  text: string;
  /** tier only: how far along this tier, 0..1 (null = no bar) */
  bar?: number | null;
  /** tier only: the small line under it */
  sub?: string | null;
}

/** The lines and stamps of a settled card, in order; a ruined pot has only its outcome line */
export function settleLines(f: SettleFacts, t: CardStrings): { lines: SettleLine[]; stamps: string[] } {
  const lines: SettleLine[] = [];
  if (f.outcome) lines.push({ key: "outcome", label: t.settleLabelOutcome, text: t.settleOutcome(f.outcome) });
  if (f.outcome === "ruined") return { lines, stamps: [] };
  const p = f.proficiency;
  if (p) {
    const next = p.toNext ? p.nextTier ?? TIER_LADDER[TIER_LADDER.indexOf(p.tier) + 1] ?? null : null;
    // An override of the 0.2.0 string writes the whole tier on one line, as it did then
    const legacy = t.settleTier;
    lines.push({
      key: "tier", label: t.settleLabelTier, text: legacy ? legacy(p.tier, p.toNext) : t.settleTierName(p.tier),
      bar: tierBar(p), sub: !legacy && p.toNext && next ? t.settleToNext(p.toNext, t.settleTierName(next)) : null,
    });
  }
  const m = f.mishap;
  // "No mishaps" only when it is known nothing happened, and never on a dish that burnt or spoiled
  if (m?.state === "had" && m.text) lines.push({ key: "mishap", label: t.settleLabelMishap, text: m.text });
  else if (m?.state === "none" && f.outcome !== "burnt" && f.outcome !== "spoiled" && f.outcome !== null) {
    lines.push({ key: "mishap", label: t.settleLabelMishap, text: t.settleSmooth });
  }
  return { lines, stamps: f.stamps };
}

/**
 * The fullest settled card there can be: three lines (the tier with its small line, the mishap on its
 * maximum two lines) and two stamps. A settled card always takes this card's height, so nothing moves when
 * the placeholder fills in, or when an old pot turns out to have only one line: a shorter card leaves room
 * at its bottom instead.
 */
export function fullestLines(t: CardStrings): { lines: SettleLine[]; stamps: string[] } {
  const lines: SettleLine[] = [
    { key: "outcome", label: t.settleLabelOutcome, text: t.settleOutcome("great") },
    { key: "tier", label: t.settleLabelTier, text: t.settleTierName(TIER_LADDER[1]), bar: 0.5, sub: t.settleToNext(9, t.settleTierName(TIER_LADDER[2])) },
    { key: "mishap", label: t.settleLabelMishap, text: "\u3000\n\u3000" },
  ];
  return { lines, stamps: ["\u3000\u3000\u3000\u3000", "\u3000\u3000\u3000\u3000"] };
}

/** How far along its tier a dish is: 0..1; full at the top tier; null when it cannot be told */
export function tierBar(p: NonNullable<KitchenSettlement["proficiency"]>): number | null {
  if (!p.toNext) return 1;
  const from = p.tierFrom ?? (TIER_LADDER.indexOf(p.tier) === 0 ? 0 : null);
  if (from === null) return null;
  const span = p.n + p.toNext - from;
  return span > 0 ? Math.min(1, Math.max(0, (p.n - from) / span)) : null;
}
