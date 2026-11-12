// Bundles the element into one ES module: web/dist/kitchenette-cooking-card.js
import { build } from "esbuild";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
await build({
  entryPoints: [join(root, "src", "index.ts")],
  outfile: join(root, "dist", "kitchenette-cooking-card.js"),
  bundle: true,
  format: "esm",
  target: "es2022",
  minify: false,
  legalComments: "none",
  banner: { js: "// kitchenette-cooking-card: built from web/src by `npm run build`. Edit the sources, not this file." },
});
console.log("built dist/kitchenette-cooking-card.js");
