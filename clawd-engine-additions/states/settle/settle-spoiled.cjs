// clawds-new-clothes · states/settle/settle-spoiled.cjs · still pose by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 结算定格 · spoiled:晕乎乎。静态定格,45 帧同一个姿势。
// 盘子不画在这里(后贴,歪着贴,盘位与歪法见 web/src/settle.ts)。
// 脚、身子、帽子一级一级往右错 5(不用 lean),缩 5;眼睛藏掉,在原位画两个 20×20 的漩涡;头顶三颗金星围一圈;
// 左手垂得很低,盘子歪在手里;右手也耷拉着。
const SWIRL = ['1111', '1001', '1011', '1000'];
module.exports = {
  id: 'settle-spoiled', label: '结算 · 变质(晕乎乎)', frames: 45, ms: [70, 60, 70], group: 'prop',
  pose() {
    const dx = 25;
    return {
      dx, squash: 5, hatShift: 5, footOffsets: [-5, -5, -5, -5], eyes: 'hidden',
      hands: [{ x: 90, y: 243 }, { x: 200 + dx, y: 228 }]
    };
  },
  paint(ctx) {
    ctx.eyes.forEach((e, n) => ctx.props.pattern(n ? SWIRL.map((row) => row.split('').reverse().join('')) : SWIRL, e.x - 5, e.y, 'ink', 5, `swirl-${n + 1}`));
    // 头顶的星:高筒帽的帽顶在帽框上 25,头巾在框下 5
    const top = ctx.hat.y + (ctx.outfit === 'chef-toque' || (ctx.outfit && ctx.outfit.name === 'chef-toque') ? -25 : ctx.outfit ? 5 : 0);
    ctx.effects.pattern(ctx.shapes.sparkle, ctx.hat.x + 5, top - 15, 'gold', 5, 'star-1');
    ctx.effects.pattern(ctx.shapes.sparkle, ctx.hat.x + 60, top - 30, 'gold', 5, 'star-2');
    ctx.effects.pattern(ctx.shapes.sparkle, ctx.hat.x + 120, top - 15, 'gold', 5, 'star-3');
    ctx.effects.rect(ctx.hat.x + 35, top - 25, 5, 5, 'gold', 'star-dot-1');
    ctx.effects.rect(ctx.hat.x + 100, top - 25, 5, 5, 'gold', 'star-dot-2');
  },
  check: { eyesHidden: [[0, 44]] }
};
