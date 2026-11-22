// clawds-new-clothes · states/vendor/peddler-pay.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ⑤收钱(循环,和 buyer-pay 同框):右手抬到台面上接硬币,收到台面下面(叮一声),点一下头。
const S = require('./_stall.cjs');
const RH = [[0, 210, 223], [2, 210, 223], [6, 225, 213], [16, 225, 213], [19, 225, 238], [22, 225, 238], [25, 210, 223]];
module.exports = {
  id: 'peddler-pay', label: '小贩收钱', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette,
  pose(i, { closedAt }) {
    const nod = S.within(i, 23, 26);
    return { hands: [S.HL(...S.L0), S.HR(...S.path(RH, i))], gazeX: 5, hatDrop: nod ? 5 : 0, eyes: nod || closedAt(36) ? 'closed' : 'open' };
  }
};
