// clawds-new-clothes · states/vendor/buyer-pay.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 买方 ①付钱(循环,和 peddler-pay 同框;穿哪套厨师服由导出时定):站在车右边,左手捏着两枚硬币抬起来,硬币跳走后收手。
const S = require('./_stall.cjs');
const LH = [[0, 70, 223], [4, 65, 208], [16, 65, 208], [22, 70, 223]];
module.exports = {
  id: 'buyer-pay', label: '买方付钱', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette,
  pose(i, { closedAt }) {
    return { hands: [S.HL(...S.path(LH, i)), S.HR(...S.R0)], gazeX: -5, eyes: closedAt(30) ? 'closed' : 'open' };
  }
};
