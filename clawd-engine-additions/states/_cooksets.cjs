// clawds-new-clothes · states/_cooksets.cjs · kitchen clips factory by tsuru0805 · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// 七种做法(炒 stirfry / 煎 fry / 炸 deepfry / 煮 boil / 蒸 steam / 烤 bake / 拌 mix)各有一套家伙(SCENES),
// 每种做法除了自己的主动作(cook-<m>-main.cjs,手画)之外,另外六段由这里按同一个骨架出:
//   wipe 擦汗 / look 抬头看过来 / hot 被热气熏到(拌=偷吃一口) / taste 尝一口加调料 / serve 装盘端上来 / fail 糊了
// 每段首帧都是「站好、看着锅、家伙摆在原位」,所以同一种做法里各段怎么接都不跳。
const K = require('./_kitchen.cjs');
const REST = [{ x: 80, y: 218 }, { x: 225, y: 218 }];

// 一盘 / 一碗菜:画在两只手中间(letter 层,手之上)
function dish(ctx, kind, burnt) {
  const [l, r] = ctx.hands;
  // 盘子固定 50 宽:两手捧拢了就在两手正中;刚端出来两手还离得远时,先托在右手那边
  const far = r.x - l.x > 80;
  const w = 50, x = far ? r.x - 20 : Math.round((l.x + r.x + 20) / 2 / 5) * 5 - 25, y = (far ? r.y : l.y) + 5;
  const c = (ok) => (burnt ? 'soupBurnt' : ok);
  if (kind === 'bowl') {
    ctx.letter.rect(x + 5, y - 5, w - 10, 5, c('noodle'), 'bowl-food');
    ctx.letter.rect(x, y, w, 5, 'bowlWhite', 'bowl'); ctx.letter.rect(x, y + 5, w, 5, 'blue'); ctx.letter.rect(x + 5, y + 10, w - 10, 5, 'bowlWhite');
  } else if (kind === 'salad') {
    ['vegGreen', 'vegOrange', 'vegGreenDark', 'noodle', 'vegGreen'].forEach((k, n) => ctx.letter.rect(x + 5 + n * 5, y - 5, 5, 5, c(k), 'leaf'));
    ctx.letter.rect(x, y, w, 5, 'bowlWhite', 'bowl'); ctx.letter.rect(x + 5, y + 5, w - 10, 5, 'blue'); ctx.letter.rect(x + 10, y + 10, w - 20, 5, 'bowlWhite');
  } else {
    // 盘子:一条白边 + 上面的菜
    ctx.letter.rect(x, y + 5, w, 5, 'bowlWhite', 'plate'); ctx.letter.rect(x + 5, y + 10, w - 10, 5, 'potRim');
    if (kind === 'buns') for (let n = 0; n < 3; n++) { const bx = x + 2 + n * Math.floor((w - 12) / 2); ctx.letter.rect(bx - bx % 5 + 0, y, 10, 5, c('bunWhite'), 'bun'); ctx.letter.rect(bx - bx % 5 + 0, y - 5, 10, 5, c('bunWhite')); }
    else if (kind === 'loaf') { ctx.letter.rect(x + 5, y - 5, w - 10, 10, c('friedBrown'), 'loaf'); ctx.letter.rect(x + 10, y - 10, w - 20, 5, c('friedBrown')); }
    else if (kind === 'patty') ctx.letter.rect(x + 5, y, w - 10, 5, c('friedBrown'), 'patty');
    else if (kind === 'fried') for (let n = 0; n < 3; n++) ctx.letter.rect(x + 5 + n * 10, y - (n === 1 ? 5 : 0), 10, 5 + (n === 1 ? 5 : 0), c('friedGold'), 'fry-piece');
    else ['vegGreen', 'vegOrange', 'noodle', 'vegGreenDark'].forEach((k, n) => ctx.letter.rect(x + 5 + n * 7 - (n * 7) % 5, y, 5, 5, c(k), 'food'));
  }
}

// ── 七套家伙:rest=摆在原位的样子(k 帧号;burnt 糊了;gone 菜已经盛走;off 火关了) ──
const SCENES = {
  stirfry: {
    label: '炒', reach: { x: 230, y: 208 }, dish: 'plate', heat: true,
    rest(ctx, k, o = {}) {
      const g = ctx.baseline;
      K.stove(ctx, k, !o.off); K.panOnStove(ctx);
      if (!o.gone) ['vegGreen', 'vegOrange', 'noodle', 'vegGreenDark'].forEach((c, n) => ctx.effects.rect(258 + n * 8 - (n * 8) % 5, g - 55, 5, 5, o.burnt ? 'soupBurnt' : c, 'food'));
    }
  },
  fry: {
    label: '煎', reach: { x: 230, y: 208 }, dish: 'patty', heat: true,
    rest(ctx, k, o = {}) {
      const g = ctx.baseline;
      K.stove(ctx, k, !o.off); K.panOnStove(ctx);
      if (!o.gone) ctx.effects.rect(258, g - 55, 25, 5, o.burnt ? 'soupBurnt' : 'friedBrown', 'patty');
      if (!o.off && !o.gone && !o.burnt) K.sparks(ctx, k, g - 60);
    }
  },
  deepfry: {
    label: '炸', reach: { x: 225, y: 213 }, dish: 'fried', heat: true,
    rest(ctx, k, o = {}) { K.oilPot(ctx, k, !o.off && !o.gone); if (o.burnt) ctx.props.rect(225, ctx.baseline - 40, 60, 5, 'soupBurnt', 'oil-burnt'); }
  },
  boil: {
    label: '煮', reach: { x: 230, y: 213 }, dish: 'bowl', heat: true,
    rest(ctx, k, o = {}) {
      const g = ctx.baseline;
      K.pot(ctx, !!o.burnt);
      if (o.open) return;
      const hop = !o.off && k % 6 < 2 ? 5 : 0;
      K.lid(ctx, 220, g - 45 - hop);
      if (hop) { K.puff(ctx, 205, g - 60, 0); K.puff(ctx, 290, g - 60, 0); }
    }
  },
  steam: {
    label: '蒸', reach: { x: 235, y: 198 }, dish: 'buns', heat: true,
    rest(ctx, k, o = {}) {
      const g = ctx.baseline;
      K.steamer(ctx, !!o.open && !o.gone);
      if (!o.open) K.steamerLid(ctx, 220, g - 55);
      if (!o.off) for (let n = 0; n < 3; n++) { const ph = (k + n * 5) % 15; K.puff(ctx, 215 + n * 30 + (ph % 2 ? 5 : 0), g - 75 - ph * 5, ph < 5 ? 0 : 1); }
    }
  },
  bake: {
    label: '烤', reach: { x: 205, y: 223 }, dish: 'loaf', heat: true, mitts: true,
    rest(ctx, k, o = {}) { K.oven(ctx, o.off ? 0 : k, !!o.done || !!o.burnt); if (o.burnt) ctx.props.rect(245, ctx.baseline - 30, 25, 10, 'soupBurnt', 'loaf-burnt'); if (o.gone) ctx.props.rect(245, ctx.baseline - 35, 25, 15, 'ovenGlow', 'loaf-gone'); }
  },
  mix: {
    label: '拌', reach: { x: 225, y: 198 }, dish: 'salad', heat: false,
    rest(ctx, k, o = {}) { K.table(ctx); if (!o.gone) K.saladBowl(ctx, o.still ? 2 : k); }
  }
};

function finish(scene, ctx) { if (scene.mitts) { K.mitt(ctx, ctx.hands[0]); K.mitt(ctx, ctx.hands[1]); } }
const base = (o = {}) => ({ hands: REST.map((h) => ({ ...h })), gazeX: 5, gazeY: 5, ...o });

const CLIPS = {
  // 擦汗:抬起左手在额头上抹一下,甩掉一滴汗
  wipe: {
    label: '擦汗',
    pose(i, sc) {
      if (i < 8 || i >= 34) return base({ eyes: 'open' });
      if (i < 12) return base({ hands: [{ x: 85 + (i - 8) * 5, y: 213 - (i - 8) * 5 }, REST[1]], eyes: 'half' });
      if (i < 24) return base({ hands: [{ x: 100 + (i - 12) * 5, y: 188 }, REST[1]], eyes: 'closed', gazeX: 0, gazeY: 0 });
      const t = Math.min(1, (i - 24) / 9);   // 手从额头右边放回身侧
      return base({ hands: [{ x: Math.round((155 - t * 75) / 5) * 5, y: Math.round((188 + t * 30) / 5) * 5 }, REST[1]], eyes: i < 28 ? 'closed' : 'open' });
    },
    paint(ctx, p, i, sc) {
      sc.rest(ctx, i, { still: true });
      if (i >= 4 && i < 14) ctx.effects.pattern(['010', '111', '111'], ctx.body.x + ctx.body.w, ctx.body.y - 10, 'blue', 5, 'sweat');
      if (i >= 24 && i < 30) ctx.effects.rect(70 - (i - 24) * 5, 200 + (i - 24) * 5, 5, 5, 'blue', 'sweat-fly');
    }
  },
  // 抬头看过来:不看锅了,正对着屏幕外眨眨眼,左手挥两下
  look: {
    label: '抬头看过来',
    pose(i, sc, { closedAt }) {
      const on = i >= 8 && i <= 36;
      const wave = on && i >= 14 && i <= 30;
      return base({
        gazeX: on ? 0 : 5, gazeY: on ? -5 : 5,
        hands: [{ x: wave ? 65 : 80, y: wave ? (i % 4 < 2 ? 193 : 203) : 218 }, REST[1]],
        eyes: closedAt(11, 33) || (i >= 22 && i <= 26) ? 'closed' : 'open'
      });
    },
    paint(ctx, p, i, sc) { sc.rest(ctx, i, { still: true }); if (i >= 22 && i <= 30) ctx.lettering.pattern(ctx.shapes.miniHeart, ctx.body.x - 30, ctx.body.y - 20 - (i - 22) * 5, 'red', 5, 'heart'); }
  },
  // 被热气熏到:一团汽扑到脸上,往后一缩闭眼,拿手扇两下;拌菜没有火=偷吃一口
  hot: {
    label: '被热气熏到',
    pose(i, sc) {
      if (!sc.heat) {
        // 偷吃:右手从碗里捏一片送到脸下面,眯眼
        if (i < 8 || i >= 36) return base();
        if (i < 14) return base({ hands: [REST[0], { x: 225 - (i - 8) * 0, y: 203 }] });
        if (i < 20) return base({ hands: [REST[0], { x: 225 - (i - 14) * 15, y: 208 + (i - 14) * 5 }] });
        return base({ hands: [REST[0], { x: 150, y: 233 }], eyes: 'closed', gazeX: 0, gazeY: 0, squash: i % 6 < 3 ? 5 : 0 });
      }
      if (i < 10 || i >= 38) return base();
      if (i < 14) return base({ eyes: 'half' });
      const fan = i >= 22;
      return base({ dx: -5, eyes: 'closed', hands: [{ x: fan ? 175 : 80, y: fan ? (i % 4 < 2 ? 188 : 198) : 218 }, { x: 205, y: 208 }] });
    },
    paint(ctx, p, i, sc) {
      sc.rest(ctx, i, { still: true });
      if (!sc.heat) { if (i >= 14 && i < 36) ctx.letter.rect(ctx.hands[1].x + 5, ctx.hands[1].y - 5, 5, 5, 'vegGreen', 'leaf-snack'); return; }
      if (i >= 8 && i < 26) { const t = i - 8; K.puff(ctx, 235 - Math.min(30, t * 5), ctx.baseline - 75 - Math.min(20, t * 5), t < 4 ? 1 : 2); }
    },
    check: { eyesCovered: [[14, 37]] }
  },
  // 尝一口、加调料:小勺伸进去 → 送到脸下面 → 闭眼咂摸 → 亮一下 → 拿调料瓶往里抖
  taste: {
    label: '尝一口加调料',
    pose(i, sc) {
      const R = sc.reach;
      if (i < 4) return base();
      if (i < 8) return base({ hands: [REST[0], { x: R.x, y: R.y + 5 }] });
      if (i < 13) return base({ hands: [REST[0], { x: R.x - (i - 8) * 15, y: R.y + 5 + Math.round((233 - R.y - 5) * (i - 8) / 4 / 5) * 5 }] });
      if (i < 24) return base({ hands: [REST[0], { x: 155, y: 233 }], eyes: 'closed', gazeX: 0, gazeY: 0, squash: i >= 18 && i < 21 ? 5 : 0 });
      if (i < 27) return base({ hands: [REST[0], { x: 190, y: 223 }], eyes: 'star', gazeX: 0, gazeY: 0 });
      if (i < 41) return base({ hands: [REST[0], { x: R.x, y: R.y - 25 + (i % 4 < 2 ? 0 : 5) }] });
      return base();
    },
    paint(ctx, p, i, sc) {
      sc.rest(ctx, i, { still: true, open: sc === SCENES.boil || sc === SCENES.steam ? (i >= 4 && i < 41) : false });
      const h = ctx.hands[1];
      if (i >= 4 && i < 24) { ctx.letter.rect(h.x + 15, h.y + 5, 10, 5, 'leather', 'tasting-spoon'); ctx.letter.rect(h.x + 25, h.y + 5, 5, 5, 'knifeSteel'); }
      if (i >= 24 && i < 27) ctx.effects.pattern(ctx.shapes.sparkle, ctx.body.x + ctx.body.w - 10, ctx.body.y - 25, 'flameIn', 5, 'yum');
      if (i >= 27 && i < 41) {
        ctx.letter.rect(h.x + 15, h.y + 5, 10, 15, 'bowlWhite', 'shaker'); ctx.letter.rect(h.x + 15, h.y, 10, 5, 'chefRedCap', 'shaker-cap');
        for (let n = 0; n < 3; n++) { const ph = (i + n * 2) % 6; ctx.effects.rect(h.x + 20 + n * 5, h.y + 25 + ph * 5, 5, 5, 'puffWhite', 'salt'); }
      }
    },
    check: { eyesCovered: [[12, 26]] }
  },
  // 装盘端上来:伸手进去 → 一把端出来 → 两手捧到胸前 → 眯眼笑,一颗心长大
  serve: {
    label: '装盘端上来',
    pose(i, sc, { snap5 }) {
      const R = sc.reach;
      if (i < 8) return base();
      if (i < 12) return base({ dx: 5, hands: [REST[0], { x: R.x, y: R.y + 10 }] });
      const t = Math.min(1, (i - 12) / 7);
      const heart = i >= 22 ? Math.min(1, 0.12 + (i - 22) * 0.06) : 0;
      return { jump: i === 12 ? -10 : 0, hands: [{ x: snap5(80 + t * 45), y: snap5(208 + t * 15) }, { x: snap5(230 - t * 75), y: snap5(208 + t * 15) }], eyes: i >= 18 ? 'closed' : 'open', tool: heart ? { heart } : {} };
    },
    paint(ctx, p, i, sc) {
      sc.rest(ctx, i, { still: true, gone: i >= 12, off: i >= 12, done: true, open: i >= 8 });
      if (i >= 12) { dish(ctx, sc.dish, false); if (sc.heat) K.steam(ctx, i, ctx.hands[0].x + 20); }
    },
    check: { eyesCovered: [[12, 44]], airborne: [12] }
  },
  // 糊了:闻到不对 → 冒烟吓得往后一蹦 → 烟越冒越大 → 伸手关火 → 端着一盘黑的,垂着眼冒汗
  fail: {
    label: '糊了',
    pose(i, sc, { snap5 }) {
      const R = sc.reach;
      if (i < 5) return base();
      if (i < 12) return base({ eyes: 'half', squash: i % 4 < 2 ? 0 : 5 });
      if (i === 12) return { dx: -10, jump: -15, hands: [{ x: 70, y: 198 }, { x: 205, y: 198 }], eyes: 'dot', feet: [5, 5, 5, 5] };
      if (i < 24) return { dx: -10, hands: [{ x: 70, y: 213 }, { x: 205, y: 213 }], eyes: 'dot' };
      if (i < 30) return { dx: 0, hands: [REST[0], { x: R.x, y: R.y + 10 }], eyes: 'dot', gazeX: 5, gazeY: 5 };
      const t = Math.min(1, (i - 30) / 6);
      return { dx: -5, hands: [{ x: snap5(75 + t * 45), y: snap5(208 + t * 15) }, { x: snap5(225 - t * 75), y: snap5(208 + t * 15) }], eyes: 'half', gazeX: 0, gazeY: 5 };
    },
    paint(ctx, p, i, sc) {
      sc.rest(ctx, i, { still: true, burnt: i >= 8, off: i >= 27, gone: i >= 30, open: i >= 8 });
      if (i >= 6 && i < 34) K.smoke(ctx, Math.min(1, (i - 6) / 24));
      if (i >= 30) dish(ctx, sc.dish, true);
      if (i >= 34) ctx.effects.pattern(['010', '111', '111'], ctx.body.x + ctx.body.w + 5, ctx.body.y - 5, 'blue', 5, 'sweat');
    },
    check: { airborne: [12], eyesCovered: [[30, 44]] }
  }
};

const palette = { ...K.palette, chefRedCap: '#d8463c' };

function make(m, kind) {
  const sc = SCENES[m], c = CLIPS[kind];
  if (!sc || !c) throw new Error(`没有这一段:${m}/${kind}`);
  return {
    id: `cook-${m}-${kind}`, label: `${sc.label} · ${c.label}`, frames: 45, ms: [70, 60, 70], group: 'prop', palette,
    pose(i, ctx) { return c.pose(i, sc, ctx); },
    paint(ctx, p, i) { c.paint(ctx, p, i, sc); finish(sc, ctx); },
    ...(c.check ? { check: c.check } : {})
  };
}
module.exports = { SCENES, CLIPS, make, dish, palette };
