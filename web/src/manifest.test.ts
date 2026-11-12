// The registry and the files on disk say the same thing: every registered file exists, and every
// image under assets/clawd/ is registered.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { missingKeys, requiredSegments } from "./manifest";
import { CLAWD_MANIFEST } from "./manifest.generated";

const pack = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "assets", "clawd");

test("the built-in registry is complete and matches assets/clawd/ both ways", () => {
  expect(missingKeys(CLAWD_MANIFEST)).toEqual([]);
  expect(Object.keys(CLAWD_MANIFEST.files)).toHaveLength(CLAWD_MANIFEST.outfits.length * requiredSegments().length);
  const registered = Object.values(CLAWD_MANIFEST.files);
  expect(registered.filter((f) => !existsSync(join(pack, f)))).toEqual([]);
  const onDisk = CLAWD_MANIFEST.outfits.flatMap((o) =>
    readdirSync(join(pack, o)).filter((n) => /\.(webp|png)$/.test(n)).map((n) => `${o}/${n}`),
  );
  expect(onDisk.filter((f) => !registered.includes(f))).toEqual([]);
  expect(JSON.parse(readFileSync(join(pack, "manifest.json"), "utf8"))).toEqual(CLAWD_MANIFEST);
});
