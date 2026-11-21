// clawds-new-clothes · states/chores/machine-load.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 洗碗机 ①放盘子:洗碗机门放倒开着,机顶摞着三只脏盘子;他一只一只拿下来、竖着插进架子里(架上一只一只多出来),插完拍拍手。
const D = require('./_dishkit.cjs');
const C0 = 2, CL = 13;                                   // 第一只从第 2 帧起,一只 13 帧
function phase(i) { const c = Math.floor((i - C0) / CL), k = (i - C0) % CL; return i < C0 || c > 2 ? null : { c, k }; }
module.exports = {
  id: 'machine-load', label: '放进洗碗机', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const ph = phase(i);
    let R = [235, 223];
    if (ph) R = D.path([[0, 235, 223], [3, 265, 178 - ph.c * 0], [5, 265, 178], [8, 245, 228], [10, 245, 233], [12, 235, 223]], ph.k);
    const clap = i >= 41 && i <= 44;
    return {
      hands: [D.HL(...D.LEFT0), D.HR(R[0], R[1])],
      gazeX: 5, gazeY: ph && ph.k >= 2 && ph.k <= 5 ? -5 : 5,
      eyes: clap ? 'closed' : (closedAt(16) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    const ph = phase(i);
    const placed = i < C0 ? 0 : ph ? ph.c + (ph.k >= 10 ? 1 : 0) : 3;
    const taken = i < C0 ? 0 : ph ? ph.c + (ph.k >= 4 ? 1 : 0) : 3;
    D.washer(ctx, { door: 'open', rack: placed, stack: 3 - taken });
    if (ph && ph.k >= 4 && ph.k <= 9) { const h = ctx.hands[1]; if (ph.k < 8) D.edge(ctx, h.x - 10, h.y + 10, 'letter', 35, true); else { ctx.letter.rect(h.x + 5, h.y - 5, 5, 25, 'bowlWhite', 'plate-in'); ctx.letter.rect(h.x + 10, h.y - 5, 5, 25, 'plateEdge'); } }
    if (i >= 41 && i <= 44) ctx.effects.pattern(['010', '111', '010'], 225, 175, 'goldLight', 5, 'done');
  }
};
