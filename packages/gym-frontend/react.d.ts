import type { Dispatch, SetStateAction } from "react";
import type {
  GymClient,
  GymError,
  Lesson,
  Visit,
  Session,
  PracticeSpec,
  DiscussionRequest,
} from "./index.js";
export interface Resource<T> {
  data: T | null;
  error: GymError | null;
  loading: boolean;
  reload(): Promise<T | null>;
  setData: Dispatch<SetStateAction<T | null>>;
}
export function useResource<T>(
  load: () => Promise<T>,
  dependencies?: unknown[],
): Resource<T>;
export function useLabVisit(
  client: GymClient,
  labId: string,
  lessonId: string,
): Resource<Visit> & {
  clockError: Error | null;
  event(
    action: Parameters<GymClient["event"]>[1],
    extra?: Parameters<GymClient["event"]>[2],
  ): Promise<Visit>;
  start(lesson: Lesson): Promise<Visit>;
  discuss(request: DiscussionRequest): Promise<unknown>;
  practice(spec: PracticeSpec): Promise<Session>;
};
export function usePracticeSession(
  client: GymClient,
  id: string,
): Resource<Session> & {
  clockError: Error | null;
  timer(
    action: "pause" | "resume" | "heartbeat",
    itemId?: string,
  ): Promise<{ running: boolean; active_seconds: number }>;
  answer(
    itemId: string,
    value: string | Record<string, string>,
    confidence?: number | null,
  ): Promise<Session | null>;
  finish(blocker?: string): Promise<Session>;
};
