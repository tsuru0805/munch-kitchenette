// clawds-new-clothes · states/chores/dish-break.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ⑧打碎一只(约二十只碎一只的分支):端起来的盘子一滑,往上一蹦,两只手手忙脚乱去接,没接住——掉在地上啪地碎成几片;
// 愣住(小方点眼、冒汗),然后不好意思地挠挠头。放一遍停在末帧(碎片留在地上)。
const D = require('./_dishkit.cjs');
// 盘子的飞行:[x, y, 'h' 横 / 'd' 斜 / 'v' 竖]
const FLY = { 9: [235, 193, 'h'], 10: [240, 178, 'd'], 11: [245, 168, 'v'], 12: [245, 173, 'd'], 13: [240, 183, 'h'], 14: [245, 178, 'd'], 15: [250, 188, 'v'],
  16: [245, 183, 'd'], 17: [250, 193, 'h'], 18: [255, 208, 'd'], 19: [255, 228, 'v'], 20: [250, 248, 'd'], 21: [250, 263, 'h'] };
const SHARDS = [[-20, -10, -5], [-10, -20, 0], [5, -25, 5], [20, -15, 10], [30, -5, 0]];   // [终点 dx, 最高点, 落点 dx 偏移]
module.exports = {
  id: 'dish-break', label: '打碎了', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let L = [70, 223], R = [235, 223], eyes = closedAt(3) ? 'closed' : 'open', jump = 0, squash = 0, gy = 5, gx = 5, tool = {};
    if (i >= 4 && i <= 8) { L = [215, [233, 223, 213, 208, 208][i - 4]]; R = [255, [233, 223, 213, 208, 208][i - 4]]; }
    if (i >= 9 && i <= 20) {                                    // 手忙脚乱
      const k = i % 4; L = [k < 2 ? 210 : 225, k < 2 ? 188 : 203]; R = [k < 2 ? 260 : 245, k < 2 ? 203 : 188];
      eyes = 'dot'; gy = 0; jump = i === 13 || i === 14 ? -10 : 0;
    }
    if (i >= 21 && i <= 23) { L = [205, 198]; R = [250, 198]; eyes = 'closed'; squash = 10; }      // 啪!
    if (i >= 24 && i <= 32) { L = [70, 223]; R = [225, 223]; eyes = 'dot'; gy = 5; gx = 5; }
    if (i >= 33) { L = [70, 223]; R = [210, i % 4 < 2 ? 193 : 198]; eyes = 'closed'; gx = 0; gy = 0; tool = { blush: true }; }
    return { jump, squash, feet: jump ? [5, 0, 0, 5] : [0, 0, 0, 0], hands: [D.HL(L[0], L[1] + jump), D.HR(R[0], R[1] + jump)], eyes, gazeX: gx, gazeY: gy, tool };
  },
  paint(ctx, p, i) {
    D.sink(ctx, i, { dirty: 1, rack: 2, foam: 3 });
    const [l, r] = ctx.hands;
    if (i >= 4 && i <= 8) D.edge(ctx, l.x + 10, l.y + 5, 'letter', r.x - l.x);
    const f = FLY[i];
    if (f) {
      const [x, y, k] = f, E = ctx.effects;
      if (k === 'h') { E.rect(x, y, 30, 5, 'bowlWhite', 'falling'); E.rect(x + 5, y + 5, 20, 5, 'plateEdge'); }
      else if (k === 'v') { E.rect(x + 10, y - 10, 5, 30, 'bowlWhite', 'falling'); E.rect(x + 15, y - 5, 5, 20, 'plateEdge'); }
      else { E.pattern(['00011', '00110', '01100', '11000'], x, y - 5, 'bowlWhite', 5, 'falling'); E.pattern(['00001', '00010', '00100', '01000'], x, y, 'plateEdge', 5); }
    }
    const g = ctx.baseline;
    if (i >= 21) {
      const t = Math.min(1, (i - 21) / 5);
      SHARDS.forEach(([ex, top], n) => {
        const x = 255 + Math.round(ex * t / 5) * 5, arc = t < 1 ? Math.round(top * Math.sin(Math.PI * t) / 5) * 5 : 0;
        ctx.effects.rect(x, g - 5 + arc, n % 2 ? 5 : 10, 5, n % 2 ? 'plateEdge' : 'bowlWhite', 'shard');
      });
      if (i <= 23) { ctx.effects.pattern(['10001', '01010', '00000', '01010', '10001'], 245, g - 35, 'goldLight', 5, 'crash'); }
    }
    if (i >= 25 && i <= 40) { const k = (i - 25) % 8; ctx.effects.rect(220, 180 + k * 3 - (k * 3) % 5, 5, 10, 'blue', 'sweat'); }
    D.cuffs(ctx);
  },
  seamStep: 30,   // 放一遍的段;循环时最后挠头那只手回到水槽边是一大步
  check: { airborne: [] }
};
