// munch-kitchenette · tools/dump_vendor.cjs · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// Renders the vendor scenes (states/vendor/: the vendor pushing his cart in, calling, waiting, leaving, and a cook
// buying from him). A scene has two Clawds and a cart, which do not fit one 300 px engine canvas: each Clawd is a
// normal move of its own (45 frames, id = file name, poses only), rendered by the engine in its outfit (the vendor
// always in `vendor-straw`, the buyer in the outfit given here) and pasted onto a wider scene; the cart, the things
// in their hands and the small marks are drawn on the same scene by states/vendor/_stall.cjs, on the same 5 px grid.
// Writes, per scene, the raw RGBA of 45 frames of the scene (W x ROWS, rows TOP..TOP+ROWS of the scene).
// Usage: node dump_vendor.cjs <engine dir> <output dir> <th|plain> <buyer outfit> [scene ...]   (called by export_vendor.py)
const path = require('node:path'), fs = require('node:fs');
const [, , engDir, outDir, variant, buyerOutfit, ...only] = process.argv;
if (!['th', 'plain'].includes(variant)) throw Error(`variant must be th or plain, got ${variant}`);
const eng = path.resolve(engDir);
const m = require(path.join(eng, 'motion.cjs'));
// The engine registers only files directly in states/; these live in states/vendor/ (so a normal export never
// sees them) and are registered here as drafts, for this one process. Files starting with "_" are helpers.
const DIR = path.join(eng, 'states', 'vendor');
for (const f of fs.readdirSync(DIR).filter((n) => n.endsWith('.cjs') && !n.startsWith('_')).sort()) {
  const st = m.registerState(require(path.join(DIR, f)), { file: `states/vendor/${f}`, draft: true });
  if (`${st.id}.cjs` !== f) throw Error(`vendor/${f}: the file name must be the move id (${st.id})`);
}
const e = require(path.join(eng, 'engine.cjs'));
const S = require(path.join(DIR, '_stall.cjs'));
const TOP = 35, ROWS = 245;                    // the part of the scene that is exported (see export_vendor.py)

const hex = { ...e.palette, ...S.palette };
const rgb = Object.fromEntries(Object.entries(hex).map(([k, h]) => [k, [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))]));
function painter(buf) {
  const rect = (x, y, w, h, c) => {
    const col = rgb[c];
    if (!col) throw Error(`unknown colour ${c}`);
    const x0 = Math.max(0, Math.round(x)), y0 = Math.max(0, Math.round(y)), x1 = Math.min(S.W, Math.round(x + w)), y1 = Math.min(S.H, Math.round(y + h));
    for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) { const n = (yy * S.W + xx) * 4; buf[n] = col[0]; buf[n + 1] = col[1]; buf[n + 2] = col[2]; buf[n + 3] = 255; }
  };
  const pat = (rows, x, y, c, u = 5) => rows.forEach((r, j) => [...r].forEach((v, i) => { if (v === '1') rect(x + i * u, y + j * u, u, u, c); }));
  return { rect, pat };
}
// paste one engine render (binary alpha) at (sx, sy), mirrored when the move says it faces left
function paste(buf, px, sx, sy, mirror) {
  for (let y = 0; y < 300; y++) {
    const ty = y + sy;
    if (ty < 0 || ty >= S.H) continue;
    for (let x = 0; x < 300; x++) {
      const src = (y * 300 + (mirror ? 299 - x : x)) * 4;
      if (!px[src + 3]) continue;
      const tx = x + sx;
      if (tx < 0 || tx >= S.W) continue;
      const n = (ty * S.W + tx) * 4;
      buf[n] = px[src]; buf[n + 1] = px[src + 1]; buf[n + 2] = px[src + 2]; buf[n + 3] = 255;
    }
  }
}
function clawd(id, i, outfit, sx) {
  const r = e.renderVariant(id, i, { outfit });
  const mirror = r.meta.pose.tool?.facing === 'left';
  const hands = r.meta.pose.hands.map((h) => ({ x: sx + (mirror ? 300 - h.x - 20 : h.x), y: h.y + S.CLAWD_DY }));
  return { px: r.pixels, mirror, sx, hands };
}

fs.mkdirSync(outDir, { recursive: true });
for (const name of S.ORDER) {
  if (only.length && !only.includes(name)) continue;
  const sc = S.SCENES[name];
  const frames = [];
  for (let i = 0; i < 45; i++) {
    const lay = sc.layout(i);
    const buf = Buffer.alloc(S.W * S.H * 4);
    const P = painter(buf);
    const v = clawd(sc.vendor, i, 'vendor-straw', lay.vendor);
    const b = sc.buyer ? clawd(sc.buyer, i, buyerOutfit, lay.buyer) : null;
    // the vendor stands behind his counter: ground, the back of the cart, him, the front of the cart, the buyer
    S.ground(P);
    S.cartBack(P, variant, lay.cart.x);
    paste(buf, v.px, v.sx, S.CLAWD_DY, v.mirror);
    S.cartFront(P, variant, lay.cart.x, lay.cart);
    if (b) paste(buf, b.px, b.sx, S.CLAWD_DY, b.mirror);
    sc.paint(P, i, { v: v.hands, b: b && b.hands }, variant);
    frames.push(buf.subarray(TOP * S.W * 4, (TOP + ROWS) * S.W * 4));
  }
  fs.writeFileSync(path.join(outDir, `${name}.rgba`), Buffer.concat(frames));
}
fs.writeFileSync(path.join(outDir, 'scene.json'), JSON.stringify({ w: S.W, rows: ROWS, top: TOP, buyer: S.ORDER.filter((n) => S.SCENES[n].buyer) }));
