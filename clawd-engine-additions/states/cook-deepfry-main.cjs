// clawds-new-clothes · states/cook-deepfry-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require("./_kitchen.cjs");
// 炸:0–9 长筷子夹着一块举在油锅上;10–13 放下去;14–29 油泡翻滚,筷子在锅里拨;30–33 夹出来(炸成金黄);34–44 举着看,眯眼
module.exports = {
  id: 'cook-deepfry-main', label: '炸', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i) {
    const ry = i < 10 ? 193 : i < 14 ? [198, 203, 208, 213][i - 10] : i < 30 ? (i % 4 < 2 ? 213 : 208) : i < 34 ? [208, 203, 198, 193][i - 30] : 193;
    return { jump: i === 36 ? -5 : 0, hands: [{ x: 80, y: 218 }, { x: 215, y: ry }], gazeX: 5, gazeY: i >= 34 ? 0 : 5, eyes: i >= 37 && i <= 42 ? 'closed' : 'open' };
  },
  paint(ctx, p, i) {
    K.oilPot(ctx, i, i >= 12 && i < 32);
    K.chopsticks(ctx, ctx.hands[1], i < 13 ? 'bunWhite' : i >= 31 ? 'friedGold' : null);
  }
};
