// The "put a dish up" sheet: a dish (name + note), a potion (amount + memo); changing a dish or a
// bottle is written on this same sheet. Only the look is here: the state and what happens on
// submit are in the page (KitchenPage.tsx).
// The hand sits in the lower half of the screen, which is where an on-screen keyboard comes up, so
// everything that needs typing is on this sheet that drops from the top.
import { ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { GrowingInput } from "../runtime/GrowingInput";
import { KC, KF, bodoniFor } from "./kitchenTheme";
import { PCT_MAX_DIGITS } from "./potionApi";
import { HeadBtn, Label, Paper, SheetBtn, SheetFoot, SheetFrame, SheetHead, sh } from "./sheetParts";

export interface WriteSheetProps {
  open: boolean;
  onClose: () => void;
  /** the row being changed; null = a new one */
  edit: { potion: boolean; name: string } | null;
  editName: string;
  editNote: string;
  setEditName: (v: string) => void;
  setEditNote: (v: string) => void;
  onSaveEdit: () => void;
  dishDraft: string;
  dishNoteDraft: string;
  setDishDraft: (v: string) => void;
  setDishNoteDraft: (v: string) => void;
  onAdd: () => void;
  /** the potion's name (from the server); null = no potion can be hung right now, and that part is not shown */
  potionName: string | null;
  potionDraft: string;
  setPotionDraft: (v: string) => void;
  potionMemoDraft: string;
  setPotionMemoDraft: (v: string) => void;
  onAddPotion: () => void;
  /** what just happened (not filled in right / could not be put up / could not be changed); a toast would be hidden behind the open sheet, so it is written here too */
  msg?: string;
}

export function WriteSheet(p: WriteSheetProps) {
  const { height } = useWindowDimensions();
  return (
    <SheetFrame open={p.open} onClose={p.onClose}>
      <Paper style={{ maxHeight: height * 0.78 }} testID="write-sheet">
        <SheetHead title={p.edit ? (p.edit.potion ? "改这一瓶" : "改这一道") : "挂一道"}>
          <HeadBtn label="收起" onPress={p.onClose} testID="write-close" />
        </SheetHead>
        <ScrollView style={st.scroll} keyboardShouldPersistTaps="handled">
          {p.edit ? (
            p.edit.potion ? (
              <>
                <Label first>{p.edit.name}</Label>
                <View style={st.pctRow}>
                  <Text style={st.pctTx}>回</Text>
                  <GrowingInput value={p.editNote} onChangeText={p.setEditNote} placeholder="30" inputMode="numeric" maxLength={PCT_MAX_DIGITS} {...numField} style={[sh.field, st.pctField]} testID="potion-edit-pct" />
                  <Text style={st.pctTx}>% 体力</Text>
                </View>
                <Label>药剂的备注</Label>
                <GrowingInput value={p.editName} onChangeText={p.setEditName} placeholder="备注" {...field} style={sh.field} testID="potion-edit-memo" />
              </>
            ) : (
              <>
                <Label first>菜名</Label>
                <GrowingInput value={p.editName} onChangeText={p.setEditName} placeholder="菜名" {...field} style={sh.field} testID="dish-edit-name" />
                <Label>备注</Label>
                <GrowingInput value={p.editNote} onChangeText={p.setEditNote} placeholder="备注" {...field} style={sh.field} testID="dish-edit-note" />
              </>
            )
          ) : (
            <>
              <Label first>菜名</Label>
              <GrowingInput value={p.dishDraft} onChangeText={p.setDishDraft} placeholder="挂一道菜…" {...field} style={sh.field} testID="dish-name" />
              <Label>备注</Label>
              <GrowingInput value={p.dishNoteDraft} onChangeText={p.setDishNoteDraft} placeholder="备注" {...field} style={sh.field} testID="dish-note" />
              <SheetFoot>
                <SheetBtn label="挂上" onPress={p.onAdd} testID="add-dish" />
              </SheetFoot>
              {p.potionName ? (
                <View testID="potion-add">
                  <Label>{p.potionName}</Label>
                  <View style={st.pctRow}>
                    <Text style={st.pctTx}>回</Text>
                    <GrowingInput value={p.potionDraft} onChangeText={p.setPotionDraft} placeholder="30" inputMode="numeric" maxLength={PCT_MAX_DIGITS} {...numField} style={[sh.field, st.pctField]} testID="potion-pct" />
                    <Text style={st.pctTx}>% 体力</Text>
                  </View>
                  <Label>药剂的备注</Label>
                  <GrowingInput value={p.potionMemoDraft} onChangeText={p.setPotionMemoDraft} placeholder="药剂的备注" {...field} style={sh.field} testID="potion-memo" />
                  <SheetFoot>
                    <SheetBtn label="挂药剂" onPress={p.onAddPotion} testID="add-potion" />
                  </SheetFoot>
                </View>
              ) : null}
            </>
          )}
        </ScrollView>
        {p.msg ? <Text style={sh.err} testID="write-msg">{p.msg}</Text> : null}
        {p.edit ? (
          <SheetFoot>
            <HeadBtn label="算了" onPress={p.onClose} testID="edit-cancel" />
            <SheetBtn label="存" onPress={p.onSaveEdit} testID="edit-save" />
          </SheetFoot>
        ) : null}
      </Paper>
    </SheetFrame>
  );
}

const field = { fontFamily: KF, fontSize: 15, lineHeight: 22, color: KC.ink, placeholderTextColor: "#c4b5a8", maxHeight: 132 };
const numField = { ...field, fontFamily: bodoniFor(19), fontSize: 19, lineHeight: 30, maxHeight: 40 };

const st = StyleSheet.create({
  scroll: { flexGrow: 0, flexShrink: 1 },
  pctRow: { flexDirection: "row", alignItems: "flex-end", columnGap: 8 },
  pctTx: { fontFamily: KF, fontSize: 14, lineHeight: 30, letterSpacing: 1, color: KC.ink },
  pctField: { width: 58, textAlign: "center" },
});
