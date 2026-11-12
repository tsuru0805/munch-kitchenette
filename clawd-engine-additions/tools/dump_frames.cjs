// munch-kitchenette · tools/dump_frames.cjs · unofficial Clawd fan work, Clawd belongs to Anthropic
// SPDX-FileCopyrightText: 2026 tsuru0805
// SPDX-License-Identifier: MIT
// Renders frames of one move in one outfit with the clawds-new-clothes engine and writes them as
// raw RGBA, one 300 x 300 frame after another. Used by export_cook_clips.py.
//   node dump_frames.cjs <engine dir> <output file> <outfit> <move id> <frame count>
const path = require('node:path'), fs = require('node:fs');
const [, , engineDir, out, outfit, id, count] = process.argv;
const engine = require(path.join(path.resolve(engineDir), 'engine.cjs'));
const frames = [];
for (let f = 0; f < Number(count); f++) frames.push(engine.renderVariant(id, f, { outfit }).pixels);
fs.writeFileSync(out, Buffer.concat(frames));
