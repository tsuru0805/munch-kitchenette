// The settled card: which face a done pot shows, and which lines are on it.
import type { KitchenSettlement } from "./api";
import { fullestLines, settleLines, settleView, tierBar, type SettleFacts, type SettleInput } from "./settleCard";
import { STRINGS } from "./strings";

const zh = STRINGS.zh;
const en = STRINGS.en;

const full: KitchenSettlement = {
  outcome: "great", link: "follow", icon: "stirfry", stamps: ["照谱做成"],
  proficiency: { tier: "拿手", n: 5, toNext: 3, nextTier: "招牌", tierFrom: 3 },
  mishap: { state: "none", text: "一路顺利" },
};
const base: SettleInput = { done: true, ruined: false, settlement: undefined, missing: undefined, answered: false, canRead: true };
const facts = (over: Partial<SettleFacts>): SettleFacts => ({
  outcome: "great", proficiency: null, mishap: null, stamps: [], icon: "", ...over,
});
const keys = (f: SettleFacts) => settleLines(f, zh).lines.map((l) => l.key);

describe("which face a done pot shows", () => {
  it("a pot that is not done yet is the card as it always was", () => {
    expect(settleView({ ...base, done: false, settlement: full }).kind).toBe("plain");
  });

  it("a settlement makes the settled card", () => {
    const v = settleView({ ...base, settlement: full, answered: true });
    expect(v.kind === "settled" && v.facts.outcome).toBe("great");
  });

  it("waits in a placeholder of the same layout until the read is back, and keeps it when the read failed", () => {
    expect(settleView(base).kind).toBe("pending");
    expect(settleView({ ...base, missing: { why: "not_settled", legacyOutcome: null }, answered: true }).kind).toBe("pending");
    expect(settleView({ ...base, missing: { why: "error", legacyOutcome: null }, answered: true }).kind).toBe("pending");
  });

  it("a backend without settled cards (switched off, or older) keeps the card as it was", () => {
    expect(settleView({ ...base, answered: true }).kind).toBe("plain");
    expect(settleView({ ...base, missing: { why: "feature_off", legacyOutcome: null }, answered: true }).kind).toBe("plain");
    expect(settleView({ ...base, canRead: false }).kind).toBe("plain");
  });

  it("an old pot shows only the outcome it had, and nothing when that is not known any more", () => {
    const had = settleView({ ...base, missing: { why: "legacy", legacyOutcome: "burnt" }, answered: true });
    expect(had.kind).toBe("settled");
    if (had.kind === "settled") expect(settleLines(had.facts, zh).lines.map((l) => [l.key, l.text])).toEqual([["outcome", "糊了"]]);
    const lost = settleView({ ...base, missing: { why: "legacy", legacyOutcome: null }, answered: true });
    expect(lost.kind === "settled" && settleLines(lost.facts, zh).lines).toEqual([]);
  });

  it("a ruined pot: the settled card with only its outcome line, when the backend has settled cards", () => {
    const sent = settleView({ ...base, ruined: true, settlement: { ...full, outcome: "ruined" }, answered: true });
    expect(sent.kind).toBe("settled");
    if (sent.kind === "settled") {
      const { lines, stamps } = settleLines(sent.facts, zh);
      expect(lines.map((l) => [l.key, l.text])).toEqual([["outcome", "毁了"]]);
      expect(stamps).toEqual([]);
    }
    // an old ruined pot is known to be ruined from the pot itself
    const old = settleView({ ...base, ruined: true, missing: { why: "legacy", legacyOutcome: null }, answered: true });
    expect(old.kind === "settled" && keys(old.facts)).toEqual(["outcome"]);
  });

  it("a ruined pot with settled cards switched off is the card as it always was (no picture)", () => {
    expect(settleView({ ...base, ruined: true, missing: { why: "feature_off", legacyOutcome: null }, answered: true }).kind).toBe("plain");
    // a backend that sends nothing about settled cards (off, or older), and a card that cannot read at all
    expect(settleView({ ...base, ruined: true, answered: true }).kind).toBe("plain");
    expect(settleView({ ...base, ruined: true, canRead: false }).kind).toBe("plain");
    // until the read is back it waits like any other pot
    expect(settleView({ ...base, ruined: true }).kind).toBe("pending");
  });
});

describe("the lines", () => {
  it("all three, each with its small title, the tier naming the next one", () => {
    const { lines, stamps } = settleLines(facts({ proficiency: full.proficiency, mishap: full.mishap, stamps: ["照谱做成"] }), zh);
    expect(lines.map((l) => [l.label, l.text])).toEqual([["成色", "很好"], ["熟练", "拿手"], ["意外", "一路顺利"]]);
    expect(lines[1].sub).toBe("再做 3 次升招牌");
    expect(lines[1].bar).toBeCloseTo(0.4);
    expect(stamps).toEqual(["照谱做成"]);
  });

  it("an older backend that does not name the next tier: it is the next on the ladder", () => {
    const { lines } = settleLines(facts({ proficiency: { tier: "生疏", n: 1, toNext: 2 } }), zh);
    expect(lines[1].sub).toBe("再做 2 次升拿手");
    expect(lines[1].bar).toBeCloseTo(1 / 3);
  });

  it("the top tier has no next one: a full bar and no small line", () => {
    const { lines } = settleLines(facts({ proficiency: { tier: "招牌", n: 9, toNext: null, nextTier: null, tierFrom: 8 } }), zh);
    expect(lines[1].sub).toBeNull();
    expect(lines[1].bar).toBe(1);
  });

  it("a line whose fact is missing is left out", () => {
    expect(keys(facts({}))).toEqual(["outcome"]);
    expect(keys(facts({ outcome: null, proficiency: full.proficiency }))).toEqual(["tier"]);
    expect(keys(facts({ mishap: { state: "had", text: "汤溢出来了一点。" } }))).toEqual(["outcome", "mishap"]);
  });

  it("not known is not none: no 'no mishaps' for an unknown mishap, an unknown outcome, or a burnt or spoiled dish", () => {
    expect(keys(facts({ mishap: { state: "unknown", text: null } }))).toEqual(["outcome"]);
    expect(keys(facts({ mishap: { state: "had", text: null } }))).toEqual(["outcome"]);
    expect(keys(facts({ outcome: null, mishap: { state: "none", text: "一路顺利" } }))).toEqual([]);
    for (const outcome of ["burnt", "spoiled"]) {
      expect(keys(facts({ outcome, mishap: { state: "none", text: "一路顺利" } }))).toEqual(["outcome"]);
    }
    // a mishap that happened is shown whatever the outcome
    expect(settleLines(facts({ outcome: "burnt", mishap: { state: "had", text: "炒的时候油溅到手背上，烫了一下。" } }), zh).lines[1].text)
      .toBe("炒的时候油溅到手背上，烫了一下。");
  });

  it("an unknown outcome is never written as 'ok'", () => {
    expect(settleLines(facts({ outcome: null }), zh).lines).toEqual([]);
    expect(settleLines(facts({ outcome: "ok" }), zh).lines[0].text).toBe("普通");
  });

  it("in English, tiers and the next one are named in English", () => {
    const { lines } = settleLines(facts({ proficiency: full.proficiency, mishap: full.mishap }), en);
    expect(lines.map((l) => [l.label, l.text])).toEqual([["Result", "great"], ["Skill", "practised"], ["Mishap", "no mishaps"]]);
    expect(lines[1].sub).toBe("3 more to signature");
  });
});

it("the bar runs from where the tier started; null when that cannot be told", () => {
  expect(tierBar({ tier: "拿手", n: 3, toNext: 5, tierFrom: 3 })).toBe(0);
  expect(tierBar({ tier: "拿手", n: 3, toNext: 5 })).toBeNull();
  expect(tierBar({ tier: "生疏", n: 0, toNext: 3 })).toBe(0);
});

describe("the height a settled card keeps", () => {
  it("is the fullest card: three lines, the tier with its small line, the mishap on two lines, two stamps", () => {
    const { lines, stamps } = fullestLines(zh);
    expect(lines.map((l) => l.key)).toEqual(["outcome", "tier", "mishap"]);
    expect(lines[1].sub).toBeTruthy();
    expect(lines[1].bar).not.toBeNull();
    expect(lines[2].text.split("\n")).toHaveLength(2);
    expect(stamps).toHaveLength(2);
  });

  it("no real card has more than that, so the placeholder never grows when its lines arrive", () => {
    const most = settleLines(facts({
      outcome: "great", proficiency: full.proficiency, mishap: { state: "had", text: "一句" },
      stamps: ["第一次做", "照谱做成"],
    }), zh);
    const full_ = fullestLines(zh);
    expect(most.lines.map((l) => l.key)).toEqual(full_.lines.map((l) => l.key));
    expect(most.stamps.length).toBeLessThanOrEqual(full_.stamps.length);
    // the backend gives at most two stamps: "first" and one of follow / changed
  });
});

describe("the 0.2.0 tier string", () => {
  it("is not set by default", () => {
    expect(zh.settleTier).toBeUndefined();
    expect(en.settleTier).toBeUndefined();
  });

  it("an override of it still writes the tier line, on one line as before", () => {
    const t = { ...zh, settleTier: (tier: string, toNext: number | null) => `${tier}(还差 ${toNext})` };
    const { lines } = settleLines(facts({ proficiency: full.proficiency }), t);
    expect(lines[1].text).toBe("拿手(还差 3)");
    expect(lines[1].sub).toBeNull();
    expect(lines[1].bar).toBeCloseTo(0.4);
  });
});
