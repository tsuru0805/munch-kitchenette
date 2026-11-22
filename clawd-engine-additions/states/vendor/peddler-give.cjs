// clawds-new-clothes · states/vendor/peddler-give.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 小贩 ⑥递货(放一遍,和 buyer-give 同框):右手从台面右头的草把子 / 纸袋箱里拿一件(第 7 帧拿到),直接递到买方手边,
// 第 18 帧买方接过去;收手,点点头。东西在 _stall 的场景里画,跟着手走。
const S = require('./_stall.cjs');
const RH = [[0, 210, 223], [5, 225, 203], [7, 225, 203], [13, 225, 213], [19, 225, 213], [24, 210, 223]];
module.exports = {
  id: 'peddler-give', label: '小贩递货', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i) {
    const nod = S.within(i, 29, 33);
    return { hands: [S.HL(...S.L0), S.HR(...S.path(RH, i))], gazeX: 5, hatDrop: nod ? 5 : 0, eyes: nod ? 'closed' : 'open' };
  }
};
