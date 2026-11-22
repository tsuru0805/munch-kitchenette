// clawds-new-clothes · states/vendor/peddler-bye.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ⑨送客(放一遍,和 buyer-walkout 同框):右手举起来摆一摆,目送他走,再转回来看街上。末帧 = peddler-wait / peddler-call 的首帧。
const S = require('./_stall.cjs');
module.exports = {
  id: 'peddler-bye', label: '小贩送客', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    let r = S.R0;
    if (S.within(i, 3, 20)) r = (Math.floor((i - 3) / 3) % 2) ? [235, 193] : [225, 198];
    else if (S.within(i, 21, 23)) r = [215, 213];
    return { hands: [S.HL(...S.L0), S.HR(...r)], gazeX: i <= 26 ? 5 : 0, eyes: S.within(i, 30, 31) ? 'closed' : 'open' };
  }
};
