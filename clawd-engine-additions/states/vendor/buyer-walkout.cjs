// clawds-new-clothes · states/vendor/buyer-walkout.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 买方 ④走回去(放一遍,和 peddler-bye 同框):捧着买到的东西(或者空着手:退了款、没扣成),点一下头,
// 侧过身往画面右边走出去(每帧 10,脚踩实不滑;第 18 帧前后整个出去)。首帧 = buyer-eat / buyer-give 的末帧。
// 侧身时东西拿在前面那只手上(场景里画)。
const S = require('./_stall.cjs');
module.exports = {
  id: 'buyer-walkout', label: '买方走回去', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    if (i <= 1) return { hands: [S.HL(75, 208), S.HR(...S.R0)], gazeX: -5, eyes: i === 1 ? 'closed' : 'open', hatDrop: i === 1 ? 5 : 0 };
    const walk = i >= 3 ? S.stride(i - 3) : { footOffsets: [0, 0, 0, 0], feet: [0, 0, 0, 0] };
    const sw = i >= 3 ? S.armSwing(i - 3) : 0;
    return { side: true, ...walk, squash: i === 2 ? 5 : 0, hands: [S.HL(70 + sw, 223), S.HR(215, 208)] };
  }
};
