// <kitchenette-cooking-card>: one pot on a chat page. A ticket-stub card that counts down in real
// time, with a tiny cook standing on its top edge.
//
// The element decides nothing about timing itself: which phase the pot is in comes from
// cookPhase.ts, which clip plays comes from cookSegments.ts, and both are recomputed on every tick
// from facts (start time, duration, when the element was connected, what the backend said). Taking
// the element out of the document and putting it back, or reloading the page, therefore lands on
// the right moment instead of replaying anything.
import {
  apiProbe, asKitchenError, notFound, probeFromSession, type KitchenFetchError, type KitchenProbe, type KitchenSession, type ProbeFn,
} from "./api";
import {
  EXIT_MS, OUTCOME_WAIT_MS, cookProgress, fmtHM, fmtRemaining, kitchenPhase, phaseIsLive, pickTimeZone, revealAtMs, spriteOnStage,
  type KitchenFacts, type KitchenOutcome, type KitchenPhase,
} from "./cookPhase";
import { assetKey, cookSegment, outfitFor, parseMethod } from "./cookSegments";
import { STAGE_PX, type SpriteManifest } from "./manifest";
import { CLAWD_MANIFEST } from "./manifest.generated";
import { acquireSeat, onSeatFree, releaseSeat, seatFree } from "./seats";
import { isFirstSeen, markSeen } from "./seen";
import { SERIF_RARE_RANGE } from "./serifRange.generated";
import { springFrames } from "./spring";
import { stringsFor, type CardStrings } from "./strings";
import { CARD_CSS } from "./styles";

/** The ticker. 250 ms: phase changes (the 700 ms entrance, the 450 ms exit) have to be caught in time */
const TICK_MS = 250;
/** How often a pot that is still cooking is checked for having been cancelled (only while the page is visible) */
const CANCEL_POLL_MS = 15_000;
/** How often the outcome is asked for once the pot is due (for at most OUTCOME_WAIT_MS) */
const OUTCOME_POLL_MS = 1_500;
const CROSSFADE_MS = 120;
/** Fully below the cut line (8 px extra so no sub-pixel sliver shows) */
const HIDDEN_Y = STAGE_PX + 8;

// Where this script lives; the default asset and font folders are found relative to it
// (web/dist/kitchenette-cooking-card.js -> assets/clawd/ and web/fonts/).
const SCRIPT_URL: string = import.meta.url;
const DEFAULT_ASSETS = new URL("../../assets/clawd/", SCRIPT_URL).href;
const DEFAULT_FONTS = new URL("../fonts/", SCRIPT_URL).href;

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
function ensureFonts(base: string): void {
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
const blobs = new Map<string, Blob>();
const loading = new Map<string, Promise<void>>();
/** Files that turned out not to exist: they are not asked for again, and their segment shows an empty stage */
const broken = new Set<string>();

function preload(url: string): Promise<void> {
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

function checkPack(folder: string, probeUrl: string): Pack {
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

interface Layer {
  url: string;
  img: HTMLImageElement;
  objectUrl: string | null;
}

interface PotState {
  id: string;
  dish: string;
  note: string;
  startedAt: number;
  durationSec: number;
  method: string | null | undefined;
  mountedAtMs: number;
  firstSeen: boolean;
  cancelledSeenAtMs: number | undefined;
  outcome: { v: KitchenOutcome | null; atMs: number } | undefined;
}

const h = <K extends keyof HTMLElementTagNameMap>(tag: K, cls: string, parent?: Node): HTMLElementTagNameMap[K] => {
  const el = document.createElement(tag);
  el.className = cls;
  parent?.appendChild(el);
  return el;
};

// Importable outside a browser too (a server render, a test runner): there the class is never instantiated
const Base: typeof HTMLElement = typeof HTMLElement === "undefined" ? (class {} as unknown as typeof HTMLElement) : HTMLElement;

export class KitchenetteCookingCard extends Base {
  static observedAttributes = ["api-base", "session-id", "assets", "fonts", "lang", "timezone"];

  // ── configuration (properties) ──
  #session: KitchenSession | null = null;
  #probe: ProbeFn | null = null;
  #clock: () => number = Date.now;
  #manifest: SpriteManifest = CLAWD_MANIFEST;
  #strings: Partial<CardStrings> = {};

  // ── state of the current mount ──
  #pot: PotState | null = null;
  #phase: KitchenPhase | null = null;
  #segment: string | null = null;
  #tick: ReturnType<typeof setInterval> | undefined;
  #cancelPoll: ReturnType<typeof setInterval> | undefined;
  #outcomePoll: ReturnType<typeof setInterval> | undefined;
  #pollKey = "";
  #awaiting = false;
  #loadToken = 0;
  /** Set when the card was asked to fetch its pot and could not */
  #failure: KitchenFetchError | null = null;
  /** The time zone the backend said its clock times are in ("" = it did not say) */
  #serverTz = "";
  #packWatched = false;
  #preloaded = false;

  // ── sprite ──
  #layers: Layer[] = [];
  #stillImg: HTMLImageElement | null = null;
  #seat: ReturnType<typeof acquireSeat> | null = null;
  #seatWanted = false;
  #offSeatFree: (() => void) | null = null;
  #slide: Animation | null = null;
  #lastSpritePhase: KitchenPhase | null = null;
  #reduced: MediaQueryList | null = null;

  // ── DOM ──
  #root: ShadowRoot;
  #stage!: HTMLElement;
  #canvas!: HTMLElement;
  #frame!: HTMLElement;
  #card!: HTMLElement;
  #symText!: HTMLElement;
  #symEn!: HTMLElement;
  #eyebrow!: HTMLElement;
  #dish!: HTMLElement;
  #note!: HTMLElement;
  #clockEl!: HTMLElement;
  #stateWord!: HTMLElement;
  #track!: HTMLElement;
  #fill!: HTMLElement;
  #foot!: HTMLElement;
  #wrap!: HTMLElement;

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = CARD_CSS;
    this.#root.appendChild(style);
    const wrap = (this.#wrap = h("div", "wrap", this.#root));
    wrap.hidden = true;
    this.#stage = h("div", "stage", wrap);
    this.#stage.setAttribute("aria-hidden", "true");
    this.#stage.hidden = true;
    this.#canvas = h("div", "canvas", this.#stage);
    this.#frame = h("div", "frame", wrap);
    h("div", "shadow", this.#frame);
    this.#card = h("div", "card", this.#frame);
    this.#card.setAttribute("role", "group");
    const sym = h("div", "sym", this.#card);
    sym.setAttribute("aria-hidden", "true");
    this.#symText = h("span", "sym-text", sym);
    this.#symEn = h("span", "sym-en", sym);
    const body = h("div", "body", this.#card);
    const top = h("div", "top", body);
    const left = h("div", "left", top);
    this.#eyebrow = h("div", "eyebrow", left);
    this.#dish = h("div", "dish", left);
    this.#note = h("div", "note", left);
    const right = h("div", "right", top);
    this.#clockEl = h("div", "clock", right);
    this.#stateWord = h("div", "state-word", right);
    this.#track = h("div", "track", body);
    this.#fill = h("div", "fill", this.#track);
    this.#foot = h("div", "foot", body);
  }

  // ── public API ──

  /** One pot's data. Assign it directly, or leave it unset and give `api-base` + `session-id` instead. */
  get session(): KitchenSession | null {
    return this.#session;
  }
  set session(s: KitchenSession | null) {
    this.#session = s;
    if (!this.isConnected) return;
    if (s && this.#pot && this.#pot.id === s.id) {
      this.#take(probeFromSession(s)); // same pot: only its status / outcome can be news
      this.#render();
    } else this.#mount();
  }

  /**
   * Where the card asks whether the pot was cancelled and how it turned out. Defaults to the backend at
   * `api-base` when that attribute is set; assign your own function to use another transport or local data.
   */
  get probe(): ProbeFn | null {
    return this.#probe;
  }
  set probe(fn: ProbeFn | null) {
    this.#probe = fn;
    this.#pollKey = "";
    if (this.isConnected && this.#pot) this.#render();
  }

  /** The clock the card counts against, in epoch milliseconds. Defaults to Date.now. */
  get clock(): () => number {
    return this.#clock;
  }
  set clock(fn: () => number) {
    this.#clock = fn;
    if (this.isConnected) this.#mount();
  }

  /** The sprite registry. Defaults to the built-in Clawd pack; assign your own to use another character. */
  get manifest(): SpriteManifest {
    return this.#manifest;
  }
  set manifest(m: SpriteManifest) {
    this.#manifest = m;
    if (this.isConnected) this.#mount();
  }

  /** Overrides for any of the words on the card (see strings.ts) */
  get strings(): Partial<CardStrings> {
    return this.#strings;
  }
  set strings(s: Partial<CardStrings>) {
    this.#strings = s ?? {};
    if (!this.isConnected) return;
    if (this.#pot) this.#render();
    else this.#renderFailure();
  }

  /** The phase the pot is in right now (null before any data) */
  get phase(): KitchenPhase | null {
    return this.#phase;
  }

  /** The sprite segment on stage right now (null when the cook is off stage) */
  get segment(): string | null {
    return this.#segment;
  }

  /** The outfit this pot wears */
  get outfit(): string | null {
    return this.#pot ? outfitFor(this.#pot.id, this.#manifest.outfits) : null;
  }

  // ── lifecycle ──

  connectedCallback(): void {
    this.#reduced = typeof matchMedia === "function" ? matchMedia("(prefers-reduced-motion: reduce)") : null;
    this.#reduced?.addEventListener("change", this.#onEnvChange);
    document.addEventListener("visibilitychange", this.#onEnvChange);
    this.#mount();
  }

  disconnectedCallback(): void {
    this.#reduced?.removeEventListener("change", this.#onEnvChange);
    document.removeEventListener("visibilitychange", this.#onEnvChange);
    this.#unmount();
  }

  attributeChangedCallback(name: string, old: string | null, value: string | null): void {
    if (old === value || !this.isConnected) return;
    if (name === "lang" || name === "timezone") {
      if (this.#pot) this.#render();
      else if (this.#failure) this.#renderFailure();
    } else this.#mount();
  }

  #onEnvChange = (): void => {
    if (this.#pot) this.#render();
    // A card that could not fetch its pot tries again when the page comes back to the foreground
    else if (this.#failure && document.visibilityState !== "hidden") this.#mount();
  };

  // ── mounting: everything that is decided once per appearance in the document ──

  #unmount(): void {
    this.#loadToken++;
    clearInterval(this.#tick);
    clearInterval(this.#cancelPoll);
    clearInterval(this.#outcomePoll);
    this.#tick = this.#cancelPoll = this.#outcomePoll = undefined;
    this.#pollKey = "";
    this.#awaiting = false;
    this.#wantSeat(false);
    this.#clearSprite();
    this.#pot = null;
    this.#phase = null;
    this.#segment = null;
    this.#lastSpritePhase = null;
    this.#failure = null;
    this.#serverTz = "";
    this.#packWatched = false;
    this.#preloaded = false;
    this.#card.classList.remove("failed");
  }

  #mount(): void {
    this.#unmount();
    const fonts = this.getAttribute("fonts");
    if (fonts !== "none") ensureFonts(fonts ? withSlash(new URL(fonts, document.baseURI).href) : DEFAULT_FONTS);
    const s = this.#session;
    if (s) {
      this.#begin(s);
      return;
    }
    // No data given: fetch the pot by id
    const id = this.getAttribute("session-id");
    const probe = this.#activeProbe();
    this.#wrap.hidden = true;
    if (!id || !probe) return;
    const token = this.#loadToken;
    probe(id, true)
      .then((r) => {
        if (token !== this.#loadToken) return;
        if (r.timezone) this.#serverTz = r.timezone;
        if (r.session) this.#begin(r.session);
        else this.#fail(notFound());
      })
      .catch((e: unknown) => {
        if (token === this.#loadToken) this.#fail(asKitchenError(e), e);
      });
  }

  /** The pot could not be fetched: the card stays on the page and says so in one line */
  #fail(failure: KitchenFetchError, cause: unknown = failure): void {
    this.#failure = failure;
    this.#renderFailure();
    this.dispatchEvent(
      new CustomEvent("kitchenette-error", {
        detail: { kind: failure.kind, status: failure.status, message: failure.message, error: cause },
      }),
    );
  }

  #renderFailure(): void {
    const failure = this.#failure;
    if (!failure) return;
    const t = { ...stringsFor(this.getAttribute("lang")), ...this.#strings };
    const line = t.loadFailed(failure.kind, failure.status);
    this.#stage.hidden = true;
    this.#card.classList.add("failed");
    this.#frame.classList.remove("dim");
    setText(this.#symText, t.symbol);
    setText(this.#symEn, t.symbolLabel);
    setText(this.#eyebrow, t.eyebrow);
    setText(this.#note, line);
    this.#note.hidden = false;
    this.#card.setAttribute("aria-label", line);
    this.#wrap.hidden = false;
  }

  #begin(s: KitchenSession): void {
    const now = this.#clock();
    this.#pot = {
      id: String(s.id),
      dish: String(s.dish ?? ""),
      note: String(s.note ?? ""),
      startedAt: Number(s.started_at),
      durationSec: Number(s.duration_seconds),
      method: s.method,
      mountedAtMs: now,
      // Read here, recorded later: a pot only counts as seen once its entrance has finished
      firstSeen: isFirstSeen(String(s.id)),
      cancelledSeenAtMs: undefined,
      outcome: undefined,
    };
    this.#take(probeFromSession(s));
    this.#wrap.hidden = false;
    this.#render();
    if (this.#phase && phaseIsLive(this.#phase)) this.#tick = setInterval(() => this.#render(), TICK_MS);
  }

  #activeProbe(): ProbeFn | null {
    if (this.#probe) return this.#probe;
    const base = this.getAttribute("api-base");
    if (!base) return null;
    return apiProbe(new URL(base, document.baseURI).href, () => this.getAttribute("token"));
  }

  #take(r: KitchenProbe): void {
    const pot = this.#pot;
    if (r.timezone) this.#serverTz = r.timezone;
    if (!pot) return;
    if (r.status === "cancelled") pot.cancelledSeenAtMs ??= this.#clock();
    else if (r.status === "served") pot.outcome ??= { v: r.outcome, atMs: this.#clock() };
  }

  #check(fresh: boolean): void {
    const pot = this.#pot;
    const probe = this.#activeProbe();
    if (!pot || !probe) return;
    const token = this.#loadToken;
    probe(pot.id, fresh)
      .then((r) => {
        if (token !== this.#loadToken || this.#pot !== pot) return;
        this.#take(r);
        this.#render();
      })
      .catch(() => {
        // A failed read counts as "nothing changed"; it never blocks the card
      });
  }

  // ── one tick: recompute everything from facts, touch the DOM only where it changed ──

  #facts(pot: PotState): KitchenFacts {
    return {
      startedAt: pot.startedAt,
      durationSec: pot.durationSec,
      mountedAtMs: pot.mountedAtMs,
      firstSeen: pot.firstSeen,
      cancelledSeenAtMs: pot.cancelledSeenAtMs,
      outcome: pot.outcome?.v ?? null,
      outcomeAtMs: pot.outcome?.atMs,
    };
  }

  #render(): void {
    const pot = this.#pot;
    if (!pot) return;
    const nowMs = this.#clock();
    const facts = this.#facts(pot);
    const phase = kitchenPhase(facts, nowMs);
    this.#phase = phase;
    // Seen only once the entrance is over (or was never needed): a card removed mid-entrance plays it again from the start
    if (phase !== "enter") markSeen(pot.id);

    const dueMs = (pot.startedAt + pot.durationSec) * 1000;
    const cancelled = pot.cancelledSeenAtMs !== undefined;
    const visible = document.visibilityState !== "hidden";

    // Reading back from the backend. While the pot is cooking: once now, then every 15 s (visible pages only),
    // to notice a cancelled pot. Each time "cooking" flips (due, or cancelled) one more read happens at once.
    const cooking = !cancelled && nowMs < dueMs;
    const pollKey = `${cooking}|${visible}`;
    if (pollKey !== this.#pollKey) {
      this.#pollKey = pollKey;
      clearInterval(this.#cancelPoll);
      this.#cancelPoll = undefined;
      this.#check(false);
      if (cooking && visible) this.#cancelPoll = setInterval(() => this.#check(false), CANCEL_POLL_MS);
    }
    // Due, on screen since before it was due, outcome still unknown: ask more often (skipping caches)
    // until it arrives or the wait runs out, at which point the pot is served as "ok".
    const awaiting =
      !cancelled && pot.outcome === undefined && pot.mountedAtMs < dueMs && nowMs >= dueMs && nowMs < dueMs + OUTCOME_WAIT_MS;
    if (awaiting !== this.#awaiting) {
      this.#awaiting = awaiting;
      clearInterval(this.#outcomePoll);
      this.#outcomePoll = undefined;
      if (awaiting) {
        this.#check(true);
        this.#outcomePoll = setInterval(() => this.#check(true), OUTCOME_POLL_MS);
      }
    }

    // The cook
    const sinceRevealMs = nowMs - revealAtMs(facts);
    const outfit = outfitFor(pot.id, this.#manifest.outfits);
    const segment = cookSegment({
      phase, nowMs, startedAt: pot.startedAt, durationSec: pot.durationSec, mountedAtMs: pot.mountedAtMs,
      firstSeen: pot.firstSeen, sinceRevealMs, outcome: pot.outcome?.v ?? null, method: parseMethod(pot.method),
      sessionId: pot.id,
    });
    this.#segment = segment;
    this.#renderSprite(phase, outfit, segment, visible);

    // The card
    const t = { ...stringsFor(this.getAttribute("lang")), ...this.#strings };
    const p = cookProgress(pot.startedAt, pot.durationSec, nowMs);
    const onFire = !cancelled && p.remainingSec > 0;
    const served = t.served(pot.outcome?.v ?? null);
    // Clock times are written in the backend's time zone when it says one, else the card's `timezone`
    // attribute, else the visitor's device: the card and the backend's own notes then name the same hour.
    const tz = pickTimeZone(this.#serverTz, this.getAttribute("timezone"));
    const start = fmtHM(pot.startedAt, tz);
    const due = fmtHM(pot.startedAt + pot.durationSec, tz);
    const duration = t.minutes(pot.durationSec);
    const remaining = fmtRemaining(p.remainingSec);
    setText(this.#symText, t.symbol);
    setText(this.#symEn, t.symbolLabel);
    setText(this.#eyebrow, t.eyebrow);
    setText(this.#dish, pot.dish);
    setText(this.#note, pot.note);
    this.#note.hidden = !pot.note;
    this.#frame.classList.toggle("dim", cancelled);
    this.#clockEl.hidden = !onFire;
    this.#stateWord.hidden = onFire;
    if (onFire) setText(this.#clockEl, remaining);
    else setText(this.#stateWord, cancelled ? t.cancelled : served);
    this.#track.hidden = !onFire;
    if (onFire) this.#fill.style.width = `${Math.round(p.progress * 1000) / 10}%`;
    setText(
      this.#foot,
      cancelled ? t.footCancelled(start) : onFire ? t.footCooking(start, duration, due) : t.footServed(start, duration, due),
    );
    const label = cancelled ? t.ariaCancelled(pot.dish) : onFire ? t.ariaCooking(pot.dish, remaining) : t.ariaServed(pot.dish, served);
    if (this.#card.getAttribute("aria-label") !== label) this.#card.setAttribute("aria-label", label);

    // After the final state: no timers at all
    if (!phaseIsLive(phase)) {
      clearInterval(this.#tick);
      this.#tick = undefined;
    }
  }

  // ── sprite: slide in / out, the cut line, cross-fading between clips ──

  #assetsFolder(): string {
    const base = this.getAttribute("assets");
    return base ? withSlash(new URL(base, document.baseURI).href) : DEFAULT_ASSETS;
  }

  /** Where a registered file is; null when it is not registered or is known not to exist */
  #assetUrl(key: string): string | null {
    const file = this.#manifest.files[key];
    if (file === undefined) return null;
    const url = new URL(file, this.#assetsFolder()).href;
    return broken.has(url) ? null : url;
  }

  /**
   * Is the sprite pack there? The first card to ask sends one request for one file; until the answer is
   * in, and for good when the answer is no, nothing else is requested and the stage stays empty.
   */
  #packReady(outfit: string): boolean {
    const folder = this.#assetsFolder();
    const file = this.#manifest.files[assetKey(outfit, "base")] ?? Object.values(this.#manifest.files)[0];
    if (file === undefined) return false;
    const pack = checkPack(folder, new URL(file, folder).href);
    if (pack.state === "checking" && !this.#packWatched) {
      this.#packWatched = true;
      const token = this.#loadToken;
      void pack.ready.then(() => {
        if (token === this.#loadToken && this.#pot) this.#render();
      });
    }
    if (pack.state === "ok" && !this.#preloaded) {
      this.#preloaded = true;
      this.#preloadPot();
    }
    return pack.state === "ok";
  }

  /** Fetch everything this pot can show, so a new clip is already there when its moment comes */
  #preloadPot(): void {
    const pot = this.#pot;
    if (!pot) return;
    const outfit = outfitFor(pot.id, this.#manifest.outfits);
    const m = parseMethod(pot.method);
    const segs = ["base", "wash", "chop", ...["main", "wipe", "look", "hot", "taste", "serve", "fail", "serve_last", "fail_last"].map((k) => `${m}_${k}`)];
    for (const s of segs) {
      const url = this.#assetUrl(assetKey(outfit, s));
      if (url) void preload(url);
    }
  }

  #wantSeat(wanted: boolean): void {
    if (wanted === this.#seatWanted) return;
    this.#seatWanted = wanted;
    if (wanted) {
      const revoke = (): void => {
        // A newer card took the seat: back to the still pose, and wait for a free one
        this.#seat = null;
        if (this.#pot) this.#render();
      };
      // Mounting takes a seat (newest first); after losing it, only a free seat is taken, nobody is pushed out
      this.#seat = acquireSeat(revoke);
      this.#offSeatFree = onSeatFree(() => {
        if (this.#seat || !seatFree()) return;
        this.#seat = acquireSeat(revoke);
        if (this.#pot) this.#render();
      });
    } else {
      this.#offSeatFree?.();
      this.#offSeatFree = null;
      if (this.#seat) {
        releaseSeat(this.#seat);
        this.#seat = null;
      }
    }
  }

  #clearSprite(): void {
    this.#slide?.cancel();
    this.#slide = null;
    for (const l of this.#layers) dropLayer(l);
    this.#layers = [];
    this.#stillImg?.remove();
    this.#stillImg = null;
    this.#canvas.style.transform = "";
    this.#stage.hidden = true;
  }

  #renderSprite(phase: KitchenPhase, outfit: string, segment: string | null, visible: boolean): void {
    if (spriteOnStage(phase) && segment && !this.#packReady(outfit)) {
      // No sprite pack (yet, or at all): no cook. The phase is not recorded, so an entrance that is still
      // due plays once the pack turns out to be there.
      this.#wantSeat(false);
      this.#clearSprite();
      return;
    }
    const url = segment ? this.#assetUrl(assetKey(outfit, segment)) : null;
    const baseUrl = this.#assetUrl(assetKey(outfit, "base"));
    if (!spriteOnStage(phase) || !segment || !url) {
      this.#wantSeat(false);
      this.#clearSprite();
      this.#lastSpritePhase = phase;
      return;
    }
    // "Reduce motion" or a hidden page: no slide, no clips, the still base pose
    const still = !!this.#reduced?.matches || !visible;
    this.#wantSeat(!still);
    this.#stage.hidden = false;

    // The slide: enter springs up from below the cut line; exit sinks back below it; otherwise stay put
    if (this.#lastSpritePhase !== phase) {
      const first = this.#lastSpritePhase === null;
      this.#lastSpritePhase = phase;
      if (phase === "enter" && first && !still) {
        const frames = springFrames(HIDDEN_Y, 0);
        this.#slide?.cancel();
        this.#canvas.style.transform = "translateY(0px)";
        this.#slide = this.#canvas.animate(
          frames.values.map((y) => ({ transform: `translateY(${y.toFixed(2)}px)` })),
          { duration: frames.durationMs, easing: "linear" },
        );
      } else if (phase === "exit") {
        this.#slide?.cancel();
        this.#canvas.style.transform = `translateY(${HIDDEN_Y}px)`;
        if (!still) {
          this.#slide = this.#canvas.animate(
            [{ transform: "translateY(0px)" }, { transform: `translateY(${HIDDEN_Y}px)` }],
            { duration: EXIT_MS, easing: "cubic-bezier(0.32, 0, 0.67, 0)" },
          );
        }
      }
    }

    const playable = !still && this.#seat !== null;
    if (!playable) {
      for (const l of this.#layers) dropLayer(l);
      this.#layers = [];
      if (!this.#stillImg) {
        this.#stillImg = document.createElement("img");
        this.#stillImg.alt = "";
        this.#stillImg.draggable = false;
        this.#canvas.appendChild(this.#stillImg);
      }
      const src = baseUrl ?? url;
      if (this.#stillImg.dataset.url !== src) {
        this.#stillImg.dataset.url = src;
        this.#stillImg.src = src;
      }
      return;
    }
    this.#stillImg?.remove();
    this.#stillImg = null;

    // Cross-fade: the new clip fades in over the old one, then the old one goes. Every clip starts from the
    // same base pose, so the seam does not jump. The same file is never swapped for itself: a new layer
    // restarts the clip from its first frame, which would make a loop skip.
    const top = this.#layers[this.#layers.length - 1];
    if (top && top.url === url) return;
    const img = document.createElement("img");
    img.alt = "";
    img.draggable = false;
    const blob = blobs.get(url);
    const objectUrl = blob ? URL.createObjectURL(blob) : null;
    if (!objectUrl) {
      img.onerror = () => {
        broken.add(url); // not there: do not ask again, leave the stage empty for this segment
        if (this.#pot) this.#render();
      };
    }
    img.src = objectUrl ?? url;
    const layer: Layer = { url, img, objectUrl };
    for (const old of this.#layers.slice(0, -1)) dropLayer(old);
    this.#layers = [...this.#layers.slice(-1), layer];
    this.#canvas.appendChild(img);
    if (this.#layers.length > 1) {
      const fade = img.animate([{ opacity: 0 }, { opacity: 1 }], { duration: CROSSFADE_MS, easing: "linear" });
      fade.onfinish = () => {
        if (this.#layers[this.#layers.length - 1] !== layer) return;
        for (const old of this.#layers.slice(0, -1)) dropLayer(old);
        this.#layers = [layer];
      };
    }
  }
}

function dropLayer(l: Layer): void {
  l.img.remove();
  if (l.objectUrl) URL.revokeObjectURL(l.objectUrl);
}

function setText(el: HTMLElement, text: string): void {
  if (el.textContent !== text) el.textContent = text;
}

function withSlash(url: string): string {
  return url.endsWith("/") ? url : `${url}/`;
}

export const TAG = "kitchenette-cooking-card";

/** Registers <kitchenette-cooking-card> (does nothing when it is already registered, or outside a browser) */
export function defineCookingCard(): void {
  if (typeof customElements !== "undefined" && !customElements.get(TAG)) customElements.define(TAG, KitchenetteCookingCard);
}
