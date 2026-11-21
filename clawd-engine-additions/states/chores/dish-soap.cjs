// clawds-new-clothes · states/chores/dish-soap.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ②挤洗洁精:从台上拿起绿瓶子,倒过来对着盆捏三下(瓶身一瘪、一滴落下去、盆里泡泡越冒越多),放回去。
const D = require('./_dishkit.cjs');
const RH = [[0, 235, 223], [4, 235, 223], [8, 285, 213], [10, 285, 213], [14, 245, 188], [30, 245, 188], [34, 285, 213], [36, 285, 213], [41, 235, 223]];
const SQ = [17, 22, 27];                       // 捏的那三帧
module.exports = {
  id: 'dish-soap', label: '挤洗洁精', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let [rx, ry] = D.path(RH, i);
    const sq = SQ.some((f) => i === f || i === f + 1);
    if (sq) ry += 5;
    return {
      squash: sq ? 5 : 0,
      hands: [D.HL(...D.LEFT0), D.HR(rx, ry)],
      gazeX: 5, gazeY: i >= 12 && i <= 31 ? 0 : 5,
      eyes: i >= 28 && i <= 31 ? 'closed' : (closedAt(6) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    const held = i >= 10 && i <= 34;
    const foam = Math.min(6, 2 + SQ.filter((f) => i > f + 2).length * 1 + (i > 29 ? 1 : 0));
    D.sink(ctx, i, { dirty: 2, rack: 2, foam: i > 41 ? 2 : foam, bottle: !held });
    D.cuffs(ctx);
    if (held) D.bottleHeld(ctx, ctx.hands[1], SQ.some((f) => i === f || i === f + 1));
    // 每捏一下落一滴
    for (const f of SQ) { const k = i - f; if (k >= 1 && k <= 3) ctx.effects.rect(250, 213 + k * 5, 5, 5, 'soapGreen', 'drop'); }
    if (i >= 20 && i <= 40) D.bubbles(ctx, i, 235, 210, 3);
  }
};
