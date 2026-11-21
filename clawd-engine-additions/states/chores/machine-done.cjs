// clawds-new-clothes · states/chores/machine-done.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 洗碗机 ⑤洗好开门:灯一跳变成金色「叮」,他拉住把手把门放倒,一大团热气扑出来(熏得往后一仰、眯眼),
// 汽散了露出一排亮晶晶的盘子,他星星眼蹦一下。放一遍停在末帧(门开着、盘子闪着)。
const D = require('./_dishkit.cjs');
module.exports = {
  id: 'machine-done', label: '洗好开门', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let R = [235, 223], dx = 0, eyes = closedAt(2) ? 'closed' : 'open', gx = 5, gy = 5, jump = 0, tool = {};
    if (i >= 5 && i <= 8) gy = -5;
    if (i >= 9 && i <= 16) R = [[240, 218], [245, 213], [245, 213], [245, 228], [245, 243], [245, 253], [240, 248], [235, 233]][i - 9];
    if (i >= 17 && i <= 25) { dx = -5; eyes = 'closed'; R = [230, 218]; }
    if (i >= 26) { eyes = 'star'; gx = 5; gy = 5; tool = { blush: true }; }
    if (i === 30 || i === 31) jump = -10;
    return { dx, jump, feet: jump ? [5, 0, 0, 5] : [0, 0, 0, 0], hands: [D.HL(D.LEFT0[0] + dx, D.LEFT0[1] + jump, dx), D.HR(R[0], R[1] + jump, dx)], gazeX: gx, gazeY: gy, eyes, tool };
  },
  paint(ctx, p, i) {
    const door = i < 12 ? 'closed' : i < 14 ? 'half' : 'open';
    D.washer(ctx, { door, rack: 3, light: i < 5 ? 'on' : 'done', swirl: i < 5 ? i : null });
    const g = ctx.baseline;
    if (i >= 5 && i <= 9) ctx.effects.pattern(['010', '111', '010'], 265, 180, 'lightDone', 5, 'ding');
    if (i >= 14 && i <= 27) { const t = i - 14; D.K.puff(ctx, 235, g - 60 - t * 5, t < 3 ? 1 : 2); if (t > 2) D.K.puff(ctx, 260, g - 50 - (t - 2) * 5, 1); }
    if (i >= 26) for (let k = 0; k < 3; k++) if ((i + k * 2) % 6 < 3) ctx.effects.pattern(['010', '111', '010'], 222 + k * 12 - (k * 12) % 5 + 3, g - 60 - (k % 2) * 10, 'goldLight', 5, 'shine');
  },
  check: { airborne: [] }
};
