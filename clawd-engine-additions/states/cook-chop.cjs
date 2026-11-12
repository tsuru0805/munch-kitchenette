// clawds-new-clothes · states/cook-chop.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require('./_kitchen.cjs');
module.exports = {
  id: 'cook-chop', label: '切菜', frames: 45, ms: [70, 60, 70], group: 'prop',
  palette: K.palette,
  pose(i, { closedAt }) {
    // 一刀 5 帧(抬 2 落 1 停 2),连切 7 刀把一根胡萝卜切完;最后 10 帧放下刀抬头看过来、眯眼得意一下
    const done = i >= 35;
    const ph = i % 5;
    const ry = done ? 208 : [198, 188, 213, 213, 203][ph];
    return {
      dx: !done && ph === 2 ? 5 : 0,
      squash: !done && ph === 2 ? 5 : 0,
      hands: [{ x: 80, y: 218 }, { x: 220, y: ry }],
      gazeX: done ? 0 : 5, gazeY: done ? -5 : 5,
      eyes: done && i >= 39 ? 'closed' : (closedAt(17) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    K.board(ctx);
    K.carrot(ctx, Math.min(7, Math.floor((i + 2) / 5)));
    K.knife(ctx, ctx.hands[1]);
  }
};
