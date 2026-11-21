// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// Renders the five settled stills (states/settle/settle-*.cjs) in both outfits, one frame each, and writes
// the raw RGBA (the whole frame, and a front layer holding only the hands) plus where the hands are.
// Usage: node dump_settle.cjs <engine dir> <output dir>      (called by export_settle.py)
const path = require('node:path'), fs = require('node:fs');
const [, , engDir, outDir] = process.argv;
const m = require(path.join(engDir, 'motion.cjs'));
// A move id may only hold lower-case letters and "-", and the engine registers only files directly in
// states/; these five live in states/settle/ (so a normal export never sees them) and are registered here
// as drafts, for this one process.
const DIR = path.join(engDir, 'states', 'settle');
for (const f of fs.readdirSync(DIR).filter((n) => n.endsWith('.cjs')).sort()) m.registerState(require(path.join(DIR, f)), { file: `states/settle/${f}`, draft: true });
const e = require(path.join(engDir, 'engine.cjs'));
const POSES = ['great', 'ok', 'burnt', 'spoiled', 'ruined'];
const OUTFITS = { 'chef-toque': 'toque', 'chef-scarf': 'scarf' };
fs.mkdirSync(outDir, { recursive: true });
const info = {};
for (const [outfit, short] of Object.entries(OUTFITS)) for (const pose of POSES) {
  const opts = { outfit };
  // The headscarf is 30 lower than the toque: the hands held above the head come down with it
  if (pose === 'great' && outfit === 'chef-scarf') opts.hands = [{ x: 110, y: 153, a: 0 }, { x: 170, y: 153, a: 0 }];
  const r = e.renderVariant(`settle-${pose}`, 0, opts);
  const front = Buffer.alloc(r.pixels.length);
  for (const name of ['hand-left', 'hand-right']) { const b = r.layers[name]; for (let k = 0; k < b.length; k += 4) if (b[k + 3]) b.copy(front, k, k, k + 4); }
  fs.writeFileSync(path.join(outDir, `${short}_${pose}.rgba`), r.pixels);
  fs.writeFileSync(path.join(outDir, `${short}_${pose}_front.rgba`), front);
  info[`${short}_${pose}`] = { hands: r.meta.pose.hands, body: r.meta.body };
}
fs.writeFileSync(path.join(outDir, 'info.json'), JSON.stringify(info, null, 1));
