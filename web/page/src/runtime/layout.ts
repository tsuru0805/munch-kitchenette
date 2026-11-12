import { useWindowDimensions } from "react-native";
import { PAGE_MAX_W } from "../kitchen/kitchenTheme";

/** The width of the column the page is laid out in (the window's, up to PAGE_MAX_W) */
export function usePageWidth(): number {
  return Math.min(useWindowDimensions().width, PAGE_MAX_W);
}
