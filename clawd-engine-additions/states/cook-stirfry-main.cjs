// clawds-new-clothes · states/cook-stirfry-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require('./_kitchen.cjs');
// 一圈 15 帧:0–5 端着锅在火上晃;6–7 往下一沉蓄力;8 猛地一抬;9–12 菜在半空;13–14 接住
const HAND_Y = [213, 213, 213, 213, 213, 213, 218, 223, 203, 203, 208, 208, 213, 218, 213];
const HAND_X = [225, 230, 225, 230, 225, 230, 225, 225, 225, 225, 225, 225, 225, 225, 225];
const AIR = [0, 0, 0, 0, 0, 0, 0, 0, 10, 30, 40, 30, 15, 0, 0];
module.exports = {
  id: 'cook-stirfry-main', label: '颠锅', frames: 45, ms: [70, 60, 70], group: 'prop',
  palette: K.palette,
  pose(i, { closedAt }) {
    const ph = i % 15;
    return {
      jump: ph === 8 ? -5 : 0,
      squash: ph === 7 ? 5 : 0,
      hands: [{ x: 80, y: 218 }, { x: HAND_X[ph], y: HAND_Y[ph] }],
      gazeX: 5, gazeY: AIR[ph] >= 30 ? -5 : 5,
      eyes: closedAt(21) ? 'closed' : 'open'
    };
  },
  paint(ctx, p, i) {
    const ph = i % 15;
    K.stove(ctx, i);
    const at = K.pan(ctx, ctx.hands[1]);
    K.food(ctx, at, AIR[ph]);
    if (ph >= 9 && ph <= 11) ctx.effects.rect(at.x + 45, at.y - 15, 5, 5, 'oilGold', 'oil');
  }
};
