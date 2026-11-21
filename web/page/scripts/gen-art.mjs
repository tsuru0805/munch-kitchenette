// Writes src/kitchen/art.generated.ts: one entry per picture in assets/kitchen/fridge/ with its pixel size
// (the page lays pictures out from these sizes before they have loaded).
// Usage: node scripts/gen-art.mjs     (run from web/page/ after adding or replacing a picture)
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const page = join(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(page, "assets", "kitchen", "fridge");

function pngSize(file) {
  const b = readFileSync(file);
  if (b.readUInt32BE(0) !== 0x89504e47 || b.toString("ascii", 12, 16) !== "IHDR") throw new Error(`${file} is not a PNG`);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

const names = readdirSync(dir).filter((f) => f.endsWith(".png")).map((f) => f.slice(0, -4)).sort();
const rows = names.map((n) => {
  const { w, h } = pngSize(join(dir, `${n}.png`));
  return `  "${n}": { src: require("../../assets/kitchen/fridge/${n}.png"), w: ${w}, h: ${h} },`;
});
const out = `// Generated: one entry per picture in assets/kitchen/fridge/ with its pixel size. Do not edit by hand;
// run \`node scripts/gen-art.mjs\` after adding or replacing a picture.
import type { ImageSourcePropType } from "react-native";

export interface FridgeArt { src: ImageSourcePropType; w: number; h: number }

export const FRIDGE_ART = {
${rows.join("\n")}
} satisfies Record<string, FridgeArt>;

export type FridgeArtId = keyof typeof FRIDGE_ART;
`;
writeFileSync(join(page, "src", "kitchen", "art.generated.ts"), out);
console.log(`art.generated.ts: ${names.length} pictures`);
