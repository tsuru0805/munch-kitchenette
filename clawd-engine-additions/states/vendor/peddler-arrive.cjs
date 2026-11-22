// clawds-new-clothes · states/vendor/peddler-arrive.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ①推车进场(放一遍):在车后面侧着身子,两手扶着台面,推着车从画面右边往左走进来(0–41 帧,每帧 10,
// 脚踩实不滑),刹住压一下,眨眼转过来面朝外,就站在台子后面开张。末帧 = 吆喝 / 等客的首帧。
// 身子画成朝右,场景里整张左右翻成朝左(tool.facing)。
const S = require('./_stall.cjs');
module.exports = {
  id: 'peddler-arrive', label: '小贩推车进场', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    if (i <= 42) {
      const walk = i <= S.ARRIVE_LAST_STEP ? S.stride(i) : { footOffsets: [0, 0, 0, 0], feet: [0, 0, 0, 0] };
      return { side: true, ...walk, squash: i === 42 ? 5 : 0, hands: [S.HL(205, 218), S.HR(225, 208)], tool: { facing: 'left' } };
    }
    return { eyes: i === 43 ? 'closed' : 'open', hands: [S.HL(...S.L0), S.HR(...S.R0)] };
  },
  check: { airborne: [] }
};
