// A field that grows with what is typed (one line when empty), up to maxHeight, then scrolls.
// The height comes from an invisible mirror of the text: the mirror is laid out off-screen at the
// field's width and measured, so the field never jumps while a character is being composed.
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, TextInput, View, type StyleProp, type TextInputProps, type TextStyle } from "react-native";

export const PAD_V = 8;
export const PAD_H = 10;
const CARET_SLACK = 2;

/** The height: empty text -> undefined (one line); otherwise min(text height + padding + room for the caret, max), raised to min. */
export function growHeight(value: string, textH: number, maxHeight: number, minHeight?: number): number | undefined {
  const grown = value !== "" && textH > 0 ? Math.min(textH + PAD_V * 2 + CARET_SLACK, maxHeight) : undefined;
  if (grown === undefined) return minHeight;
  return minHeight !== undefined ? Math.max(grown, minHeight) : grown;
}

/** How many lines the mirror measures = enough to fill maxHeight + 2, so the measured height can reach the top and scrolling takes over */
export function mirrorLines(maxHeight: number, fontSize: number, lineHeight?: number): number {
  const lh = lineHeight ?? fontSize * 1.5;
  return Math.ceil(maxHeight / lh) + 2;
}

export function GrowingInput({
  value,
  onChangeText,
  style,
  maxHeight = 160,
  minHeight,
  fontFamily,
  fontSize = 14,
  lineHeight,
  color,
  ...rest
}: Omit<TextInputProps, "style" | "multiline" | "value" | "onChangeText"> & {
  value: string;
  onChangeText: (t: string) => void;
  style?: StyleProp<TextStyle>;
  maxHeight?: number;
  minHeight?: number;
  fontFamily?: string;
  fontSize?: number;
  lineHeight?: number;
  color?: string;
}) {
  const [textH, setTextH] = useState(0);
  const [boxW, setBoxW] = useState(0);
  const onBoxLayout = useCallback((e: { nativeEvent: { layout: { width: number } } }) => {
    setBoxW(e.nativeEvent.layout.width);
  }, []);
  const onMirrorLayout = useCallback((e: { nativeEvent: { layout: { height: number } } }) => {
    setTextH(e.nativeEvent.layout.height);
  }, []);
  useEffect(() => {
    if (value === "") setTextH(0); // back to one line after clearing, so the next character does not start at the old height
  }, [value]);
  const font: TextStyle = { fontFamily, fontSize, lineHeight, color };
  const h = growHeight(value, textH, maxHeight, minHeight);
  return (
    <View onLayout={onBoxLayout}>
      <TextInput
        {...rest}
        value={value}
        onChangeText={onChangeText}
        multiline
        numberOfLines={1}
        style={[g.input, font, style, h !== undefined ? { height: h } : null, { maxHeight }]}
      />
      {value !== "" && boxW > 0 ? (
        // The mirror: off-screen, takes no room and no touches; its width is the field's content width
        // (a touch narrower, so it wraps early rather than late: it can only measure too tall, never too
        // short). A trailing newline is not a line for Text but is for a field: a zero-width character stands in.
        <View style={[g.mirror, { width: Math.max(boxW - PAD_H * 2 - 4, 1) }]}>
          <Text onLayout={onMirrorLayout} numberOfLines={mirrorLines(maxHeight, fontSize, lineHeight)} style={font}>
            {value.endsWith("\n") ? value + "\u200b" : value}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const g = StyleSheet.create({
  input: { paddingHorizontal: PAD_H, paddingVertical: PAD_V, textAlignVertical: "top", outlineWidth: 0 },
  mirror: { position: "absolute", left: -9999, top: 0, pointerEvents: "none" },
});
