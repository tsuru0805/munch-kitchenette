// clawds-new-clothes · states/chores/vendor-call.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩交接 ①叫住:站在窗边,举手朝窗外挥、冒一个「!」,蹦两下;窗外伸进来一只手朝他摆摆(小贩不画形象,只露手和篷)。
const D = require('./_dishkit.cjs');
const RH = [[0, 210, 223], [4, 210, 223], [7, 225, 173], [23, 225, 173], [27, 220, 213], [37, 220, 213], [41, 210, 223]];
module.exports = {
  id: 'vendor-call', label: '叫住小贩', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let [x, y] = D.path(RH, i);
    const wave = i >= 8 && i <= 23;
    if (wave) x += (i % 4 < 2) ? 0 : 10;
    const hop = i === 10 || i === 11 || i === 18 || i === 19;
    const jump = hop ? -10 : 0;
    const happy = i >= 28 && i <= 33;
    return {
      jump, feet: hop ? [5, 0, 0, 5] : [0, 0, 0, 0],
      hands: [D.HL(...D.LEFT0), D.HR(x, y + jump)],
      gazeX: 5, gazeY: i >= 7 && i <= 23 ? -5 : 0,
      eyes: happy ? 'closed' : (closedAt(39) ? 'closed' : 'open'),
      tool: happy ? { blush: true } : {}
    };
  },
  paint(ctx, p, i) {
    D.windowFrame(ctx);
    // 「!」:举手那几帧冒在窗边、帽子右上
    if (i >= 8 && i <= 23) {
      const y = i < 10 ? 125 : 120;
      ctx.lettering.rect(240, y - 5, 20, 25, 'white', 'call-bubble'); ctx.lettering.rect(245, y, 10, 10, 'ink'); ctx.lettering.rect(245, y + 15, 10, 5, 'ink');
      ctx.lettering.rect(240, y + 20, 5, 5, 'white');
    }
    // 窗外伸进来的手:24 起伸进来,摆两下,35 起缩回去
    const tip = i < 24 ? 300 : i < 28 ? 300 - (i - 23) * 10 : i < 35 ? 260 : 260 + (i - 34) * 10;
    const bob = i >= 28 && i < 35 && i % 4 < 2 ? -5 : 0;
    D.vendorHand(ctx, tip, 175 + bob);
  }
};
