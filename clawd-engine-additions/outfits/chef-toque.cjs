// clawds-new-clothes · outfits/chef-toque.cjs · outfit by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// 经典白厨师服:高筒帽 + 白双排扣 + 红领巾
module.exports = {
  name: 'chef-toque', label: '经典白厨师服',
  palette: { chefWhite: '#fbf7ee', chefShade: '#d9cdb8', chefRed: '#d8463c', chefRedDark: '#a8322b', chefButton: '#3c4a57' },
  hat(ctx) {
    // 高筒帽:帽墙三行贴头,筒身带三道褶,顶上一圈蓬出来
    ctx.rect(20, 25, 100, 15, 'chefWhite', 'toque-band');
    ctx.rect(20, 35, 100, 5, 'chefShade');
    ctx.rect(25, -5, 90, 30, 'chefWhite', 'toque-body');
    for (const x of [40, 65, 90]) ctx.rect(x, 5, 5, 20, 'chefShade');
    ctx.rect(15, -15, 110, 15, 'chefWhite', 'toque-puff');
    ctx.rect(20, -20, 25, 5, 'chefWhite'); ctx.rect(55, -25, 30, 10, 'chefWhite'); ctx.rect(95, -20, 25, 5, 'chefWhite');
    ctx.rect(20, 0, 100, 5, 'chefShade');
    ctx.rect(45, -15, 5, 10, 'chefShade'); ctx.rect(90, -15, 5, 10, 'chefShade');
  },
  costume(ctx, { body, bottom }) {
    const top = Math.max(body.y + 30, bottom - 25), x = body.x, w = body.w;
    ctx.rect(x, top, w, bottom - top, 'chefWhite', 'chef-coat');
    ctx.rect(x, bottom - 5, w, 5, 'chefShade');                       // 下摆一道影子
    ctx.rect(x + 35, top + 5, 5, bottom - top - 5, 'chefShade');      // 双排扣的门襟线
    for (const bx of [x + 45, x + 70]) for (const by of [top + 5, top + 15]) if (by + 5 <= bottom) ctx.rect(bx, by, 5, 5, 'chefButton');
    // 红领巾:领口一条 + 垂下来的结
    ctx.rect(x + 25, top, 70, 5, 'chefRed', 'kerchief');
    ctx.rect(x + 55, top + 5, 10, 5, 'chefRedDark'); ctx.rect(x + 50, top + 10, 5, 5, 'chefRed'); ctx.rect(x + 65, top + 10, 5, 5, 'chefRed');
    if (ctx.side) ctx.rect(x, top, 20, bottom - top, 'chefShade');
  },
  hideBag: true, hideWatch: true
};
