// clawds-new-clothes · states/cook-wash.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
const K = require('./_kitchen.cjs');
// 洗手:开锅前先洗手。台子上一只水盆,两只手在盆里搓(泡泡往上冒)→ 抬起来甩两下(水珠飞)→ 站好,眨一下眼
module.exports = {
  id: 'cook-wash', label: '洗手', frames: 45, ms: [70, 60, 70], group: 'prop', palette: K.palette,
  pose(i, { closedAt }) {
    if (i < 4) return { hands: [{ x: 80, y: 218 }, { x: 225, y: 218 }], gazeX: 5, gazeY: 5 };
    if (i < 26) { const a = i % 4 < 2; return { hands: [{ x: a ? 220 : 230, y: 198 }, { x: a ? 260 : 250, y: 198 }], gazeX: 5, gazeY: 5, eyes: closedAt(15) ? 'closed' : 'open' }; }
    if (i < 36) { const up = i % 4 < 2; return { hands: [{ x: 215, y: up ? 178 : 188 }, { x: 255, y: up ? 188 : 178 }], gazeX: 5, gazeY: 0 }; }
    return { hands: [{ x: 80, y: 218 }, { x: 225, y: 218 }], gazeX: 0, gazeY: 0, eyes: i >= 39 && i <= 42 ? 'closed' : 'open' };
  },
  paint(ctx, p, i) {
    const g = ctx.baseline;
    K.table(ctx);
    ctx.props.rect(225, g - 55, 60, 5, 'bowlWhite', 'basin'); ctx.props.rect(230, g - 50, 50, 10, 'potRim'); ctx.props.rect(230, g - 55, 50, 5, 'blue', 'water');
    if (i >= 4 && i < 26) for (let n = 0; n < 3; n++) { const ph = (i + n * 4) % 10; if (ph < 7) ctx.effects.rect(235 + n * 15 + (ph % 2 ? 5 : 0), g - 65 - ph * 5, 5, 5, 'puffWhite', 'bubble'); }
    if (i >= 26 && i < 36) for (let n = 0; n < 4; n++) { const ph = (i - 26 + n * 2) % 5; ctx.effects.rect(205 + n * 25, g - 105 - ph * 5 + n % 2 * 10, 5, 5, 'blue', 'drop'); }
  }
};
