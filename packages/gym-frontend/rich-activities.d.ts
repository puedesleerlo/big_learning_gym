import type { ReactElement } from "react";
import type { LabBlock, Visit, GymClient, DiscussionRequest } from "./index.js";
type Props<K> = {
  block: Extract<LabBlock, { type: K }>;
  enabled: boolean;
  preview: boolean;
  run?: Visit | null;
  onEvent?: (
    action: Parameters<GymClient["event"]>[1],
    extra?: Parameters<GymClient["event"]>[2],
  ) => Promise<unknown>;
  onDiscuss?: (request: DiscussionRequest) => Promise<unknown>;
};
export function MediaActivity(props: Props<"media">): ReactElement;
export function VisualizationActivity(
  props: Props<"visualization">,
): ReactElement;
export function DiscussionActivity(props: Props<"discussion">): ReactElement;
