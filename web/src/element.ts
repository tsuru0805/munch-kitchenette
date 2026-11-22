// <kitchenette-cooking-card>: one pot on a chat page. A ticket-stub card that counts down in real
// time, with a tiny cook standing on its top edge.
//
// The element decides nothing about timing itself: which phase the pot is in comes from
// cookPhase.ts, which clip plays comes from cookSegments.ts, and both are recomputed on every tick
// from facts (start time, duration, when the element was connected, what the backend said). Taking
// the element out of the document and putting it back, or reloading the page, therefore lands on
// the right moment instead of replaying anything.
import {
  apiProbe, asKitchenError, notFound, probeFromSession, type KitchenFetchError, type KitchenProbe, type KitchenSession,
  type KitchenSettleMissing, type KitchenSettlement, type ProbeFn,
} from "./api";
import {
  EXIT_MS, OUTCOME_WAIT_MS, cookProgress, fmtHM, fmtRemaining, kitchenPhase, phaseIsLive, pickTimeZone, revealAtMs,
  spriteOnStage,
  type KitchenFacts, type KitchenOutcome, type KitchenPhase,
} from "./cookPhase";
import { assetKey, cookSegment, outfitFor, parseMethod } from "./cookSegments";
import { STAGE_PX, type SpriteManifest } from "./manifest";
import { StillCache, drawSettle, frameStill, poseFor, settleKeys } from "./settle";
import { fullestLines, settleLines, settleView, type SettleFacts, type SettleLine, type SettleView } from "./settleCard";
import { CLAWD_MANIFEST } from "./manifest.generated";
import { SeatClaim } from "./seats";
import {
  Base, DEFAULT_ASSETS, DEFAULT_FONTS, blobs, broken, checkPack, dropLayer, ensureFonts, h, preload, setText, withSlash, type Layer,
} from "./cardKit";
import { isFirstSeen, markSeen } from "./seen";
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
  /** the settled card, once the backend sent one */
  settlement?: KitchenSettlement | null;
  /** why there is none, when the backend said so */
  settleMissing?: KitchenSettleMissing | null;
  /** a read with the pot's final state came back (from the backend, not from the data the card was given) */
  settleAnswered: boolean;
  /** a bad egg ruined the pot the moment it was started */
  ruined: boolean;
}

interface Still {
  url: string;
  /** size of the cropped picture in canvas pixels */
  w: number;
  h: number;
}

/** Settled stills already drawn (as data URLs), by the URLs of their pictures */
const settleCache = new StillCache<Still>();

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
  /** Settled stills this appearance of the card has asked for (a failed one is asked again on the next) */
  #stillsTried = new Set<string>();

  // ── sprite ──
  #layers: Layer[] = [];
  #stillImg: HTMLImageElement | null = null;
  #seat = new SeatClaim(() => {
    if (this.#pot) this.#render();
  });
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
  #pic!: HTMLElement;
  #picImg!: HTMLImageElement;
  #lines!: HTMLElement;
  #chips!: HTMLElement;
  #sizer!: HTMLElement;
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
    // The settled card's picture column (him with the dish), left of a dashed line; hidden otherwise
    this.#pic = h("div", "pic", this.#card);
    this.#pic.setAttribute("aria-hidden", "true");
    this.#pic.hidden = true;
    this.#picImg = h("img", "pic-img", this.#pic);
    this.#picImg.alt = "";
    this.#picImg.draggable = false;
    this.#picImg.hidden = true;
    const sym = h("div", "sym", this.#card);
    sym.setAttribute("aria-hidden", "true");
    this.#symText = h("span", "sym-text", sym);
    this.#symEn = h("span", "sym-en", sym);
    const body = h("div", "body", this.#card);
    // What shows, and (settled cards only) an invisible copy of the fullest settled card in the same place:
    // the card takes the taller of the two, so its height is the same before and after its lines arrive
    const content = h("div", "content", body);
    this.#sizer = h("div", "sizer", body);
    this.#sizer.setAttribute("aria-hidden", "true");
    const top = h("div", "top", content);
    const left = h("div", "left", top);
    this.#eyebrow = h("div", "eyebrow", left);
    this.#dish = h("div", "dish", left);
    this.#note = h("div", "note", left);
    const right = h("div", "right", top);
    this.#clockEl = h("div", "clock", right);
    this.#stateWord = h("div", "state-word", right);
    this.#track = h("div", "track", content);
    this.#fill = h("div", "fill", this.#track);
    this.#lines = h("div", "lines", content);
    this.#lines.hidden = true;
    this.#chips = h("div", "chips", content);
    this.#chips.hidden = true;
    this.#foot = h("div", "foot", content);
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
      this.#take(probeFromSession(s), false); // same pot: only its status / outcome can be news
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
    this.#stillsTried = new Set();
    this.#card.classList.remove("failed", "settled");
    this.#pic.hidden = true;
    this.#lines.hidden = true;
    this.#chips.hidden = true;
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
        if (r.session) {
          this.#begin(r.session);
          this.#take(r, true); // the same answer may already carry the settled card
          this.#render();
        } else this.#fail(notFound());
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
      settleAnswered: false,
      ruined: false,
    };
    this.#take(probeFromSession(s), false);
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

  /** fromRead = the answer came from the backend (the data a card was given does not settle anything) */
  #take(r: KitchenProbe, fromRead: boolean): void {
    const pot = this.#pot;
    if (r.timezone) this.#serverTz = r.timezone;
    if (!pot) return;
    if (r.status === "cancelled") pot.cancelledSeenAtMs ??= this.#clock();
    else if (r.status === "served") pot.outcome ??= { v: r.outcome, atMs: this.#clock() };
    else if (r.status === "ruined") pot.ruined = true;
    if (r.settlement) pot.settlement ??= r.settlement;
    if (r.settleMissing) pot.settleMissing = r.settleMissing;
    if (fromRead && (r.status === "served" || r.status === "ruined")) pot.settleAnswered = true;
  }

  #check(fresh: boolean): void {
    const pot = this.#pot;
    const probe = this.#activeProbe();
    if (!pot || !probe) return;
    const token = this.#loadToken;
    probe(pot.id, fresh)
      .then((r) => {
        if (token !== this.#loadToken || this.#pot !== pot) return;
        this.#take(r, true);
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
    // A ruined pot was never on the fire: its card is final from the start
    const phase: KitchenPhase = pot.ruined ? "done" : kitchenPhase(facts, nowMs);
    this.#phase = phase;
    // Seen only once the entrance is over (or was never needed): a card removed mid-entrance plays it again from the start
    if (phase !== "enter") markSeen(pot.id);

    const dueMs = (pot.startedAt + pot.durationSec) * 1000;
    const cancelled = pot.cancelledSeenAtMs !== undefined;
    const visible = document.visibilityState !== "hidden";

    // Reading back from the backend. While the pot is cooking: once now, then every 15 s (visible pages only),
    // to notice a cancelled pot. Each time "cooking" flips (due, or cancelled) one more read happens at once.
    const cooking = !cancelled && !pot.ruined && nowMs < dueMs;
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
      !cancelled && !pot.ruined && pot.outcome === undefined && pot.mountedAtMs < dueMs && nowMs >= dueMs && nowMs < dueMs + OUTCOME_WAIT_MS;
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
    this.#segment = pot.ruined ? null : segment;
    this.#renderSprite(phase, outfit, this.#segment, visible);

    // The card
    const t = { ...stringsFor(this.getAttribute("lang")), ...this.#strings };
    const p = cookProgress(pot.startedAt, pot.durationSec, nowMs);
    const onFire = !cancelled && !pot.ruined && p.remainingSec > 0;
    const served = t.served(pot.outcome?.v ?? null);
    // Clock times are written in the backend's time zone when it says one, else the card's `timezone`
    // attribute, else the visitor's device: the card and the backend's own notes then name the same hour.
    const tz = pickTimeZone(this.#serverTz, this.getAttribute("timezone"));
    const start = fmtHM(pot.startedAt, tz);
    const due = fmtHM(pot.startedAt + pot.durationSec, tz);
    const duration = t.minutes(pot.durationSec);
    const remaining = fmtRemaining(p.remainingSec);
    // Once the cook has gone (or never came), a done pot's card turns into the settled card
    const view = settleView({
      done: !cancelled && (pot.ruined || phase === "done"),
      ruined: pot.ruined,
      settlement: pot.settlement,
      missing: pot.settleMissing,
      answered: pot.settleAnswered,
      canRead: this.#activeProbe() !== null,
    });
    const settledFace = view.kind !== "plain";
    this.#card.classList.toggle("settled", settledFace);
    setText(this.#symText, t.symbol);
    setText(this.#symEn, t.symbolLabel);
    // "Done" above the dish, except on a ruined pot (its outcome line says what happened)
    setText(this.#eyebrow, settledFace && !pot.ruined ? t.settleEyebrow(t.eyebrow) : t.eyebrow);
    setText(this.#dish, pot.dish);
    setText(this.#note, pot.note);
    this.#note.hidden = !pot.note;
    this.#frame.classList.toggle("dim", cancelled);
    this.#clockEl.hidden = !onFire;
    this.#stateWord.hidden = onFire;
    if (onFire) setText(this.#clockEl, remaining);
    else setText(this.#stateWord, cancelled ? t.cancelled : pot.ruined ? t.settleOutcome("ruined") : served);
    this.#track.hidden = !onFire;
    if (onFire) this.#fill.style.width = `${Math.round(p.progress * 1000) / 10}%`;
    setText(
      this.#foot,
      cancelled ? t.footCancelled(start)
        : pot.ruined ? t.footRuined(start)
        : onFire ? t.footCooking(start, duration, due)
        : settledFace ? t.footSettled(start, duration)
        : t.footServed(start, duration, due),
    );
    const said = this.#renderSettled(view, t, outfit);
    const label = cancelled ? t.ariaCancelled(pot.dish)
      : onFire ? t.ariaCooking(pot.dish, remaining)
      : t.ariaServed(pot.dish, settledFace ? said || t.settleEyebrow(t.eyebrow) : served);
    if (this.#card.getAttribute("aria-label") !== label) this.#card.setAttribute("aria-label", label);

    // After the final state: no timers at all
    if (!phaseIsLive(phase)) {
      clearInterval(this.#tick);
      this.#tick = undefined;
    }
  }

  // ── the settled card: the picture on the left, the lines on the right ──

  /** Draws the settled parts of the card for this view; returns the lines read out for screen readers */
  #renderSettled(view: SettleView, t: CardStrings, outfit: string): string {
    const facts = view.kind === "settled" ? view.facts : null;
    this.#pic.hidden = view.kind === "plain";
    const still = facts ? this.#stillFor(outfit, facts) : null;
    this.#picImg.hidden = !still;
    if (still) {
      if (this.#picImg.dataset.url !== still.url) {
        this.#picImg.dataset.url = still.url;
        this.#picImg.src = still.url;
      }
    }
    const { lines, stamps } = facts ? settleLines(facts, t) : { lines: [], stamps: [] };
    fillLines(this.#lines, this.#chips, lines, stamps);
    this.#lines.hidden = lines.length === 0;
    this.#chips.hidden = stamps.length === 0;
    // The reserved height (every settled card, so they are all one height): the same dish name, note and
    // time line, with the fullest set of lines
    if (view.kind !== "plain") this.#renderSizer(t);
    return [...lines.map((l) => `${l.label} ${l.text}${l.sub ? `,${l.sub}` : ""}`), ...stamps].join(",");
  }

  #renderSizer(t: CardStrings): void {
    const pot = this.#pot;
    if (!pot) return;
    const full = fullestLines(t);
    const eyebrow = pot.ruined ? t.eyebrow : t.settleEyebrow(t.eyebrow);
    const key = JSON.stringify([eyebrow, pot.dish, pot.note, this.#foot.textContent, full]);
    if (this.#sizer.dataset.key === key) return;
    this.#sizer.dataset.key = key;
    this.#sizer.replaceChildren();
    const left = h("div", "left", h("div", "top", this.#sizer));
    h("div", "eyebrow", left).textContent = eyebrow;
    h("div", "dish", left).textContent = pot.dish;
    if (pot.note) h("div", "note", left).textContent = pot.note;
    fillLines(h("div", "lines", this.#sizer), h("div", "chips", this.#sizer), full.lines, full.stamps);
    h("div", "foot", this.#sizer).textContent = this.#foot.textContent;
  }

  /** The still for a settled card: him in the pose for the outcome, with the dish; the plain standing pose when the outcome is not known */
  #stillFor(outfit: string, f: SettleFacts): Still | null {
    if (!this.#packReady(outfit, false)) return null;
    const pose = f.outcome ? poseFor(f.outcome) : null;
    const keys = pose ? settleKeys(outfit, pose, f.icon) : [assetKey(outfit, "base")];
    const urls = keys.map((k) => this.#assetUrl(k));
    if (urls.some((u) => !u)) return null;
    const cacheKey = urls.join("|");
    const load = (u: string) => new Promise<HTMLImageElement>((ok, no) => {
      const im = new Image();
      im.crossOrigin = "anonymous";
      im.onload = () => ok(im);
      im.onerror = no;
      im.src = u;
    });
    // A picture that is missing (an older sprite pack) or did not load leaves the column empty; the card
    // asks again the next time it is put on the page
    return settleCache.get(cacheKey, this.#stillsTried, async () => {
      const [poseImg, front, dish] = await Promise.all(urls.map((u) => load(u!)));
      const c = document.createElement("canvas");
      if (pose) {
        if (!drawSettle(c, pose, outfit, { pose: poseImg, front, dish })) return null;
      } else {
        const ctx = c.getContext("2d");
        if (!ctx) return null;
        c.width = poseImg.naturalWidth;
        c.height = poseImg.naturalHeight;
        ctx.drawImage(poseImg, 0, 0);
      }
      const cut = frameStill(c);
      return cut ? { url: cut.toDataURL("image/png"), w: cut.width, h: cut.height } : null;
    }, this.#onStill);
  }

  /** A still this card waits for is drawn (or failed): one function per card, so waiting is registered once */
  #onStill = (): void => {
    if (this.isConnected && this.#pot) this.#render();
  };

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
  #packReady(outfit: string, preloadClips = true): boolean {
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
    if (pack.state === "ok" && preloadClips && !this.#preloaded) {
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
      const src = url.startsWith("data:") ? url : baseUrl ?? url;
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

/** Writes the lines and stamps of a settled card into their two boxes (only when they changed) */
function fillLines(linesEl: HTMLElement, chipsEl: HTMLElement, lines: SettleLine[], stamps: string[]): void {
  const key = JSON.stringify([lines, stamps]);
  if (linesEl.dataset.key === key) return;
  linesEl.dataset.key = key;
  linesEl.replaceChildren();
  for (const l of lines) {
    const row = h("div", `line line-${l.key}`, linesEl);
    h("div", "line-label", row).textContent = l.label;
    const v = h("div", "line-value", row);
    h("span", "line-text", v).textContent = l.text;
    if (l.bar !== undefined && l.bar !== null) {
      const bar = h("span", "line-bar", v);
      h("span", "line-bar-fill", bar).style.width = `${Math.round(l.bar * 1000) / 10}%`;
    }
    if (l.sub) h("div", "line-sub", v).textContent = l.sub;
  }
  chipsEl.replaceChildren();
  for (const s of stamps) h("span", "chip", chipsEl).textContent = s;
}

export const TAG = "kitchenette-cooking-card";

/** Registers <kitchenette-cooking-card> (does nothing when it is already registered, or outside a browser) */
export function defineCookingCard(): void {
  if (typeof customElements !== "undefined" && !customElements.get(TAG)) customElements.define(TAG, KitchenetteCookingCard);
}
