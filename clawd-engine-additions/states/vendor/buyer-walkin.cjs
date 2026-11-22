// clawds-new-clothes · states/vendor/buyer-walkin.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 买方 ⓪走过去(放一遍,和 peddler-greet 同框):侧着身子从画面右边走到车边(0–19 帧,每帧 10,脚踩实不滑),
// 停下压一下,眨眼转过来,看看台面上的东西。末帧 = buyer-pay 的首帧。身子画成朝右,场景里左右翻成朝左(tool.facing)。
const S = require('./_stall.cjs');
module.exports = {
  id: 'buyer-walkin', label: '买方走过去', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    if (i <= 20) {
      const walk = i < S.WALK_STEPS ? S.stride(i) : { footOffsets: [0, 0, 0, 0], feet: [0, 0, 0, 0] };
      const sw = i < S.WALK_STEPS ? S.armSwing(i) : 0;
      return { side: true, ...walk, squash: i === 20 ? 5 : 0, hands: [S.HL(70 + sw, 223), S.HR(210 - sw, 223)], tool: { facing: 'left' } };
    }
    return { hands: [S.HL(...S.L0), S.HR(...S.R0)], eyes: i === 21 ? 'closed' : 'open', gazeX: -5, gazeY: S.within(i, 28, 33) ? 5 : 0 };
  }
};
