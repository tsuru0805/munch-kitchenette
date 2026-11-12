// clawds-new-clothes · outfits/chef-scarf.cjs · outfit by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// 头巾 + 大围裙:蓝底白点头巾 + 米色围裙 + 粉心口袋
module.exports = {
  name: 'chef-scarf', label: '头巾 + 大围裙',
  palette: { scarfBlue: '#5f8fc4', scarfDark: '#3f6a9c', scarfDot: '#fff6dc', bibCream: '#f6ead0', bibLine: '#d8c49c', bibGreen: '#5f9c7a', bibGreenDark: '#3f7458', bibPink: '#f07ca6' },
  hat(ctx) {
    // 三角头巾:包住整个头顶,白点子,右后脑打个结垂两条
    ctx.rect(35, 5, 70, 5, 'scarfBlue', 'scarf');
    ctx.rect(20, 10, 100, 10, 'scarfBlue');
    ctx.rect(10, 20, 120, 15, 'scarfBlue');
    ctx.rect(10, 35, 120, 5, 'scarfDark');
    for (const [dx, dy] of [[30, 15], [55, 10], [80, 15], [105, 20], [20, 25], [45, 25], [70, 25], [95, 28]]) ctx.rect(dx, Math.round(dy / 5) * 5, 5, 5, 'scarfDot');
    ctx.rect(125, 15, 10, 10, 'scarfDark', 'scarf-knot');
    ctx.rect(135, 5, 5, 10, 'scarfBlue'); ctx.rect(135, 25, 10, 5, 'scarfBlue');
  },
  costume(ctx, { body, bottom }) {
    const top = Math.max(body.y + 30, bottom - 25), x = body.x, w = body.w;
    ctx.rect(x, top, w, bottom - top, 'bibCream', 'bib');
    ctx.rect(x, top, w, 5, 'bibGreen');                               // 腰上一道绿边
    ctx.rect(x - 5, top, 5, 10, 'bibGreenDark', 'bib-bow'); ctx.rect(x + w, top, 5, 10, 'bibGreenDark');   // 两边系带的结
    // 正中一个大口袋,口袋上一颗心
    ctx.rect(x + 40, top + 10, 40, 15, 'bibLine', 'bib-pocket');
    ctx.rect(x + 45, top + 15, 30, 10, 'bibCream');
    ctx.rect(x + 55, top + 15, 5, 5, 'bibPink'); ctx.rect(x + 65, top + 15, 5, 5, 'bibPink'); ctx.rect(x + 60, top + 20, 5, 5, 'bibPink');
    // 下摆一圈小波浪
    for (let hx = x; hx < x + w; hx += 10) if (hx < x + 40 || hx >= x + 80) ctx.rect(hx, bottom - 5, 5, 5, 'bibLine');
    if (ctx.side) ctx.rect(x, top, 20, bottom - top, 'bibLine');
  },
  hideBag: true, hideWatch: true
};
