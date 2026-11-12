// Pictures of ingredient kinds: the built-in ones ship with the page (art.generated); a kind the
// human added is drawn by the server (when an art provider is configured) and fetched by
// "kind id + freshness + version", with the token as a header. Both become "one picture to draw".
import type { ImageSourcePropType } from "react-native";
import { FRIDGE_ART, type FridgeArtId } from "./art.generated";
import type { ArtAuth, Freshness, KindArt } from "./fridgeApi";

export interface ArtRef {
  src: ImageSourcePropType;
  w: number;
  h: number;
}

/** A bundled picture goes by its key, a server-drawn one by an ArtRef */
export type AnyArt = FridgeArtId | ArtRef;

export function artRef(a: AnyArt): ArtRef {
  return typeof a === "string" ? FRIDGE_ART[a] : a;
}

/** The picture of an added kind; null when none was ever drawn (the caller shows the first character of its name) */
export function remoteArt(itemId: string, f: Freshness, art: KindArt | null | undefined, auth: ArtAuth | null): ArtRef | null {
  const size = art?.sizes[f];
  if (!art || art.v <= 0 || !size || !auth) return null;
  return {
    src: { uri: `${auth.base}/api/fridge/art/${encodeURIComponent(itemId)}/${f}.png?v=${art.v}`, headers: auth.headers },
    w: size.w,
    h: size.h,
  };
}

/** Which picture for a kind at a freshness: the bundled one when there is one, otherwise the server-drawn one */
export function artOf(itemId: string, f: Freshness, art: KindArt | null | undefined, auth: ArtAuth | null): AnyArt | null {
  const id = `${itemId}_${f}`;
  if (id in FRIDGE_ART) return id as FridgeArtId;
  return remoteArt(itemId, f, art, auth);
}
