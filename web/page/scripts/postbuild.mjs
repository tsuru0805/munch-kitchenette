// After `expo export --source-maps`: finish the output, then copy it to where the Python package ships it
// from (src/kitchenette/page/, served by `kitchenette serve` at /page/).
//
// 1. The source map says which packages from node_modules ended up in the bundle. Their names, versions
//    and license texts are written to THIRD-PARTY.txt, which ships next to the bundle.
// 2. The source map itself is removed (it is only needed for step 1) and so is the line pointing at it.
// 3. The build fails if a map is left, or if a font license, ASSETS.md or THIRD-PARTY.txt is missing.
// Usage: node scripts/postbuild.mjs <export dir> <package dir>
import { cpSync, existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";

const [src, dest] = process.argv.slice(2);
if (!src || !dest || !existsSync(join(src, "index.html"))) {
  console.error("usage: node scripts/postbuild.mjs <export dir> <package dir>  (no index.html in the export dir)");
  process.exit(1);
}
const walk = (d) => readdirSync(d).flatMap((f) => {
  const p = join(d, f);
  return statSync(p).isDirectory() ? walk(p) : [p];
});

// ── 1. what is in the bundle ────────────────────────────────────────
const root = resolve(".");
const bundled = new Set(); // package folders, relative to the project
for (const map of walk(src).filter((f) => f.endsWith(".js.map"))) {
  for (const source of JSON.parse(readFileSync(map, "utf8")).sources) {
    const at = source.lastIndexOf("node_modules/");
    if (at < 0) continue;
    const parts = source.slice(at + "node_modules/".length).split("/");
    const name = parts[0].startsWith("@") ? `${parts[0]}/${parts[1]}` : parts[0];
    bundled.add(`${source.slice(0, at)}node_modules/${name}`);
  }
}
if (!bundled.size) {
  console.error("no source map in the export: run `expo export` with --source-maps (npm run build does)");
  process.exit(1);
}
const licenseFile = (dir) => readdirSync(dir).find((f) => /^(licen[sc]e|copying)(\.|$)/i.test(f));
const entries = [...bundled].map((rel) => {
  const dir = join(root, rel);
  const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"));
  const file = licenseFile(dir);
  const repo = typeof pkg.repository === "string" ? pkg.repository : pkg.repository?.url;
  return {
    name: pkg.name,
    version: pkg.version,
    license: typeof pkg.license === "string" ? pkg.license : pkg.license?.type ?? "",
    home: (pkg.homepage ?? repo ?? "").replace(/^git\+/, "").replace(/\.git$/, ""),
    text: file ? readFileSync(join(dir, file), "utf8").trim() : "",
  };
}).sort((a, b) => a.name.localeCompare(b.name));

// A package published without a license file of its own: the text of the license its package.json names.
// Who holds the copyright, as stated in the license file at the root of each project's repository.
const HOLDERS = [
  [/^(expo$|expo-|@expo\/)/, "2015-present 650 Industries, Inc. (aka Expo)"],
  [/^@react-native\//, "Meta Platforms, Inc. and affiliates."],
];
const holder = (name) => HOLDERS.find(([re]) => re.test(name))?.[1] ?? `the authors of ${name}`;
const MIT = (name) => `MIT License

Copyright (c) ${holder(name)}

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

(This package is published without a license file of its own; its package.json names the MIT license, and the
copyright line is the one in the license file of the repository it is published from.)`;
const noText = [];
for (const e of entries) {
  if (e.text) continue;
  if (e.license !== "MIT") {
    console.error(`${e.name} ships no license file and is not MIT (${e.license || "no license field"}): add its license text by hand`);
    process.exit(1);
  }
  noText.push(e.name);
  e.text = MIT(e.name);
}
const rule = "=".repeat(100);
writeFileSync(join(src, "THIRD-PARTY.txt"), [
  "Third-party software in the kitchen page's script bundle (_expo/static/js/web/*.js)",
  "厨房页脚本包里的第三方软件",
  "",
  "The bundle is built from the page's own source (web/page/) and the packages below. Each stays under its",
  "own license; none is relicensed by this repository. Written by web/page/scripts/postbuild.mjs from the build.",
  "脚本包由页面自己的源码（web/page/）和下面这些包构建而成。它们各按原许可，不随本仓改授权。",
  "",
  ...entries.map((e) => `  ${e.name} ${e.version} — ${e.license}${e.home ? `  (${e.home})` : ""}`),
  "",
  ...entries.flatMap((e) => [rule, `${e.name} ${e.version} — ${e.license}`, rule, "", e.text, ""]),
].join("\n") + "\n");

// ── 2. the map has done its work ────────────────────────────────────
for (const f of walk(src)) {
  if (f.endsWith(".map")) rmSync(f);
  else if (f.endsWith(".js")) writeFileSync(f, readFileSync(f, "utf8").replace(/\n\/\/# sourceMappingURL=[^\n]*/g, ""));
}

// ── 3. checks, then copy ────────────────────────────────────────────
const files = walk(src);
const maps = files.filter((f) => f.endsWith(".map"));
if (maps.length) {
  console.error("source maps in the output:", maps);
  process.exit(1);
}
for (const f of ["fonts/OFL-NotoSerifSC.txt", "fonts/OFL-BodoniModa.txt", "fonts.css", "ASSETS.md", "THIRD-PARTY.txt"]) {
  if (!existsSync(join(src, f))) {
    console.error(`missing in the output: ${f}`);
    process.exit(1);
  }
}
const target = resolve(dest);
// the target is wiped first: refuse anything that is not the package's page folder
if (basename(target) !== "page" || basename(dirname(target)) !== "kitchenette") {
  console.error(`refusing to replace ${target}: expected …/kitchenette/page`);
  process.exit(1);
}
rmSync(target, { recursive: true, force: true });
cpSync(src, target, { recursive: true });
const bytes = files.reduce((n, f) => n + statSync(f).size, 0);
console.log(`postbuild ok: ${files.length} files, ${(bytes / 1048576).toFixed(1)} MB -> ${dest}`);
console.log(`third-party packages in the bundle: ${entries.length}${noText.length ? ` (no license file of their own: ${noText.join(", ")})` : ""}`);
