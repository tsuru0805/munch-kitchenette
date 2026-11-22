// The cook's chore panel: plays what choreAnim names; with "reduce motion" on, only a still frame.
import TestRenderer, { act } from "react-test-renderer";
import { AccessibilityInfo } from "react-native";
import { ChoreStage } from "./ChoreStage";
import type { ChoreClip } from "./choreAnim";

const clip = (segment: string): ChoreClip => ({ segment, outfit: "toque", run: "r" });

async function render(reduce: boolean, segment: string | null) {
  jest.spyOn(AccessibilityInfo, "isReduceMotionEnabled").mockResolvedValue(reduce);
  let r!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    r = TestRenderer.create(<ChoreStage pick={() => (segment ? clip(segment) : null)} testID="cook" />);
  });
  return r;
}
const shown = (r: TestRenderer.ReactTestRenderer) =>
  r.root.findAll((n) => typeof n.props.testID === "string" && n.props.testID.startsWith("cook-")).map((n) => n.props.testID as string)[0] ?? null;

afterEach(() => jest.restoreAllMocks());

test("plays the named clip", async () => {
  const r = await render(false, "machine_run");
  expect(shown(r)).toBe("cook-machine_run");
  act(() => r.unmount());
});

test("reduce motion: a looping clip stands still in the base pose; one that plays once, on its last frame", async () => {
  let r = await render(true, "machine_run");
  expect(shown(r)).toBe("cook-base");
  act(() => r.unmount());
  r = await render(true, "vendor_th_give");
  expect(shown(r)).toBe("cook-vendor_th_give_last");
  act(() => r.unmount());
  r = await render(true, "vendor_call");
  expect(shown(r)).toBe("cook-vendor_still");
  act(() => r.unmount());
  r = await render(true, "machine_done");
  expect(shown(r)).toBe("cook-machine_done_last");
  act(() => r.unmount());
});

test("nothing to play: no panel", async () => {
  const r = await render(false, null);
  expect(r.toJSON()).toBeNull();
  act(() => r.unmount());
});
