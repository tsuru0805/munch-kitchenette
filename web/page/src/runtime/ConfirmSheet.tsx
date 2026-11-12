// A yes/no question on a slip of paper. The app this page comes from asks through the phone's own
// alert; a web page has none worth using, so the question is written on the same paper as the other sheets.
import { StyleSheet, Text } from "react-native";
import { KC, KF, KL } from "../kitchen/kitchenTheme";
import { HeadBtn, Paper, SheetBtn, SheetFoot, SheetFrame } from "../kitchen/sheetParts";

export interface ConfirmAsk {
  title: string;
  message?: string;
  /** the word on the button that goes ahead */
  yes: string;
  /** the word on the button that backs out (「算了」 when left out) */
  no?: string;
  onYes: () => void;
}

export function ConfirmSheet({ ask, onDone }: { ask: ConfirmAsk | null; onDone: () => void }) {
  return (
    <SheetFrame open={ask !== null} onClose={onDone}>
      <Paper testID="confirm-sheet">
        <Text style={st.title}>{ask?.title ?? ""}</Text>
        {ask?.message ? <Text style={st.msg}>{ask.message}</Text> : null}
        <SheetFoot>
          <HeadBtn label={ask?.no ?? "算了"} onPress={onDone} testID="confirm-no" />
          <SheetBtn
            label={ask?.yes ?? ""}
            onPress={() => {
              const a = ask;
              onDone();
              a?.onYes();
            }}
            testID="confirm-yes"
          />
        </SheetFoot>
      </Paper>
    </SheetFrame>
  );
}

const st = StyleSheet.create({
  title: { fontFamily: KF, fontSize: 17, lineHeight: 26, letterSpacing: 2, color: KC.ink },
  msg: { fontFamily: KL, fontSize: 12.5, lineHeight: 21, color: KC.ink, marginTop: 8 },
});
