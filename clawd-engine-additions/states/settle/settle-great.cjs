// clawds-new-clothes · states/settle/settle-great.cjs · still pose by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 结算定格 · great:开心炫耀,双手把盘子高高举过头顶。静态定格,45 帧同一个姿势。
// 盘子不画在这里——只画空手托举,盘子由程序后贴(盘位见 web/src/settle.ts)。
// 手按高筒帽的帽顶摆(帽顶 y 143,手画在 123–143);头巾矮 30,导出脚本用 renderVariant 的 hands 覆盖把手降 30,
// 旁边的星和心都跟着手走(paint 里按 ctx.hands 定位),所以两套衣服同一份文件。
module.exports = {
  id: 'settle-great', label: '结算 · 很好(举过头顶)', frames: 45, ms: [70, 60, 70], group: 'prop',
  pose() {
    return { hands: [{ x: 120, y: 118 }, { x: 160, y: 118 }], eyes: 'closed', gazeY: -5, tool: { blush: true } };
  },
  paint(ctx) {
    // 笑眼:闭眼那一横两头各补一格,成「∩ ∩」
    ctx.eyes.forEach((e, n) => {
      const d = e.drawn;
      ctx.effects.rect(d.x - 5, d.y + 5, 5, 5, 'ink', `smile-${n + 1}-a`);
      ctx.effects.rect(d.x + 10, d.y + 5, 5, 5, 'ink', `smile-${n + 1}-b`);
    });
    const [l, r] = ctx.hands;
    // 盘子两边的星和一颗小心(盘子占 x 115–185、手顶往上 50)
    ctx.effects.pattern(ctx.shapes.sparkle, l.x - 45, l.y - 30, 'gold', 5, 'spark-left');
    ctx.effects.pattern(ctx.shapes.sparkle, r.x + 45, r.y - 45, 'gold', 5, 'spark-right');
    ctx.effects.rect(l.x - 25, l.y - 55, 5, 5, 'gold', 'spark-dot');
    ctx.effects.pattern(ctx.shapes.miniHeart, r.x + 50, r.y - 5, 'red', 5, 'heart');
  },
  check: { firstFrameEyesClosed: true }
};
