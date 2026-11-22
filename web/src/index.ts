// The cooking card <kitchenette-cooking-card> and the washing card <kitchenette-washing-card>.
// Importing this file registers both elements.
export { KitchenetteCookingCard, TAG, defineCookingCard } from "./element";
export { KitchenFetchError, apiProbe, fetchKitchen, fetchSession, parseAnswer, parseOutcome, probeFromSession } from "./api";
export type { KitchenAnswer, KitchenErrorKind, KitchenIngredient, KitchenProbe, KitchenSession, ProbeFn } from "./api";
export * from "./cookPhase";
export * from "./cookSegments";
export { CHORE_SEGMENTS, METHOD_PARTS, missingChoreKeys, missingKeys, requiredSegments, CANVAS_PX, SRC_CANVAS, SRC_LINE_Y, STAGE_PX } from "./manifest";
export type { SpriteManifest } from "./manifest";
export { CLAWD_MANIFEST } from "./manifest.generated";
export { MAX_ANIMATED } from "./seats";
export { STRINGS, stringsFor } from "./strings";
export type { CardStrings } from "./strings";
export { KitchenetteWashingCard, WASH_POLL_MS, WASH_READ_LAG_MS, WASH_TAG, defineWashingCard } from "./washElement";
export { factsFromAttachment, factsFromRead, fetchWashing, parseWashRead, washApiProbe } from "./washApi";
export type { WashProbeFn, WashingAttachment } from "./washApi";
export * from "./washSegments";
export { washFace } from "./washFace";
export type { WashFace } from "./washFace";
export { WASH_STRINGS, washStringsFor } from "./washStrings";
export type { WashCardStrings, WashCounts } from "./washStrings";

import { defineCookingCard } from "./element";
import { defineWashingCard } from "./washElement";

defineCookingCard();
defineWashingCard();
