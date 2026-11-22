// What every card on a page shares: where the sprite pack and the fonts are, the font registration, the
// image cache (bytes fetched once per URL), the one-request check that a sprite pack is there, and small
// DOM helpers. Module-level, so a cooking card and a washing card on the same page share one cache.
import { SERIF_RARE_RANGE } from "./serifRange.generated";

// Where this script lives; the default asset and font folders are found relative to it
// (web/dist/kitchenette-cooking-card.js -> assets/clawd/ and web/fonts/).
const SCRIPT_URL: string = import.meta.url;
export const DEFAULT_ASSETS = new URL("../../assets/clawd/", SCRIPT_URL).href;
export const DEFAULT_FONTS = new URL("../fonts/", SCRIPT_URL).href;

// The numerals: two small files, loaded as soon as a card appears.
const DISPLAY_FONTS: [family: string, file: string][] = [
  ["Kitchenette Bodoni 11", "BodoniModa11pt-Regular.woff2"],
  ["Kitchenette Bodoni 28", "BodoniModa28pt-Regular.woff2"],
];
// The text face, "Kitchenette Serif". A font already on the device comes first: the system Songti, or an
// installed copy of the bundled typeface (Noto Serif SC, also published as Source Han Serif). Only when
// none of them exists does the browser download the bundled file, and then only the part a character on
// the card needs: `common` for most text, `rare` for the Han characters listed in SERIF_RARE_RANGE.
const SERIF_FAMILY = "Kitchenette Serif";
const SERIF_FONTS: { weight: string; file: string; local: string[] }[] = [
  {
    weight: "400",
    file: "NotoSerifSC-Regular",
    local: ["Songti SC Regular", "STSongti-SC-Regular", "NotoSerifSC-Regular", "NotoSerifCJKsc-Regular", "SourceHanSerifSC-Regular"],
  },
  {
    weight: "700",
    file: "NotoSerifSC-Bold",
    local: ["Songti SC Bold", "STSongti-SC-Bold", "NotoSerifSC-Bold", "NotoSerifCJKsc-Bold", "SourceHanSerifSC-Bold"],
  },
];
const fontsLoaded = new Set<string>();

/** Registers the font files with the document (once per folder). A missing file only means the next font in the list shows. */
export function ensureFonts(base: string): void {
  if (fontsLoaded.has(base) || typeof FontFace === "undefined") return;
  fontsLoaded.add(base);
  for (const [family, file] of DISPLAY_FONTS) {
    const face = new FontFace(family, `url("${base}${file}") format("woff2")`, { display: "swap" });
    document.fonts.add(face);
    face.load().catch(() => {});
  }
  // Not loaded here: the browser fetches a serif part by itself when text on a card needs it
  for (const { weight, file, local } of SERIF_FONTS) {
    const locals = local.map((name) => `local("${name}")`).join(", ");
    const src = (part: string): string => `${locals}, url("${base}${file}.${part}.woff2") format("woff2")`;
    document.fonts.add(new FontFace(SERIF_FAMILY, src("common"), { weight, display: "swap" }));
    // Added second so that it is the one asked first for the characters it lists
    document.fonts.add(new FontFace(SERIF_FAMILY, src("rare"), { weight, display: "swap", unicodeRange: SERIF_RARE_RANGE }));
  }
}

// Image bytes, fetched once per URL. Each layer then gets its own object URL: a fresh URL is a fresh
// image to the browser, so an animated clip always starts from its first frame when it comes on.
export const blobs = new Map<string, Blob>();
const loading = new Map<string, Promise<void>>();
/** Files that turned out not to exist: they are not asked for again, and their segment shows an empty stage */
export const broken = new Set<string>();

export function preload(url: string): Promise<void> {
  let p = loading.get(url);
  if (!p) {
    p = fetch(url)
      .then((r) => {
        if (!r.ok) {
          broken.add(url);
          return;
        }
        return r.blob().then((b) => {
          blobs.set(url, b);
        });
      })
      .catch(() => {
        // Not fetchable (file://, a cross-origin host without CORS): the <img> loads the URL directly instead
      });
    loading.set(url, p);
  }
  return p;
}

// Is the sprite pack there at all? Asked once per folder, with one file, before anything else is requested.
// A folder that is not there gets exactly that one request: the card then shows no cook and only counts down.
interface Pack {
  state: "checking" | "ok" | "missing";
  ready: Promise<void>;
}
const packs = new Map<string, Pack>();

function imageLoads(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = url;
  });
}

export function checkPack(folder: string, probeUrl: string): Pack {
  let pack = packs.get(folder);
  if (!pack) {
    const entry: Pack = { state: "checking", ready: Promise.resolve() };
    entry.ready = fetch(probeUrl)
      .then(async (r) => {
        if (r.ok) blobs.set(probeUrl, await r.blob());
        entry.state = r.ok ? "ok" : "missing";
      })
      // fetch itself is not possible here (file://, no CORS): see whether an <img> can load the file
      .catch(() => imageLoads(probeUrl).then((ok) => void (entry.state = ok ? "ok" : "missing")));
    loading.set(probeUrl, entry.ready);
    packs.set(folder, entry);
    pack = entry;
  }
  return pack;
}

export interface Layer {
  url: string;
  img: HTMLImageElement;
  objectUrl: string | null;
}

export const h = <K extends keyof HTMLElementTagNameMap>(tag: K, cls: string, parent?: Node): HTMLElementTagNameMap[K] => {
  const el = document.createElement(tag);
  el.className = cls;
  parent?.appendChild(el);
  return el;
};

export function dropLayer(l: Layer): void {
  l.img.remove();
  if (l.objectUrl) URL.revokeObjectURL(l.objectUrl);
}

export function setText(el: HTMLElement, text: string): void {
  if (el.textContent !== text) el.textContent = text;
}

export function withSlash(url: string): string {
  return url.endsWith("/") ? url : `${url}/`;
}

// Importable outside a browser too (a server render, a test runner): there the class is never instantiated
export const Base: typeof HTMLElement = typeof HTMLElement === "undefined" ? (class {} as unknown as typeof HTMLElement) : HTMLElement;
