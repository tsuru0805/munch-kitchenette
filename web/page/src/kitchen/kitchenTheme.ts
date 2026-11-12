// Colours and typefaces of the kitchen page (one source for all of it).
// The families are declared in public/fonts.css: an installed Noto Serif SC / Source Han Serif SC is
// used first, the bundled files otherwise. No fontWeight is written next to them: the weight is in
// the family name.
export const KC = {
  bg: "#fbf6ef",
  ink: "#4a3a2f",
  soft: "#9a887a",
  line: "#eadfd2",
  card: "#ffffff",
  tomato: "#e0563f",
  fresh: "#5f9c5a",
  meh: "#d0952f",
  bad: "#9b5a43",
  tix: "#fdf1e6",
  tixOff: "#d8c6b6",
  thumb: "#f4efe8",
  tag: "rgba(255,255,255,0.85)",
  shadow: "rgba(74,58,47,0.18)",
} as const;

/** Noto Serif SC 400 */
export const KF = '"Kitchenette Serif", "Songti SC", serif';
/** Noto Serif SC 300 (the body of a note) */
export const KL = '"Kitchenette Serif Light", "Kitchenette Serif", "Songti SC", serif';

const BODONI_FALLBACK = '"Bodoni Moda", "Bodoni 72", Didot, serif';
/** Bodoni Moda by optical size: the 11 pt cut under 18 px, the 28 pt cut under 40 px, the 96 pt cut above */
export const bodoniFor = (px: number): string =>
  `"Kitchenette Bodoni ${px < 18 ? 11 : px < 40 ? 28 : 96}", ${BODONI_FALLBACK}`;

/**
 * Bodoni's natural line is 1.525 × its size (the ascender alone takes 1.125 em); a smaller lineHeight
 * clips the top of the figures. To set it tight, use this instead of lineHeight: no line height is
 * set, and a negative top margin pulls the box back to `lineHeight`, so the baseline stays where it
 * would be and nothing is clipped.
 */
export const BODONI_LINE = 1.525;
export const bodoniTight = (fontSize: number, lineHeight: number, marginTop = 0) => ({ fontSize, marginTop: marginTop + lineHeight - BODONI_LINE * fontSize });

export const FRESH_LABEL = { fresh: "新鲜", meh: "不太新鲜", bad: "坏了" } as const;
export const FRESH_COLOR = { fresh: KC.fresh, meh: KC.meh, bad: KC.bad } as const;

/** A soft shadow under a piece of paper */
export const shadow = (opacity: number, radius: number, dy: number) => ({ boxShadow: `0px ${dy}px ${radius}px rgba(74,58,47,${opacity})` });

/** The page is a phone-width column: on a wide window it sits in the middle at this width at most */
export const PAGE_MAX_W = 520;
