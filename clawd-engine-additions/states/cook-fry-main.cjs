// clawds-new-clothes · states/cook-fry-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require("./_kitchen.cjs");
// 煎:平底锅坐在灶上不颠。0–14 盯着、油星蹦(被溅到缩一下);15–22 锅铲探到底下;23–26 翻面(抛起来、落下是焦黄的那面);27–44 压一压
module.exports = {
  id: 'cook-fry-main', label: '煎', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i) {
    const flinch = i === 6 || i === 7 || i === 34 || i === 35;
    const ry = i < 15 ? 208 : i < 23 ? 213 : i < 27 ? [203, 193, 198, 208][i - 23] : (i % 6 < 3 ? 208 : 213);
    const rx = i >= 15 && i < 23 ? 220 + Math.min(10, (i - 15) * 5) : 225;
    return { dx: flinch ? -5 : 0, hands: [{ x: 80, y: 218 }, { x: rx, y: ry }], gazeX: 5, gazeY: 5, eyes: flinch ? 'closed' : 'open' };
  },
  paint(ctx, p, i) {
    const g = ctx.baseline;
    K.stove(ctx, i); K.panOnStove(ctx);
    const air = i >= 23 && i < 27 ? [10, 25, 15, 0][i - 23] : 0;
    ctx.effects.rect(258, g - 55 - air, 25, 5, i >= 24 ? 'friedBrown' : 'friedGold', 'patty');
    K.spatula(ctx, ctx.hands[1]);
    K.sparks(ctx, i, g - 60);
  }
};
