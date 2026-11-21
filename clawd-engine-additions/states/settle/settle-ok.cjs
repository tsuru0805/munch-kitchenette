// clawds-new-clothes · states/settle/settle-ok.cjs · still pose by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 结算定格 · ok:平平常常端着盘子。静态定格,45 帧同一个姿势。
// 盘子不画在这里(后贴,盘位见 web/src/settle.ts)。
// 像素菜有 9–14 格宽、8–10 格高,和他的身子差不多高,放在正胸口会把眼睛盖掉;所以人往左让 25,右手平托在身侧胸口那么高,盘子坐在右手上。
module.exports = {
  id: 'settle-ok', label: '结算 · 一般(端在身侧)', frames: 45, ms: [70, 60, 70], group: 'prop',
  pose() {
    const dx = -25;
    return { dx, hands: [{ x: 80 + dx, y: 218 }, { x: 185, y: 238 }], eyes: 'open' };
  }
};
