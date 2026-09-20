import { readBootstrap, GymClient } from "@learning-gym/frontend";
export let workspaceStorage;
export let workspaceConfig;
export let workspaceClient;
export async function initializeWorkspace() {
  workspaceConfig = await readBootstrap();
  workspaceClient = new GymClient(workspaceConfig);
  workspaceStorage = workspaceClient.storage;
}
export function initialRoute() {
  const query = new URLSearchParams(window.location.search);
  const allowed = [
    "home",
    "labs",
    "lab",
    "session",
    "create",
    "coursework",
    "plan",
    "research",
    "progress",
    "system",
  ];
  let page = allowed.includes(query.get("page")) ? query.get("page") : "home";
  const get = (key) => (query.get(key) || "").slice(0, 200) || null;
  if (page === "lab" && !get("lab_id")) page = "labs";
  if (page === "session" && !get("session_id")) page = "home";
  return {
    page,
    labId: get("lab_id"),
    lessonId: get("lesson_id"),
    sessionId: get("session_id"),
    courseId: get("course_id"),
    assignmentId: get("assignment_id"),
  };
}
