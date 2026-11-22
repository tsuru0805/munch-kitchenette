// Small shared parts: one cut-out picture, a thumbnail, a row, and the "refresh failed" line.
import { useState, type ReactNode } from "react";
import { Image, Pressable, StyleSheet, Text, View, type ImageStyle, type StyleProp } from "react-native";
import { useAuthedSource } from "./authedImage";
import { artRef, type AnyArt } from "./kindArt";
import { KC, KF } from "./kitchenTheme";

/**
 * One picture; when there is none, or the server's one could not be fetched, the fallback (a character card)
 * is drawn instead of an empty box. A picture the server gives out only with the token is fetched with it
 * first (authedImage.ts); the fallback stands in until it is there.
 */
export function ArtImage({ art, style, fallback = null }: { art: AnyArt | null; style: StyleProp<ImageStyle>; fallback?: ReactNode }) {
  const src = art ? artRef(art).src : null;
  const loaded = useAuthedSource(src);
  // what the <Image> is actually given (a fetched picture gets a new object URL every time it is fetched):
  // a failure belongs to that, so a later fetch of the same picture that works is shown
  const shown = loaded.state !== "ready" ? "" : typeof loaded.src === "object" && loaded.src && "uri" in loaded.src ? String(loaded.src.uri) : String(art);
  const [failed, setFailed] = useState<string | null>(null);
  if (!src || loaded.state !== "ready" || failed === shown) return <>{fallback}</>;
  return <Image source={loaded.src} style={style} resizeMode="contain" accessible={false} onError={() => setFailed(shown)} />;
}

/** A 40 × 40 rounded thumbnail; with no picture (an added kind that was never drawn) it shows the first character of the name */
export function Thumb({ art, name }: { art: AnyArt | null; name?: string }) {
  return (
    <View style={ps.thumb}>
      <ArtImage art={art} style={ps.thumbImg} fallback={name ? <Text style={ps.thumbTx}>{Array.from(name)[0]}</Text> : null} />
    </View>
  );
}

/** There is older data and this refresh failed: the old data stays, with one small line above it to try again */
export function RefreshFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <Pressable onPress={onRetry} hitSlop={8} accessibilityRole="button" accessibilityLabel="刷新失败,重试" testID="refresh-failed">
      <Text style={ps.refreshFail}>刷新失败 · 重试</Text>
    </Pressable>
  );
}

export const ps = StyleSheet.create({
  thumb: { width: 40, height: 40, borderRadius: 10, backgroundColor: KC.thumb, padding: 4, overflow: "hidden" },
  thumbImg: { width: "100%", height: "100%" },
  thumbTx: { fontFamily: KF, fontSize: 17, lineHeight: 32, textAlign: "center", color: KC.soft },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: KC.line,
  },
  rowLast: { borderBottomWidth: 0 },
  nm: { flex: 1, minWidth: 0 },
  nmTx: { fontFamily: KF, fontSize: 16, lineHeight: 22, letterSpacing: 1, color: KC.ink },
  nmSmall: { fontFamily: KF, fontSize: 11, lineHeight: 16, color: KC.soft, marginTop: 1 },
  refreshFail: { fontFamily: KF, fontSize: 12, lineHeight: 18, letterSpacing: 1, color: KC.bad, marginTop: 10 },
  status: { fontFamily: KF, fontSize: 13, lineHeight: 20, color: KC.soft, paddingVertical: 16, textAlign: "center" },
});
