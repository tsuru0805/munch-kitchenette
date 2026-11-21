// clawds-new-clothes · states/chores/dish-scrub.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ③搓:从盆里捞起一只脏盘子(正面朝外),左手扶着,右手拿海绵绕圈搓,泡泡直冒,脏点一块块没了,「啾」一下眯眼。
const D = require('./_dishkit.cjs');
const DX = 225;
const discY = (i) => (i < 4 ? 233 : i <= 7 ? [218, 203, 193, 183][i - 4] : i <= 36 ? 183 : i <= 40 ? [188, 198, 213, 233][i - 37] : 233);
const CIRCLE = [[240, 183], [250, 188], [250, 198], [240, 203], [230, 198], [230, 188]];
const DIRT = [[10, 5, 14], [20, 15, 22], [5, 20, 30]];    // [x, y, 第几帧搓掉]
module.exports = {
  id: 'dish-scrub', label: '搓', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const y = discY(i);
    let L = [70, 223], R = [235, 223];
    if (i >= 4 && i <= 40) { L = [210, Math.max(198, y + 15)]; R = i >= 8 && i <= 36 ? CIRCLE[Math.floor((i - 8) / 2) % 6] : [250, Math.max(198, y + 15)]; }
    if (i === 41) { L = [140, 233]; }
    const lean = i >= 10 && i <= 34;
    return {
      dx: lean ? 5 : 0,
      hands: [D.HL(L[0], L[1], lean ? 5 : 0), D.HR(R[0], R[1], lean ? 5 : 0)],
      gazeX: 5, gazeY: 5,
      eyes: i >= 30 && i <= 33 ? 'closed' : (closedAt(19) ? 'closed' : 'open'),
      tool: i >= 30 && i <= 33 ? { blush: true } : {}
    };
  },
  paint(ctx, p, i) {
    D.sink(ctx, i, { dirty: 1, rack: 2, foam: 5 });
    const y = discY(i);
    if (y < 233) D.disc(ctx, DX, y, { dirt: DIRT.filter(([, , t]) => i < t).map(([x, yy]) => [x, yy]) });
    D.cuffs(ctx);
    if (i >= 8 && i <= 36) { const h = ctx.hands[1]; D.sponge(ctx, h.x, h.y + 2 - (h.y + 2) % 5); D.bubbles(ctx, i, h.x - 5, h.y - 5, 3); }
    if (i >= 30 && i <= 34) ctx.effects.pattern(['010', '111', '010'], 265, 170, 'goldLight', 5, 'squeak');
  }
};
