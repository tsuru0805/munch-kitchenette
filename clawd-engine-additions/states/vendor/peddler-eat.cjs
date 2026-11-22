// clawds-new-clothes · states/vendor/peddler-eat.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ⑦看着他吃(放一遍,和 buyer-eat 同框):站着看,他咬下去那会儿眯眼笑、点一下头。
const S = require('./_stall.cjs');
module.exports = {
  id: 'peddler-eat', label: '小贩看他吃', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    return { hands: [S.HL(...S.L0), S.HR(...S.R0)], gazeX: 5, eyes: S.within(i, 20, 26) ? 'closed' : 'open', hatDrop: S.within(i, 21, 24) ? 5 : 0 };
  }
};
