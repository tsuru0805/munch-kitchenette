// clawds-new-clothes · states/chores/machine-run.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 洗碗机 ④转着(循环):机器一下一下轻轻抖、小窗里水在转、灯一闪一闪、顶上冒热气;他在旁边等,身子跟着晃,中间凑过去看一眼。整段无缝循环。
const D = require('./_dishkit.cjs');
module.exports = {
  id: 'machine-run', label: '洗碗机转着', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    const peek = i >= 24 && i <= 33;
    const dx = peek ? 5 : (Math.floor(i / 9) % 2 ? 5 : 0) * 0;
    const sway = !peek && i % 15 >= 8 ? 5 : 0;
    return {
      dx: peek ? 5 : 0,
      hands: [D.HL(D.LEFT0[0] + (peek ? 5 : 0), D.LEFT0[1], dx), D.HR(peek ? 230 : 235, peek ? 218 : 223, dx)],
      gazeX: 5, gazeY: peek ? 5 : 0, hatDrop: sway,
      eyes: sway ? 'half' : (closedAt(12) ? 'closed' : 'open')
    };
  },
  paint(ctx, p, i) {
    D.washer(ctx, { door: 'closed', light: i % 6 < 3 ? 'on' : 'off', swirl: i, shake: i % 3 === 0 ? 5 : 0 });
    const g = ctx.baseline;
    // 机身两侧的抖动线
    if (i % 3 === 0) { ctx.effects.rect(215, g - 50, 5, 5, 'smokeLight', 'buzz'); ctx.effects.rect(215, g - 30, 5, 5, 'smokeLight'); }
    // 顶上冒热气:15 帧一缕,三缕一圈
    for (let m = 0; m < 2; m++) { const ph = (i + m * 7) % 15; if (ph < 10) ctx.effects.rect(225 + m * 10 + (Math.floor(ph / 3) % 2) * 5, g - 75 - ph * 5, 5, 5, 'puffWhite', 'steam'); }
  }
};
