// clawds-new-clothes · states/chores/machine-close.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 洗碗机 ②关门:蹲一下捏住放倒的门,往上一抬——半开——「咔」地关上(门边冒两道线、他一缩);拍拍手、得意地眯眼。
const D = require('./_dishkit.cjs');
module.exports = {
  id: 'machine-close', label: '关门', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let R = [235, 223], L = D.LEFT0, squash = 0, eyes = closedAt(4) ? 'closed' : 'open', gx = 5, gy = 5, tool = {};
    if (i >= 5 && i <= 10) { R = D.path([[5, 235, 223], [9, 240, 253], [10, 240, 253]], i); squash = i >= 8 ? 5 : 0; }
    if (i >= 11 && i <= 16) { R = [[240, 248], [240, 238], [245, 228], [245, 223], [245, 218], [245, 213]][i - 11]; }
    if (i >= 17 && i <= 19) { R = [235, 213]; squash = 5; eyes = 'closed'; }
    if (i >= 20 && i <= 28) { const k = i % 4 < 2; L = [k ? 120 : 125, 238]; R = [k ? 160 : 155, 238]; gx = 0; gy = 5; }
    if (i >= 29 && i <= 36) { gx = 0; gy = 0; eyes = i >= 31 && i <= 35 ? 'closed' : 'open'; tool = i >= 31 && i <= 35 ? { blush: true } : {}; }
    if (i >= 37) { R = D.path([[37, 210, 223], [42, 235, 223]], i); }
    if (i >= 29 && i <= 36) R = [210, 223];
    return { squash, hands: [D.HL(L[0], L[1]), D.HR(R[0], R[1])], gazeX: gx, gazeY: gy, eyes, tool };
  },
  paint(ctx, p, i) {
    const door = i < 12 ? 'open' : i < 15 ? 'half' : 'closed';
    D.washer(ctx, { door, rack: 3 });
    if (i >= 17 && i <= 19) { const E = ctx.effects; E.rect(210, 223, 5, 10, 'ink', 'clunk'); E.rect(300 - 5, 223, 5, 10, 'ink'); E.rect(215, 213, 5, 5, 'ink'); }
    if (i >= 20 && i <= 28 && i % 4 < 2) ctx.effects.rect(140, 225, 5, 5, 'smokeLight', 'dust');
  }
};
