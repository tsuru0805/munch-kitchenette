// The settled still: which pictures it needs, and where the dish goes on the cook's grid.
import { CLAWD_MANIFEST } from "./manifest.generated";
import { CELL, PLATES, placeDish, poseFor, settleKeys } from "./settle";

test("every picture a settled still can ask for is in the built-in pack", () => {
  for (const o of CLAWD_MANIFEST.outfits) {
    for (const pose of ["great", "ok", "burnt", "spoiled", "ruined"] as const) {
      for (const icon of ["stirfry", "soup", "bowl", "nonsense", ""]) {
        for (const k of settleKeys(o, pose, icon)) expect(CLAWD_MANIFEST.files[k]).toBeDefined();
      }
    }
  }
  expect(settleKeys("toque", "ruined", "soup")).toEqual(["toque/settle_ruined"]);
  expect(settleKeys("toque", "burnt", "soup")[2]).toBe("dishes/soup_burnt_cells");
  expect(settleKeys("toque", "ok", "nonsense")[2]).toBe("dishes/bowl_cells");
  expect(poseFor("great")).toBe("great");
  expect(poseFor("raw")).toBeNull();
});

test("the dish sits on the grid with its bottom where the plate goes; spoiled tips away from the hand", () => {
  const p = placeDish(PLATES.toque.ok, 12, 8);
  expect((p.x - 6) % CELL).toBe(0);
  expect(p.y + 8 * CELL).toBe(510);
  expect(p.drop(5)).toBe(0);
  const s = placeDish(PLATES.toque.spoiled, 12, 8);
  expect(s.drop(11)).toBe(0);          // the column by the hand stays up
  expect(s.drop(0)).toBe(3);           // the far one is three cells lower
});
