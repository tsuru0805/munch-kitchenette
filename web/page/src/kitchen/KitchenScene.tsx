// The picture: the empty kitchen with cut-out pictures placed in fixed slots according to the data
// (the slots are in sceneSlots.ts). Every thing in it can be tapped on its own (which things, where,
// and how large a tap area: the pure functions in pick.ts); the one being held is drawn a little
// larger. The words 「买菜券」 are printed on the coupon here. Under the lower shelf hang the
// "meals today" receipt and one strip per dish on the menu (too small for lettering at this scale:
// a strip only says a dish is up); the last, dashed one = put a dish up.
// Nothing moves here: the picture is still.
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { BG_KITCHEN } from "./art.generated";
import { COUPON_ART, COUPON_TEXT } from "./couponArt";
import { ArtImage } from "./panelParts";
import { KC, KF, shadow } from "./kitchenTheme";
import { hitBoxes, tapKey, type Pick, type SceneObj, type Tap } from "./pick";
import { NOTE_SLOTS, SCENE_SRC, noteCount } from "./sceneSlots";

export function KitchenScene({
  width,
  objs,
  pick,
  logCount,
  onTap,
}: {
  width: number;
  objs: SceneObj[];
  pick: Pick | null;
  logCount: number;
  onTap: (t: Tap) => void;
}) {
  const k = width / SCENE_SRC;
  const pickedKey = pick ? tapKey(pick) : "";
  const hits = hitBoxes(objs, k);
  // One name per thing, the same from one render to the next whatever else comes or goes around it
  // (the second coupon is "coupon-2", a dish's bowl after its strip "dish-<id>-2"). Used as the
  // element key, so a thing keeps its element when the fridge fills up, and as its test id.
  const seen: Record<string, number> = {};
  const names = objs.map((o) => {
    const key = tapKey(o.tap);
    seen[key] = (seen[key] ?? 0) + 1;
    return seen[key] === 1 ? key : `${key}-${seen[key]}`;
  });
  return (
    <View style={{ width, height: width, overflow: "hidden" }} testID="kitchen-scene">
      <Image source={BG_KITCHEN} style={{ width, height: width }} resizeMode="cover" accessible={false} />
      {objs.map((o, i) => {
        const b = { left: o.box.x * k, top: o.box.y * k, width: o.box.w * k, height: o.box.h * k };
        const on = tapKey(o.tap) === pickedKey;
        if (o.zone) return null;
        if (o.paper === "cork") {
          return NOTE_SLOTS.slice(0, noteCount(logCount)).map((s, n) => (
            <View
              key={`note-${n}`}
              testID={`scene-note-${n}`}
              style={[st.abs, st.note, {
                left: (s.x - s.w / 2) * k, top: (s.y - s.h) * k, width: s.w * k, height: s.h * k,
                backgroundColor: s.color, transform: [{ rotate: `${s.rot ?? 0}deg` }],
              }]}
            >
              <View style={[st.pin, { width: 18 * k, height: 18 * k, borderRadius: 9 * k, marginTop: 4 * k }]} />
            </View>
          ));
        }
        if (o.paper) {
          return (
            <View key={`paper-${names[i]}`} style={[st.abs, b, o.paper === "blank" ? st.blank : st.strip, on && st.stripOn]}>
              <View style={[st.clip, { width: Math.max(4, 14 * k), height: Math.max(3, 12 * k), top: -Math.max(1.5, 5 * k) }]} />
              {o.paper === "blank" ? null : <View style={[st.ink, { top: b.height * 0.2, height: b.height * (o.paper === "receipt" ? 0.5 : 0.62) }]} />}
            </View>
          );
        }
        const rot = o.slot?.rot ? [{ rotate: `${o.slot.rot}deg` }] : [];
        const coupon = o.art === COUPON_ART;
        const f = Math.max(6.5, b.height * 0.165);
        return (
          <View key={`art-${names[i]}`} style={[st.abs, b, on && st.picked, { transform: [...rot, ...(on ? [{ translateY: -b.height * 0.07 }, { scale: 1.14 }] : [])] }]}>
            <ArtImage art={o.art ?? null} style={st.fill} />
            {coupon ? (
              <Text
                style={[st.couponTx, { left: b.width * (COUPON_TEXT.cx - 0.5), top: b.height * COUPON_TEXT.cy - f * 0.7, width: b.width, fontSize: f, lineHeight: f * 1.3, letterSpacing: f * 0.12, color: COUPON_TEXT.color }]}
                numberOfLines={1}
              >
                买菜券
              </Text>
            ) : null}
          </View>
        );
      })}
      {/* The tap layer: one area per thing (a small picture grows until a finger can hit it, never past the midline to its neighbour) */}
      {objs.map((o, i) => {
        const key = tapKey(o.tap);
        const h = hits[i];
        return (
          <Pressable
            key={`hit-${names[i]}`}
            onPress={() => onTap(o.tap)}
            style={[st.hit, { left: h.x, top: h.y, width: h.w, height: h.h }]}
            accessibilityRole="button"
            accessibilityLabel={o.label}
            accessibilityState={{ selected: key === pickedKey }}
            testID={`obj-${names[i]}`}
          />
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  abs: { position: "absolute", pointerEvents: "none" },
  hit: { position: "absolute" },
  fill: { width: "100%", height: "100%" },
  // the shadow follows the outline of the cut-out, not its box
  picked: { filter: "drop-shadow(0px 3px 5px rgba(74,58,47,0.4))", zIndex: 3 },
  note: { alignItems: "center", ...shadow(0.18, 1.5, 1) },
  pin: { backgroundColor: KC.tomato },
  strip: { backgroundColor: "rgba(255,253,244,0.94)", alignItems: "center", ...shadow(0.3, 1.5, 1) },
  blank: { backgroundColor: "rgba(255,254,249,0.4)", alignItems: "center", borderWidth: 1, borderStyle: "dashed", borderColor: "#8d7a6b" },
  ink: { position: "absolute", width: 1.5, backgroundColor: "rgba(74,58,47,0.3)" },
  stripOn: { borderWidth: 1.5, borderStyle: "solid", borderColor: KC.ink },
  clip: { position: "absolute", backgroundColor: "#8a6a45", borderRadius: 1 },
  couponTx: { position: "absolute", fontFamily: KF, textAlign: "center" },
});
