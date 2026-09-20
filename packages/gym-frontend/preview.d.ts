import type { GymClient } from "./index.js";
/** Explicit in-memory synthetic design preview; never connects to a server. */
export function createPreviewClient(): GymClient;
