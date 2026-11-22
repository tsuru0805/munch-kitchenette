// munch-kitchenette · tools/check_vendor.cjs · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// Runs the engine's own per-move check (state-check.cjs: the same one check-art.cjs and `export.cjs --state
// <id> --preview` use) over every move in states/vendor/, in each outfit it is worn in: the vendor's moves in
// vendor-straw, the buyer's in chef-toque and chef-scarf. A Clawd is checked on its own canvas, as the engine
// renders it, before it is placed on the scene.
// Moves that play once (`once: true` in the file: arriving, leaving, handing over, eating, walking over / back)
// end on another pose on purpose, so the loop-seam check, which is about clips that loop, is reported for
// them as a note, not a problem. Everything else the engine reports as a problem is one.
// Usage: node check_vendor.cjs <engine dir with states/vendor/ and the three outfits>     exit code 1 = problems
const path = require('node:path'), fs = require('node:fs');
const eng = path.resolve(process.argv[2] || '.');
const m = require(path.join(eng, 'motion.cjs'));
const DIR = path.join(eng, 'states', 'vendor');
const states = [];
for (const f of fs.readdirSync(DIR).filter((n) => n.endsWith('.cjs') && !n.startsWith('_')).sort()) {
  const mod = require(path.join(DIR, f));
  states.push({ st: m.registerState(mod, { file: `states/vendor/${f}`, draft: true }), once: mod.once === true });
}
const e = require(path.join(eng, 'engine.cjs'));
const { checkState } = require(path.join(eng, 'state-check.cjs'));
let problems = 0;
for (const { st, once } of states) {
  const outfits = st.id.startsWith('peddler-') ? ['vendor-straw'] : ['chef-toque', 'chef-scarf'];
  for (const outfit of outfits) {
    const rep = checkState(st, (i) => e.renderVariant(st.id, i, { outfit }), { order: e.ORDER });
    const seam = (t) => t.startsWith('接缝');
    const real = rep.problems.filter((t) => !(once && seam(t)));
    const notes = [...rep.problems.filter((t) => once && seam(t)), ...rep.warnings];
    problems += real.length;
    console.log(`${real.length ? 'FAIL' : 'ok  '} ${st.id} (${outfit})${once ? ' · plays once' : ''}`);
    for (const t of real) console.log(`       problem: ${t}`);
    for (const t of notes) console.log(`       note: ${t}`);
  }
}
console.log(problems ? `${problems} problem(s)` : 'no problems');
process.exit(problems ? 1 : 0);
