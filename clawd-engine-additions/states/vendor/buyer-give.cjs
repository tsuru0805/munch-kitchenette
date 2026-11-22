// clawds-new-clothes · states/vendor/buyer-give.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 买方 ②接过来(放一遍,和 peddler-give 同框):左手抬起来,第 18 帧接住,捧到胸前;眯眼脸红、蹦两下,头顶冒小心。
// 末帧 = buyer-eat 的首帧(东西捧在胸前)。
const S = require('./_stall.cjs');
const LH = [[0, 70, 223], [10, 70, 223], [15, 65, 208], [19, 65, 208], [25, 75, 208]];
module.exports = {
  id: 'buyer-give', label: '买方接过来', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    const happy = S.within(i, 26, 38), hop = [28, 29, 33, 34].includes(i);
    return { hands: [S.HL(...S.path(LH, i)), S.HR(...S.R0)], gazeX: happy ? 0 : -5, eyes: happy ? 'closed' : 'open', jump: hop ? -5 : 0, tool: { blush: S.within(i, 26, 40) } };
  },
  check: { airborne: [[28, 29], [33, 34]] }
};
