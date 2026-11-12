// The entrance bounce as plain numbers: a damped spring sampled at 60 fps, to be handed to the
// Web Animations API as keyframes. Stiffness and damping are fixed: a quick rise that overshoots
// the resting place once (about 15%) and settles.
const STIFFNESS = 338.8;
const DAMPING = 19;
const MASS = 1;
const FRAME_MS = 1000 / 60;
const MAX_MS = 1500;
/** Settled when the remaining swing is under half a pixel */
const REST_PX = 0.5;

export interface SpringFrames {
  /** One position per frame, the first is `from`, the last is `to` */
  values: number[];
  durationMs: number;
}

export function springFrames(from: number, to: number): SpringFrames {
  const omega0 = Math.sqrt(STIFFNESS / MASS);
  const zeta = DAMPING / (2 * Math.sqrt(STIFFNESS * MASS));
  const omega1 = omega0 * Math.sqrt(1 - zeta * zeta);
  const x0 = to - from;
  const values: number[] = [];
  let t = 0;
  for (; t <= MAX_MS; t += FRAME_MS) {
    const s = t / 1000;
    const envelope = Math.exp(-zeta * omega0 * s);
    values.push(to - envelope * (((zeta * omega0 * x0) / omega1) * Math.sin(omega1 * s) + x0 * Math.cos(omega1 * s)));
    if (Math.abs(x0) * envelope < REST_PX) break;
  }
  values.push(to);
  return { values, durationMs: Math.min(t, MAX_MS) + FRAME_MS };
}
