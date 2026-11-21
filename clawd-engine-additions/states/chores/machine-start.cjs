// clawds-new-clothes · states/chores/machine-start.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 洗碗机 ③按按钮:抬手「嘀」地按下面板上的红钮,灯亮成绿的、小窗里水转起来;他高兴得原地蹦两下,然后站好看着。
const D = require('./_dishkit.cjs');
module.exports = {
  id: 'machine-start', label: '按按钮', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let R = D.path([[0, 235, 223], [4, 235, 223], [9, 275, 188], [11, 275, 193], [13, 275, 188], [18, 235, 223]], i);
    const hops = { 21: -15, 22: -15, 27: -10, 28: -10 };
    const jump = hops[i] || 0;
    const happy = i >= 20 && i <= 30;
    return {
      jump, feet: jump ? [5, 0, 0, 5] : [0, 0, 0, 0], squash: i === 23 || i === 29 ? 5 : 0,
      hands: [D.HL(D.LEFT0[0], D.LEFT0[1] + jump), D.HR(R[0], R[1] + jump)],
      gazeX: 5, gazeY: i >= 5 && i <= 14 ? -5 : 5,
      eyes: happy ? 'closed' : (closedAt(38) ? 'closed' : 'open'), tool: happy ? { blush: true } : {}
    };
  },
  paint(ctx, p, i) {
    const on = i >= 11;
    D.washer(ctx, { door: 'closed', light: on ? 'on' : 'off', swirl: i >= 16 ? i : null });
    if (i >= 11 && i <= 15) { const E = ctx.effects; E.rect(280, 175, 5, 5, 'lightOn', 'beep'); E.rect(290, 170, 5, 5, 'lightOn'); E.rect(290, 180, 5, 5, 'lightOn'); }
  }
};
