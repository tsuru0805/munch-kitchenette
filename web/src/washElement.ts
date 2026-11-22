// <kitchenette-washing-card>: one washing-up on a chat page. The same ticket-stub card as the cooking
// card, with the cook at the sink on its top edge, plate after plate, in real time.
//
// The element decides nothing about timing itself: which clip plays and whether he is on stage comes from
// washSegments.ts, what the card says from washFace.ts, both recomputed on every tick from facts (start
// time, plates, seconds each, what the backend said and when the card first saw it). Taking the element out
// of the document and putting it back, or reloading the page, lands on the right moment.
//
// It can sit next to a cooking card: both are on the same page-wide cap of moving cooks (seats.ts).
import { asKitchenError, notFound, type KitchenFetchError } from "./api";
import {
  Base, DEFAULT_ASSETS, DEFAULT_FONTS, blobs, broken, checkPack, dropLayer, ensureFonts, h, preload, setText, withSlash, type Layer,
} from "./cardKit";
import { ENTER_MS, EXIT_MS, pickTimeZone } from "./cookPhase";
import { assetKey, outfitFor } from "./cookSegments";
import { STAGE_PX, type SpriteManifest } from "./manifest";
import { CLAWD_MANIFEST } from "./manifest.generated";
import { SeatClaim } from "./seats";
import { isFirstSeen, markSeen } from "./seen";
import { springFrames } from "./spring";
import { CARD_CSS } from "./styles";
import { factsFromAttachment, factsFromRead, washApiProbe, type WashProbeFn, type WashingAttachment } from "./washApi";
import { washFace } from "./washFace";
import {
  WASH_SEGMENTS, isFinal, momentAt, nextReadAtDevice, offsetFrom, washFrame, washStill, type WashCardState, type WashFacts,
  type WashFrame, type WashPhase, type WashRead,
} from "./washSegments";
import { washStringsFor, type WashCardStrings } from "./washStrings";

const TICK_MS = 250;
/** How often a washing is read again while it goes on (only while the page is visible) */
export const WASH_POLL_MS = 15_000;
/** A plate's result is read this long after it is due */
export const WASH_READ_LAG_MS = 1_200;
const CROSSFADE_MS = 120;
const HIDDEN_Y = STAGE_PX + 8;

interface WashLayer extends Layer {
  run: string;
}

export class KitchenetteWashingCard extends Base {
  static observedAttributes = ["api-base", "job-id", "assets", "fonts", "lang", "timezone"];

  // ── configuration (properties) ──
  #washing: WashingAttachment | null = null;
  #probe: WashProbeFn | null = null;
  #clock: () => number = Date.now;
  #manifest: SpriteManifest = CLAWD_MANIFEST;
  #strings: Partial<WashCardStrings> = {};

  // ── state of the current mount ──
  #facts: WashFacts | null = null;
  #read: WashRead | null = null;
  #seenAt: Record<number, number> = {};
  #endSeenAt: number | undefined;
  #unavailable = false;
  /** server clock minus device clock (ms), from the latest answer; 0 before the first */
  #offset = 0;
  #mountedAt = 0;
  #firstSeen = false;
  #frame: WashFrame | null = null;
  #failure: KitchenFetchError | null = null;
  #serverTz = "";
  #tick: ReturnType<typeof setInterval> | undefined;
  #nextReadAt: number | null = null;
  #lastReadAt = -Infinity;
  #reading = false;
  #loadToken = 0;
  #packWatched = false;
  #preloaded = false;

  // ── sprite ──
  #layers: WashLayer[] = [];
  #stillImg: HTMLImageElement | null = null;
  #seat = new SeatClaim(() => {
    if (this.#facts) this.#render();
  });
  #slide: Animation | null = null;
  #lastPhase: WashPhase | null = null;
  #reduced: MediaQueryList | null = null;

  // ── DOM ──
  #root: ShadowRoot;
  #wrap!: HTMLElement;
  #stage!: HTMLElement;
  #canvas!: HTMLElement;
  #card!: HTMLElement;
  #symText!: HTMLElement;
  #symEn!: HTMLElement;
  #eyebrow!: HTMLElement;
  #title!: HTMLElement;
  #note!: HTMLElement;
  #clockEl!: HTMLElement;
  #word!: HTMLElement;
  #track!: HTMLElement;
  #fill!: HTMLElement;
  #foot!: HTMLElement;

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
    const frame = h("div", "frame", wrap);
    h("div", "shadow", frame);
    this.#card = h("div", "card", frame);
    this.#card.setAttribute("role", "group");
    const sym = h("div", "sym", this.#card);
    sym.setAttribute("aria-hidden", "true");
    this.#symText = h("span", "sym-text", sym);
    this.#symEn = h("span", "sym-en", sym);
    const body = h("div", "body", this.#card);
    const content = h("div", "content", body);
    const top = h("div", "top", content);
    const left = h("div", "left", top);
    this.#eyebrow = h("div", "eyebrow", left);
    this.#title = h("div", "dish", left);
    this.#note = h("div", "note", left);
    const right = h("div", "right", top);
    this.#clockEl = h("div", "clock", right);
    this.#word = h("div", "state-word", right);
    this.#track = h("div", "track", content);
    this.#fill = h("div", "fill", this.#track);
    this.#foot = h("div", "foot", content);
  }

  // ── public API ──

  /** The washing, as the card attachment a [刷盘子] returned ({ job_id, n, per_s, started_at }) */
  get washing(): WashingAttachment | null {
    return this.#washing;
  }
  set washing(a: WashingAttachment | null) {
    this.#washing = a;
    if (!this.isConnected) return;
    const f = factsFromAttachment(a);
    if (f && this.#facts && f.jobId === this.#facts.jobId) return; // the same washing: nothing new in it
    this.#mount();
  }

  /** Where the card reads the washing back. Defaults to the backend at `api-base` when that attribute is set. */
  get probe(): WashProbeFn | null {
    return this.#probe;
  }
  set probe(fn: WashProbeFn | null) {
    this.#probe = fn;
    if (this.isConnected) this.#mount();
  }

  /** The clock the card counts against, in epoch milliseconds. Defaults to Date.now. */
  get clock(): () => number {
    return this.#clock;
  }
  set clock(fn: () => number) {
    this.#clock = fn;
    if (this.isConnected) this.#mount();
  }

  /** The sprite registry. Defaults to the built-in Clawd pack. */
  get manifest(): SpriteManifest {
    return this.#manifest;
  }
  set manifest(m: SpriteManifest) {
    this.#manifest = m;
    if (this.isConnected) this.#mount();
  }

  /** Overrides for any of the words on the card (see washStrings.ts) */
  get strings(): Partial<WashCardStrings> {
    return this.#strings;
  }
  set strings(s: Partial<WashCardStrings>) {
    this.#strings = s ?? {};
    if (!this.isConnected) return;
    if (this.#facts) this.#render();
    else this.#renderFailure();
  }

  /** wait / wash / exit / done (null before any data) */
  get phase(): WashPhase | null {
    return this.#frame?.phase ?? null;
  }

  /** The clip on stage right now (null when the cook is not on stage) */
  get segment(): string | null {
    return this.#frame?.segment ?? null;
  }

  /** The outfit this washing wears (the cooking card's rule, by the washing's id) */
  get outfit(): string | null {
    return this.#facts ? outfitFor(this.#facts.jobId, this.#manifest.outfits) : null;
  }

  /** The latest answer from the backend (null = none yet) */
  get result(): WashRead | null {
    return this.#read;
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
      if (this.#facts) this.#render();
      else if (this.#failure) this.#renderFailure();
    } else this.#mount();
  }

  #onEnvChange = (): void => {
    if (this.#facts) {
      // back in the foreground: read once more right away (a stop or a broken plate may have happened meanwhile)
      if (document.visibilityState !== "hidden" && !isFinal(this.#read)) this.#nextReadAt = this.#clock();
      this.#render();
    } else if (this.#failure && document.visibilityState !== "hidden") this.#mount();
  };

  // ── mounting ──

  #unmount(): void {
    this.#loadToken++;
    clearInterval(this.#tick);
    this.#tick = undefined;
    this.#wantSeat(false);
    this.#clearSprite();
    this.#facts = null;
    this.#read = null;
    this.#seenAt = {};
    this.#endSeenAt = undefined;
    this.#unavailable = false;
    this.#offset = 0;
    this.#frame = null;
    this.#failure = null;
    this.#serverTz = "";
    this.#nextReadAt = null;
    this.#lastReadAt = -Infinity;
    this.#reading = false;
    this.#lastPhase = null;
    this.#packWatched = false;
    this.#preloaded = false;
    this.#card.classList.remove("failed");
  }

  #mount(): void {
    this.#unmount();
    const fonts = this.getAttribute("fonts");
    if (fonts !== "none") ensureFonts(fonts ? withSlash(new URL(fonts, document.baseURI).href) : DEFAULT_FONTS);
    const f = factsFromAttachment(this.#washing);
    if (f) {
      this.#begin(f);
      return;
    }
    // No attachment given: fetch the washing by id
    const id = this.getAttribute("job-id");
    const probe = this.#activeProbe();
    this.#wrap.hidden = true;
    if (!id || !probe) return;
    const token = this.#loadToken;
    probe(id, true)
      .then((r) => {
        if (token !== this.#loadToken) return;
        if (!r) return this.#fail(notFound());
        this.#offset = offsetFrom(r, this.#clock());
        this.#begin(factsFromRead(id, r));
        this.#take(r);
        this.#lastReadAt = this.#clock();
        this.#render();
      })
      .catch((e: unknown) => {
        if (token === this.#loadToken) this.#fail(asKitchenError(e), e);
      });
  }

  #fail(failure: KitchenFetchError, cause: unknown = failure): void {
    this.#failure = failure;
    this.#renderFailure();
    this.dispatchEvent(
      new CustomEvent("kitchenette-error", {
        detail: { kind: failure.kind, status: failure.status, message: failure.message, error: cause },
      }),
    );
  }

  #t(): WashCardStrings {
    return { ...washStringsFor(this.getAttribute("lang")), ...this.#strings };
  }

  #renderFailure(): void {
    const failure = this.#failure;
    if (!failure) return;
    const t = this.#t();
    const line = t.loadFailed(failure.kind, failure.status);
    this.#stage.hidden = true;
    this.#card.classList.add("failed");
    setText(this.#symText, t.symbol);
    setText(this.#symEn, t.symbolLabel);
    setText(this.#eyebrow, t.eyebrow);
    setText(this.#note, line);
    this.#note.hidden = false;
    this.#card.setAttribute("aria-label", line);
    this.#wrap.hidden = false;
  }

  #begin(f: WashFacts): void {
    this.#facts = f;
    this.#mountedAt = this.#clock();
    this.#firstSeen = isFirstSeen(`wash:${f.jobId}`);
    // Nothing to read back from: play by time alone, wait for nothing
    this.#unavailable = this.#activeProbe() === null;
    this.#nextReadAt = this.#unavailable ? null : this.#mountedAt;
    this.#wrap.hidden = false;
    this.#render();
    // Ticks until nothing more can change (#render stops it): even a card that looks over by the device's
    // clock, which may be ahead of the server's until the first answer comes back
    this.#tick ??= setInterval(() => this.#render(), TICK_MS);
  }

  #activeProbe(): WashProbeFn | null {
    if (this.#probe) return this.#probe;
    const base = this.getAttribute("api-base");
    if (!base) return null;
    return washApiProbe(new URL(base, document.baseURI).href, () => this.getAttribute("token"));
  }

  /** What the backend said: when each plate's result and the end were first seen are kept */
  #take(r: WashRead): void {
    const now = this.#clock();
    this.#offset = offsetFrom(r, now);
    for (const d of r.dishes) if (d.state !== "washing" && this.#seenAt[d.i] === undefined) this.#seenAt[d.i] = now;
    if (isFinal(r) && this.#endSeenAt === undefined) this.#endSeenAt = now;
    if (r.timezone) this.#serverTz = r.timezone;
    this.#read = r;
    this.#unavailable = false;
  }

  #readBack(): void {
    const facts = this.#facts;
    const probe = this.#activeProbe();
    if (!facts || !probe || this.#reading) return;
    this.#reading = true;
    this.#lastReadAt = this.#clock();
    const token = this.#loadToken;
    probe(facts.jobId, true)
      .then((r) => {
        if (token !== this.#loadToken) return;
        if (r) this.#take(r);
        else if (!this.#read) this.#unavailable = true; // the backend does not know it: play by time
      })
      .catch(() => {
        // A failed read: nothing learnt. Before any answer the card plays by time and waits for nothing.
        if (token === this.#loadToken && !this.#read) this.#unavailable = true;
      })
      .finally(() => {
        if (token !== this.#loadToken) return;
        this.#reading = false;
        this.#planRead();
        this.#render();
      });
  }

  #planRead(): void {
    const facts = this.#facts;
    if (!facts || !this.#activeProbe()) {
      this.#nextReadAt = null;
      return;
    }
    this.#nextReadAt = nextReadAtDevice(this.#state(facts), this.#clock(), this.#lastReadAt, WASH_POLL_MS, WASH_READ_LAG_MS);
  }

  #state(facts: WashFacts): WashCardState {
    return {
      facts, read: this.#read, offsetMs: this.#offset, seenAtDeviceMs: this.#seenAt, endSeenAtDeviceMs: this.#endSeenAt,
      unavailable: this.#unavailable, mountedAtDeviceMs: this.#mountedAt,
    };
  }

  // ── one tick ──

  #render(): void {
    const facts = this.#facts;
    if (!facts) return;
    const nowMs = this.#clock();
    const visible = document.visibilityState !== "hidden";
    // Reading back: only while the page is visible
    if (visible && this.#nextReadAt !== null && nowMs >= this.#nextReadAt && !this.#reading) {
      this.#nextReadAt = null;
      this.#readBack();
    }
    // Every rule runs on the server's clock (device clock + the offset the latest answer gave)
    const moment = momentAt(this.#state(facts), nowMs);
    const frame = washFrame(moment);
    this.#frame = frame;
    this.#renderSprite(frame, facts, visible);

    const t = this.#t();
    const tz = pickTimeZone(this.#serverTz, this.getAttribute("timezone"));
    const face = washFace(frame, facts, this.#read, moment.nowMs, t, tz);
    setText(this.#symText, t.symbol);
    setText(this.#symEn, t.symbolLabel);
    setText(this.#eyebrow, t.eyebrow);
    setText(this.#title, t.title);
    setText(this.#note, face.result);
    this.#note.hidden = !face.result;
    this.#clockEl.hidden = face.clock === null;
    if (face.clock !== null) setText(this.#clockEl, face.clock);
    setText(this.#word, face.word);
    this.#track.hidden = face.progress === null;
    if (face.progress !== null) this.#fill.style.width = `${Math.round(face.progress * 1000) / 10}%`;
    setText(this.#foot, face.foot);
    if (this.#card.getAttribute("aria-label") !== face.aria) this.#card.setAttribute("aria-label", face.aria);

    // Nothing more to come: no timers at all
    const settled = isFinal(this.#read) || this.#unavailable || this.#nextReadAt === null;
    if (frame.phase === "done" && frame.finished && settled && !this.#reading) {
      clearInterval(this.#tick);
      this.#tick = undefined;
    }
  }

  // ── sprite ──

  #assetsFolder(): string {
    const base = this.getAttribute("assets");
    return base ? withSlash(new URL(base, document.baseURI).href) : DEFAULT_ASSETS;
  }

  #assetUrl(key: string): string | null {
    const file = this.#manifest.files[key];
    if (file === undefined) return null;
    const url = new URL(file, this.#assetsFolder()).href;
    return broken.has(url) ? null : url;
  }

  #packReady(outfit: string): boolean {
    const folder = this.#assetsFolder();
    const file = this.#manifest.files[assetKey(outfit, "base")] ?? Object.values(this.#manifest.files)[0];
    if (file === undefined) return false;
    const pack = checkPack(folder, new URL(file, folder).href);
    if (pack.state === "checking" && !this.#packWatched) {
      this.#packWatched = true;
      const token = this.#loadToken;
      void pack.ready.then(() => {
        if (token === this.#loadToken && this.#facts) this.#render();
      });
    }
    if (pack.state === "ok" && !this.#preloaded) {
      this.#preloaded = true;
      for (const s of ["base", ...WASH_SEGMENTS]) {
        const url = this.#assetUrl(assetKey(outfit, s));
        if (url) void preload(url);
      }
    }
    return pack.state === "ok";
  }

  #wantSeat(wanted: boolean): void {
    this.#seat.want(wanted);
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

  #renderSprite(frame: WashFrame, facts: WashFacts, visible: boolean): void {
    const outfit = outfitFor(facts.jobId, this.#manifest.outfits);
    const onStage = (frame.phase === "wash" || frame.phase === "exit") && !!frame.segment;
    if (!onStage) {
      this.#wantSeat(false);
      this.#clearSprite();
      this.#lastPhase = frame.phase;
      if (frame.phase === "done") markSeen(`wash:${facts.jobId}`);
      return;
    }
    if (!this.#packReady(outfit)) {
      // No sprite pack (yet, or at all): no cook. The phase is not recorded, so the entrance still plays.
      this.#wantSeat(false);
      this.#clearSprite();
      return;
    }
    const still = !!this.#reduced?.matches || !visible;
    const shown = still ? washStill(frame.segment!) : frame.segment!;
    // A pack without the washing clips: no cook, the card only counts
    const url = this.#manifest.files[assetKey(outfit, frame.segment!)] === undefined ? null
      : this.#assetUrl(assetKey(outfit, shown)) ?? this.#assetUrl(assetKey(outfit, "base"));
    if (!url) {
      this.#wantSeat(false);
      this.#clearSprite();
      this.#lastPhase = frame.phase;
      return;
    }
    this.#wantSeat(!still);
    this.#stage.hidden = false;

    // The slide: up from below the card when this page first sees the washing; down below it at the end
    if (this.#lastPhase !== frame.phase) {
      const from = this.#lastPhase;
      this.#lastPhase = frame.phase;
      const id = `wash:${facts.jobId}`;
      if (frame.phase === "wash" && (from === null || from === "wait")) {
        if (this.#firstSeen && !still) {
          const frames = springFrames(HIDDEN_Y, 0);
          this.#slide?.cancel();
          this.#canvas.style.transform = "translateY(0px)";
          this.#slide = this.#canvas.animate(
            frames.values.map((y) => ({ transform: `translateY(${y.toFixed(2)}px)` })),
            { duration: frames.durationMs, easing: "linear" },
          );
          // Seen once the entrance is over: a card removed mid-entrance plays it again from the start
          this.#slide.onfinish = () => markSeen(id);
          setTimeout(() => markSeen(id), ENTER_MS);
        } else markSeen(id);
      } else if (frame.phase === "exit") {
        this.#slide?.cancel();
        this.#canvas.style.transform = `translateY(${HIDDEN_Y}px)`;
        if (!still && from === "wash") {
          this.#slide = this.#canvas.animate(
            [{ transform: "translateY(0px)" }, { transform: `translateY(${HIDDEN_Y}px)` }],
            { duration: EXIT_MS, easing: "cubic-bezier(0.32, 0, 0.67, 0)" },
          );
        }
      }
    }

    const playable = !still && this.#seat.held;
    if (!playable) {
      for (const l of this.#layers) dropLayer(l);
      this.#layers = [];
      if (!this.#stillImg) {
        this.#stillImg = document.createElement("img");
        this.#stillImg.alt = "";
        this.#stillImg.draggable = false;
        this.#canvas.appendChild(this.#stillImg);
      }
      // Without a seat (more cooks than may move at once): the still in place of the clip
      const src = still ? url : this.#assetUrl(assetKey(outfit, washStill(frame.segment!))) ?? url;
      if (this.#stillImg.dataset.url !== src) {
        this.#stillImg.dataset.url = src;
        this.#stillImg.src = src;
      }
      return;
    }
    this.#stillImg?.remove();
    this.#stillImg = null;

    // Cross-fade into the new clip. A new run of the same clip (the next plate) starts it from its first
    // frame; the same run is never swapped for itself, which would make a loop skip.
    const top = this.#layers[this.#layers.length - 1];
    if (top && top.url === url && top.run === frame.run) return;
    const img = document.createElement("img");
    img.alt = "";
    img.draggable = false;
    const blob = blobs.get(url);
    const objectUrl = blob ? URL.createObjectURL(blob) : null;
    if (!objectUrl) {
      img.onerror = () => {
        broken.add(url);
        if (this.#facts) this.#render();
      };
    }
    img.src = objectUrl ?? url;
    const layer: WashLayer = { url, img, objectUrl, run: frame.run };
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

export const WASH_TAG = "kitchenette-washing-card";

/** Registers <kitchenette-washing-card> (does nothing when it is already registered, or outside a browser) */
export function defineWashingCard(): void {
  if (typeof customElements !== "undefined" && !customElements.get(WASH_TAG)) customElements.define(WASH_TAG, KitchenetteWashingCard);
}
