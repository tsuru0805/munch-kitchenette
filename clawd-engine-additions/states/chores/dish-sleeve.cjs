// clawds-new-clothes · states/chores/dish-sleeve.cjs · animation by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 刷盘子 ①挽袖子:转过来,左手捏住右手腕往上捋两下(右手腕多出一道卷起的袖口),再换右手捋左手;两只手握拳往上一举、蹦一下——开刷。
// 首帧没有袖口、末帧两只都挽好了;循环时袖口会「放下来」重挽一遍(这一段建议每次刷只在开头放一遍)。
const D = require('./_dishkit.cjs');
const RH = [[0, 235, 223], [4, 225, 218], [17, 225, 218], [20, 185, 243], [22, 185, 238], [30, 185, 238], [34, 210, 198], [38, 210, 198], [42, 235, 223]];
const LH = [[0, 70, 223], [4, 70, 223], [6, 120, 243], [8, 200, 228], [17, 200, 228], [18, 170, 243], [19, 110, 243], [20, 75, 218], [30, 75, 218], [34, 70, 198], [38, 70, 198], [42, 70, 223]];
module.exports = {
  id: 'dish-sleeve', label: '挽袖子', frames: 45, ms: [70, 60, 70], group: 'prop', palette: D.palette,
  pose(i, { closedAt }) {
    let [rx, ry] = D.path(RH, i), [lx, ly] = D.path(LH, i);
    // 8–17 左手顺着右手腕往上捋两下;21–30 右手捋左手腕
    if (i >= 8 && i <= 17) ly += [0, -5, -10, -10, 0, 0, -5, -10, -10, 0][i - 8];
    if (i >= 21 && i <= 30) ry += [0, -5, -10, -10, 0, 0, -5, -10, -10, 0][i - 21];
    const cheer = i >= 34 && i <= 38;
    const jump = i === 35 || i === 36 ? -10 : 0;
    return {
      jump, feet: jump ? [5, 0, 0, 5] : [0, 0, 0, 0],
      hands: [D.HL(lx, ly + jump), D.HR(rx, ry + jump)],
      gazeX: i < 4 || i > 40 ? 5 : (i <= 17 ? 5 : i <= 30 ? -5 : 0), gazeY: i < 4 || i > 40 ? 5 : (i <= 30 ? 5 : -5),
      eyes: cheer ? 'closed' : (closedAt(25) ? 'closed' : 'open'),
      tool: cheer ? { blush: true } : {}
    };
  },
  paint(ctx, p, i) {
    D.sink(ctx, i, { dirty: 2, rack: 2, foam: 2, bottle: true });
    D.cuffs(ctx, [i >= 27, i >= 13]);
    if (i >= 34 && i <= 39) { ctx.effects.pattern(['010', '111', '010'], 50, 170, 'goldLight', 5, 'spark'); ctx.effects.pattern(['010', '111', '010'], 235, 165, 'goldLight', 5, 'spark'); }
  }
};
