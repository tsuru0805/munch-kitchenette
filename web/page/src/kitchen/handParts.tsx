// Shared parts of "the hand": the block under the picture. On the left the thing that was taken
// down, enlarged; on the right its name / count / state; under them a line of what can be done with
// it; at the bottom a row of the other things from the same place. A thin line runs from where the
// thing is in the picture to the enlarged one.
import type { ReactNode } from "react";
import { Image, Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import type { AnyArt } from "./kindArt";
import { KC, KF, KL, bodoniFor, bodoniTight } from "./kitchenTheme";
import { ArtImage } from "./panelParts";
import { TAN } from "./sheetParts";

/** The colour along the top of the hand (it continues the floor of the picture); the bottom edge of the picture fades into it */
export const HAND_TOP = "#efdfc8";
/** The enlarged picture's box: 30 from the left, 34 from the top of the hand, 156 wide, 140 high; the leader line lands on the middle of its top */
export const HERO = { left: 30, top: 34, w: 156, h: 140 } as const;
const RING = require("../../assets/kitchen/ring.png");

/** A red pen circle (around the chosen one) */
export function Ring({ style }: { style: StyleProp<ViewStyle> }) {
  return (
    <View style={[hp.ringBox, style]}>
      <Image source={RING} style={hp.fill} resizeMode="stretch" accessible={false} />
    </View>
  );
}

/** A thin line with a small dot at the thing's end (coordinates relative to the hand's top left; the end up in the picture has a negative y) */
export function Leader({ from, to }: { from: { x: number; y: number }; to: { x: number; y: number } }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len < 4) return null;
  return (
    <View style={[StyleSheet.absoluteFill, hp.noTouch]}>
      <View
        style={{
          position: "absolute", left: (from.x + to.x) / 2 - len / 2, top: (from.y + to.y) / 2 - 0.5, width: len, height: 1,
          backgroundColor: KC.ink, transform: [{ rotate: `${Math.atan2(dy, dx)}rad` }],
        }}
      />
      <View style={[hp.dot, { left: from.x - 3, top: from.y - 3 }]} />
    </View>
  );
}

export function HandShell({
  anchor, sceneH, children, testID,
}: { anchor: { x: number; y: number } | null; sceneH: number; children: ReactNode; testID?: string }) {
  return (
    <View style={hp.root} testID={testID}>
      <LinearGradient colors={[HAND_TOP, "#f3e6d3", KC.bg]} locations={[0, 0.05, 0.3]} style={[StyleSheet.absoluteFill, hp.noTouch]} />
      {anchor ? <Leader from={{ x: anchor.x, y: anchor.y - sceneH }} to={{ x: HERO.left + HERO.w / 2, y: HERO.top + 8 }} /> : null}
      {children}
    </View>
  );
}

/** The upper half: the enlarged picture on the left, the name and numbers on the right. No hero = no picture (the right column moves to the left edge) */
export function Top({ hero, children }: { hero?: ReactNode; children: ReactNode }) {
  return (
    <View style={hp.top}>
      {hero !== undefined ? <View style={hp.heroBox}>{hero}</View> : null}
      <View style={[hp.info, hero === undefined && { paddingLeft: 4 }]}>{children}</View>
    </View>
  );
}

/** A thing's enlarged picture with a faint shadow under it; with no picture (an added kind that was never drawn) the first character of its name */
export function HeroArt({ art, name, children }: { art: AnyArt | null; name?: string; children?: ReactNode }) {
  return (
    <>
      <View style={hp.heroShadow} />
      <ArtImage art={art} style={hp.heroImg} fallback={name ? <Text style={hp.heroCh}>{Array.from(name)[0]}</Text> : null} />
      {children}
    </>
  );
}

export function Name({ children, small }: { children: ReactNode; small?: boolean }) {
  return <Text style={[hp.name, small && hp.nameSmall]}>{children}</Text>;
}

/** A large number (Bodoni) followed by a few small words */
export function Big({ n, tail }: { n: string; tail?: string }) {
  return (
    <View style={hp.bigRow}>
      <Text style={[hp.big, { fontFamily: bodoniFor(44) }, bodoniTight(44, 46)]}>{n}</Text>
      {tail ? <Text style={hp.bigTail}>{tail}</Text> : null}
    </View>
  );
}

export function Line({ children, dot, style }: { children: ReactNode; dot?: string; style?: StyleProp<TextStyle> }) {
  return (
    <View style={hp.lineRow}>
      {dot ? <View style={[hp.lineDot, { backgroundColor: dot }]} /> : null}
      <Text style={[hp.line, style]}>{children}</Text>
    </View>
  );
}
export const lineInk: TextStyle = { color: KC.ink };

/** A note: the light weight, never cut short (shown as long as it was written) */
export function Note({ children }: { children: ReactNode }) {
  return <Text style={hp.note}>{children}</Text>;
}

/** The line of what can be done (a dashed rule above it) */
export function Acts({ children }: { children: ReactNode }) {
  return (
    <View style={hp.actsWrap}>
      <View style={hp.dash} />
      <View style={hp.acts}>{children}</View>
    </View>
  );
}
export function Sp() {
  return <View style={hp.sp} />;
}

export function Act({
  label, onPress, tone = "ink", disabled, testID, a11y, selected,
}: { label: string; onPress?: () => void; tone?: "go" | "ink" | "mute"; disabled?: boolean; testID?: string; a11y?: string; /** the chosen one of a group (a screen reader says so) */ selected?: boolean }) {
  const color = tone === "go" ? KC.tomato : tone === "mute" ? KC.soft : KC.ink;
  if (!onPress) return <Text style={[hp.act, { color }]}>{label}</Text>;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      hitSlop={10}
      accessibilityRole="button"
      accessibilityLabel={a11y ?? label}
      accessibilityState={selected === undefined ? { disabled: !!disabled } : { disabled: !!disabled, selected }}
      testID={testID}
      style={disabled ? hp.off : null}
    >
      <Text style={[hp.act, { color }]}>{label}</Text>
    </Pressable>
  );
}

/** The heading of the bottom row: on the left what this place is called and how many things it holds, on the right what can be done here; an ink line under it */
export function Bar({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <View style={hp.bar}>
      <View style={hp.barSide}>{left}</View>
      <View style={hp.barSide}>{right}</View>
    </View>
  );
}
export function BarTx({ children, ink, go }: { children: ReactNode; ink?: boolean; go?: boolean }) {
  return <Text style={[hp.barTx, ink && { color: KC.ink }, go && { color: KC.tomato }]}>{children}</Text>;
}
export function BarNum({ children }: { children: ReactNode }) {
  return <Text style={[hp.barTx, hp.barNum, { fontFamily: bodoniFor(12) }]}>{children}</Text>;
}
export function BarBtn({ label, onPress, go, testID, disabled }: { label: string; onPress: () => void; go?: boolean; testID?: string; disabled?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} hitSlop={10} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} testID={testID} style={disabled ? hp.off : null}>
      <Text style={[hp.barTx, { color: go ? KC.tomato : KC.ink }]}>{label}</Text>
    </Pressable>
  );
}

export interface ThumbItem {
  key: string;
  art: AnyArt | null;
  name: string;
  badge?: string | number;
}

/** The other things from the same place: a row of small pictures, tap one to hold it instead; a red line under the one being held. More than seven = smaller, in two rows */
export function Thumbs({ items, cur, onPick, idPrefix }: { items: ThumbItem[]; cur?: string; onPick: (key: string) => void; idPrefix: string }) {
  const many = items.length > 7;
  const w = many ? 38 : 44;
  return (
    <View style={hp.thumbs}>
      {items.map((it) => (
        <Pressable
          key={it.key}
          onPress={() => onPick(it.key)}
          hitSlop={3}
          accessibilityRole="button"
          accessibilityLabel={it.name}
          accessibilityState={{ selected: it.key === cur }}
          testID={`${idPrefix}-${it.key}`}
          style={{ width: w, height: w }}
        >
          <ArtImage art={it.art} style={{ width: w, height: w - 6 }} fallback={<Text style={[hp.thumbCh, { width: w, lineHeight: w - 6 }]}>{Array.from(it.name)[0]}</Text>} />
          {it.badge !== undefined && it.badge !== "" ? <Text style={[hp.badge, { fontFamily: bodoniFor(10) }]}>{it.badge}</Text> : null}
          {it.key === cur ? <View style={hp.cur} /> : null}
        </Pressable>
      ))}
    </View>
  );
}

/** One sentence: loading / could not be read / empty (the "could not be read" one can be tapped to try again) */
export function Status({ text, onPress }: { text: string; onPress?: () => void }) {
  if (!onPress) return <Text style={hp.status}>{text}</Text>;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel="重新读取" testID="status-retry">
      <Text style={hp.status}>{text}</Text>
    </Pressable>
  );
}

export const hp = StyleSheet.create({
  fill: { width: "100%", height: "100%" },
  noTouch: { pointerEvents: "none" },
  ringBox: { position: "absolute", pointerEvents: "none" },
  root: { paddingTop: HERO.top, paddingHorizontal: 20, paddingBottom: 6, minHeight: 330 },
  dot: { position: "absolute", width: 6, height: 6, borderRadius: 3, backgroundColor: "#fffdf8", borderWidth: 1, borderColor: KC.ink },
  top: { flexDirection: "row", minHeight: HERO.h + 10 },
  heroBox: { width: HERO.w + 30, height: HERO.h, paddingLeft: 10 },
  heroImg: { width: HERO.w, height: HERO.h },
  heroShadow: { position: "absolute", left: 44, right: 54, bottom: -3, height: 8, borderRadius: 4, backgroundColor: "rgba(74,58,47,0.09)" },
  heroCh: { width: HERO.w, lineHeight: HERO.h, textAlign: "center", fontFamily: KF, fontSize: 64, color: KC.soft },
  info: { flex: 1, minWidth: 0, paddingTop: 8 },
  name: { fontFamily: KF, fontSize: 25, lineHeight: 32, letterSpacing: 4, color: KC.ink },
  nameSmall: { fontSize: 21, lineHeight: 29, letterSpacing: 3 },
  bigRow: { flexDirection: "row", alignItems: "flex-end", marginTop: 10, marginBottom: 6, height: 46 },
  big: { color: KC.ink, fontVariant: ["tabular-nums"] },
  bigTail: { fontFamily: KF, fontSize: 12, lineHeight: 18, letterSpacing: 1, color: KC.soft, marginLeft: 8, marginBottom: 6, flexShrink: 1 },
  lineRow: { flexDirection: "row", alignItems: "center" },
  lineDot: { width: 7, height: 7, borderRadius: 3.5, marginRight: 6 },
  line: { fontFamily: KF, fontSize: 12, lineHeight: 21, letterSpacing: 1, color: KC.soft, flexShrink: 1 },
  note: { fontFamily: KL, fontSize: 12.5, lineHeight: 21, color: KC.ink, marginTop: 10, paddingHorizontal: 4 },
  actsWrap: { marginTop: 14, paddingHorizontal: 4 },
  dash: { height: 1, borderTopWidth: 1, borderStyle: "dashed", borderColor: TAN },
  acts: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", columnGap: 16, rowGap: 6, paddingTop: 9 },
  sp: { flex: 1 },
  act: { fontFamily: KF, fontSize: 12.5, lineHeight: 20, letterSpacing: 2 },
  off: { opacity: 0.4 },
  bar: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", paddingBottom: 6, marginTop: 22, borderBottomWidth: 1, borderBottomColor: KC.ink },
  barSide: { flexDirection: "row", alignItems: "baseline", columnGap: 10, flexShrink: 1 },
  barTx: { fontFamily: KF, fontSize: 11, lineHeight: 17, letterSpacing: 1.5, color: KC.soft },
  barNum: { color: KC.ink, letterSpacing: 0, fontSize: 11.5, lineHeight: 18 },
  thumbs: { flexDirection: "row", flexWrap: "wrap", columnGap: 6, rowGap: 6, marginTop: 8, minHeight: 44 },
  thumbCh: { fontFamily: KF, fontSize: 17, textAlign: "center", color: KC.soft },
  badge: { position: "absolute", right: 0, bottom: 0, fontSize: 10, lineHeight: 16, paddingHorizontal: 2, color: KC.ink, backgroundColor: KC.bg },
  cur: { position: "absolute", left: 6, right: 6, bottom: -3, height: 2, backgroundColor: KC.tomato },
  status: { fontFamily: KF, fontSize: 13, lineHeight: 20, color: KC.soft, paddingVertical: 22, textAlign: "center" },
});
