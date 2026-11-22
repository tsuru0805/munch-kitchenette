// clawds-new-clothes · outfits/vendor-straw.cjs · outfit by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// 流动小贩「草帽货郎」:宽檐草帽 + 靛蓝短褂 + 脖子上搭一条白毛巾 + 左腰钱袋。
// 和两套厨师服站在一起要一眼分得开:剪影靠又宽又扁的草帽(高筒帽是又高又白),颜色靠靛蓝(厨师是白 / 奶油)。
module.exports = {
  name: 'vendor-straw', label: '草帽货郎',
  palette: {
    straw: '#e9c66c', strawLight: '#f7de92', strawDark: '#b98d3c', hatBand: '#8a3b2c',
    indigo: '#3a4f78', indigoDark: '#27375a', towel: '#fbf6ea', towelShade: '#d9d2c2'
  },
  hat(ctx) {
    // 矮帽顶 + 一圈宽檐(檐比礼帽框还宽,两头各出去 20)
    ctx.rect(35, 10, 70, 20, 'straw', 'straw-crown');
    ctx.rect(40, 5, 60, 5, 'strawLight');
    ctx.rect(35, 20, 70, 5, 'hatBand');
    for (const [x, y] of [[45, 10], [70, 15], [90, 10], [55, 15]]) ctx.rect(x, y, 5, 5, 'strawDark');
    ctx.rect(-10, 25, 160, 10, 'straw', 'straw-brim');
    ctx.rect(-20, 30, 180, 5, 'straw');
    ctx.rect(-20, 35, 180, 5, 'strawDark');
    for (const x of [0, 30, 110, 140]) ctx.rect(x, 25, 5, 5, 'strawLight');
  },
  costume(ctx, { body, bottom }) {
    const top = Math.max(body.y + 30, bottom - 25), x = body.x, w = body.w;
    ctx.rect(x, top, w, bottom - top, 'indigo', 'happi');
    ctx.rect(x, bottom - 5, w, 5, 'indigoDark');
    ctx.rect(x + 55, top + 5, 10, bottom - top - 5, 'indigoDark');        // 前襟
    // 白毛巾搭在脖子上,两头垂下来
    ctx.rect(x + 15, top, 90, 5, 'towel', 'towel');
    ctx.rect(x + 30, top + 5, 10, 10, 'towel'); ctx.rect(x + 30, top + 15, 10, 5, 'towelShade');
    ctx.rect(x + 80, top + 5, 10, 10, 'towel'); ctx.rect(x + 80, top + 15, 10, 5, 'towelShade');
    // 左腰钱袋(收钱时手往这儿放)
    if (!ctx.side) { ctx.rect(x + 5, top + 10, 15, 15, 'leather', 'pouch'); ctx.rect(x + 5, top + 10, 15, 5, 'leatherDark'); ctx.rect(x + 10, top + 15, 5, 5, 'gold'); }
    if (ctx.side) ctx.rect(x, top, 20, bottom - top, 'indigoDark');
  },
  hideBag: true, hideWatch: true
};
