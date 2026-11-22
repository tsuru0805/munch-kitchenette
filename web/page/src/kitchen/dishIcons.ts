// The fourteen small pixel dishes the cook holds up on the settled card (assets/clawd/dishes/, drawn by
// tools/draw_dish_icons.py; which dish gets which = src/kitchenette/data/dish_icons.json, worked out by the
// server and sent as `icon`). The dish book shows one where a page has no picture of its own: in colour for
// a dish that was made, as a grey silhouette for one collected and not made yet.
// Clawd artwork: CC BY-NC-SA 4.0, see assets/clawd/ATTRIBUTION.md.
import type { ImageSourcePropType } from "react-native";

export const DISH_ICON_KINDS = [
  "stirfry", "soup", "noodles", "donburi", "friedrice", "friedegg", "fish", "meat", "steamer", "bake", "salad", "dessert", "drink", "bowl",
] as const;
export type DishIconKind = (typeof DISH_ICON_KINDS)[number];

/** Each picture and its size in pixel cells (one cell = one pixel of the file) */
export const DISH_ICON: Record<DishIconKind, { src: ImageSourcePropType; w: number; h: number }> = {
  stirfry: { src: require("../../../../assets/clawd/dishes/stirfry_cells.png"), w: 12, h: 8 },
  soup: { src: require("../../../../assets/clawd/dishes/soup_cells.png"), w: 12, h: 9 },
  noodles: { src: require("../../../../assets/clawd/dishes/noodles_cells.png"), w: 12, h: 12 },
  donburi: { src: require("../../../../assets/clawd/dishes/donburi_cells.png"), w: 12, h: 10 },
  friedrice: { src: require("../../../../assets/clawd/dishes/friedrice_cells.png"), w: 12, h: 8 },
  friedegg: { src: require("../../../../assets/clawd/dishes/friedegg_cells.png"), w: 13, h: 8 },
  fish: { src: require("../../../../assets/clawd/dishes/fish_cells.png"), w: 13, h: 8 },
  meat: { src: require("../../../../assets/clawd/dishes/meat_cells.png"), w: 12, h: 11 },
  steamer: { src: require("../../../../assets/clawd/dishes/steamer_cells.png"), w: 13, h: 9 },
  bake: { src: require("../../../../assets/clawd/dishes/bake_cells.png"), w: 13, h: 8 },
  salad: { src: require("../../../../assets/clawd/dishes/salad_cells.png"), w: 12, h: 8 },
  dessert: { src: require("../../../../assets/clawd/dishes/dessert_cells.png"), w: 10, h: 9 },
  drink: { src: require("../../../../assets/clawd/dishes/drink_cells.png"), w: 10, h: 11 },
  bowl: { src: require("../../../../assets/clawd/dishes/bowl_cells.png"), w: 12, h: 9 },
};

/** The icon for a kind the server named; an unknown or missing one = the plain bowl (the server's own fallback) */
export function dishIcon(kind: string | null | undefined): { src: ImageSourcePropType; w: number; h: number } {
  return (DISH_ICON as Record<string, (typeof DISH_ICON)[DishIconKind]>)[kind ?? ""] ?? DISH_ICON.bowl;
}

/** How many screen pixels per cell so the icon fits a box: a whole number, never smoothed */
export function cellScale(w: number, h: number, box: number): number {
  return Math.max(1, Math.floor(Math.min(box / w, box / h)));
}
