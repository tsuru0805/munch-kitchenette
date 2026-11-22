// clawds-new-clothes · states/vendor/peddler-greet.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ⑧迎客(放一遍,和 buyer-walkin 同框):先站着等,买方走到车边时转过来看他、点一下头。末帧 = peddler-pay 的首帧。
const S = require('./_stall.cjs');
module.exports = {
  id: 'peddler-greet', label: '小贩迎客', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i, { closedAt }) {
    const nod = S.within(i, 24, 26);
    return { hands: [S.HL(...S.L0), S.HR(...S.R0)], gazeX: i >= 12 ? 5 : 0, hatDrop: nod ? 5 : 0, eyes: nod || closedAt(6) ? 'closed' : 'open' };
  }
};
