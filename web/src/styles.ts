// The card's look: a ticket-stub strip (paper ground, ink outline, an offset solid shadow, an accent
// block with a glyph on the left, a dashed divider). Every colour and font is a custom property, so a
// host page can restyle the card from outside without touching the shadow tree.
import { CANVAS_PX, STAGE_PX } from "./manifest";

export const CARD_CSS = `
:host {
  display: block;
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
.right { flex: none; display: flex; flex-direction: column; align-items: flex-end; justify-content: center; }
.clock { font-family: var(--_display); font-size: 26px; color: var(--_ink); font-variant-numeric: tabular-nums; white-space: nowrap; }
.state-word { font-family: var(--_serif); font-size: 12.5px; line-height: 19px; color: var(--_accent); text-align: right; }
/* The pot could not be fetched: the same card, with one line saying so */
.card.failed .dish, .card.failed .right, .card.failed .track, .card.failed .foot { display: none; }
[hidden] { display: none !important; }
`;
