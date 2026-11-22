// clawds-new-clothes · states/vendor/buyer-eat.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 买方 ③吃一口(放一遍,和 peddler-eat 同框):把手里的举到脸前,第 9 帧咬一口(糖葫芦少最上面一颗、纸袋口冒碎屑),
// 鼓着嚼三下,眯眼脸红冒小心,再捧回胸前。
const S = require('./_stall.cjs');
// 手先往下、再横着挪到身子正中,从眼睛下面过,不挡眼(引擎体检「眼睛被盖住」)
const LH = [[0, 75, 208], [2, 75, 208], [4, 75, 243], [7, 135, 248], [24, 135, 248], [27, 75, 243], [30, 75, 208]];
module.exports = {
  id: 'buyer-eat', label: '买方吃一口', frames: 45, ms: [70, 60, 70], group: 'prop', palette: S.palette, once: true,
  pose(i, { closedAt }) {
    const chew = [11, 12, 15, 16, 19, 20].includes(i);
    return {
      hands: [S.HL(...S.path(LH, i)), S.HR(...S.R0)],
      squash: chew ? 5 : 0, gazeX: i < 2 || i > 30 ? -5 : 0,
      eyes: S.within(i, 9, 30) || closedAt(40) ? 'closed' : 'open', tool: { blush: S.within(i, 12, 36) }
    };
  }
};
