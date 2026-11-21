// clawds-new-clothes · states/chores/vendor-take.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩交接 ③接过东西:窗外的手拎着一只冒热气的纸袋伸进来,他两只手一起去接,抱到胸前、星星眼、冒一颗小心。
const D = require('./_dishkit.cjs');
const RH = [[0, 210, 223], [10, 210, 223], [15, 235, 218], [21, 235, 218], [27, 165, 238], [44, 165, 238]];   // 末了和「捧着回来」首帧同一个抱法
const LH = [[0, 70, 223], [10, 70, 223], [13, 120, 243], [15, 200, 243], [21, 200, 243], [27, 115, 238], [44, 115, 238]];  // 横过身子时走眼睛下面
module.exports = {
  id: 'vendor-take', label: '接过东西', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  // 放一遍、接「捧着回来」的段(末帧=捧着回来首帧的抱法);引擎体检会报一条「接缝」,是预期内的:这段不拿来循环
  pose(i, { closedAt }) {
    const [rx, ry] = D.path(RH, i), [lx, ly] = D.path(LH, i);
    const glad = i >= 28;
    const hop = i === 30 || i === 31;
    return {
      jump: hop ? -10 : 0,
      hands: [D.HL(lx, ly + (hop ? -10 : 0)), D.HR(rx, ry + (hop ? -10 : 0))],
      gazeX: glad ? 0 : 5, gazeY: 0,
      eyes: glad ? (i >= 36 && i <= 40 ? 'closed' : 'star') : (closedAt(6) ? 'closed' : 'open'),
      tool: glad ? { blush: true, ...(i >= 33 ? { miniHeart: { x: 230, y: 190 - Math.min(4, i - 33) * 5 } } : {}) } : {}
    };
  },
  paint(ctx, p, i) {
    D.windowFrame(ctx);
    const [l, r] = ctx.hands;
    // 窗外的手拎着袋子:3 起伸进来,到窗台停住;21 他接住,22 起那只手空着缩回
    const tip = i < 3 ? 300 : i < 8 ? 300 - (i - 2) * 8 : i < 22 ? 260 : 260 + (i - 21) * 10;
    const tipQ = Math.round(tip / 5) * 5;
    if (i < 22) D.bag(ctx, tipQ - 15, 195, 'props', i);
    D.vendorHand(ctx, tipQ - 10, 185);
    if (i >= 22) {
      // 在他手里:两手中间
      // 同「捧着回来」:袋子在两手正中;往胸前收的路上压在眼睛下面走,热气只在抱稳以后冒(冒在两眼之间)
      const bx = Math.round((l.x + r.x) / 2 / 5) * 5 - 5, by = Math.max(l.y - 5, 233);
      D.bag(ctx, bx, by, 'letter', i >= 28 ? i : null);
    }
  }
};
