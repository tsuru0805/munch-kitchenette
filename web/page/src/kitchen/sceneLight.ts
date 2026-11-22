// Which picture of the kitchen is shown and which cut-out pieces go back onto it. Pure functions; the
// scene only draws what these return.
// - The light follows the kitchen's clock: day 06:00–17:00, dusk 17:00–19:00, night the rest.
// - The sill holds one bunch of flowers at a time: the kind and how it looks (fresh / droopy / wilted)
//   come from the vendor answer; no bunch, or a kind that has no picture, = an empty sill.
// - The three jars stand on the counter: empty, or what is sealed in it (sugar / honey = fruit, salt =
//   pickles).
// - The drying rack and the sink: how many plates, and foam while the role is washing.
// A play that is switched off shows its things as they stand empty: the empty picture already has the
// sill, the sink and the rack; the three jars are pieces, so with the jars off they are put back empty
// (and nothing there can be tapped: pick.ts only makes them tappable while the jars are on).
import { SCENE_PIECES, type Light } from "./sceneArt.generated";

export const DUSK_FROM = 17 * 60;
export const NIGHT_FROM = 19 * 60;
export const DAY_FROM = 6 * 60;

/** The light at a wall-clock time of the kitchen */
export function lightAt(hour: number, minute = 0): Light {
  const m = hour * 60 + minute;
  if (m >= DAY_FROM && m < DUSK_FROM) return "day";
  if (m >= DUSK_FROM && m < NIGHT_FROM) return "dusk";
  return "night";
}

/** A flower kind (the server's variety id) -> which sheet it was drawn on and its place there */
export const FLOWER_PIECE: Record<string, [string, number]> = {
  sunflower: ["fl1", 0], rose: ["fl1", 1], tulip: ["fl1", 2],
  bellflower: ["fl2", 0], chamomile: ["fl2", 1], narcissus: ["fl2", 2],
};
const FLOWER_LOOK: Record<string, number> = { fresh: 0, droopy: 1, wilted: 2 };

export interface SceneFlower { variety: string; state: string }

/** Is there a picture for this bunch (a kind or a look without one = the sill stays empty, and nothing there can be tapped) */
export function flowerDrawn(f: SceneFlower | null): boolean {
  return !!f && FLOWER_PIECE[f.variety] !== undefined && FLOWER_LOOK[f.state] !== undefined;
}
export interface SceneJar { slot: number; state: string; how: string }
export interface ScenePlates { sink: number; washing: number; rack: number }

/** One jar's look: 0 empty, 1 fruit (sugar / honey), 2 pickles (salt) */
export function jarLook(j: SceneJar | undefined): number {
  if (!j || j.state !== "sealed") return 0;
  if (j.how === "salt") return 2;
  return j.how === "sugar" || j.how === "honey" ? 1 : 0;
}

/** How full: 0 none, 1 a few (1–3), 2 many (4 and more) */
export const fullness = (n: number): number => (n <= 0 ? 0 : n < 4 ? 1 : 2);

/** The sink: 0 empty, 1 a few, 2 piled up, 3 foam (being washed) */
export function sinkLook(p: ScenePlates): number {
  return p.washing > 0 ? 3 : fullness(p.sink);
}

/** How long washed plates stand on the rack after the washing ended (then they are put away) */
export const RACK_HOURS = 3;

/**
 * Plates on the rack, from the last washing (the server's /api/dishes `job`): while it runs, the
 * ones washed so far; after it ended, all of it for RACK_HOURS; older = none.
 */
export function rackCount(job: { state: string; startedAt: number; perS: number; n: number; endedAt: number | null } | null, now: number): number {
  if (!job || job.n <= 0) return 0;
  if (job.state === "running") return Math.max(0, Math.min(job.n, Math.floor((now - job.startedAt) / Math.max(1, job.perS))));
  const end = job.endedAt ?? job.startedAt + job.n * job.perS;
  if (now - end > RACK_HOURS * 3600) return 0;
  return job.state === "done" ? job.n : Math.max(0, Math.min(job.n, Math.floor((end - job.startedAt) / Math.max(1, job.perS))));
}

export interface SceneState {
  /** null = no bunch on the sill (or the vendor is off) */
  flower: SceneFlower | null;
  /** null = sealed jars are off (or not read yet): the three jars stand empty */
  jars: SceneJar[] | null;
  /** null = plates are off */
  plates: ScenePlates | null;
}

/** The pieces to put onto the picture in this light, in drawing order (keys of SCENE_PIECES; a missing piece is left out) */
export function scenePieces(light: Light, s: SceneState): string[] {
  const out: string[] = [];
  const add = (sheet: string, n: number) => {
    const key = `${light}_${sheet}_${n}`;
    if (SCENE_PIECES[key]) out.push(key);
  };
  if (s.flower) {
    const f = FLOWER_PIECE[s.flower.variety];
    const look = FLOWER_LOOK[s.flower.state];
    if (f && look !== undefined) add(f[0], f[1] * 3 + look + 1);
  }
  for (let i = 0; i < 3; i++) add("jars", i * 3 + jarLook(s.jars?.find((j) => j.slot === i + 1)) + 1);
  if (s.plates) {
    add("dish", fullness(s.plates.rack) + 1);
    add("dish", 3 + sinkLook(s.plates) + 1);
  }
  return out;
}
