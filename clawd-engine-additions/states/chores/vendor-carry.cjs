// clawds-new-clothes · states/chores/vendor-carry.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩交接 ④捧着回来:纸袋抱在胸前,一颠一颠往回走(原地踏步,接入方要横移自己挪),眯眼脸红、头顶冒小心。整段无缝循环。
const D = require('./_dishkit.cjs');
module.exports = {
  id: 'vendor-carry', label: '捧着回来', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i) {
    const k = i % 9, a = k < 5;                   // 一步 9 帧:前 5 帧左脚、后 4 帧右脚,45 帧正好 5 步
    const up = k === 2 || k === 7;                 // 每只脚落定前颠一下(首帧站稳在地上)
    const dx = Math.floor(i / 9) % 2 ? 5 : 0;
    const j = up ? -5 : 0;
    return {
      dx, jump: j, feet: a ? [5, 0, 5, 0] : [0, 5, 0, 5],
      hands: [D.HL(115 + dx, 238 + j, dx), D.HR(165 + dx, 238 + j, dx)],
      eyes: i >= 10 && i <= 34 ? 'closed' : 'open', gazeY: 0,
      tool: { blush: i >= 10 && i <= 34 }
    };
  },
  paint(ctx, p, i) {
    const [l, r] = ctx.hands;
    D.bag(ctx, Math.round((l.x + r.x) / 2 / 5) * 5 - 5, l.y - 5, 'letter', i);
    // 头顶右边一颗小心往上飘,15 帧一颗,三颗正好一圈
    const ph = i % 15;
    if (ph < 10) ctx.effects.pattern(['101', '111', '010'], 225 + (Math.floor(i / 15) % 2) * 10, 185 - ph * 5, 'red', 5, 'heart');
  },
  check: { airborne: [] }
};
