// munch-kitchenette · tools/dump_chores.cjs · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// Renders the seventeen chore moves (states/chores/: buying from the vendor, washing plates by hand, the
// dishwasher) in one outfit and writes the raw RGBA of each, 45 frames of 300 x 300 one after another.
// Usage: node dump_chores.cjs <engine dir> <output dir> <outfit> [move id ...]     (called by export_chores.py)
const path = require('node:path'), fs = require('node:fs');
const [, , engDir, outDir, outfit, ...only] = process.argv;
const m = require(path.join(path.resolve(engDir), 'motion.cjs'));
// The engine registers only files directly in states/; these live in states/chores/ (so a normal export
// never sees them) and are registered here as drafts, for this one process. Files starting with "_" are helpers.
const DIR = path.join(path.resolve(engDir), 'states', 'chores');
const ids = [];
for (const f of fs.readdirSync(DIR).filter((n) => n.endsWith('.cjs') && !n.startsWith('_')).sort()) {
  const st = m.registerState(require(path.join(DIR, f)), { file: `states/chores/${f}`, draft: true });
  if (`${st.id}.cjs` !== f) throw Error(`chores/${f}: the file name must be the move id (${st.id})`);
  ids.push(st);
}
const e = require(path.join(path.resolve(engDir), 'engine.cjs'));
fs.mkdirSync(outDir, { recursive: true });
for (const st of ids) {
  if (only.length && !only.includes(st.id)) continue;
  const frames = [];
  for (let f = 0; f < st.frames; f++) frames.push(e.renderVariant(st.id, f, { outfit }).pixels);
  fs.writeFileSync(path.join(outDir, `${st.id}.rgba`), Buffer.concat(frames));
}
