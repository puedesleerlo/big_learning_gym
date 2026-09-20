import fixture from "./demo.json" with { type: "json" };
import { GymClient, GymError, createMemoryStorage } from "./client.js";

// An explicit, in-memory design preview. It neither calls nor falls back to a real server.
export function createPreviewClient() {
  const data = structuredClone(fixture),
    visits = new Map(),
    sessions = new Map(),
    receipts = new Map();
  const now = () => new Date().toISOString();
  const required = (map, id) => {
    const value = map.get(id);
    if (!value) throw new GymError("Synthetic example not found", 404);
    return value;
  };
  const transport = async (method, path, body) => {
    const parts = path.split("?")[0].split("/").filter(Boolean);
    const [kind, id, action] = parts;
    const receipt = body?.idempotency_key && `${path}:${body.idempotency_key}`;
    if (receipt && receipts.has(receipt))
      return structuredClone(receipts.get(receipt));
    let result;
    if (method === "GET" && kind === "overview")
      result = {
        courses: [{ id: "demo-course", title: "The practice kitchen" }],
        sessions: [...sessions.values()],
      };
    else if (method === "GET" && kind === "lab-activity-types")
      result = data.registry;
    else if (method === "GET" && kind === "labs" && !id) result = data.labs;
    else if (kind === "labs" && id === data.lab.id) {
      if (method === "GET")
        result = { ...data.lab, activities: [...visits.values()] };
      else if (action === "activities") {
        const lesson = data.lab.lessons.find((l) => l.id === body.lesson_id);
        if (!lesson) throw new GymError("Synthetic lesson not found", 404);
        for (const visit of visits.values()) visit.running = false;
        result = {
          id: crypto.randomUUID(),
          lab_id: id,
          lesson_id: lesson.id,
          lesson_snapshot: lesson,
          course_id: data.lab.course_id,
          module: lesson.module,
          status: "active",
          running: true,
          active_seconds: 0,
          elapsed_seconds: 0,
          started_at: now(),
          last_tick: now(),
          lab_revision: 1,
          session_id: null,
          reading_count: 0,
          help_count: 0,
          experiment_count: 0,
          mastery_awarded: false,
          responses: {},
          experiment_results: {},
          visualization_inputs: {},
          discussions: {},
        };
        visits.set(result.id, result);
      }
    } else if (kind === "lab-activities") {
      const visit = required(visits, id);
      result = visit;
      if (action === "events") {
        const p = body.parameters || {};
        if (body.action === "pause") visit.running = false;
        if (body.action === "resume") visit.running = true;
        if (body.action === "finish") {
          visit.running = false;
          visit.status = "finished";
        }
        if (body.action === "reading" || body.action === "media")
          visit.reading_count++;
        if (body.action === "response")
          visit.responses[p.activity_id] = {
            value: p.value,
            recorded_at: now(),
          };
        if (body.action === "visualization") {
          visit.visualization_inputs[p.activity_id] = p.inputs;
          visit.experiment_count++;
        }
        if (body.action === "experiment") {
          const block = visit.lesson_snapshot.activities.find(
            (b) => b.id === p.activity_id,
          );
          visit.experiment_count++;
          visit.experiment_results[p.activity_id] = {
            inputs: p.inputs,
            output:
              block.offset +
              block.inputs.reduce(
                (n, input) => n + input.coefficient * p.inputs[input.key],
                0,
              ),
          };
        }
      } else if (action === "link-session") {
        const session = required(sessions, body.session_id);
        session.guided_activity_id = id;
        visit.session_id = session.id;
        visit.status = "finished";
        visit.running = false;
      } else if (action === "discussion") {
        const thread = (visit.discussions[body.activity_id] ||= {
          turns: [],
          pending: false,
        });
        thread.turns.push({
          message: body.message,
          reply:
            "Synthetic preview reply: which condition did you hold constant?",
          citations: [],
          sources: [],
          provenance: { model: "design fixture" },
        });
        visit.help_count++;
      }
    } else if (kind === "sessions") {
      if (!id && method === "POST") {
        result = {
          ...body,
          id: crypto.randomUUID(),
          status: "active",
          running: true,
          started_at: now(),
          active_seconds: 0,
          items: data.items.slice(0, body.count),
          answers: {},
          current_item: data.items[0].id,
        };
        sessions.set(result.id, result);
      } else {
        const session = required(sessions, id);
        result = session;
        if (action === "timer") {
          if (body.action !== "heartbeat")
            session.running = body.action === "resume";
        }
        if (action === "aid")
          result = {
            kind: body.kind,
            content:
              body.kind === "terms"
                ? []
                : "Synthetic hint: count the changed inputs.",
          };
        if (action === "answers") {
          session.answers[body.item_id] = {
            id: crypto.randomUUID(),
            answer: body.answer,
            status: "scored",
            score: 5,
            feedback: {
              explanation:
                "Illustrative feedback only. The preview does not assess your answer.",
            },
          };
        }
        if (action === "finish") {
          session.status = "finished";
          session.running = false;
          session.score = Object.keys(session.answers).length * 5;
          session.max_score = session.items.length * 5;
          session.completion =
            Object.keys(session.answers).length === session.items.length
              ? "complete"
              : "unfinished";
          session.review = session.items.map((item) => ({
            item,
            feedback: { explanation: "Illustrative preview feedback." },
            attempt: session.answers[item.id] || null,
          }));
        }
      }
    }
    if (result === undefined)
      throw new GymError(`Preview does not implement ${method} ${path}`, 404);
    if (receipt) receipts.set(receipt, structuredClone(result));
    return structuredClone(result);
  };
  return new GymClient(
    {
      workspace_id: "synthetic-preview",
      contract_version: "1.0",
      api_base: "/api",
      experiences: [],
      preview: true,
    },
    { transport, storage: createMemoryStorage() },
  );
}
