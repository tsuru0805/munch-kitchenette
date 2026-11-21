// clawds-new-clothes · states/chores/dish-rinse.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ④冲:拧开水龙头,把满是泡沫的盘子举到水下,左右转着冲,泡沫顺着往下淌、水花溅起来(溅到脸上眯一下眼),冲干净关水。
const D = require('./_dishkit.cjs');
const discX = (i) => (i <= 12 ? 225 : i <= 34 ? 245 + ((Math.floor((i - 13) / 3) % 2) ? -5 : 0) : 225);
const discY = (i) => (i < 4 ? 233 : i <= 7 ? [218, 203, 193, 183][i - 4] : i <= 38 ? 183 : i <= 41 ? [198, 213, 233][i - 39] : 233);
module.exports = {
  id: 'dish-rinse', label: '冲', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const x = discX(i), y = discY(i);
    let L = [70, 223], R = [235, 223];
    if (i >= 8 && i <= 11) R = [285, 168];                         // 拧开水
    if (i >= 35 && i <= 37) R = [285, 168];                        // 关水
    if (i >= 4 && i <= 40) L = [x - 10, Math.max(198, y + 15)];
    if ((i >= 4 && i <= 7) || (i >= 12 && i <= 34) || (i >= 38 && i <= 40)) R = [x + 30, Math.max(198, y + 15)];
    const splash = i >= 20 && i <= 22;
    return {
      dx: splash ? -5 : 0,
      hands: [D.HL(L[0], L[1], splash ? -5 : 0), D.HR(R[0], R[1], splash ? -5 : 0)],
      gazeX: 5, gazeY: i >= 12 && i <= 34 ? 0 : 5,
      eyes: splash ? 'closed' : (closedAt(30) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    const on = i >= 10 && i <= 36;
    D.sink(ctx, i, { dirty: 1, rack: 2, foam: 5, stream: on });
    const y = discY(i);
    if (y < 233) {
      const suds = i < 16 ? [[5, 10], [20, 5], [15, 25], [25, 20]] : i < 24 ? [[15, 25], [25, 20]] : i < 30 ? [[20, 30]] : [];
      D.disc(ctx, discX(i), y, {});
      suds.forEach(([dx, dy]) => ctx.effects.rect(discX(i) + dx, y + dy, 5, 5, 'puffWhite', 'suds'));
    }
    D.cuffs(ctx);
    if (on && i >= 13 && i <= 34) {
      for (let n = 0; n < 3; n++) { const ph = (i + n * 2) % 4; ctx.effects.rect(235 + n * 25 + (ph % 2) * 5, 178 - ph * 5, 5, 5, 'waterLight', 'splash'); }
      if (i >= 19 && i <= 21) { ctx.effects.rect(200, 190, 5, 5, 'waterLight', 'splash-face'); ctx.effects.rect(210, 180, 5, 5, 'blue'); }
    }
  }
};
