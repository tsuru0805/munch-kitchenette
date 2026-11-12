// The cooking card: <kitchenette-cooking-card>. Importing this file registers the element.
export { KitchenetteCookingCard, TAG, defineCookingCard } from "./element";
export { KitchenFetchError, apiProbe, fetchKitchen, fetchSession, parseAnswer, parseOutcome, probeFromSession } from "./api";
export type { KitchenAnswer, KitchenErrorKind, KitchenIngredient, KitchenProbe, KitchenSession, ProbeFn } from "./api";
export * from "./cookPhase";
export * from "./cookSegments";
export { METHOD_PARTS, missingKeys, requiredSegments, CANVAS_PX, SRC_CANVAS, SRC_LINE_Y, STAGE_PX } from "./manifest";
export type { SpriteManifest } from "./manifest";
export { CLAWD_MANIFEST } from "./manifest.generated";
export { MAX_ANIMATED } from "./seats";
export { STRINGS, stringsFor } from "./strings";
export type { CardStrings } from "./strings";

import { defineCookingCard } from "./element";

defineCookingCard();
