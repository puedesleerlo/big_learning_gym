export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}
export interface Bootstrap {
  workspace_id: string;
  contract_version: "1.0";
  api_base: "/api";
  experiences: { id: string; version: string; capabilities: string[] }[];
  preview?: boolean;
}
export interface Parameter {
  key: string;
  label: string;
  min: number;
  max: number;
  initial: number;
  step: number;
  coefficient?: number;
}
export interface BlockBase {
  id: string;
  title: string;
}
export type LabBlock = BlockBase &
  (
    | { type: "reading" | "worked_example"; body: string }
    | { type: "prediction" | "reflection"; prompt: string }
    | {
        type: "parameter_experiment";
        description: string;
        inputs: Parameter[];
        offset: number;
        output_label: string;
        unit: string;
      }
    | { type: "assessment"; mode: "practice" | "transfer"; count: number }
    | { type: "coursework"; assignment_id: string }
    | {
        type: "media";
        kind: "audio" | "video";
        provider: "native" | "youtube" | "vimeo";
        url: string;
        description: string;
        transcript: string;
        start_seconds: number;
        end_seconds?: number | null;
        captions_url?: string | null;
        captions_language: string;
      }
    | {
        type: "visualization";
        html: string;
        css: string;
        javascript: string;
        data: Record<string, Json>;
        parameters: Parameter[];
        description: string;
        fallback: string;
        height: number;
      }
    | {
        type: "discussion";
        prompt: string;
        objectives: string[];
        max_turns: number;
        response_words: number;
        style: string;
      }
  );
export interface Lesson {
  id: string;
  module: string;
  title: string;
  minutes: number;
  objectives: string[];
  activities: LabBlock[];
  source_ids: string[];
  experiment?: string;
  sections?: unknown[];
}
export interface LabSummary {
  id: string;
  course_id: string;
  title: string;
  description: string;
  revision: number;
  course_title: string;
  lesson_count: number;
  activity_count: number;
  objectives: string[];
  prerequisite_lab_ids: string[];
}
export interface Lab extends Omit<
  LabSummary,
  "lesson_count" | "activity_count"
> {
  lessons: Lesson[];
  activities: Omit<Visit, "lesson_snapshot" | "discussions">[];
  activity_summary: {
    active_seconds: number;
    study_visits: number;
    finished_visits: number;
    practice_linked_visits: number;
    mastery_awarded: false;
  };
}
export interface DiscussionRequest {
  activity_id: string;
  message: string;
  expected_turn: number;
  idempotency_key?: string;
}
export interface DiscussionTurn {
  message: string;
  reply: string;
  citations: string[];
  sources: {
    id: string;
    text: string;
    anchor: string;
    source_version_id: string;
  }[];
  provenance: { model: string; [key: string]: Json };
}
export interface Visit {
  id: string;
  lab_id: string;
  course_id: string;
  module: string;
  lesson_id: string;
  status: "active" | "finished";
  running: boolean;
  active_seconds: number;
  elapsed_seconds: number;
  started_at: string;
  last_tick: string;
  lesson_snapshot: Lesson;
  lab_revision: number;
  session_id: string | null;
  reading_count: number;
  help_count: number;
  experiment_count: number;
  mastery_awarded: false;
  responses: Record<string, { value: string; recorded_at: string }>;
  experiment_results: Record<
    string,
    { inputs: Record<string, number>; output: number }
  >;
  visualization_inputs?: Record<string, Record<string, number>>;
  discussions: Record<string, { turns: DiscussionTurn[]; pending: boolean }>;
}
export interface Criterion {
  name: string;
  weight: number;
  anchors: string[];
}
export interface PublicItem {
  id: string;
  type: "mcq" | "matching" | "open" | "case" | "counterfactual" | "coding";
  stem: string;
  points: number;
  module: string;
  options?: { label: string; text: string }[];
  prompts?: { id: string; text: string }[];
  terms?: { id: string; text: string }[];
  rubric?: Criterion[];
  vignette?: {
    id: string;
    title: string;
    text: string;
    table?: { caption: string; columns: string[]; rows: string[][] };
  };
  capabilities: string[];
}
export interface Answer {
  answer: string | Record<string, string>;
  id: string;
  status: string;
  score?: number | null;
  feedback?: Record<string, Json> | null;
}
export interface SessionSummary {
  id: string;
  course_id: string;
  module: string;
  mode: "practice" | "transfer" | "simulation";
  status: "active" | "finished";
  started_at: string;
  active_seconds: number;
}
export interface Session extends SessionSummary {
  running: boolean;
  items: PublicItem[];
  answers: Record<string, Answer>;
  score?: number;
  max_score?: number;
  pending_assessments?: number;
  completion?: string;
  current_item: string;
  guided_activity_id?: string;
  review?: {
    item: PublicItem;
    feedback: Record<string, Json>;
    attempt: Record<string, Json> | null;
  }[];
}
export interface PracticeSpec {
  course_id: string;
  module: string;
  mode: "practice" | "transfer";
  count: number;
  blueprint_id?: string | null;
}
export interface Overview {
  courses: { id: string; title: string; [key: string]: unknown }[];
  sessions: SessionSummary[];
  [key: string]: unknown;
}
export interface ClientOptions {
  fetch?: typeof fetch;
  storage?: StorageLike;
  transport?: (method: string, path: string, body?: unknown) => Promise<any>;
}
export class GymError extends Error {
  status: number;
  detail: any;
  constructor(message: string, status?: number, detail?: unknown);
}
export const CONTRACT_VERSION: "1.0";
export function readBootstrap(fetcher?: typeof fetch): Promise<Bootstrap>;
export function workspaceStorage(
  id: string,
  storage?: StorageLike,
): StorageLike;
export function createMemoryStorage(): StorageLike;
export function connectGym(options?: ClientOptions): Promise<GymClient>;
export function standardGymLink(
  page?: string,
  context?: {
    lab_id?: string;
    lesson_id?: string;
    session_id?: string;
    course_id?: string;
    assignment_id?: string;
  },
): string;
export class GymClient {
  config: Bootstrap;
  storage: StorageLike;
  constructor(config: Bootstrap, options?: ClientOptions);
  setToken(token: string): void;
  clearToken(): void;
  request<T = unknown>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T>;
  overview(): Promise<Overview>;
  labs(courseId?: string): Promise<LabSummary[]>;
  lab(id: string): Promise<Lab>;
  activityTypes(): Promise<{
    version: string;
    types: { type: string; template: LabBlock; schema: unknown }[];
  }>;
  visit(id: string): Promise<Visit>;
  session(id: string): Promise<Session>;
  startVisit(labId: string, lesson: Lesson): Promise<Visit>;
  event(
    visitId: string,
    action:
      | "heartbeat"
      | "pause"
      | "resume"
      | "reading"
      | "help"
      | "experiment"
      | "response"
      | "media"
      | "visualization"
      | "finish",
    extra?: { parameters?: Record<string, Json>; reflection?: string },
  ): Promise<Visit>;
  discuss(visitId: string, request: DiscussionRequest): Promise<unknown>;
  answer(
    sessionId: string,
    itemId: string,
    answer: string | Record<string, string>,
    confidence?: number | null,
  ): Promise<Session>;
  timer(
    sessionId: string,
    action: "pause" | "resume" | "heartbeat",
    itemId?: string,
  ): Promise<{ running: boolean; active_seconds: number }>;
  aid(
    sessionId: string,
    itemId: string,
    kind: "hint" | "plain" | "terms",
  ): Promise<{ kind: string; content: Json }>;
  finish(sessionId: string, blocker?: string | null): Promise<Session>;
  startLinkedPractice(visit: Visit, spec: PracticeSpec): Promise<Session>;
  abandonPendingPractice(visitId: string): void;
  recoveryCandidates(visit: Visit): Promise<SessionSummary[]>;
  linkPractice(visitId: string, sessionId: string): Promise<Session>;
}
