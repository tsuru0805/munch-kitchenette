// clawds-new-clothes · states/vendor/_stall.cjs · vendor cart, props and scenes by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 流动小贩那一组的公用件:餐车(木屋台,两种摆设)、道具(硬币、糖葫芦、纸袋、铜铃、小心、音符)、十一段场景怎么摆。
// 下划线开头,不登记成动作。
//
// 为什么要「场景」:一段里有两只 Clawd(买东西的厨师 + 小贩)和一辆车,引擎一张 300 画布只放得下一只。
// 所以每只 Clawd 仍是一支标准动作(states/vendor/<id>.cjs,45 帧,id = 文件名,只管姿势),
// 由 tools/dump_vendor.cjs 各自按衣服渲染,贴到一张更宽的场景画布上;车和道具按这里的 SCENES 画在同一张场景上。
// 场景坐标就是引擎像素:宽 W、脚底线 GROUND;一只 Clawd 的 300 画布贴在 (x, CLAWD_DY),
// CLAWD_DY = -3 让它的 5px 细部格(引擎里落在 y ≡ 3)对齐到场景的整 5 格,车和道具都画在整 5 格上。
//
// 两种摆设(variant):
//   'th'    卖糖葫芦的:台面右头立一捆草把子,糖葫芦朝上、朝右插着,递过去的是一串糖葫芦,吃的是咬掉最上面一颗;
//   'plain' 其余小贩:台面右头一只小木箱摞着纸袋,递过去的是一只纸袋,吃的是捧着纸袋凑到嘴边。
// 摆法:小贩站在自己的车台后面(车挡住他下半身,台面上露出眼睛和草帽,像摊主守着摊子),
// 草把子 / 纸袋在台面右头,买方站在车的右边。小贩右手一伸就拿到、一递就到买方左手边,
// 不用换手、不从脸前过,两只手都不必伸出身子很远。推车时他也在车后面推,停下转过身就站在原地开张。

const W = 430, H = 285, GROUND = 270, CLAWD_DY = -3, CART_DY = GROUND - 200;
const CX = -10;                    // 车停好时车的左上角 x(车自己的画布 270 宽,底线 200)
const VX = CX + 15;                // 小贩那张 300 画布贴在哪(身子落在车里 105 .. 225,台面后面)
const BX = CX + 195;               // 买方那张 300 画布贴在哪(身子落在车里 285 .. 405,车的右边)

const palette = {
  strawBundle: '#e9c66c', strawBundleDark: '#b98d3c', glaze: '#f4a08e',
  kraft: '#d9b27a', kraftDark: '#a87d48', kraftLight: '#ecd3a6'
};

// ── 手:用「画出来的左上角」写,换算成姿势坐标(引擎收尾时左手 x−10、右手 x+10、两只 y+5)──
// 手画在身子上(x 落在 90 .. 210 里)自动换 skinSide,不然皮肤叠皮肤看不见
const over = (X) => X + 20 > 90 && X < 210;
function HL(X, Y) { const h = { x: X + 10, y: Y - 5, a: 0 }; if (over(X)) h.color = 'skinSide'; return h; }
function HR(X, Y) { const h = { x: X - 10, y: Y - 5, a: 0 }; if (over(X)) h.color = 'skinSide'; return h; }
const L0 = [70, 223], R0 = [210, 223];            // 两只手垂着时画在哪
const snap = (v) => Math.round(v / 5) * 5;
// 一串关键帧 [[帧, X, Y], …] → 第 i 帧的 [X, Y](两点之间线性、对到 5 格)
function path(keys, i) {
  if (i <= keys[0][0]) return [keys[0][1], keys[0][2]];
  for (let k = 1; k < keys.length; k++) {
    const [f1, x1, y1] = keys[k - 1], [f2, x2, y2] = keys[k];
    if (i <= f2) { const t = (i - f1) / (f2 - f1); return [snap(x1 + (x2 - x1) * t), snap(y1 + (y2 - y1) * t)]; }
  }
  const last = keys[keys.length - 1];
  return [last[1], last[2]];
}
const within = (i, a, b) => i >= a && i <= b;

// ── 推车走路:身子每帧走 10,脚踩实了就不滑 ──
// 四只脚两两一组交替:着地那组每帧往后退 10(= 身子前进的 10,所以落在地上不动),
// 抬起那组 3 帧里从后面荡到前面。一步 3 帧,一个来回 6 帧。
const STEP = 10;
const PLANT = [15, 5, -5], SWING = [0, 10, 15];
function stride(k) {
  const a = k % 6, b = (k + 3) % 6;
  const off = (q) => (q < 3 ? PLANT[q] : SWING[q - 3]);
  const lift = (q) => (q < 3 ? 0 : 5);
  return { footOffsets: [off(a), off(b), off(a), off(b)], feet: [lift(a), lift(b), lift(a), lift(b)] };
}
// 摆臂:走路时两只手跟着步子前后错开 5
function armSwing(k) { return (k % 6) < 3 ? 5 : -5; }
// 买方走过去:0–19 帧在走,离车边的位置还差多少(往右为正,他从画面右边往左走过来);20 起停住
const WALK_STEPS = 20;
function walkinOffset(i) { return i < WALK_STEPS ? STEP * (WALK_STEPS - i) : 0; }
// 买方走回去:0–2 帧点头、转身,3 起往右走出画面
function walkoutOffset(i) { return i < 3 ? 0 : STEP * (i - 2); }
// 进场:0–41 帧在走,离停好的位置还差多少(往右为正:他在车后面推着车,从画面右边往左进来);42 起停住
const ARRIVE_LAST_STEP = 41;
function arriveOffset(i) { return i <= ARRIVE_LAST_STEP ? STEP * (ARRIVE_LAST_STEP - i) : 0; }
// 离开:0–2 帧眨眼、转身扶住台面,3 起往左推出画面(第 28 帧前后整个出去,后面是空着的路边)
function leaveOffset(i) { return i < 3 ? 0 : i === 3 ? 5 : 15 + STEP * (i - 4); }

// ── 画:P.rect(x, y, w, h, color) / P.pat(rows, x, y, color, unit=5),场景坐标 ──
function coin(P, x, y) { P.rect(x, y, 10, 10, 'gold'); P.rect(x, y, 5, 5, 'goldLight'); }

// 一颗山楂:十字形 15×15,左边一格糖壳亮光
function haw(P, x, y) { P.pat(['010', '111', '010'], x, y, 'red'); P.rect(x, y + 5, 5, 5, 'glaze'); }
// 竖着拿的糖葫芦:(x, y) = 拿着它的那只手画出来的左上角;竹签插在手心,往上一颗挨一颗
function tanghulu(P, hand, balls = 3) {
  const x = hand.x + 5, y = hand.y;
  for (let k = 0; k < balls; k++) haw(P, x, y - 15 * (k + 1));
  P.rect(x + 5, y - 15 * balls - 10, 5, 10, 'paperEdge');
}
// 横插在草把上的糖葫芦:x = 插进草把那一头,向左(left)或向右伸
function tanghuluSide(P, x, y, balls, left) {
  P.rect(left ? x - 10 : x, y + 5, 10, 5, 'paperEdge');
  for (let k = 0; k < balls; k++) {
    const bx = left ? x - 10 - 15 * (k + 1) : x + 10 + 15 * k;
    P.pat(['010', '111', '010'], bx, y, 'red'); P.rect(bx + 5, y, 5, 5, 'glaze');
  }
  P.rect(left ? x - 10 - 15 * balls - 5 : x + 10 + 15 * balls, y + 5, 5, 5, 'paperEdge');
}
// 纸袋:拿着它的那只手上面;折口深一道、正面一枚红贴纸
function bag(P, hand) {
  const x = hand.x, y = hand.y - 20;
  P.rect(x, y + 5, 20, 15, 'kraft'); P.rect(x, y, 20, 5, 'kraftDark'); P.rect(x + 5, y + 10, 5, 5, 'red'); P.rect(x + 15, y + 5, 5, 15, 'kraftDark');
}
function crumbs(P, x, y, k) {
  const pts = [[0, 0], [15, -5], [-5, -10], [20, 5]];
  for (let j = 0; j < 2 + (k % 2); j++) { const [dx, dy] = pts[(j + k) % 4]; P.rect(x + dx, y + dy - 5 * (k % 2), 5, 5, 'goldLight'); }
}
// 手摇铜铃(柄朝上、铃身坐在手上、铃舌在下沿):swing = -5 / 0 / 5 整只左右摆;ring 时两边各一道亮线
function bell(P, hand, swing = 0, ring = false) {
  const x = hand.x + swing, y = hand.y;
  P.rect(x + 5, y - 35, 10, 10, 'leather');
  P.pat(['0110', '1111', '1111'], x, y - 25, 'gold');
  P.rect(x - 5, y - 10, 30, 5, 'gold');
  P.rect(x + 5, y - 20, 5, 10, 'goldLight');
  P.rect(x + 5 - swing, y - 5, 5, 5, 'leatherDark');
  if (ring) { P.rect(hand.x - 15, y - 30, 5, 15, 'goldLight'); P.rect(hand.x + 30, y - 30, 5, 15, 'goldLight'); }
}
function note(P, x, y, big) { P.pat(big ? ['0011', '0010', '0010', '1110', '1110'] : ['011', '010', '110'], x, y, 'goldLight'); }
function heart(P, x, y) { P.pat(['1010', '1111', '0110'], x, y, 'red'); P.rect(x, y, 5, 5, 'redLight'); }
function sparkle(P, x, y) { P.pat(['010', '111', '010'], x, y, 'goldLight'); }

// ── 车:自己的画布 270×200,底线 200;矮台子(台面在 160,刚好在他眼睛下沿),篷布罩在头顶 ──
// x 是车的左上角(场景坐标);phase 轮辐转到哪(0/1);taken 递出去的那件已经被拿走了。
// back 画在小贩后面(篷布、杆子、灯笼),front 画在小贩前面(台子、轮子、草把子 / 纸袋)。
function wheel(P, x, y, phase) {
  P.pat(['01110', '10001', '10001', '10001', '01110'], x, y, 'leatherDark');
  const spokes = phase % 2 === 0 ? [[2, 1], [2, 3], [1, 2], [3, 2]] : [[1, 1], [3, 3], [1, 3], [3, 1]];
  for (const [c, r] of spokes) P.rect(x + c * 5, y + r * 5, 5, 5, 'leatherLight');
  P.rect(x + 10, y + 10, 5, 5, 'gold');
}
function cartBack(P, variant, x0) {
  const y0 = CART_DY, R = (x, y, w, h, c) => P.rect(x0 + x, y0 + y, w, h, c);
  R(35, 40, 5, 120, 'leatherDark'); R(220, 40, 5, 120, 'leatherDark');
  R(30, 25, 200, 5, 'red');
  for (let k = 0; k < 21; k++) { const c = k % 2 === 0 ? 'red' : 'white'; R(25 + k * 10, 30, 10, 20, c); if (k % 2 === 0) R(25 + k * 10, 50, 10, 5, c); }
  // 小红灯笼挂在左头
  R(60, 55, 5, 5, 'leatherDark'); R(55, 60, 15, 5, 'gold'); R(50, 65, 25, 20, 'red'); R(55, 65, 5, 20, 'redLight'); R(55, 85, 15, 5, 'gold'); R(60, 90, 5, 5, 'goldLight');
}
function cartFront(P, variant, x0, { phase = 0, taken = false } = {}) {
  const y0 = CART_DY, R = (x, y, w, h, c) => P.rect(x0 + x, y0 + y, w, h, c);
  // 台子:台面一道、木板、正面一张红纸菱形招牌
  R(25, 160, 210, 5, 'leather');
  R(30, 165, 200, 20, 'leatherDark'); R(35, 165, 190, 15, 'leatherLight'); R(35, 170, 190, 5, 'leather');
  P.pat(['010', '111', '010'], x0 + 120, y0 + 165, 'red'); R(125, 170, 5, 5, 'goldLight');
  wheel(P, x0 + 45, y0 + 175, phase); wheel(P, x0 + 190, y0 + 175, phase);
  if (variant === 'th') {
    // 草把子:台面右头一捆稻草,糖葫芦朝上两串、朝右两串;右下那串是递出去的那串
    R(205, 110, 25, 50, 'strawBundle'); R(210, 105, 15, 5, 'strawBundle');
    R(205, 120, 25, 5, 'strawBundleDark'); R(205, 145, 25, 5, 'strawBundleDark');
    for (const [x, n] of [[205, 2], [215, 3]]) {
      P.rect(x0 + x + 5, y0 + 105 - 15 * n - 10, 5, 10, 'paperEdge');
      for (let k = 0; k < n; k++) haw(P, x0 + x, y0 + 105 - 15 * (k + 1));
    }
    tanghuluSide(P, x0 + 230, y0 + 115, 2, false);
    if (!taken) tanghuluSide(P, x0 + 230, y0 + 135, 1, false);
  } else {
    // 小木箱摞着纸袋;右边那只是递出去的那只
    R(200, 140, 30, 20, 'leather'); R(200, 140, 30, 5, 'leatherLight'); R(205, 150, 20, 5, 'leatherDark');
    R(200, 120, 15, 20, 'kraft'); R(200, 120, 15, 5, 'kraftDark'); R(205, 130, 5, 5, 'red');
    if (!taken) { R(215, 125, 15, 15, 'kraftLight'); R(215, 125, 15, 5, 'kraftDark'); R(220, 130, 5, 5, 'red'); }
  }
}
function ground(P) { for (let x = 0; x < W; x += 30) P.rect(x, GROUND + 3, 20, 3, 'paperEdge'); }

// 轮子转多少:按走过的路程,每 15 换一次辐条
const phaseOf = (dist) => Math.floor(Math.abs(dist) / 15) % 2;

// ── 场景(七段 + 买方走过去、走回去) ──
// 每段:vendor / buyer = 哪支动作(buyer 为空 = 只有小贩);layout(i) 每只的画布贴在哪、车在哪;
// paint(P, i, s, variant) 画手里的东西和小特效,s.v / s.b 是两只 Clawd 这一帧真画出来的手(场景坐标,左手在前)。
// 画的先后:地 → 车的后半(篷布、杆子)→ 小贩 → 车的前半(台子、草把子)→ 买方 → paint。
// 每段 45 帧;arrive 的末帧 = call / wait 的首帧,leave 的末帧是空着的路边,give 的末帧 = eat 的首帧。
const SCENES = {
  arrive: {
    vendor: 'peddler-arrive', buyer: null, once: true,
    layout(i) { const d = arriveOffset(i); return { cart: { x: CX + d, phase: phaseOf(d) }, vendor: VX + d }; },
    paint(P, i) {
      const d = arriveOffset(i);
      if (i <= ARRIVE_LAST_STEP && i % 3 !== 2) { P.rect(VX + d + 215, GROUND - 5, 5, 5, 'paperEdge'); P.rect(VX + d + 225, GROUND - 10, 5, 5, 'paperEdge'); }
      if (i === 42 || i === 43) { const k = i - 42; P.rect(CX + 30 - 5 * k, GROUND - 5 - 5 * k, 5, 5, 'paperEdge'); P.rect(CX + 175 + 5 * k, GROUND - 5 - 5 * k, 5, 5, 'paperEdge'); }
    }
  },
  call: {
    vendor: 'peddler-call', buyer: null,
    layout() { return { cart: { x: CX }, vendor: VX }; },
    paint(P, i, s) {
      if (i >= 1 && i <= 41) { const ringing = within(i, 4, 37); bell(P, s.v[0], ringing ? [-5, 0, 5, 0][i % 4] : 0, ringing && i % 2 === 0); }
      // 吆喝:帽顶冒音符往上飘
      for (const [ph, big, x] of [[6, true, VX + 150], [16, false, VX + 170], [24, true, VX + 140]]) {
        const k = i - ph;
        if (k >= 0 && k < 12) note(P, x + ((k >> 2) % 2) * 5, 150 - 5 * (k >> 1), big);
      }
    }
  },
  wait: {
    vendor: 'peddler-wait', buyer: null,
    layout() { return { cart: { x: CX }, vendor: VX }; },
    paint() {}
  },
  leave: {
    vendor: 'peddler-leave', buyer: null, once: true,
    layout(i) { const d = leaveOffset(i); return { cart: { x: CX - d, phase: phaseOf(d) }, vendor: VX - d }; },
    paint(P, i) {
      const d = leaveOffset(i);
      if (i >= 3 && i % 3 !== 2) { P.rect(VX - d + 215, GROUND - 5, 5, 5, 'paperEdge'); P.rect(VX - d + 225, GROUND - 10, 5, 5, 'paperEdge'); }
    }
  },
  walkin: {
    vendor: 'peddler-greet', buyer: 'buyer-walkin',
    layout(i) { return { cart: { x: CX }, vendor: VX, buyer: BX + walkinOffset(i) }; },
    paint(P, i) {
      const d = walkinOffset(i);
      if (i < WALK_STEPS && i % 3 !== 2) { P.rect(BX + d + 215, GROUND - 5, 5, 5, 'paperEdge'); P.rect(BX + d + 225, GROUND - 10, 5, 5, 'paperEdge'); }
    }
  },
  pay: {
    vendor: 'peddler-pay', buyer: 'buyer-pay',
    layout() { return { cart: { x: CX }, vendor: VX, buyer: BX }; },
    paint(P, i, s) {
      const bh = s.b[0], vh = s.v[1];
      // 两枚硬币:先在买方左手里,第 8 / 12 帧各跳一枚(4 帧一条弧),落在小贩右手心;小贩的手收到台面下面那一下叮一声
      for (let n = 0; n < 2; n++) {
        const t0 = 8 + 4 * n, k = i - t0;
        if (i >= 1 && i < t0) coin(P, bh.x + 10 * n, bh.y - 10);
        else if (k >= 0 && k < 4) {
          const sx = bh.x + 10 * n, sy = bh.y - 10, tx = vh.x + 10 * n, ty = vh.y - 10, t = (k + 1) / 4;
          coin(P, snap(sx + (tx - sx) * t), snap(sy + (ty - sy) * t - 15 * Math.sin(Math.PI * t)));
        } else if (k >= 4 && i <= 18) coin(P, vh.x + 10 * n, vh.y - 10);
      }
      if (i === 20 || i === 21) sparkle(P, VX + 230, CLAWD_DY + 210 - 5 * (i - 20));
    }
  },
  give: {
    vendor: 'peddler-give', buyer: 'buyer-give', once: true,
    layout(i) { return { cart: { x: CX, taken: i >= 7 }, vendor: VX, buyer: BX }; },
    paint(P, i, s, variant) {
      const item = variant === 'th' ? (h) => tanghulu(P, h, 3) : (h) => bag(P, h);
      if (i >= 7 && i < 18) item(s.v[1]);
      else if (i >= 18) item(s.b[0]);
      if (within(i, 27, 40)) heart(P, BX + 190, 125 - 5 * ((i - 27) >> 1));
    }
  },
  eat: {
    vendor: 'peddler-eat', buyer: 'buyer-eat', once: true,
    layout() { return { cart: { x: CX, taken: true }, vendor: VX, buyer: BX }; },
    paint(P, i, s, variant) {
      const h = s.b[0];
      if (variant === 'th') {
        tanghulu(P, h, i < 9 ? 3 : 2);
        if (within(i, 9, 14)) crumbs(P, h.x, h.y - 50, i);
      } else {
        bag(P, h);
        if (within(i, 9, 22) && i % 4 < 2) crumbs(P, h.x, h.y - 25, i);
      }
      if (within(i, 22, 36)) heart(P, BX + 190, 125 - 5 * ((i - 22) >> 1));
    }
  },
  // 买方捧着东西走回去:吃过一口的(糖葫芦少一颗)、只是拿着的(食材、花)、空着手的(退了款、没扣成)
  walkout: walkout('eaten'),
  walkout_hold: walkout('hold'),
  walkout_empty: walkout('empty')
};
function walkout(item) {
  return {
    vendor: 'peddler-bye', buyer: 'buyer-walkout',
    layout(i) { return { cart: { x: CX, taken: item !== 'empty' }, vendor: VX, buyer: BX + walkoutOffset(i) }; },
    paint(P, i, s, variant) {
      const d = walkoutOffset(i);
      if (i >= 3 && i % 3 !== 2) { P.rect(BX + d + 80, GROUND - 5, 5, 5, 'paperEdge'); P.rect(BX + d + 70, GROUND - 10, 5, 5, 'paperEdge'); }
      if (item === 'empty') return;
      const h = i <= 1 ? s.b[0] : s.b[1];
      if (variant === 'th') tanghulu(P, h, item === 'eaten' ? 2 : 3);
      else bag(P, h);
    }
  };
}
const ORDER = ['arrive', 'call', 'wait', 'leave', 'walkin', 'pay', 'give', 'eat', 'walkout', 'walkout_hold', 'walkout_empty'];

module.exports = {
  W, H, GROUND, CLAWD_DY, CART_DY, CX, VX, BX, palette, HL, HR, L0, R0, path, within, snap,
  stride, armSwing, WALK_STEPS, arriveOffset, leaveOffset, walkinOffset, walkoutOffset, ARRIVE_LAST_STEP, cartBack, cartFront, ground, SCENES, ORDER
};
