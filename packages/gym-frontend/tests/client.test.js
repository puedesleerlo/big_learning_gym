import test from "node:test";
import assert from "node:assert/strict";
import {
  GymClient,
  createMemoryStorage,
  workspaceStorage,
  standardGymLink,
  readBootstrap,
} from "../client.js";
import { createPreviewClient } from "../preview.js";
const config = {
  workspace_id: "alpha",
  contract_version: "1.0",
  api_base: "/api",
  experiences: [],
};

test("workspace state, credentials, drafts, and default migration stay separate", () => {
  const memory = createMemoryStorage();
  memory.setItem("gym-session", "old-session");
  const a = workspaceStorage("alpha", memory),
    b = workspaceStorage("beta", memory),
    old = workspaceStorage("default", memory);
  assert.equal(a.getItem("gym-session"), null);
  assert.equal(old.getItem("gym-session"), "old-session");
  assert.equal(memory.getItem("gym-session"), null);
  a.setItem("gym-token", "alpha-token");
  a.setItem("draft", "alpha-answer");
  assert.equal(b.getItem("gym-token"), null);
  assert.equal(b.getItem("draft"), null);
  assert.equal(
    workspaceStorage("alpha", memory).getItem("draft"),
    "alpha-answer",
  );
});
test("answer receipt survives a lost response and a new client", async () => {
  const memory = createMemoryStorage(),
    effects = new Map(),
    calls = [];
  const transport = async (method, path, body) => {
    calls.push(body.idempotency_key);
    if (!effects.has(body.idempotency_key)) {
      effects.set(body.idempotency_key, body);
      throw new TypeError("Connection lost");
    }
    return { saved: true };
  };
  const first = new GymClient(config, { storage: memory, transport });
  await assert.rejects(first.answer("s", "q", "A"));
  assert.equal(calls.length, 1);
  const second = new GymClient(config, { storage: memory, transport });
  await second.answer("s", "q", "A");
  assert.equal(effects.size, 1);
  assert.equal(calls[0], calls[1]);
});
test("non-idempotent session creation is never automatically retried; explicit recovery links once", async () => {
  const memory = createMemoryStorage();
  let creates = 0,
    links = 0,
    exists = false;
  const visit = {
    id: "visit",
    course_id: "c",
    module: "m",
    started_at: "2026-01-01",
  };
  const transport = async (method, path) => {
    if (path === "/overview")
      return {
        sessions: exists
          ? [
              {
                id: "new",
                course_id: "c",
                module: "m",
                mode: "practice",
                status: "active",
                started_at: "2026-02-01",
              },
            ]
          : [],
      };
    if (path === "/sessions") {
      creates++;
      exists = true;
      throw new TypeError("Response lost");
    }
    if (path.includes("link-session")) {
      links++;
      return {};
    }
    return { id: "new" };
  };
  const client = new GymClient(config, { storage: memory, transport });
  await assert.rejects(
    client.startLinkedPractice(visit, {
      course_id: "c",
      module: "m",
      mode: "practice",
      count: 1,
    }),
    (e) => e.detail.recovery,
  );
  await assert.rejects(
    client.startLinkedPractice(visit, {
      course_id: "c",
      module: "m",
      mode: "practice",
      count: 1,
    }),
    (e) => e.detail.recovery,
  );
  assert.equal(creates, 1);
  const recovered = await client.recoveryCandidates(visit);
  assert.equal(recovered.length, 1);
  await client.linkPractice(visit.id, recovered[0].id);
  assert.equal(links, 1);
  assert.equal(client.storage.getItem("gym-session"), "new");
});
test("failed link recovers the known session without creating another", async () => {
  let creates = 0,
    links = 0;
  const client = new GymClient(config, {
    storage: createMemoryStorage(),
    transport: async (method, path) => {
      if (path === "/overview") return { sessions: [] };
      if (path === "/sessions") {
        creates++;
        return { id: "known" };
      }
      if (path.endsWith("link-session") && ++links === 1)
        throw new TypeError("lost link response");
      return { id: "known" };
    },
  });
  const visit = { id: "v" },
    spec = { mode: "practice" };
  await assert.rejects(client.startLinkedPractice(visit, spec));
  await client.startLinkedPractice(visit, spec);
  assert.equal(creates, 1);
  assert.equal(links, 2);
});
test("live requests keep API errors, use current token, and never select preview", async () => {
  let calls = 0;
  const client = new GymClient(config, {
    storage: createMemoryStorage(),
    fetch: async (url, options) => {
      calls++;
      assert.equal(url, "/api/labs");
      assert.equal(options.headers.Authorization, "Bearer secret");
      return new Response(
        JSON.stringify({ detail: "Enter the server access token" }),
        { status: 401 },
      );
    },
  });
  client.setToken("secret");
  await assert.rejects(client.labs(), (e) => e.status === 401);
  assert.equal(calls, 1);
  await assert.rejects(
    readBootstrap(
      async () =>
        new Response(JSON.stringify({ ...config, contract_version: "9" })),
    ),
    /compatible/,
  );
});
test("preview completes an illustrative journey without fetching a server", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = () => {
    throw new Error("No network in preview");
  };
  try {
    const client = createPreviewClient(),
      [lab] = await client.labs(),
      detail = await client.lab(lab.id);
    const visit = await client.startVisit(lab.id, detail.lessons[0]);
    await client.event(visit.id, "reading", {
      parameters: { section: "lesson" },
    });
    const session = await client.startLinkedPractice(visit, {
      course_id: lab.course_id,
      module: visit.module,
      mode: "practice",
      count: 1,
    });
    await client.answer(session.id, session.items[0].id, "A");
    const result = await client.finish(session.id);
    assert.equal(result.status, "finished");
    assert.equal(client.config.preview, true);
  } finally {
    globalThis.fetch = previous;
  }
});
test("standard links encode identifiers and reject unknown pages", () => {
  assert.equal(
    standardGymLink("coursework", { assignment_id: "a&b" }),
    "/?page=coursework&assignment_id=a%26b",
  );
  assert.throws(() => standardGymLink("javascript:bad"));
});

test("a known legacy pending session is reused and linked visits do not create another", async () => {
  const memory = createMemoryStorage();
  const client = new GymClient(config, {
    storage: memory,
    transport: async (method, path) => {
      assert.notEqual(path, "/sessions", "must never create another session");
      return { id: "known" };
    },
  });
  client.storage.setItem("gym-lab-pending:v", "known");
  assert.equal((await client.startLinkedPractice({ id: "v" }, {})).id, "known");
  assert.equal(client.storage.getItem("gym-lab-pending:v"), null);
  assert.equal(
    (await client.startLinkedPractice({ id: "v", session_id: "known" }, {})).id,
    "known",
  );
});

test("legacy lesson links identify the exact lesson in the full Gym", () => {
  assert.equal(
    standardGymLink("lab", { lab_id: "lab", lesson_id: "second lesson" }),
    "/?page=lab&lab_id=lab&lesson_id=second+lesson",
  );
});
