// The registry and the files on disk say the same thing: every registered file exists, and every
// image under assets/clawd/ is registered.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { CHORE_SEGMENTS, missingChoreKeys, missingKeys, requiredSegments } from "./manifest";
import { CLAWD_MANIFEST } from "./manifest.generated";

const pack = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "assets", "clawd");

test("the built-in registry is complete and matches assets/clawd/ both ways", () => {
  expect(missingKeys(CLAWD_MANIFEST)).toEqual([]);
  expect(missingChoreKeys(CLAWD_MANIFEST)).toEqual([]);
  // plus, optional, the settled stills (five poses, four with a front layer), the chores (17 clips, three
  // of them with a still last frame) and the 14 × 2 dish pictures
  expect(CHORE_SEGMENTS).toHaveLength(20);
  expect(Object.keys(CLAWD_MANIFEST.files)).toHaveLength(
    CLAWD_MANIFEST.outfits.length * (requiredSegments().length + 9 + CHORE_SEGMENTS.length) + 28,
  );
  const registered = Object.values(CLAWD_MANIFEST.files);
  expect(registered.filter((f) => !existsSync(join(pack, f)))).toEqual([]);
  const onDisk = [...CLAWD_MANIFEST.outfits, "dishes"].flatMap((o) =>
    readdirSync(join(pack, o)).filter((n) => /\.(webp|png)$/.test(n)).map((n) => `${o}/${n}`),
  );
  expect(onDisk.filter((f) => !registered.includes(f))).toEqual([]);
  expect(JSON.parse(readFileSync(join(pack, "manifest.json"), "utf8"))).toEqual(CLAWD_MANIFEST);
});

test("a pack without the chores is still complete for the card; the chores are reported on their own", () => {
  const files = Object.fromEntries(Object.entries(CLAWD_MANIFEST.files).filter(([k]) => !/\/(vendor|dish|machine)_/.test(k)));
  const pack = { ...CLAWD_MANIFEST, files };
  expect(missingKeys(pack)).toEqual([]);
  expect(missingChoreKeys(pack)).toHaveLength(CLAWD_MANIFEST.outfits.length * CHORE_SEGMENTS.length);
  expect(missingChoreKeys(pack)).toContain("scarf/dish_break_last");
});
