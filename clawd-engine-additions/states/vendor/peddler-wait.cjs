// clawds-new-clothes · states/vendor/peddler-wait.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ③等客(循环):站在台子后面,往右边路上看看、往左看看,眨眨眼,扶一下帽檐。
const S = require('./_stall.cjs');
const RH = [[0, 210, 223], [30, 210, 223], [33, 215, 203], [37, 215, 203], [40, 210, 223]];
module.exports = {
  id: 'peddler-wait', label: '小贩等客', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette,
  pose(i, { closedAt }) {
    return {
      hands: [S.HL(...S.L0), S.HR(...S.path(RH, i))],
      gazeX: S.within(i, 6, 14) ? -5 : S.within(i, 22, 28) ? 5 : 0,
      hatDrop: S.within(i, 34, 36) ? 5 : 0,
      eyes: closedAt(18) || closedAt(42) ? 'closed' : 'open'
    };
  }
};
