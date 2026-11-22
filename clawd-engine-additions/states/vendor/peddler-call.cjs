// clawds-new-clothes · states/vendor/peddler-call.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ②吆喝摇铃(循环):左手在台面上方举起铜铃摇,眯着眼一颠一颠,帽顶冒音符(铃和音符在 _stall 的场景里画)。
const S = require('./_stall.cjs');
const LH = [[0, 70, 223], [3, 50, 198], [38, 50, 198], [42, 70, 223]];
module.exports = {
  id: 'peddler-call', label: '小贩吆喝摇铃', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette,
  pose(i) {
    const hop = [12, 13, 20, 21, 28, 29].includes(i);
    return { hands: [S.HL(...S.path(LH, i)), S.HR(...S.R0)], eyes: S.within(i, 8, 30) ? 'closed' : 'open', jump: hop ? -5 : 0, gazeX: S.within(i, 33, 40) ? 5 : 0 };
  },
  check: { airborne: [[12, 13], [20, 21], [28, 29]] }
};
