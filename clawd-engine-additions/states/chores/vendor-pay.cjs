// clawds-new-clothes · states/chores/vendor-pay.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩交接 ②递零花钱:右手捏着两枚硬币伸到窗台;窗外一只手摊开掌心伸进来,硬币一枚一枚跳过去,那只手攥起来缩回;他点点头。
const D = require('./_dishkit.cjs');
const RH = [[0, 210, 223], [3, 210, 223], [8, 235, 213], [26, 235, 213], [31, 220, 218], [38, 220, 218], [42, 210, 223]];
// 两枚硬币各自的路线:在手里 → 抛物线跳到对方掌心
function coinAt(n, i, hand) {
  const t0 = 12 + n * 5;                         // 第 n 枚起跳的帧
  const hx = hand.x + 5, hy = hand.y - 10 + n * 0;
  if (i < t0) return { x: hx - n * 5, y: hy - n * 5, where: 'his' };
  const k = i - t0;
  if (k >= 4) return { x: 265, y: 208 - n * 5, where: 'theirs' };
  const xs = [hx + 5, 250, 260, 265], ys = [hy - 10, hy - 15, hy - 10, 208 - n * 5];
  return { x: Math.round(xs[k] / 5) * 5, y: Math.round(ys[k] / 5) * 5, where: 'air' };
}
module.exports = {
  id: 'vendor-pay', label: '递零花钱', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const [x, y] = D.path(RH, i);
    const nod = i >= 26 && i <= 29;
    return {
      hands: [D.HL(...D.LEFT0), D.HR(x, y)],
      gazeX: 5, gazeY: nod ? 5 : 0, hatDrop: nod ? 5 : 0,
      eyes: i >= 31 && i <= 35 ? 'closed' : (closedAt(9) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    D.windowFrame(ctx);
    const h = ctx.hands[1];
    // 窗外的手:6 起伸进来摊开,22 攥起来,24 起缩回
    const tip = i < 6 ? 300 : i < 10 ? 300 - (i - 5) * 10 : i < 24 ? 260 : 260 + (i - 23) * 10;
    const closed = i >= 22;
    D.vendorHand(ctx, tip, 205, { open: !closed });
    for (let n = 0; n < 2; n++) {
      const c = coinAt(n, i, h);
      if (c.where === 'his' && i <= 26) D.coin(ctx, c.x, c.y);
      else if (c.where === 'air') { D.coin(ctx, c.x, c.y, 'effects'); if (i % 2 === 0) ctx.effects.pattern(['010', '111', '010'], c.x + 10, c.y - 15, 'goldLight', 5, 'chink'); }
      else if (c.where === 'theirs' && !closed) D.coin(ctx, c.x, c.y, 'effects');
    }
    if (i >= 27 && i <= 33) ctx.effects.pattern(['101', '111', '010'], 245, 180 - (i - 27) * 5, 'red', 5, 'heart');
  }
};
