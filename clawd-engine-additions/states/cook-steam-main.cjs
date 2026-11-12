// clawds-new-clothes · states/cook-steam-main.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require("./_kitchen.cjs");
// 蒸:蒸笼摞两屉一直冒白汽。0–19 守着;20–23 伸手到盖钮;24–34 掀开(白汽扑出来、露出三个白馒头),眯眼笑;35–38 盖回去;39–44 守着
module.exports = {
  id: 'cook-steam-main', label: '蒸', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i, { closedAt }) {
    const open = i >= 24 && i <= 34;
    const ry = i < 20 ? 218 : i < 24 ? [213, 208, 203, 198][i - 20] : open ? 178 : i <= 38 ? [183, 188, 193, 198][i - 35] : 218;
    const rx = i < 20 || i > 38 ? 225 : 235;
    return { hands: [{ x: 80, y: 218 }, { x: rx, y: ry }], gazeX: 5, gazeY: open ? 5 : 0, eyes: (i >= 25 && i <= 27) || (i >= 30 && i <= 34) || closedAt(8) ? 'closed' : 'open' };
  },
  paint(ctx, p, i) {
    const g = ctx.baseline, h = ctx.hands[1];
    const held = i >= 22 && i <= 38, open = i >= 24 && i <= 34;
    K.steamer(ctx, open);
    if (held) K.steamerLid(ctx, h.x - 20, h.y + 30); else K.steamerLid(ctx, 220, g - 55);
    for (let n = 0; n < 3; n++) {
      const ph = (i + n * 5) % 15;
      K.puff(ctx, 215 + n * 30 + (ph % 2 ? 5 : 0), g - 75 - ph * 5, open ? 2 : (ph < 5 ? 0 : 1));
    }
  }
};
