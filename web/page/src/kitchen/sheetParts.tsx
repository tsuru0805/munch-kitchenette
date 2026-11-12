// The look shared by the "sheets" that come down over the page (the grocery catalog / adding a kind /
// putting a dish up / changing one): paper ground, one ink line around it, a solid shadow offset to
// the lower right. A sheet drops from the top of the screen, so every field that needs typing is in
// the upper half and an on-screen keyboard does not cover it. A chosen thing is circled in red pen
// (handParts.Ring).
import type { ReactNode } from "react";
import { Modal, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { usePageWidth } from "../runtime/layout";
import { KC, KF } from "./kitchenTheme";

export const TAN = "#d8c6b6";

/** The veil over the page with the sheet at its top; tapping below the sheet closes it */
export function SheetFrame({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const width = usePageWidth();
  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
      <View style={sh.veil}>
        <View style={[sh.col, { width }]}>
          {children}
          <Pressable style={sh.dim} onPress={onClose} accessibilityRole="button" accessibilityLabel="收起" />
        </View>
      </View>
    </Modal>
  );
}

/** The sheet itself: an offset shadow block behind the paper */
export function Paper({ children, style, testID }: { children: ReactNode; style?: StyleProp<ViewStyle>; testID?: string }) {
  return (
    <View style={[sh.wrap, style]}>
      <View style={sh.shadow} />
      <View style={sh.paper} testID={testID}>{children}</View>
    </View>
  );
}

export function SheetHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <View style={sh.head}>
      <Text style={sh.title}>{title}</Text>
      <View style={sh.headR}>{children}</View>
    </View>
  );
}

export function HeadBtn({ label, onPress, testID, a11y, disabled }: { label: string; onPress: () => void; testID?: string; a11y?: string; disabled?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} hitSlop={10} accessibilityRole="button" accessibilityLabel={a11y ?? label} accessibilityState={{ disabled: !!disabled }} testID={testID} style={disabled ? sh.off : null}>
      <Text style={sh.headBtn}>{label}</Text>
    </Pressable>
  );
}

/** The main action on a sheet: a red line box with a pale red shadow offset behind it */
export function SheetBtn({ label, onPress, disabled, testID }: { label: string; onPress: () => void; disabled?: boolean; testID?: string }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      hitSlop={6}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled }}
      testID={testID}
      style={[sh.btnWrap, disabled && sh.off]}
    >
      <View style={sh.btnShadow} />
      <View style={sh.btn}>
        <Text style={sh.btnTx}>{label}</Text>
      </View>
    </Pressable>
  );
}

export function Label({ children, first }: { children: ReactNode; first?: boolean }) {
  return <Text style={[sh.label, first && { marginTop: 10 }]}>{children}</Text>;
}

/** The bottom line of a sheet: a dashed rule above, a small note on the left, the main action on the right */
export function SheetFoot({ left, children }: { left?: string; children: ReactNode }) {
  return (
    <View style={sh.footWrap}>
      <View style={sh.dash} />
      <View style={sh.foot}>
        <Text style={sh.footTx}>{left ?? ""}</Text>
        <View style={sh.footR}>{children}</View>
      </View>
    </View>
  );
}

export const sh = StyleSheet.create({
  // the whole screen: a pale paper veil over the page behind (not a dark one)
  veil: { flex: 1, backgroundColor: "rgba(251,246,239,0.62)", alignItems: "center" },
  col: { flex: 1, paddingTop: 18 },
  dim: { flex: 1, minHeight: 40 },
  wrap: { marginHorizontal: 14, paddingRight: 4, paddingBottom: 4, flexShrink: 1 },
  shadow: { position: "absolute", left: 4, top: 4, right: 0, bottom: 0, backgroundColor: TAN },
  paper: { backgroundColor: "#fffdf8", borderWidth: 1, borderColor: KC.ink, paddingTop: 14, paddingHorizontal: 16, paddingBottom: 14, flexShrink: 1 },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  title: { fontFamily: KF, fontSize: 17, lineHeight: 24, letterSpacing: 3, color: KC.ink },
  headR: { flexDirection: "row", alignItems: "center", columnGap: 16 },
  headBtn: { fontFamily: KF, fontSize: 12, lineHeight: 18, letterSpacing: 1, color: KC.soft },
  btnWrap: { paddingRight: 2, paddingBottom: 2 },
  btnShadow: { position: "absolute", left: 2, top: 2, right: 0, bottom: 0, backgroundColor: "#f3c9bf" },
  btn: { borderWidth: 1, borderColor: KC.tomato, backgroundColor: "#fffdf8", paddingTop: 5, paddingBottom: 4, paddingHorizontal: 14 },
  btnTx: { fontFamily: KF, fontSize: 14, lineHeight: 20, letterSpacing: 3, color: KC.tomato },
  off: { opacity: 0.4 },
  label: { fontFamily: KF, fontSize: 10.5, lineHeight: 16, letterSpacing: 2, color: KC.soft, marginTop: 12, marginBottom: 3 },
  // a field to write in: only an ink line under it
  field: { borderBottomWidth: 1, borderBottomColor: KC.ink, paddingHorizontal: 0, paddingTop: 3, paddingBottom: 4 },
  footWrap: { marginTop: 12 },
  dash: { height: 1, borderTopWidth: 1, borderStyle: "dashed", borderColor: TAN },
  foot: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingTop: 9 },
  footTx: { fontFamily: KF, fontSize: 11, lineHeight: 17, letterSpacing: 1, color: KC.soft, flexShrink: 1 },
  footR: { flexDirection: "row", alignItems: "center", columnGap: 14 },
  err: { fontFamily: KF, fontSize: 12, lineHeight: 18, color: KC.bad, marginTop: 8 },
});
