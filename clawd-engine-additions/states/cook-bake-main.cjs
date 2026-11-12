// clawds-new-clothes · states/cook-bake-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require("./_kitchen.cjs");
// 烤:戴着隔热手套蹲在烤箱前盯着小窗,炉光一明一暗,面包越烤越深;30 起「叮」烤好了,蹦两下、眯眼笑
module.exports = {
  id: 'cook-bake-main', label: '烤', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i) {
    const done = i >= 30;
    return {
      squash: done ? 0 : (i % 10 < 5 ? 10 : 5),
      jump: i === 31 || i === 35 ? -10 : (i === 32 || i === 36 ? -5 : 0),
      hands: [{ x: 80, y: done ? 208 : 223 }, { x: 205, y: done ? 208 : 223 }],
      gazeX: 5, gazeY: done ? 0 : 5, eyes: i >= 37 ? 'closed' : 'open'
    };
  },
  paint(ctx, p, i) {
    K.oven(ctx, i, i >= 30);
    K.mitt(ctx, ctx.hands[0]); K.mitt(ctx, ctx.hands[1]);
    if (i >= 30 && i <= 33) ctx.effects.pattern(ctx.shapes.sparkle, 285, ctx.baseline - 90, 'flameIn', 5, 'ding');
  }
};
