// clawds-new-clothes · states/chores/dish-shake.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ⑤甩水:两手横端着冲好的盘子,左右使劲甩(身子跟着晃、眯着眼),水珠往两边飞;停下来歪头看一眼、亮一下,放回去。
const D = require('./_dishkit.cjs');
const plateY = (i) => (i < 4 ? 238 : i <= 7 ? [228, 218, 213, 208][i - 4] : i <= 38 ? 208 : i <= 41 ? [218, 228, 238][i - 39] : 238);
module.exports = {
  id: 'dish-shake', label: '甩水', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const shaking = i >= 9 && i <= 28;
    const s = shaking ? [-10, 0, 10, 0][i % 4] : 0;
    const dx = shaking ? (i % 4 === 0 ? -5 : i % 4 === 2 ? 5 : 0) : 0;
    const y = plateY(i);
    let L = [70, 223], R = [235, 223];
    if (i >= 4 && i <= 41) { L = [215 + s, y - 5]; R = [260 + s, y - 5]; }
    const look = i >= 31 && i <= 36;
    return {
      dx, squash: shaking && i % 2 ? 5 : 0,
      hands: [D.HL(L[0], L[1], dx), D.HR(R[0], R[1], dx)],
      gazeX: 5, gazeY: look ? 5 : 0, hatTilt: look ? 0 : 0,
      eyes: shaking ? 'closed' : (closedAt(40) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    D.sink(ctx, i, { dirty: 1, rack: 2, foam: 4 });
    const [l, r] = ctx.hands;
    if (i >= 4 && i <= 41) D.edge(ctx, l.x + 10, l.y + 5, 'letter', r.x - l.x);
    D.cuffs(ctx);
    if (i >= 9 && i <= 30) for (let n = 0; n < 4; n++) {
      const ph = (i - 9 + n * 2) % 6, side = n % 2 ? 1 : -1;
      const x = side < 0 ? l.x - 5 - ph * 5 : r.x + 20 + ph * 5, yy = l.y - 5 - (ph < 3 ? ph * 5 : (6 - ph) * 5);
      if (x >= 0 && x < 300 && (side > 0 || x < 70 || x > 210)) ctx.effects.rect(x, yy, 5, 5, n < 2 ? 'blue' : 'waterLight', 'fling');
    }
    if (i >= 33 && i <= 37) ctx.effects.pattern(['010', '111', '010'], r.x + 25, l.y - 20, 'goldLight', 5, 'shine');
  }
};
