// A picture the server only gives out with the token (a dish-book picture, a kind the human added).
// react-native-web's <Image> sends no headers (it sets the address on an <img>), so with a token set
// the server answers 401 and the picture never shows. On the web such a picture is fetched here with
// its headers and turned into an object URL for the <Image>.
//
// Each fetch belongs to one run of the effect: its object URL is shown only while that run is the
// current one, and is released when the run ends (the picture changes, goes away, or comes back later:
// coming back fetches again, so a released URL is never handed out). A source without headers, and
// other platforms, are used as they are.
import { useEffect, useRef, useState } from "react";
import { Platform, type ImageSourcePropType } from "react-native";

type Headed = { uri: string; headers: Record<string, string> };

const headed = (src: ImageSourcePropType | null | undefined): Headed | null => {
  if (!src || typeof src !== "object" || Array.isArray(src)) return null;
  const s = src as { uri?: unknown; headers?: unknown };
  return typeof s.uri === "string" && s.headers && typeof s.headers === "object" && Object.keys(s.headers).length
    ? { uri: s.uri, headers: s.headers as Record<string, string> }
    : null;
};

let fetchHere = Platform.OS === "web";
/** For tests: fetch headed pictures as on the web */
export function _fetchHeadedPictures(on: boolean): void {
  fetchHere = on;
}

export type Loaded = { state: "ready"; src: ImageSourcePropType } | { state: "loading" } | { state: "failed" };

/** What to hand to <Image>: the source itself, or (a headed one on the web) an object URL once fetched */
export function useAuthedSource(src: ImageSourcePropType | null | undefined): Loaded {
  const h = fetchHere ? headed(src) : null;
  const key = h ? `${h.uri}\n${JSON.stringify(h.headers)}` : "";
  // the run of the effect now in charge (every change of source starts a new one, even to "none")
  const current = useRef(0);
  const [got, setGot] = useState<{ run: number; key: string; url: string | null } | null>(null);
  useEffect(() => {
    const run = ++current.current;
    if (!h) return;
    let made: string | null = null;
    let over = false;
    fetch(h.uri, { headers: h.headers })
      .then((r) => (r.ok ? r.blob() : null))
      .then((b) => {
        if (!b) throw new Error("no picture");
        if (over) return;
        made = URL.createObjectURL(b);
        setGot({ run, key, url: made });
      })
      .catch(() => {
        if (!over) setGot({ run, key, url: null });
      });
    return () => {
      over = true;
      if (made) URL.revokeObjectURL(made);
      setGot((g) => (g && g.run === run ? null : g));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` is the source's content
  }, [key]);
  if (!src) return { state: "failed" };
  if (!h) return { state: "ready", src };
  // an answer counts only for the source it was asked for and the run that asked for it, while that run is
  // the current one (on the render where the source changes, the old run is still "current" until the effect)
  if (!got || got.key !== key || got.run !== current.current) return { state: "loading" };
  return got.url ? { state: "ready", src: { uri: got.url } } : { state: "failed" };
}
