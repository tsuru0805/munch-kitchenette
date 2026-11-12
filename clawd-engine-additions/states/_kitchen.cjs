// clawds-new-clothes · states/_kitchen.cjs · kitchen props by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 下厨动作共用的道具：锅、木勺、蒸汽、烟、案板、灶、烤箱、蒸笼……下划线开头，不进 STATES。
const palette = {
  potSteel: '#9aa7ad', potDark: '#6b777d', potRim: '#d3dbde',
  soup: '#e8a048', soupBurnt: '#4a3328', smoke: '#5b5560', smokeLight: '#8a8590',
  bowlWhite: '#fbfaf6', noodle: '#f2c96b',
  // 案板 / 菜刀 / 平底锅 / 灶火 / 菜
  boardWood: '#c99a5b', boardEdge: '#a67a40', tableTop: '#e6d6bd', tableLeg: '#b79c78',
  knifeSteel: '#cfd8dc', knifeEdge: '#8d9aa1', vegOrange: '#f08a3c', vegGreen: '#6fae5a', vegGreenDark: '#4c8a45',
  panIron: '#3f4750', panRim: '#6a747d', stoveBody: '#8b949a', stoveDark: '#5c656b', flameOut: '#f2743a', flameIn: '#ffd257', oilGold: '#f6d98a',
  friedGold: '#e0a03c', friedBrown: '#b46a2c', mittRed: '#d8605a', ovenGlow: '#ffb24a', ovenGlowHot: '#ff8a3a', bunWhite: '#fff8ec', puffWhite: '#fffdf6'
};
// 锅坐在他右手边，锅底贴基线
function pot(ctx, burnt = false) {
  const g = ctx.baseline;
  ctx.props.rect(220, g - 35, 70, 5, 'potRim', 'pot-rim');
  ctx.props.rect(225, g - 30, 60, 30, 'potSteel', 'pot');
  ctx.props.rect(275, g - 30, 10, 30, 'potDark');
  ctx.props.rect(230, g - 25, 5, 20, 'potRim');
  ctx.props.rect(285, g - 25, 10, 5, 'potDark');
  ctx.props.rect(215, g - 25, 10, 5, 'potDark');
  ctx.props.rect(225, g - 40, 60, 5, burnt ? 'soupBurnt' : 'soup', 'soup');
}
// 木勺：握在右手里，勺柄往上冒一截，勺头在锅里看不见
function spoon(ctx, hand) {
  ctx.props.rect(hand.x + 10, hand.y - 25, 5, 30, 'leather', 'spoon');
}
// 三缕热气，k=帧号
function steam(ctx, k, x0 = 240) {
  for (let n = 0; n < 3; n++) {
    const ph = (k + n * 5) % 15;
    if (ph > 11) continue;
    const y = ctx.baseline - 55 - ph * 5;
    const x = x0 + n * 15 + (Math.floor(ph / 3) % 2 ? 5 : 0);
    ctx.effects.rect(x, y, 5, 10, 'white');
  }
}
// 一团烟：t 0..1 往上冒、变大
function smoke(ctx, t) {
  const r = [['01110', '11111', '01110'], ['0011100', '0111110', '1111111', '0111110'], ['001111100', '011111110', '111111111', '111111111', '011111110']];
  const k = t < 0.33 ? 0 : t < 0.66 ? 1 : 2;
  const rows = r[k];
  const w = rows[0].length * 5;
  const y = ctx.baseline - 60 - Math.round(t * 60 / 5) * 5;
  ctx.effects.pattern(rows, 255 - Math.round(w / 2 / 5) * 5, y, k === 2 ? 'smokeLight' : 'smoke', 5, 'smoke');
}
// ── 切菜、颠锅用的家伙 ──
// 小案台 + 案板:摆在他右手边,台面到他手那么高(基线上 40),刀落下来正好切到案板
function board(ctx) {
  const g = ctx.baseline;
  ctx.props.rect(210, g - 40, 90, 5, 'tableTop', 'table');
  ctx.props.rect(210, g - 35, 90, 5, 'tableLeg');
  ctx.props.rect(215, g - 30, 5, 30, 'tableLeg'); ctx.props.rect(290, g - 30, 5, 30, 'tableLeg');
  ctx.props.rect(220, g - 45, 70, 5, 'boardWood', 'board');
  ctx.props.rect(285, g - 45, 5, 5, 'boardEdge');
}
// 一根胡萝卜横在案板上:left=还没切到的那一头的 x(越切越短),切下来的片码在左边
function carrot(ctx, cut) {
  const g = ctx.baseline, y = g - 55;
  const left = 245 + cut * 5;
  if (left < 280) ctx.props.rect(left, y, 280 - left, 10, 'vegOrange', 'carrot');
  ctx.props.rect(280, y, 5, 10, 'vegGreen'); ctx.props.rect(285, y - 5, 5, 10, 'vegGreenDark');
  // 切下来的片往左码成一小堆(一排三片,往上摞)
  for (let n = 0; n < cut; n++) ctx.props.rect(220 + (n % 3) * 5, y + 5 - Math.floor(n / 3) * 5, 5, 5, n % 2 ? 'flameOut' : 'vegOrange', 'carrot-slice');
}
// 菜刀:握在右手里,刀身朝右下
function knife(ctx, hand) {
  ctx.letter.rect(hand.x + 15, hand.y, 20, 10, 'knifeSteel', 'knife');
  ctx.letter.rect(hand.x + 15, hand.y + 10, 20, 5, 'knifeEdge');
  ctx.letter.rect(hand.x + 10, hand.y + 5, 5, 5, 'leather');
}
// 灶:一个小炉头贴基线,上面两簇火,k=帧号(火苗来回跳)
function stove(ctx, k, on = true) {
  const g = ctx.baseline;
  // 灶台到他手那么高(锅端在火上方一点点),正面两个旋钮
  ctx.props.rect(235, g - 35, 65, 35, 'stoveBody', 'stove');
  ctx.props.rect(235, g - 40, 65, 5, 'stoveDark');
  ctx.props.rect(245, g - 25, 5, 5, 'stoveDark'); ctx.props.rect(260, g - 25, 5, 5, 'stoveDark');
  ctx.props.rect(235, g - 5, 65, 5, 'stoveDark');
  if (!on) return;
  for (let n = 0; n < 4; n++) {
    const x = 250 + n * 10, tall = (k + n) % 3 === 0 ? 10 : 5;
    ctx.effects.rect(x, g - 40 - tall, 5, tall, 'flameOut', 'flame');
    ctx.effects.rect(x, g - 45, 5, 5, 'flameIn');
  }
}
// 平底锅:握在右手里,锅身在手的右边;lift=抬起来多少(颠锅)
function pan(ctx, hand) {
  const x = hand.x + 20, y = hand.y + 5;
  ctx.letter.rect(hand.x + 10, y, 10, 5, 'leather', 'pan-handle');
  ctx.letter.rect(x, y, 50, 5, 'panRim', 'pan');
  ctx.letter.rect(x + 5, y + 5, 40, 5, 'panIron');
  return { x, y };
}
// 锅里的菜:三四块,air=0 贴锅底,>0 抛在半空(每块高度错开)
const BITS = [['vegGreen', 5], ['vegOrange', 15], ['noodle', 25], ['vegGreenDark', 35]];
function food(ctx, panAt, air = 0) {
  BITS.forEach(([c, dx], n) => {
    const h = air ? Math.round(air * (n % 2 ? 0.7 : 1) / 5) * 5 : 0;
    ctx.effects.rect(panAt.x + dx, panAt.y - 5 - h, 5, 5, c, 'food');
  });
}
// ── 七种做法各自的家伙 ──
// 只有台子没有案板(拌菜用)
function table(ctx) {
  const g = ctx.baseline;
  ctx.props.rect(210, g - 40, 90, 5, 'tableTop', 'table');
  ctx.props.rect(210, g - 35, 90, 5, 'tableLeg');
  ctx.props.rect(215, g - 30, 5, 30, 'tableLeg'); ctx.props.rect(290, g - 30, 5, 30, 'tableLeg');
}
// 一团白汽(点阵):size 0/1/2 越来越大
const PUFFS = [['010', '111'], ['0110', '1111', '0110'], ['01110', '11111', '11111', '01110']];
function puff(ctx, x, y, size = 1) { ctx.effects.pattern(PUFFS[size], x, y, 'puffWhite', 5, 'puff'); }
// 坐在灶上的平底锅(煎):锅柄朝他
function panOnStove(ctx) {
  const g = ctx.baseline;
  ctx.props.rect(230, g - 50, 15, 5, 'leather', 'pan-handle');
  ctx.props.rect(245, g - 50, 50, 5, 'panRim', 'pan');
  ctx.props.rect(250, g - 45, 40, 5, 'panIron');
}
// 锅铲:握在右手里,铲头朝右
function spatula(ctx, hand) {
  ctx.letter.rect(hand.x + 15, hand.y + 10, 15, 5, 'leather', 'spatula');
  ctx.letter.rect(hand.x + 30, hand.y + 10, 15, 5, 'knifeSteel');
}
// 油星:从锅面往外蹦
function sparks(ctx, k, y0) {
  for (let n = 0; n < 3; n++) {
    const ph = (k * 2 + n * 5) % 12;
    if (ph < 4) ctx.effects.rect(255 + n * 12 - (n * 12) % 5 + (ph % 2 ? 5 : 0), y0 - ph * 5, 5, 5, 'oilGold', 'spark');
  }
}
// 油锅:汤锅里换成一面油
function oilPot(ctx, k, busy) {
  pot(ctx);
  const g = ctx.baseline;
  ctx.props.rect(225, g - 40, 60, 5, 'oilGold', 'oil');
  const n = busy ? 5 : 2;
  for (let b = 0; b < n; b++) {
    const ph = (k + b * 3) % 6;
    if (ph < 3) ctx.effects.rect(230 + ((b * 13 + k * 5) % 50) - ((b * 13 + k * 5) % 50) % 5, g - 45 - (ph === 1 ? 5 : 0), 5, 5, b % 2 ? 'puffWhite' : 'oilGold', 'bubble');
  }
}
// 长筷子 + 夹着的那一块:握在右手里,筷尖朝右
function chopsticks(ctx, hand, piece) {
  ctx.letter.rect(hand.x + 15, hand.y + 5, 30, 5, 'leather', 'chopsticks');
  if (piece) ctx.letter.rect(hand.x + 40, hand.y + 5, 10, 10, piece, 'fry-piece');
}
// 锅盖:at={x,y} 是盖沿左上角
function lid(ctx, x, y) {
  ctx.letter.rect(x, y, 70, 5, 'potRim', 'lid');
  ctx.letter.rect(x + 5, y - 5, 60, 5, 'potSteel');
  ctx.letter.rect(x + 30, y - 10, 10, 5, 'potDark');
}
// 蒸笼:底下一口矮锅,摞两屉,open=掀开了(露出三个白馒头,盖子不画——在手里)
function steamer(ctx, open) {
  const g = ctx.baseline;
  ctx.props.rect(225, g - 15, 60, 15, 'potSteel', 'steamer-pot');
  ctx.props.rect(220, g - 20, 70, 5, 'potRim');
  for (let t = 0; t < 2; t++) {
    const y = g - 35 - t * 15;
    ctx.props.rect(220, y, 70, 15, 'boardWood', 'steamer-tier');
    ctx.props.rect(220, y, 70, 5, 'boardEdge'); ctx.props.rect(220, y + 10, 70, 5, 'boardEdge');
  }
  if (open) for (let n = 0; n < 3; n++) { ctx.props.rect(228 + n * 20 - 3, g - 55, 15, 5, 'bunWhite', 'bun'); ctx.props.rect(230 + n * 20, g - 60, 10, 5, 'bunWhite'); }
}
function steamerLid(ctx, x, y) {
  ctx.letter.rect(x, y, 70, 5, 'boardEdge', 'steamer-lid');
  ctx.letter.rect(x + 5, y - 5, 60, 5, 'boardWood');
  ctx.letter.rect(x + 30, y - 10, 10, 5, 'boardEdge');
}
// 烤箱:贴基线,玻璃窗里一块面包越烤越深;k=帧号(炉光一明一暗)
function oven(ctx, k, done) {
  const g = ctx.baseline;
  ctx.props.rect(220, g - 65, 75, 60, 'stoveBody', 'oven');
  ctx.props.rect(220, g - 65, 75, 10, 'stoveDark');
  for (const x of [230, 245, 260]) ctx.props.rect(x, g - 60, 5, 5, 'potRim');
  ctx.props.rect(280, g - 60, 5, 5, done ? 'vegGreen' : 'flameOut');
  ctx.props.rect(225, g - 50, 65, 40, 'panIron', 'oven-door');
  ctx.props.rect(230, g - 45, 55, 30, k % 6 < 3 ? 'ovenGlow' : 'ovenGlowHot', 'oven-glass');
  ctx.props.rect(235, g - 20, 45, 5, 'stoveDark');
  const loaf = done ? 'friedBrown' : (k > 20 ? 'friedGold' : 'noodle');
  ctx.props.rect(245, g - 30, 25, 10, loaf, 'loaf'); ctx.props.rect(250, g - 35, 15, 5, loaf);
  ctx.props.rect(225, g - 5, 10, 5, 'stoveDark'); ctx.props.rect(280, g - 5, 10, 5, 'stoveDark');
}
// 隔热手套:套在手上
function mitt(ctx, hand) {
  ctx.letter.rect(hand.x, hand.y, 20, 15, 'mittRed', 'mitt');
  ctx.letter.rect(hand.x, hand.y + 15, 20, 5, 'bowlWhite');
}
// 拌菜的大碗:坐在台子上;toss=0..1 菜叶蹦多高
function saladBowl(ctx, k) {
  const g = ctx.baseline;
  ctx.props.rect(225, g - 60, 60, 5, 'bowlWhite', 'salad-bowl');
  ctx.props.rect(230, g - 55, 50, 5, 'blue');
  ctx.props.rect(230, g - 50, 50, 5, 'bowlWhite');
  ctx.props.rect(240, g - 45, 30, 5, 'bowlWhite');
  const cols = ['vegGreen', 'vegOrange', 'vegGreenDark', 'noodle', 'vegGreen', 'flameOut', 'vegGreenDark'];
  cols.forEach((c, n) => {
    const up = (k + n * 2) % 5 === 0 ? 10 : ((k + n * 2) % 5 === 1 ? 5 : 0);
    ctx.effects.rect(232 + n * 7 - (n * 7) % 5 + 0, g - 65 - up, 5, 5, c, 'leaf');
  });
}
// 拌菜的勺叉:柄朝上握在手里,头在碗里
function server(ctx, hand) { ctx.letter.rect(hand.x + 5, hand.y + 15, 5, 15, 'leather', 'server'); }
module.exports = { palette, pot, spoon, steam, smoke, board, carrot, knife, stove, pan, food,
  table, puff, panOnStove, spatula, sparks, oilPot, chopsticks, lid, steamer, steamerLid, oven, mitt, saladBowl, server };
