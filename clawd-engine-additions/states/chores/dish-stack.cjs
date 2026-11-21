// clawds-new-clothes · states/chores/dish-stack.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ⑦码好:从盆边拿起擦干的盘子,横端着往左挪两步,立进左边沥水架(架上多一只),拍拍、眯眼点头,走回水槽。
const D = require('./_dishkit.cjs');
const DXS = [[0, 0], [8, 0], [14, -20], [30, -20], [36, 0]];
function dxAt(i) { const [x] = D.path(DXS.map(([f, v]) => [f, v, 0]), i); return x; }
module.exports = {
  id: 'dish-stack', label: '码好', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const dx = dxAt(i);
    const walking = (i > 8 && i < 14) || (i > 30 && i < 36);
    let L = [70 + dx, 223], R = [235, 223];
    if (i >= 3 && i <= 7) R = [240, 208];                            // 去盆边拿
    if (i >= 8 && i <= 14) { L = [115 + dx, 238]; R = [165 + dx, 238]; }   // 横端在胸前
    if (i >= 15 && i <= 20) { L = [[95, 70, 50, 40, 40, 40][i - 15] + dx + 20, [243, 243, 233, 218, 208, 208][i - 15]]; R = [165 + dx, 238]; }
    if (i >= 21 && i <= 26) { L = [55, i % 2 ? 198 : 203]; R = [210 + dx, 223]; }            // 立进去、拍两下
    if (i >= 27 && i <= 30) { L = [70 + dx, 223]; R = [210 + dx, 223]; }
    if (i >= 31 && i <= 35) { R = [D.lerp(210 + dx, 235, (i - 30) / 6), 223]; }
    const nod = i >= 23 && i <= 27;
    return {
      dx, feet: walking ? (i % 2 ? [5, 0, 5, 0] : [0, 5, 0, 5]) : [0, 0, 0, 0],
      hands: [D.HL(L[0], L[1], dx), D.HR(R[0], R[1], dx)],
      gazeX: i >= 8 && i <= 30 ? -5 : 5, gazeY: nod ? 5 : (i >= 8 && i <= 30 ? 0 : 5), hatDrop: nod ? 5 : 0,
      eyes: nod ? 'closed' : (closedAt(40) ? 'closed' : 'open'),
      tool: nod ? { blush: true } : {}
    };
  },
  paint(ctx, p, i) {
    D.sink(ctx, i, { dirty: 1, rack: i >= 21 ? 3 : 2, foam: 3 });
    const [l, r] = ctx.hands;
    if (i >= 3 && i <= 7) D.edge(ctx, r.x - 15, r.y + 5, 'letter', 35);
    if (i >= 8 && i <= 14) D.edge(ctx, l.x + 5, l.y + 5, 'letter', r.x - l.x + 10);
    if (i >= 15 && i <= 20) D.edge(ctx, l.x - 5, l.y + 5, 'letter', 35);
    if (i >= 22 && i <= 25) ctx.effects.pattern(['010', '111', '010'], 35, 180, 'goldLight', 5, 'shine');
    D.cuffs(ctx);
  }
};
