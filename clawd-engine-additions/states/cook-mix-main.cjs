// clawds-new-clothes · states/cook-mix-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require("./_kitchen.cjs");
// 拌:不开火。台子上一只大碗,两手各握一把勺叉,一上一下地拌,菜叶跟着蹦
module.exports = {
  id: 'cook-mix-main', label: '拌', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i, { closedAt }) {
    const ph = i % 10, up = ph < 5;
    return {
      dx: 0,
      hands: [{ x: 220, y: up ? 183 : 193 }, { x: 265, y: up ? 193 : 183 }],
      gazeX: 5, gazeY: 5, eyes: closedAt(22, 40) ? 'closed' : 'open'
    };
  },
  paint(ctx, p, i) {
    K.table(ctx); K.saladBowl(ctx, i);
    K.server(ctx, ctx.hands[0]); K.server(ctx, ctx.hands[1]);
  }
};
