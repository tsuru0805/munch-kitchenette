// clawds-new-clothes · states/chores/dish-dry.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ⑥擦干:左手扶着正面的盘子,右手拿红道毛巾一圈圈擦,水珠一颗颗没了;擦完盘子亮一下,他眯眼得意。
const D = require('./_dishkit.cjs');
const DX = 225;
const discY = (i) => (i < 4 ? 233 : i <= 7 ? [218, 203, 193, 183][i - 4] : i <= 37 ? 183 : i <= 40 ? [198, 213, 233][i - 38] : 233);
const WIPE = [[230, 183], [245, 183], [255, 193], [245, 203], [230, 203], [225, 193]];
const DROPS = [[5, 10, 13], [25, 10, 19], [15, 25, 25], [25, 20, 29]];
module.exports = {
  id: 'dish-dry', label: '擦干', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const y = discY(i);
    let L = [70, 223], R = [235, 223];
    if (i >= 4 && i <= 40) { L = [210, Math.max(198, y + 15)]; R = i >= 8 && i <= 31 ? WIPE[Math.floor((i - 8) / 2) % 6] : [255, Math.max(198, y + 15)]; }
    const proud = i >= 33 && i <= 37;
    return {
      hands: [D.HL(...L), D.HR(...R)],
      gazeX: proud ? 0 : 5, gazeY: proud ? 0 : 5,
      eyes: proud ? 'closed' : (closedAt(21) ? 'closed' : 'open'),
      tool: proud ? { blush: true } : {}
    };
  },
  paint(ctx, p, i) {
    D.sink(ctx, i, { dirty: 1, rack: 2, foam: 3 });
    const y = discY(i);
    if (y < 233) D.disc(ctx, DX, y, { drops: DROPS.filter(([, , t]) => i < t).map(([x, yy]) => [x, yy]) });
    D.cuffs(ctx);
    if (i >= 8 && i <= 31) { const h = ctx.hands[1]; D.towel(ctx, h.x + 5, h.y - 5); }
    if (i >= 32 && i <= 37) { const k = (i - 32) % 3; ctx.effects.pattern(k === 1 ? ['01010', '00100', '11111', '00100', '01010'].map((r) => r.replace(/0/g, '0')) : ['010', '111', '010'], 255, 165, 'goldLight', 5, 'shine'); }
  }
};
