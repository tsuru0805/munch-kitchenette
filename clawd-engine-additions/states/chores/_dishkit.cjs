// clawds-new-clothes · states/chores/_dishkit.cjs · sink / dishwasher / window props by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 三组新动作共用的家伙:刷盘子(水槽、水龙头、盘子、海绵、毛巾、洗洁精、沥水架)、洗碗机、窗边小贩(窗、伸进来的手、纸袋、硬币)。
// 下划线开头,不登记成动作。坐标一律是引擎 300 画布;基线 g = ctx.baseline = 273。
const K = require('../_kitchen.cjs');

const palette = {
  ...K.palette,
  soapGreen: '#7cc28a', soapGreenDark: '#4f9a62', sponge: '#f4cf4a', spongeDark: '#d9a92f',
  plateFace: '#e4e9ea', plateEdge: '#a9b5b9', plateDirt: '#b46a2c', waterLight: '#9fd0df',
  machineBody: '#e9ece9', machineShade: '#c4cbc9', machineDark: '#59636a', machineIn: '#3a4248', lightOn: '#7fd36b', lightDone: '#ffd257',
  windowSky: '#d6e7ea', windowSkyLow: '#e8f1ef', awningRed: '#d8584e',
  vendorSleeve: '#5d7891', vendorSleeveDark: '#46607a', vendorHand: '#f0c39a', vendorHandShade: '#d9a77f'
};

// ── 手:用「画出来的左上角」写,换算成姿势坐标(引擎收尾时左手 x−10、右手 x+10、两只 y+5)──
// 手画在身子上(x 落在 90+dx .. 210+dx 里)自动换 skinSide,不然皮肤叠皮肤看不见
function over(X, dx) { return X + 20 > 90 + dx && X < 210 + dx; }
function HL(X, Y, dx = 0, a = 0) { const h = { x: X + 10, y: Y - 5, a }; if (over(X, dx)) h.color = 'skinSide'; return h; }
function HR(X, Y, dx = 0, a = 0) { const h = { x: X - 10, y: Y - 5, a }; if (over(X, dx)) h.color = 'skinSide'; return h; }
const LEFT0 = [70, 223];          // 左手默认画在 (70,223)
const SINK_R = [235, 223];        // 水槽边站好时右手(同做饭 REST:姿势 225,218)
function lerp(a, b, t) { return Math.round((a + (b - a) * t) / 5) * 5; }
// 一串关键帧 [[帧, X, Y], …] → 第 i 帧的 [X, Y](两点之间线性、对到 5 格)
function path(keys, i) {
  if (i <= keys[0][0]) return [keys[0][1], keys[0][2]];
  for (let k = 1; k < keys.length; k++) {
    const [f1, x1, y1] = keys[k - 1], [f2, x2, y2] = keys[k];
    if (i <= f2) { const t = (i - f1) / (f2 - f1); return [lerp(x1, x2, t), lerp(y1, y2, t)]; }
  }
  const last = keys[keys.length - 1];
  return [last[1], last[2]];
}

// ── 水槽一侧:右边台子 + 水盆 + 水龙头;左边沥水架 ──
// o.stream 开着水;o.foam 0..6 盆里的泡泡;o.dirty 盆里露出几只脏盘子边;o.rack 沥水架上立着几只;o.bottle 洗洁精在台上
function sink(ctx, i, o = {}) {
  const g = ctx.baseline;
  // 右边台子(同 K.table 的高度)
  ctx.props.rect(210, g - 40, 90, 5, 'tableTop', 'counter');
  ctx.props.rect(210, g - 35, 90, 5, 'tableLeg');
  ctx.props.rect(215, g - 30, 5, 30, 'tableLeg'); ctx.props.rect(290, g - 30, 5, 30, 'tableLeg');
  // 盆里露出来的脏盘子边(先画,盆沿盖住下半截)
  for (let n = 0; n < (o.dirty || 0); n++) { ctx.props.rect(240 + n * 15, g - 65 + (n % 2) * 5, 5, 15, 'bowlWhite', 'dirty-plate'); ctx.props.rect(245 + n * 15, g - 65 + (n % 2) * 5, 5, 15, 'plateEdge'); }
  // 水盆
  ctx.props.rect(225, g - 55, 60, 5, 'bowlWhite', 'tub'); ctx.props.rect(230, g - 50, 50, 10, 'potRim');
  ctx.props.rect(230, g - 55, 50, 5, 'blue', 'water');
  const foam = o.foam || 0;
  for (let n = 0; n < foam; n++) { const ph = (i + n * 3) % 6; ctx.props.rect(230 + n * 10 - (n > 4 ? 45 : 0), g - 60 - (ph < 2 ? 5 : 0), 5, 5, 'puffWhite', 'foam'); }
  // 水龙头:立管在盆右边,出水口朝左
  ctx.props.rect(285, g - 90, 5, 50, 'potSteel', 'faucet');
  ctx.props.rect(260, g - 90, 30, 5, 'potSteel'); ctx.props.rect(260, g - 85, 5, 5, 'potDark');
  ctx.props.rect(285, g - 95, 10, 5, o.stream ? 'blue' : 'red', 'faucet-knob');
  if (o.bottle) bottleStanding(ctx);
  if (o.stream) {
    for (let y = g - 80; y < g - 55; y += 5) ctx.effects.rect(260, y, 5, 5, ((y / 5 + i) % 3 === 0) ? 'waterLight' : 'blue', 'stream');
  }
  // 左边:小台子 + 沥水架
  ctx.props.rect(10, g - 40, 55, 5, 'tableTop', 'rack-table');
  ctx.props.rect(15, g - 35, 5, 35, 'tableLeg'); ctx.props.rect(55, g - 35, 5, 35, 'tableLeg');
  ctx.props.rect(15, g - 45, 45, 5, 'potSteel', 'rack');
  for (let n = 0; n < 4; n++) ctx.props.rect(18 + n * 10 - (18 + n * 10) % 5, g - 55, 5, 10, 'potDark');
  rackPlates(ctx, o.rack || 0);
}
// 沥水架上立着的干净盘子(画在架子柱子前面)
function rackPlates(ctx, n) {
  const g = ctx.baseline;
  for (let k = 0; k < Math.min(n, 4); k++) {
    const x = 20 + k * 10;
    ctx.props.rect(x, g - 70, 5, 25, 'bowlWhite', 'rack-plate'); ctx.props.rect(x, g - 50, 5, 5, 'plateEdge');
  }
}
function bottleStanding(ctx) {
  const g = ctx.baseline;
  ctx.props.rect(290, g - 60, 10, 20, 'soapGreen', 'bottle'); ctx.props.rect(295, g - 60, 5, 20, 'soapGreenDark');
  ctx.props.rect(290, g - 65, 5, 5, 'white');
}
// 倒拿着的洗洁精(瓶口朝下),squeeze 时瓶身中间瘪进去
function bottleHeld(ctx, hand, squeeze) {
  const x = hand.x, y = hand.y - 5;
  ctx.letter.rect(x, y, 15, 20, 'soapGreen', 'bottle');
  ctx.letter.rect(x + 10, y, 5, 20, 'soapGreenDark');
  if (squeeze) { ctx.letter.rect(x, y + 5, 5, 10, 'soapGreenDark'); }
  ctx.letter.rect(x + 5, y + 20, 5, 5, 'white', 'nozzle');
}

// ── 盘子 ──
// 正面的盘子(圆):画在 paper 层(手在它前面,盆在它前面——放低了就「沉进盆里」)
const DISC = ['0011100', '0111110', '1111111', '1111111', '1111111', '0111110', '0011100'];
const DISC_IN = ['111', '111', '111'];
function disc(ctx, x, y, o = {}) {
  // 一圈灰边再填白:白盘子落在浅底(米色卡片、白厨师服)上也认得出
  ctx.paper.pattern(DISC, x, y, 'plateEdge', 5, 'plate');
  ctx.paper.pattern(['01110', '11111', '11111', '11111', '01110'], x + 5, y + 5, 'bowlWhite', 5);
  ctx.paper.pattern(DISC_IN, x + 10, y + 10, 'plateFace', 5);
  (o.dirt || []).forEach(([dx, dy]) => ctx.paper.rect(x + dx, y + dy, 5, 5, 'plateDirt', 'dirt'));
  (o.drops || []).forEach(([dx, dy]) => ctx.paper.rect(x + dx, y + dy, 5, 5, 'waterLight', 'drop'));
}
// 侧面的盘子(一道):layer 可选;w 宽
function edge(ctx, x, y, layer = 'letter', w = 40, dirty = false) {
  ctx[layer].rect(x, y, w, 5, 'bowlWhite', 'plate-edge');
  ctx[layer].rect(x + 5, y + 5, w - 10, 5, 'plateEdge');
  if (dirty) { ctx[layer].rect(x + 10, y - 5, 5, 5, 'plateDirt'); ctx[layer].rect(x + 25, y - 5, 5, 5, 'vegGreen'); }
}
// 海绵:黄 + 绿底
function sponge(ctx, x, y) { ctx.letter.rect(x, y, 15, 5, 'spongeDark', 'sponge'); ctx.letter.rect(x, y + 5, 15, 5, 'sponge'); ctx.letter.rect(x, y + 10, 15, 5, 'vegGreen'); }
// 毛巾:白底一道红
function towel(ctx, x, y) { ctx.letter.rect(x, y, 15, 15, 'white', 'towel'); ctx.letter.rect(x, y + 5, 15, 5, 'red'); ctx.letter.rect(x + 5, y + 15, 5, 5, 'white'); }
// 挽起来的袖口:手靠身子那一侧一道竖条(右手画在手左边、左手画在手右边)
function cuffs(ctx, which = [true, true]) {
  const [l, r] = ctx.hands;
  if (which[0]) { ctx.letter.rect(l.x + 20, l.y, 5, 20, 'white', 'cuff-left'); ctx.letter.rect(l.x + 20, l.y + 5, 5, 5, 'paperEdge'); }
  if (which[1]) { ctx.letter.rect(r.x - 5, r.y, 5, 20, 'white', 'cuff-right'); ctx.letter.rect(r.x - 5, r.y + 5, 5, 5, 'paperEdge'); }
}
// 泡泡:在 (x,y) 附近冒,k 帧号
function bubbles(ctx, k, x, y, n = 3) {
  for (let m = 0; m < n; m++) { const ph = (k + m * 3) % 8; if (ph < 6) ctx.effects.rect(x + m * 10 + (ph % 2 ? 5 : 0), y - ph * 5, 5, 5, 'puffWhite', 'bubble'); }
}

// ── 洗碗机:贴基线在他右手边;机身画在 paper 层(他的手伸进去时画在前面) ──
// o.door 'closed' | 'half' | 'open';o.rack 架上几只盘子;o.light 'off' | 'on' | 'done';o.swirl 帧号(窗里水转);o.stack 机顶摞着几只脏盘子;o.shake 抖一格
function washer(ctx, o = {}) {
  const g = ctx.baseline, P = ctx.paper, s = o.shake || 0;
  const X = 215 + s;
  P.rect(X, g - 70, 80, 70, 'machineBody', 'washer');
  P.rect(X + 75, g - 70, 5, 70, 'machineShade');
  P.rect(X, g - 70, 80, 15, 'machineShade', 'washer-panel');
  P.rect(X + 10, g - 65, 30, 5, 'machineDark');                         // 显示条
  P.rect(X + 50, g - 65, 5, 5, o.light === 'on' ? 'lightOn' : o.light === 'done' ? 'lightDone' : 'machineDark', 'washer-light');
  P.rect(X + 60, g - 65, 10, 5, 'red', 'washer-button');
  const door = o.door || 'closed';
  // 里面(开门时看得到):深色 + 一道架子 + 立着的盘子
  if (door !== 'closed') {
    P.rect(X + 5, g - 55, 70, 50, 'machineIn', 'washer-inside');
    P.rect(X + 5, g - 25, 70, 5, 'potRim', 'washer-rack');
    for (let k = 0; k < Math.min(o.rack || 0, 5); k++) { P.rect(X + 15 + k * 12 - (k * 12) % 5, g - 45, 5, 20, 'bowlWhite', 'washer-plate'); P.rect(X + 15 + k * 12 - (k * 12) % 5, g - 45, 5, 5, 'plateFace'); }
  }
  if (door === 'closed') {
    P.rect(X + 5, g - 55, 70, 50, 'machineBody', 'washer-door');
    P.rect(X + 20, g - 50, 40, 5, 'machineDark', 'washer-handle');
    // 门上一扇小圆窗
    P.rect(X + 25, g - 40, 30, 25, 'machineShade', 'washer-window');
    const sw = o.swirl;
    if (sw === undefined || sw === null) P.rect(X + 30, g - 35, 20, 15, 'machineIn');
    else {
      P.rect(X + 30, g - 35, 20, 15, 'blue');
      const k = sw % 3;
      P.rect(X + 30 + k * 5, g - 35 + (k === 1 ? 5 : 0), 5, 5, 'waterLight'); P.rect(X + 45 - k * 5, g - 25 - (k === 2 ? 5 : 0), 5, 5, 'puffWhite');
    }
  } else if (door === 'half') {
    P.rect(X + 5, g - 30, 70, 25, 'machineBody', 'washer-door'); P.rect(X + 5, g - 30, 70, 5, 'machineShade');
  } else {
    // 门放倒了:底下一条往外伸的板
    P.rect(X - 5, g - 10, 90, 5, 'machineBody', 'washer-door'); P.rect(X - 5, g - 5, 90, 5, 'machineShade');
  }
  // 机顶摞着的脏盘子
  for (let k = 0; k < (o.stack || 0); k++) {
    const y = g - 75 - k * 5;
    P.rect(X + 45, y, 30, 5, k % 2 ? 'plateFace' : 'bowlWhite', 'washer-stack');
    if (k === (o.stack || 0) - 1) P.rect(X + 55, y - 5, 5, 5, 'plateDirt');
  }
}

// ── 窗边:窗在他右手边的墙上(paper 层,在他和他的手后面);窗外露一角小贩的条纹篷 ──
function windowFrame(ctx, o = {}) {
  const P = ctx.paper;
  P.rect(235, 140, 65, 100, 'windowSky', 'window');
  P.rect(235, 200, 65, 40, 'windowSkyLow');
  // 条纹篷一角(小贩的车在楼下;只露篷,不画人)
  if (o.awning !== false) {
    for (let k = 0; k < 5; k++) P.rect(255 + k * 10, 145, 10, 15, k % 2 ? 'white' : 'awningRed', 'awning');
    for (let k = 0; k < 5; k++) P.rect(255 + k * 10 + 0, 160, 5, 5, k % 2 ? 'white' : 'awningRed');
  }
  P.rect(230, 135, 70, 5, 'leather', 'window-top');
  P.rect(230, 140, 5, 100, 'leather', 'window-post');
  P.rect(280, 140, 5, 60, 'leatherLight');                      // 窗格
  P.rect(225, 240, 75, 5, 'leatherLight', 'sill'); P.rect(225, 245, 75, 5, 'leatherDark');
}
// 从画面右边伸进来的手(带袖子):tip=手的左边 x;y 手顶;open 摊开掌心(收钱),hold 拿着东西(手指在上)
function vendorHand(ctx, tip, y, o = {}) {
  if (tip >= 300) return;
  const L = ctx.props;
  const sleeveX = tip + 15;
  if (sleeveX < 300) { L.rect(sleeveX, y - 5, 300 - sleeveX, 20, 'vendorSleeve', 'vendor-sleeve'); L.rect(sleeveX, y - 5, 5, 20, 'vendorSleeveDark'); }
  if (o.open) { L.rect(tip, y + 5, 15, 5, 'vendorHand', 'vendor-hand'); L.rect(tip, y + 10, 15, 5, 'vendorHandShade'); L.rect(tip + 10, y, 5, 5, 'vendorHand'); }
  else { L.rect(tip, y, 15, 15, 'vendorHand', 'vendor-hand'); L.rect(tip, y + 10, 15, 5, 'vendorHandShade'); }
}
// 纸袋:左上角 (x,y),25×25;steamK 不为 null 时冒两缕热气
function bag(ctx, x, y, layer = 'letter', steamK = null) {
  const L = ctx[layer];
  L.rect(x, y + 5, 25, 20, 'paper', 'bag'); L.rect(x, y, 25, 5, 'paperEdge'); L.rect(x + 20, y + 5, 5, 20, 'paperEdge');
  L.rect(x + 10, y + 10, 5, 5, 'awningRed');
  if (steamK !== null) for (let m = 0; m < 2; m++) { const ph = (steamK + m * 4) % 9; if (ph < 6) ctx.effects.rect(x + 5 + m * 10, y - 5 - ph * 5, 5, 5, 'puffWhite', 'bag-steam'); }
}
// 一枚硬币 10×10
function coin(ctx, x, y, layer = 'letter') { ctx[layer].rect(x, y, 10, 10, 'gold', 'coin'); ctx[layer].rect(x, y, 5, 5, 'goldLight'); }

module.exports = { palette, HL, HR, LEFT0, SINK_R, path, lerp, sink, rackPlates, bottleStanding, bottleHeld, disc, edge, sponge, towel, cuffs, bubbles, washer, windowFrame, vendorHand, bag, coin, K };
