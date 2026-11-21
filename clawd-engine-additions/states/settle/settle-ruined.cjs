// clawds-new-clothes · states/settle/settle-ruined.cjs · still pose by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 结算定格 · ruined:没有盘子。面前一口翻了的锅、一摊汤,他愣在那里。静态定格,45 帧同一个姿势。
// 人往左让 30;眼睛缩成小方点,帽子歪了(hatTilt 会连带把帽子抬 10,用 hatDrop 9 压回头上),两只手僵在半空;右边锅侧躺着、汤流了一地、菜撒出来,左边锅盖滚到脚边;头顶右边三个灰点。
const K = require('../_kitchen.cjs');
module.exports = {
  id: 'settle-ruined', label: '结算 · 做砸了(愣住)', frames: 45, ms: [70, 60, 70], group: 'prop',
  palette: K.palette,
  pose() {
    const dx = -30;
    return { dx, eyes: 'dot', hatTilt: -8, hatShift: -10, hatDrop: 9, hands: [{ x: 75 + dx, y: 208 }, { x: 205 + dx, y: 208 }] };
  },
  paint(ctx) {
    const g = ctx.baseline;
    // 侧躺的锅:口朝左,看得见黑洞洞的锅口,汤从口里流出来
    ctx.props.rect(235, g - 40, 50, 40, 'potSteel', 'pot');
    ctx.props.rect(235, g - 10, 50, 10, 'potDark');
    ctx.props.rect(285, g - 35, 5, 30, 'potDark');
    ctx.props.rect(220, g - 45, 15, 45, 'potRim', 'pot-rim');
    ctx.props.rect(225, g - 40, 10, 35, 'panIron', 'pot-mouth');
    ctx.props.rect(250, g - 45, 15, 5, 'potDark', 'pot-handle');
    // 流出来的汤和菜
    ctx.props.rect(185, g - 5, 45, 5, 'soup', 'spill');
    ctx.props.rect(200, g - 10, 30, 5, 'soup');
    ctx.props.rect(215, g - 15, 15, 5, 'soup');
    ctx.props.rect(225, g - 20, 10, 15, 'soup', 'spill-mouth');
    ctx.props.rect(205, g - 15, 5, 5, 'vegGreen', 'bit-1');
    ctx.props.rect(210, g - 10, 5, 5, 'vegOrange', 'bit-2');
    ctx.props.rect(195, g - 10, 5, 5, 'noodle', 'bit-3');
    ctx.props.rect(190, g - 15, 5, 5, 'vegOrange', 'bit-4');
    // 滚到左边的锅盖
    ctx.props.rect(5, g - 5, 40, 5, 'potRim', 'lid');
    ctx.props.rect(10, g - 10, 30, 5, 'potSteel');
    ctx.props.rect(20, g - 15, 10, 5, 'potDark');
    // 愣住的三个点
    for (let n = 0; n < 3; n++) ctx.effects.rect(ctx.body.x + ctx.body.w + 15 + n * 10, ctx.body.y - 30, 5, 5, 'grey', `dot-${n + 1}`);
  }
};
