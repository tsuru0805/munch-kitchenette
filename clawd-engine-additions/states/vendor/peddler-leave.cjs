// clawds-new-clothes · states/vendor/peddler-leave.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ④推车离开(放一遍):眨一下眼,侧过身扶住台面,推着车往左走出画面(脚踩实不滑,第 28 帧前后整个出去)。末帧是空着的路边。
const S = require('./_stall.cjs');
module.exports = {
  id: 'peddler-leave', label: '小贩推车离开', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    if (i <= 1) return { eyes: i === 1 ? 'closed' : 'open', hands: [S.HL(...S.L0), S.HR(...S.R0)] };
    const walk = i >= 3 ? S.stride(i - 3) : { footOffsets: [0, 0, 0, 0], feet: [0, 0, 0, 0] };
    return { side: true, ...walk, squash: i === 2 ? 5 : 0, hands: [S.HL(205, 218), S.HR(225, 208)], tool: { facing: 'left' } };
  }
};
