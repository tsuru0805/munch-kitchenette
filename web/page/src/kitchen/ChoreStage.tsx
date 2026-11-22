// The cook doing a chore, in a small panel of the sheet (never on the kitchen picture): it asks `pick`
// which clip to play now (choreAnim.ts) and plays it. The panel is a window onto the clip's 720 px canvas,
// cut to where the chores happen and scaled so one pixel cell stays a whole number of screen pixels.
import { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Image, Platform, StyleSheet, View, type ImageSourcePropType } from "react-native";
import { Asset } from "expo-asset";
import { CHORE_ART, type ChoreSegment } from "./choreArt.generated";
import { stillFor, type ChoreClip } from "./choreAnim";

/** 720 px canvas shown at 0.4: one engine cell (10 px) = 4 screen px */
export const STAGE_SCALE = 0.4;
/** The part of the canvas every chore stays inside (x 15-615, y 235-575) */
const CROP = { x: 15, y: 235, w: 600, h: 340 };
const SIDE = 720 * STAGE_SCALE;
export const STAGE_W = CROP.w * STAGE_SCALE;
export const STAGE_H = CROP.h * STAGE_SCALE;
const TICK_MS = 250;

/** The device's "reduce motion" setting, live */
export function useReduceMotion(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled?.().then((v) => alive && setOn(!!v), () => {});
    const sub = AccessibilityInfo.addEventListener?.("reduceMotionChanged", (v: boolean) => setOn(!!v));
    return () => {
      alive = false;
      sub?.remove?.();
    };
  }, []);
  return on;
}

// On the web an animated image shared by URL keeps one timeline: shown again, a clip that plays once would
// already be at its end. Each run gets its own object URL of the same bytes, so it starts from frame one.
const bytes = new Map<string, Promise<Blob | null>>();
function blobOf(uri: string): Promise<Blob | null> {
  let p = bytes.get(uri);
  if (!p) {
    p = fetch(uri).then((r) => (r.ok ? r.blob() : null), () => null);
    bytes.set(uri, p);
  }
  return p;
}

function useRunSource(src: ImageSourcePropType | undefined, run: string): ImageSourcePropType | undefined {
  const [fresh, setFresh] = useState<string | null>(null);
  const current = useRef<string | null>(null);
  useEffect(() => {
    if (Platform.OS !== "web" || src === undefined || typeof URL === "undefined" || typeof fetch === "undefined") return;
    const uri = typeof src === "number" ? Asset.fromModule(src).uri : (src as { uri?: string }).uri;
    if (!uri) return;
    let alive = true;
    void blobOf(uri).then((b) => {
      if (!alive || !b) return;
      const made = URL.createObjectURL(b);
      const old = current.current;
      current.current = made;
      setFresh(made);
      // the previous run stays on screen until this one is in; let it go a moment later
      if (old) setTimeout(() => URL.revokeObjectURL(old), 1000);
    });
    return () => {
      alive = false;
    };
  }, [src, run]);
  useEffect(() => () => {
    if (current.current) URL.revokeObjectURL(current.current);
  }, []);
  // until the first copy is in (a few ms; the bytes are cached after once): the shared file
  return fresh ? { uri: fresh } : src;
}

export function ChoreStage({ pick, testID }: { pick: (nowMs: number) => ChoreClip | null; testID?: string }) {
  const [now, setNow] = useState(() => Date.now());
  const reduce = useReduceMotion();
  const clip = pick(now);
  const segment = clip ? (reduce ? stillFor(clip.segment) : clip.segment) : null;
  const moving = !!clip && !reduce;
  useEffect(() => {
    if (!moving) return;
    const t = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(t);
  }, [moving]);
  const src = clip && segment ? CHORE_ART[clip.outfit]?.[segment as ChoreSegment] : undefined;
  const still = !segment || segment.endsWith("_last") || segment.endsWith("_still") || segment === "base";
  const run = clip ? `${clip.outfit}/${segment}/${clip.run}` : "";
  const shown = useRunSource(still ? undefined : src, run);
  if (!clip || !src) return null;
  return (
    <View style={st.stage} testID={testID} accessibilityLabel={segment ?? undefined}>
      <Image source={still ? src : shown} style={st.img} testID={testID ? `${testID}-${segment}` : undefined} />
    </View>
  );
}

const st = StyleSheet.create({
  stage: {
    width: STAGE_W, height: STAGE_H, overflow: "hidden", alignSelf: "center", marginTop: 8, marginBottom: 2,
    // pixel art: scale by whole cells without smoothing (inherited by the image inside)
    ...(Platform.OS === "web" ? ({ imageRendering: "pixelated" } as object) : null),
  },
  img: { position: "absolute", width: SIDE, height: SIDE, left: -CROP.x * STAGE_SCALE, top: -CROP.y * STAGE_SCALE },
});
