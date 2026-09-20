export const CONTRACT_VERSION = "1.0";

export class GymError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = "GymError";
    this.status = status;
    this.detail = detail;
  }
}

export function createMemoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

export function workspaceStorage(id, storage = globalThis.sessionStorage) {
  const prefix = `gym-workspace:${id}:`;
  return {
    getItem(key) {
      let value = storage.getItem(prefix + key);
      // One-way migration for the original local workspace only.
      if (value === null && id === "default") {
        value = storage.getItem(key);
        if (value !== null) {
          storage.setItem(prefix + key, value);
          storage.removeItem(key);
        }
      }
      return value;
    },
    setItem: (key, value) => storage.setItem(prefix + key, value),
    removeItem(key) {
      storage.removeItem(prefix + key);
      if (id === "default") storage.removeItem(key);
    },
  };
}

export async function readBootstrap(fetcher = globalThis.fetch) {
  const response = await fetcher("/app-config.json", { cache: "no-store" });
  if (!response.ok)
    throw new GymError(
      "Cannot load workspace configuration. Check the local Gym server.",
      response.status,
    );
  const config = await response.json();
  if (
    config.contract_version !== CONTRACT_VERSION ||
    !config.workspace_id ||
    config.api_base !== "/api"
  ) {
    throw new GymError(
      "This frontend needs a compatible Gym frontend contract (1.0).",
    );
  }
  return config;
}

export async function connectGym(options = {}) {
  const config = await readBootstrap(options.fetch);
  return new GymClient(config, options);
}

export function standardGymLink(page = "home", context = {}) {
  const supported = [
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
  if (!supported.includes(page))
    throw new GymError("Unknown standard Gym page");
  const params = new URLSearchParams({ page });
  for (const key of [
    "lab_id",
    "lesson_id",
    "session_id",
    "course_id",
    "assignment_id",
  ]) {
    if (context[key]) params.set(key, context[key]);
  }
  return `/?${params}`;
}

export class GymClient {
  constructor(
    config,
    {
      fetch: fetcher = globalThis.fetch,
      storage = globalThis.sessionStorage,
      transport,
    } = {},
  ) {
    this.config = config;
    this.storage = workspaceStorage(config.workspace_id, storage);
    this.fetcher = fetcher.bind(globalThis);
    this.transport = transport;
    this.queues = new Map();
  }
  setToken(token) {
    this.storage.setItem("gym-token", token);
  }
  clearToken() {
    this.storage.removeItem("gym-token");
  }
  async request(method, path, body) {
    if (!path.startsWith("/") || path.startsWith("//"))
      throw new GymError("Use a relative Gym API path");
    if (this.transport) return this.transport(method, path, body);
    const token = this.storage.getItem("gym-token");
    const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}) };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    // No implicit mutation retries. Receipted operations retain their key for explicit retries.
    const response = await this.fetcher(this.config.api_base + path, {
      method,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      cache: "no-store",
      ...(body?.action === "pause" ? { keepalive: true } : {}),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new GymError(
        `Gym returned an invalid response (${response.status}).`,
        response.status,
      );
    }
    if (!response.ok)
      throw new GymError(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail),
        response.status,
        data,
      );
    return data;
  }
  overview() {
    return this.request("GET", "/overview");
  }
  labs(courseId) {
    return this.request(
      "GET",
      "/labs" + (courseId ? `?course_id=${encodeURIComponent(courseId)}` : ""),
    );
  }
  lab(id) {
    return this.request("GET", `/labs/${encodeURIComponent(id)}`);
  }
  activityTypes() {
    return this.request("GET", "/lab-activity-types");
  }
  visit(id) {
    return this.request("GET", `/lab-activities/${encodeURIComponent(id)}`);
  }
  session(id) {
    return this.request("GET", `/sessions/${encodeURIComponent(id)}`);
  }
  serial(key, fn) {
    const next = (this.queues.get(key) || Promise.resolve())
      .catch(() => {})
      .then(fn);
    this.queues.set(key, next);
    next
      .finally(() => {
        if (this.queues.get(key) === next) this.queues.delete(key);
      })
      .catch(() => {});
    return next;
  }
  async receipt(path, body, scope = "") {
    const key = `pending:${path}:${scope}`;
    const signature = JSON.stringify(body);
    let pending = JSON.parse(this.storage.getItem(key) || "null");
    if (!pending || pending.signature !== signature) {
      pending = {
        signature,
        body: { ...body, idempotency_key: crypto.randomUUID() },
      };
      this.storage.setItem(key, JSON.stringify(pending));
    }
    try {
      const result = await this.request("POST", path, pending.body);
      this.storage.removeItem(key);
      return result;
    } catch (error) {
      // Validation/conflict failures have a definite response; an edited action may start afresh.
      if (error.status >= 400 && error.status < 500)
        this.storage.removeItem(key);
      throw error;
    }
  }
  startVisit(labId, lesson) {
    return this.serial(`start:${labId}`, async () => {
      const visit = await this.receipt(
        `/labs/${encodeURIComponent(labId)}/activities`,
        { module: lesson.module || lesson.id, lesson_id: lesson.id },
      );
      this.storage.setItem(`gym-lab-run:${labId}`, visit.id);
      return visit;
    });
  }
  event(visitId, action, extra = {}) {
    return this.serial(`visit:${visitId}`, () =>
      this.receipt(
        `/lab-activities/${encodeURIComponent(visitId)}/events`,
        { action, ...extra },
        action,
      ),
    );
  }
  discuss(visitId, request) {
    return this.receipt(
      `/lab-activities/${encodeURIComponent(visitId)}/discussion`,
      request,
      request.activity_id,
    );
  }
  answer(sessionId, itemId, answer, confidence = null) {
    return this.serial(`answer:${sessionId}:${itemId}`, () =>
      this.receipt(
        `/sessions/${encodeURIComponent(sessionId)}/answers`,
        { item_id: itemId, answer, confidence },
        itemId,
      ),
    );
  }
  timer(sessionId, action, itemId) {
    return this.serial(`session:${sessionId}`, () =>
      this.request("POST", `/sessions/${encodeURIComponent(sessionId)}/timer`, {
        action,
        ...(itemId ? { item_id: itemId } : {}),
      }),
    );
  }
  aid(sessionId, itemId, kind) {
    return this.request(
      "POST",
      `/sessions/${encodeURIComponent(sessionId)}/aid`,
      { item_id: itemId, kind },
    );
  }
  finish(sessionId, blocker = null) {
    return this.serial(`session:${sessionId}`, () =>
      this.request(
        "POST",
        `/sessions/${encodeURIComponent(sessionId)}/finish`,
        { blocker },
      ),
    );
  }
  abandonPendingPractice(visitId) {
    this.storage.removeItem(`gym-lab-pending:${visitId}`);
  }
  pendingPractice(visitId) {
    const raw = this.storage.getItem(`gym-lab-pending:${visitId}`);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return { session_id: raw };
    } // The original Gym stored only the known session ID.
  }
  async startLinkedPractice(visit, spec) {
    return this.serial(`practice:${visit.id}`, async () => {
      if (visit.session_id) {
        const session = await this.session(visit.session_id);
        this.abandonPendingPractice(visit.id);
        return session;
      }
      const key = `gym-lab-pending:${visit.id}`;
      let pending = this.pendingPractice(visit.id);
      if (pending?.uncertain)
        throw new GymError(
          "The previous start may have succeeded. Choose the interrupted practice session to recover it.",
          409,
          { recovery: true },
        );
      if (!pending) {
        const before = await this.overview();
        pending = {
          uncertain: true,
          before: before.sessions.map((s) => s.id),
          spec,
        };
        this.storage.setItem(key, JSON.stringify(pending));
        try {
          const session = await this.request("POST", "/sessions", spec);
          pending = { session_id: session.id };
          this.storage.setItem(key, JSON.stringify(pending));
        } catch (error) {
          if (error.status >= 400 && error.status < 500)
            this.storage.removeItem(key);
          else
            throw new GymError(
              "The practice start was interrupted. Recover the session before trying again.",
              0,
              { recovery: true },
            );
          throw error;
        }
      }
      return this.linkPractice(visit.id, pending.session_id);
    });
  }
  async recoveryCandidates(visit) {
    const pending = this.pendingPractice(visit.id);
    const overview = await this.overview();
    return overview.sessions.filter(
      (s) =>
        s.course_id === visit.course_id &&
        s.module === visit.module &&
        (!pending?.session_id || s.id === pending.session_id) &&
        (!pending?.spec?.mode || s.mode === pending.spec.mode) &&
        s.status === "active" &&
        ["practice", "transfer"].includes(s.mode) &&
        !pending?.before?.includes(s.id) &&
        s.started_at >= visit.started_at,
    );
  }
  async linkPractice(visitId, sessionId) {
    const key = `gym-lab-pending:${visitId}`;
    this.storage.setItem(key, JSON.stringify({ session_id: sessionId }));
    try {
      await this.request(
        "POST",
        `/lab-activities/${encodeURIComponent(visitId)}/link-session`,
        { session_id: sessionId },
      );
      await this.timer(sessionId, "resume");
      this.storage.setItem("gym-session", sessionId);
      const session = await this.session(sessionId);
      this.storage.removeItem(key);
      return session;
    } catch (error) {
      await this.timer(sessionId, "pause").catch(() => {});
      throw error;
    }
  }
}
