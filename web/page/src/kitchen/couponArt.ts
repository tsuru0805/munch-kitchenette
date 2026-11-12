// Two small things on the fridge door: the grocery coupon and the "buy him groceries" memo.
// The pictures carry no lettering; the page prints the words on the coupon. To swap in another
// picture, change this file only (which picture, where the words sit on it, their colour).
import type { FridgeArtId } from "./art.generated";

export const COUPON_ART: FridgeArtId = "coupon";
/** Centre of the three characters 「买菜券」 on the picture (as fractions of its width / height) and their colour: the blank area is the right two thirds */
export const COUPON_TEXT = { cx: 0.655, cy: 0.63, color: "#c8432f" } as const;
export const BUY_ART: FridgeArtId = "buy";
