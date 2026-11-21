// clawds-new-clothes · states/settle/settle-burnt.cjs · still pose by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 结算定格 · burnt:端着一盘黑炭,不好意思。静态定格,45 帧同一个姿势。
// 盘子不画在这里(后贴焦黑版,盘位见 web/src/settle.ts)。
// 人往右让 25、缩 5;左手把盘子托得离自己远远的,盘子上方一缕黑烟;眼睛往右飘开,右手按在腮上挠(借「尴尬流汗」那只暗色的手),右上一颗汗。
const DROP = ['0010', '0110', '1111', '1111', '0110'];
const WISP = ['0110', '0011', '0110', '1100', '0110', '0011'];
module.exports = {
  id: 'settle-burnt', label: '结算 · 糊了(不好意思)', frames: 45, ms: [70, 60, 70], group: 'prop',
  palette: { cheekHand: '#c95d45', charSmoke: '#3d3840', charSmokeLight: '#77727d' },
  pose() {
    const dx = 25;
    return {
      dx, squash: 5, gazeX: 5, eyes: 'open', hatShift: 5,
      hands: [{ x: 95, y: 238 }, { x: 190 + dx, y: 213, a: 45, color: 'cheekHand' }]
    };
  },
  paint(ctx) {
    const l = ctx.hands[0];
    // 黑烟:盘子最高 50(盘底在手顶下 5),烟从那上面起
    ctx.effects.pattern(WISP, l.x - 35, l.y - 85, 'charSmoke', 5, 'smoke');
    ctx.effects.rect(l.x - 20, l.y - 100, 10, 10, 'charSmokeLight', 'smoke-puff');
    ctx.effects.rect(l.x - 35, l.y - 115, 5, 5, 'charSmokeLight', 'smoke-dot');
    // 汗:挂在头的右上外面(头巾的结伸到帽框外 5,让开)
    ctx.effects.pattern(DROP, ctx.hat.x + 155, ctx.hat.y + 15, 'blue', 5, 'sweat');
  }
};
