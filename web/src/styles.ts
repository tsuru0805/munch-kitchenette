// The card's look: a ticket-stub strip (paper ground, ink outline, an offset solid shadow, an accent
// block with a glyph on the left, a dashed divider; once settled, the picture column takes the block's place). Every colour and font is a custom property, so a
// host page can restyle the card from outside without touching the shadow tree.
import { CANVAS_PX, STAGE_PX } from "./manifest";
import { PIC_NARROW_BELOW_PX, PIC_PAD_Y, PIC_SCALE, PIC_SCALE_NARROW, picBox } from "./settle";

const PIC = picBox(PIC_SCALE);
const PIC_NARROW = picBox(PIC_SCALE_NARROW);

export const CARD_CSS = `
:host {
  display: block;
  container: kitchenette-card / inline-size;
  margin: 8px 0;
  /* Text settings a host page may have set on an ancestor do not leak into the card */
  font-size: 14px; line-height: normal; font-weight: 400; font-style: normal; letter-spacing: normal;
  text-align: left; text-transform: none; text-indent: 0; word-spacing: normal;
  --_paper: var(--kitchenette-paper, #FEFEFD);
  --_ink: var(--kitchenette-ink, #2A3550);
  --_accent: var(--kitchenette-accent, #4159E8);
  --_mute: var(--kitchenette-mute, #5A6377);
  --_hair: var(--kitchenette-hair, rgba(42, 53, 80, 0.22));
  --_shadow: var(--kitchenette-shadow, #394CB3);
  --_offset: var(--kitchenette-shadow-offset, 4px);
  --_serif: var(--kitchenette-font-serif, "Kitchenette Serif", "Songti SC", "Noto Serif SC", serif);
  --_display: var(--kitchenette-font-display, "Kitchenette Bodoni 28", "Bodoni Moda", "Bodoni 72", Didot, serif);
  --_display-small: var(--kitchenette-font-display-small, "Kitchenette Bodoni 11", "Bodoni Moda", "Bodoni 72", Didot, serif);
}
:host([theme="dark"]) {
  --_paper: var(--kitchenette-paper, #111524);
  --_ink: var(--kitchenette-ink, #EDE7D6);
  --_accent: var(--kitchenette-accent, #4159E8);
  --_mute: var(--kitchenette-mute, #A8A795);
  --_hair: var(--kitchenette-hair, rgba(237, 231, 214, 0.2));
  --_shadow: var(--kitchenette-shadow, #7D8BE2);
}
:host([hidden]) { display: none; }
* { box-sizing: border-box; }
.stage {
  height: ${STAGE_PX}px;
  width: ${CANVAS_PX}px;
  overflow: hidden;
  margin-left: auto;
  margin-right: 12px;
  pointer-events: none;
}
.canvas { position: relative; width: ${CANVAS_PX}px; height: ${CANVAS_PX}px; }
.canvas img {
  position: absolute; left: 0; top: 0;
  width: ${CANVAS_PX}px; height: ${CANVAS_PX}px;
  object-fit: contain;
  user-select: none; -webkit-user-drag: none;
}
.frame { position: relative; padding-right: var(--_offset); padding-bottom: var(--_offset); }
.frame.dim { opacity: 0.55; }
.shadow { position: absolute; left: var(--_offset); top: var(--_offset); right: 0; bottom: 0; background: var(--_shadow); }
.card {
  position: relative;
  display: flex; flex-direction: row;
  background: var(--_paper);
  border: 1px solid var(--_ink);
}
.sym {
  flex: none; width: 44px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px;
  background: var(--_accent);
  border-right: 1px dashed var(--_paper);
}
.sym-text { color: var(--_paper); font-family: var(--_serif); font-size: 15px; line-height: 18px; }
.sym-en { color: var(--_paper); font-family: var(--_display-small); font-size: 7px; letter-spacing: 1.1px; }
.body { flex: 1; min-width: 0; padding: 8px 11px; }
.top { display: flex; flex-direction: row; align-items: center; gap: 10px; }
.left { flex: 1; min-width: 0; }
.eyebrow { font-family: var(--_serif); font-size: 9.5px; letter-spacing: 1.2px; color: var(--_accent); }
.dish, .note { white-space: pre-wrap; overflow-wrap: anywhere; }
.dish { font-family: var(--_serif); font-size: 14px; line-height: 21px; font-weight: 600; color: var(--_ink); margin-top: 1px; }
.note { font-family: var(--_serif); font-size: 11.5px; line-height: 18px; color: var(--_mute); margin-top: 1px; }
.track { height: 2px; background: var(--_hair); margin-top: 8px; overflow: hidden; }
.fill { height: 2px; background: var(--_accent); }
.foot { font-family: var(--_serif); font-size: 10.5px; line-height: 16px; color: var(--_mute); margin-top: 6px; font-variant-numeric: tabular-nums; }
/* The settled card: the picture column on the left (him with the dish, feet on one line), a dashed line,
   then the dish and one line per fact, each with its small title on the left */
.pic {
  flex: none; width: ${PIC.col}px; min-height: ${PIC.minH}px; position: relative; overflow: hidden;
  display: flex; align-items: center; justify-content: center; padding: ${PIC_PAD_Y}px 0;
  border-right: 1px dashed var(--_ink);
}
/* Every pose through the same frame at the same scale, the frame in the middle of the column: the same
   size, feet on the same line */
.pic-img {
  display: block; flex: none; width: ${PIC.w}px; height: ${PIC.h}px;
  image-rendering: pixelated; user-select: none; -webkit-user-drag: none;
}
/* A narrow card: every still a size smaller (still all the same size) */
@container kitchenette-card (max-width: ${PIC_NARROW_BELOW_PX - 1}px) {
  .pic { width: ${PIC_NARROW.col}px; min-height: ${PIC_NARROW.minH}px; }
  .pic-img { width: ${PIC_NARROW.w}px; height: ${PIC_NARROW.h}px; }
}
.card.settled .sym, .card.settled .right, .card.settled .track { display: none; }
.card.settled .body { padding: 9px 11px 9px 12px; display: grid; align-content: start; }
/* The invisible fullest card shares the content's place: the card is as tall as the taller of the two,
   content at the top. Every settled card is then one height, before and after its lines arrive. */
.sizer { display: none; visibility: hidden; pointer-events: none; }
.card.settled .content, .card.settled .sizer { grid-area: 1 / 1; min-width: 0; }
.card.settled .sizer { display: block; }
.sizer .line-text { white-space: pre-line; }
.card.settled .foot { font-size: 10px; line-height: 15px; margin-top: 5px; }
.lines {
  display: grid; grid-template-columns: max-content minmax(0, 1fr);
  margin-top: 6px; border-top: 1px solid var(--_hair);
  font-family: var(--_serif); font-size: 11px; line-height: 17px;
}
.line { display: contents; }
.line-label, .line-value { padding: 3px 0; border-bottom: 1px solid var(--_hair); }
.line-label { min-width: 34px; padding-right: 8px; color: var(--_mute); }
.line-value { min-width: 0; color: var(--_ink); overflow-wrap: anywhere; }
.line-bar { display: inline-block; position: relative; width: 46px; height: 2px; margin-left: 6px; vertical-align: middle; background: var(--_hair); }
.line-bar-fill { position: absolute; left: 0; top: 0; height: 2px; background: var(--_accent); }
/* A mishap is at most two lines */
.line-mishap .line-text { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.line-sub { font-size: 10px; line-height: 15px; color: var(--_mute); }
.chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.chip {
  font-family: var(--_serif); font-size: 9.5px; line-height: 14px; letter-spacing: 0.5px; padding: 0 5px;
  color: var(--_accent); border: 1px solid var(--_accent);
}
.right { flex: none; display: flex; flex-direction: column; align-items: flex-end; justify-content: center; }
.clock { font-family: var(--_display); font-size: 26px; color: var(--_ink); font-variant-numeric: tabular-nums; white-space: nowrap; }
.state-word { font-family: var(--_serif); font-size: 12.5px; line-height: 19px; color: var(--_accent); text-align: right; }
/* The pot could not be fetched: the same card, with one line saying so */
.card.failed .dish, .card.failed .right, .card.failed .track, .card.failed .foot { display: none; }
[hidden] { display: none !important; }
`;
