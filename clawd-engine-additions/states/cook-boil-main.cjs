// clawds-new-clothes · states/cook-boil-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require("./_kitchen.cjs");
// 煮:0–17 盖着咕嘟,锅盖被顶得一跳一跳、两边漏白汽;18–21 伸手捏住盖钮;22–36 掀开,一大团汽扑上来(熏得闭眼),凑过去看;37–40 盖回去;41–44 接着咕嘟
module.exports = {
  id: 'cook-boil-main', label: '煮', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i) {
    const open = i >= 22 && i <= 36;
    const ry = i < 18 ? 218 : i < 22 ? [213, 208, 203, 198][i - 18] : open ? 183 : i <= 40 ? [188, 193, 198, 203][i - 37] : 218;
    const rx = i < 18 || i > 40 ? 225 : 235;
    return { dx: open && i >= 28 ? 5 : 0, hands: [{ x: 80, y: 218 }, { x: rx, y: ry }], gazeX: 5, gazeY: 5, eyes: i >= 23 && i <= 27 ? 'closed' : 'open' };
  },
  paint(ctx, p, i) {
    const g = ctx.baseline, h = ctx.hands[1];
    K.pot(ctx);
    const held = i >= 20 && i <= 40;
    if (held) K.lid(ctx, h.x - 20, h.y + 30);
    else {
      const hop = i % 6 < 2 ? 5 : 0;
      K.lid(ctx, 220, g - 45 - hop);
      if (hop) { K.puff(ctx, 205, g - 60, 0); K.puff(ctx, 290, g - 60, 0); }
    }
    if (i >= 22 && i <= 36) { const t = i - 22; K.puff(ctx, 240, g - 65 - t * 5, t < 3 ? 1 : 2); if (t > 4) K.puff(ctx, 265, g - 55 - (t - 4) * 5, 1); }
  }
};
