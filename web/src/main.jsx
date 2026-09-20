import {
  workspaceStorage,
  workspaceConfig,
  workspaceClient,
  initializeWorkspace,
  initialRoute,
} from "./workspace.js";
import React, { useEffect, useState, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  BookOpen,
  Compass,
  CalendarDays,
  FlaskConical,
  Activity,
  Settings,
  Plus,
  Play,
  Pause,
  ArrowLeft,
  Check,
  ChevronRight,
  FileText,
  Upload,
  Clock3,
  Lightbulb,
  ShieldCheck,
  CircleHelp,
  X,
  Pin,
  RefreshCw,
  Search,
} from "lucide-react";
import "./style.css";
import GuidedLab from "./GuidedLab.jsx";
import Labs from "./Labs.jsx";

async function api(path, data, method) {
  const options = {
    method: method || (data === undefined ? "GET" : "POST"),
    headers: {},
  };
  const token = workspaceStorage.getItem("gym-token");
  if (token) options.headers.Authorization = `Bearer ${token}`;
  if (data instanceof FormData) options.body = data;
  else if (data !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(data);
  }
  const response = await fetch("/api" + path, options);
  if (!response.ok) {
    let body;
    try {
      body = await response.json();
    } catch {
      body = { detail: `Request failed (${response.status})` };
    }
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  return response.json();
}
function useLoad(path, refresh = 0) {
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  const reload = useCallback(
    () =>
      api(path)
        .then((x) => {
          setData(x);
          setError("");
          return x;
        })
        .catch((e) => setError(e.message)),
    [path],
  );
  useEffect(() => {
    reload();
  }, [reload, refresh]);
  return [data, reload, error];
}
const fmtDate = (s) =>
  s
    ? new Date(s).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : "No deadline";
const minutes = (s) => `${Math.round((s || 0) / 60)} min`;
const activityDuration = (s) =>
  (s || 0) < 60 ? `${Math.round(s || 0)} sec` : minutes(s);
const percent = (x) => `${Math.round(x * 100)}%`;
function Empty({ title, children }) {
  return (
    <div className="empty">
      <BookOpen size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Badge({ children, tone = "" }) {
  return <span className={"badge " + tone}>{children}</span>;
}
function ErrorBox({ message }) {
  return message ? (
    <div role="alert" className="error">
      {message}
    </div>
  ) : null;
}
function Action({
  children,
  onClick,
  className = "",
  disabled = false,
  type = "button",
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={"button " + className}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function Modal({ title, children, close }) {
  return (
    <div className="modal-shade" onClick={close}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="row between">
          <h2>{title}</h2>
          <button className="icon" aria-label="Close" onClick={close}>
            <X />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
function PageHead({ title, children, actions }) {
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {actions}
    </header>
  );
}

function TokenGate({ reload }) {
  const [token, setToken] = useState("");
  return (
    <section className="panel">
      <h2>Unlock your workspace</h2>
      <Field label="Server access token">
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
      </Field>
      <Action
        onClick={() => {
          workspaceStorage.setItem("gym-token", token);
          reload();
        }}
      >
        Unlock
      </Action>
    </section>
  );
}

function App() {
  const route = useRef(initialRoute()).current;
  const [page, setPage] = useState(route.page),
    [labId, setLabId] = useState(route.labId),
    [labFilter, setLabFilter] = useState(route.courseId || ""),
    [labEdit, setLabEdit] = useState(null),
    [courseworkAssignmentId, setCourseworkAssignmentId] = useState(
      route.assignmentId,
    ),
    [sessionId, setSessionId] = useState(
      route.sessionId || workspaceStorage.getItem("gym-session"),
    ),
    [recoveryVisit, setRecoveryVisit] = useState(null),
    [recoverySessions, setRecoverySessions] = useState(null),
    [refresh, setRefresh] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [overview, reload, loadError] = useLoad("/overview", refresh),
    [health] = useLoad("/health", refresh);
  const act = async (fn) => {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const navigate = (p, contextId, assignmentId) => {
    if (p === "labs") {
      setLabFilter(contextId || "");
      setLabEdit(null);
    }
    if (p === "lab" && contextId) setLabId(contextId);
    if (p === "session" && contextId) {
      setSessionId(contextId);
      workspaceStorage.setItem("gym-session", contextId);
    }
    if (p === "coursework") setCourseworkAssignmentId(assignmentId || null);
    setError("");
    setPage(p);
    setRefresh((x) => x + 1);
  };
  const openSession = (id) => {
    setSessionId(id);
    workspaceStorage.setItem("gym-session", id);
    setPage("session");
  };
  const start = (spec, labActivityId) =>
    act(async () => {
      let s;
      if (labActivityId) {
        const visit = await workspaceClient.visit(labActivityId);
        try {
          s = await workspaceClient.startLinkedPractice(visit, spec);
          setRecoveryVisit(null);
        } catch (error) {
          if (workspaceStorage.getItem(`gym-lab-pending:${labActivityId}`)) {
            setRecoveryVisit(visit);
            setRecoverySessions(null);
          }
          throw error;
        }
      } else s = await api("/sessions", spec);
      openSession(s.id);
      reload();
      return s;
    });
  const nav = [
    ["home", Compass, "Workbench"],
    ["labs", FlaskConical, "Labs"],
    ["create", Plus, "Sources & create"],
    ["coursework", FileText, "Coursework & rubrics"],
    ["plan", CalendarDays, "Plan my time"],
    ["research", FlaskConical, "Research & writing"],
    ["progress", Activity, "Learning evidence"],
    ["system", Settings, "System"],
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("home");
          }}
        >
          <span className="brand-mark">
            <BookOpen size={22} />
          </span>
          <span>
            Learning
            <br />
            <strong>Gym</strong>
          </span>
        </a>
        <div className="nav-label">Your learning practice</div>
        <nav>
          {nav.map(([id, Icon, title]) => (
            <button
              key={id}
              className={
                page === id || (page === "lab" && id === "labs")
                  ? "selected"
                  : ""
              }
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              {title}
            </button>
          ))}
        </nav>
        {sessionId && (
          <button className="resume" onClick={() => setPage("session")}>
            <Play size={16} />
            Open last session
          </button>
        )}
        <div className="sidebar-bottom">
          {workspaceConfig.experiences.map((x) => (
            <a key={x.id} href={`/experience/${x.id}/`}>
              Open {x.id} experience
            </a>
          ))}
          <span className="status-dot" />
          Local workspace<small>Evidence before assumptions.</small>
        </div>
      </aside>
      <div className="main-shell">
        <div className="topbar">
          <div className="breadcrumb">
            Personal learning lab <ChevronRight size={14} />
            {page === "session"
              ? "Session"
              : page === "lab"
                ? "Lab"
                : nav.find((x) => x[0] === page)?.[2]}
          </div>
          <div className="row">
            <span className="desktop-only">
              {new Date().toLocaleDateString(undefined, {
                weekday: "short",
                month: "short",
                day: "numeric",
              })}
            </span>
            <span className="avatar">You</span>
          </div>
        </div>
        <main>
          <ErrorBox message={error || loadError} />
          {recoveryVisit && (
            <section
              className="notice experience-recovery"
              aria-label="Interrupted practice"
            >
              <p>
                A practice start needs recovery. Choose the existing session
                before continuing.
              </p>
              <Action
                disabled={busy}
                onClick={() =>
                  act(async () =>
                    setRecoverySessions(
                      await workspaceClient.recoveryCandidates(recoveryVisit),
                    ),
                  )
                }
              >
                Find interrupted practice
              </Action>
              {recoverySessions?.map((s) => (
                <Action
                  key={s.id}
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await workspaceClient.linkPractice(
                        recoveryVisit.id,
                        s.id,
                      );
                      setRecoveryVisit(null);
                      openSession(s.id);
                    })
                  }
                >
                  Recover practice from{" "}
                  {new Date(s.started_at).toLocaleTimeString()}
                </Action>
              ))}
              {recoverySessions?.length === 0 && (
                <>
                  <p>
                    No matching recent session was found. Inspect recent work
                    before starting another.
                  </p>
                  <Action
                    onClick={() => {
                      workspaceClient.abandonPendingPractice(recoveryVisit.id);
                      setRecoveryVisit(null);
                    }}
                  >
                    I checked; allow a new practice start
                  </Action>
                </>
              )}
            </section>
          )}
          {!overview ? (
            loadError?.toLowerCase().includes("token") ? (
              <TokenGate reload={reload} />
            ) : (
              <div className="loading">Loading your workspace…</div>
            )
          ) : (
            <>
              {page === "home" && (
                <Home
                  overview={overview}
                  start={start}
                  navigate={navigate}
                  resume={openSession}
                  busy={busy}
                />
              )}
              {page === "labs" && (
                <Labs
                  api={api}
                  courses={overview.courses}
                  initialCourseId={labFilter}
                  navigate={navigate}
                  editLab={labEdit}
                  onEdit={setLabEdit}
                  onPublished={reload}
                />
              )}
              {page === "lab" && labId && (
                <GuidedLab
                  key={labId}
                  labId={labId}
                  initialLessonId={
                    labId === route.labId ? route.lessonId : null
                  }
                  api={api}
                  start={start}
                  navigate={navigate}
                  onEdit={(lab) => {
                    setLabEdit(lab);
                    setLabFilter(lab.course_id);
                    setPage("labs");
                  }}
                />
              )}
              {page === "session" && sessionId && (
                <Session
                  ident={sessionId}
                  act={act}
                  busy={busy}
                  done={() => navigate("progress")}
                />
              )}
              {page === "create" && (
                <CreateGym
                  overview={overview}
                  act={act}
                  busy={busy}
                  refresh={() => {
                    reload();
                    setRefresh((x) => x + 1);
                  }}
                  start={start}
                />
              )}
              {page === "coursework" && (
                <Coursework
                  overview={overview}
                  act={act}
                  busy={busy}
                  initialAssignmentId={courseworkAssignmentId}
                />
              )}
              {page === "plan" && (
                <Planner act={act} busy={busy} overview={overview} />
              )}
              {page === "research" && (
                <Research act={act} busy={busy} overview={overview} />
              )}
              {page === "progress" && <Progress act={act} start={start} />}
              {page === "system" && (
                <System
                  act={act}
                  health={health}
                  refresh={() => setRefresh((x) => x + 1)}
                />
              )}
            </>
          )}
        </main>
        <footer>
          Learning is demonstrated in your work. Estimates remain open to
          correction.
        </footer>
      </div>
    </div>
  );
}

function Home({ overview, start, navigate, resume, busy }) {
  const [courseId, setCourseId] = useState(overview.courses[0]?.id || ""),
    [module, setModule] = useState("all"),
    [mode, setMode] = useState("practice"),
    [form, setForm] = useState(""),
    [count, setCount] = useState(8),
    [library, setLibrary] = useState(null),
    [tab, setTab] = useState("guides"),
    [query, setQuery] = useState("");
  const course = overview.courses.find((c) => c.id === courseId);
  const r = overview.recommendation;
  useEffect(() => {
    setModule("all");
    setForm("");
    setLibrary(null);
  }, [courseId]);
  return (
    <>
      <PageHead
        title="Make the next hour count."
        actions={
          <Action className="secondary" onClick={() => navigate("create")}>
            <Plus size={17} />
            Create a gym
          </Action>
        }
      >
        Practice with a purpose. Leave with evidence.
      </PageHead>
      <div className="home-layout">
        <div>
          <section className="next-activity">
            <div className="row">
              <Compass size={20} />
              <span>Suggested next activity</span>
            </div>
            <h2>{r.title}</h2>
            <p>{r.rationale}</p>
            <div className="activity-meta">
              <div>
                <span>What you produce</span>
                <strong>{r.expected_output}</strong>
              </div>
              <div>
                <span>Time to allow</span>
                <strong>
                  {r.minutes[0]}–{r.minutes[1]} minutes
                </strong>
              </div>
            </div>
            <div className="row">
              <Action
                disabled={busy || !r.course_id}
                onClick={() =>
                  r.mode === "coursework"
                    ? navigate("coursework")
                    : start({
                        course_id: r.course_id,
                        mode: r.mode,
                        module: r.module,
                        count: 5,
                      })
                }
              >
                <Play size={16} />
                Start this activity
              </Action>
              <button
                className="text-button"
                onClick={() => navigate("progress")}
              >
                Inspect the evidence
              </button>
            </div>
          </section>
          <section className="section">
            <div className="section-title">
              <h2>Your gyms</h2>
              <span>{overview.courses.length} learning environments</span>
            </div>
            {!course ? (
              <Empty title="Start with your own materials">
                Create a gym, upload your course or research sources, then
                define the kind of practice you need.
              </Empty>
            ) : (
              <>
                <div className="course-tabs">
                  {overview.courses.map((c) => (
                    <button
                      key={c.id}
                      className={courseId === c.id ? "active" : ""}
                      onClick={() => setCourseId(c.id)}
                    >
                      {c.title}
                    </button>
                  ))}
                </div>
                <div className="gym-panel">
                  <div className="row between">
                    <div>
                      <h3>{course.title}</h3>
                      <p>{course.description}</p>
                    </div>
                    <BookOpen size={28} color="#537093" />
                  </div>
                  {course.imported_content && (
                    <p className="import-note">
                      Legacy demo content. Behavioral evidence starts with your
                      new sessions here.
                    </p>
                  )}
                  <div className="counts">
                    <span>
                      <strong>{course.counts.practice}</strong> practice items
                    </span>
                    <span>
                      <strong>{course.forms.length}</strong> fixed simulations
                    </span>
                    <span>
                      <strong>{course.counts.transfer}</strong> transfer items
                    </span>
                  </div>
                  {
                    <Action
                      className="secondary"
                      onClick={() => navigate("labs", course.id)}
                    >
                      <FlaskConical size={17} /> Browse labs in this gym
                    </Action>
                  }
                  <div className="segmented" aria-label="Activity mode">
                    {["practice", "simulation", "transfer"].map((m) => (
                      <button
                        className={mode === m ? "active" : ""}
                        onClick={() => setMode(m)}
                        key={m}
                      >
                        {m === "simulation"
                          ? "Mock exam"
                          : m === "transfer"
                            ? "Transfer"
                            : "Practice"}
                      </button>
                    ))}
                  </div>
                  <p className="mode-description">
                    {mode === "practice"
                      ? "Questions favor unseen material and recent mistakes. Hints are available and recorded."
                      : mode === "simulation"
                        ? "A fixed, timed form. Answer keys and feedback stay sealed until you finish."
                        : "Unfamiliar contexts and changed assumptions. Create transfer items from your sources first."}
                  </p>
                  <div className="form-row">
                    {mode === "simulation" ? (
                      <Field label="Exam form">
                        <select
                          value={form}
                          onChange={(e) => setForm(e.target.value)}
                        >
                          <option value="">Choose a form</option>
                          {course.forms.map((f) => (
                            <option key={f.id} value={f.id}>
                              {f.label} · {f.item_ids.length} items · {f.points}{" "}
                              points · {f.minutes} min
                            </option>
                          ))}
                        </select>
                      </Field>
                    ) : (
                      <>
                        <Field label="Topic">
                          <select
                            value={module}
                            onChange={(e) => setModule(e.target.value)}
                          >
                            <option value="all">All topics</option>
                            {course.modules.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.id} — {m.title}
                              </option>
                            ))}
                          </select>
                        </Field>
                        <Field label="Questions">
                          <select
                            value={count}
                            onChange={(e) => setCount(+e.target.value)}
                          >
                            {[3, 5, 8, 12, 16].map((n) => (
                              <option key={n}>{n}</option>
                            ))}
                          </select>
                        </Field>
                      </>
                    )}
                    <Action
                      disabled={busy || (mode === "simulation" && !form)}
                      onClick={() =>
                        start({
                          course_id: courseId,
                          mode,
                          module,
                          count,
                          form: form || null,
                        })
                      }
                    >
                      <Play size={16} />
                      {mode === "simulation"
                        ? "Begin simulation"
                        : "Begin practice"}
                    </Action>
                  </div>
                  <button
                    className="text-button"
                    onClick={async () =>
                      setLibrary(await api("/library/" + courseId))
                    }
                  >
                    Open study guides & glossary
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
        <aside className="context-rail">
          <h3>The learning loop</h3>
          <ol className="loop-steps">
            <li>
              <strong>Set the target</strong>
              <span>Define the capability and what good work looks like.</span>
            </li>
            <li>
              <strong>Make an attempt</strong>
              <span>Work before help. Record the assistance you use.</span>
            </li>
            <li>
              <strong>Inspect the evidence</strong>
              <span>Understand the error, not just the score.</span>
            </li>
            <li>
              <strong>Choose the next test</strong>
              <span>Revisit later and apply it somewhere new.</span>
            </li>
          </ol>
          <div className="rail-note">
            <ShieldCheck size={21} />
            <p>
              {overview.attempts === 0
                ? "No learning history yet. Imported questions are content, not evidence of your ability."
                : `${overview.attempts} attempts recorded. Your estimates reflect new work in this workspace.`}
            </p>
          </div>
          <h3>Recent sessions</h3>
          {overview.sessions.length ? (
            overview.sessions
              .slice(-4)
              .reverse()
              .map((s) => (
                <button
                  className="recent"
                  key={s.id}
                  onClick={() => resume(s.id)}
                >
                  <span>
                    {s.mode}
                    <small>{fmtDate(s.started_at)}</small>
                  </span>
                  <Badge>{s.status}</Badge>
                </button>
              ))
          ) : (
            <p className="muted">Your first session will appear here.</p>
          )}
        </aside>
      </div>
      {library && (
        <Modal title="Study library" close={() => setLibrary(null)}>
          <div className="segmented">
            <button
              className={tab === "guides" ? "active" : ""}
              onClick={() => setTab("guides")}
            >
              Study guides
            </button>
            <button
              className={tab === "terms" ? "active" : ""}
              onClick={() => setTab("terms")}
            >
              Glossary
            </button>
          </div>
          {tab === "guides" ? (
            library.guides.map((g) => (
              <details key={g.id}>
                <summary>
                  {g.code} — {g.subtitle}
                </summary>
                <article className="prose">
                  {g.blocks.map((b) => (
                    <section key={b.id}>
                      <h3>{b.h}</h3>
                      <div dangerouslySetInnerHTML={{ __html: b.html }} />
                    </section>
                  ))}
                </article>
              </details>
            ))
          ) : (
            <>
              <input
                placeholder={`Search ${library.terms.length} concepts…`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {library.terms
                .filter((t) =>
                  (t.term + " " + t.def)
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .slice(0, 60)
                .map((t) => (
                  <div className="term" key={t.id}>
                    <h3>
                      {t.term}
                      <Badge>{t.module}</Badge>
                    </h3>
                    <p>{t.def}</p>
                    <p>
                      <strong>Distinguish from:</strong> {t.distinguish}
                    </p>
                    <p>
                      <strong>Why it matters:</strong> {t.why}
                    </p>
                  </div>
                ))}
            </>
          )}
        </Modal>
      )}
    </>
  );
}

function Vignette({ value }) {
  if (!value) return null;
  return (
    <details className="vignette" open>
      <summary>{value.title || "Case context"}</summary>
      <div className="prose">
        <p className="preserve">{value.text}</p>
        {value.table && (
          <div className="table-scroll">
            <table>
              <caption>{value.table.caption}</caption>
              <thead>
                <tr>
                  {value.table.columns.map((v, i) => (
                    <th key={i}>{v}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {value.table.rows.map((r, i) => (
                  <tr key={i}>
                    {r.map((v, j) => (
                      <td key={j}>{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  );
}
function Feedback({ value, score, points }) {
  if (!value) return null;
  return (
    <div className="feedback">
      <div className="row between">
        <h3>
          {value.kind === "provisional_model_judgment"
            ? "Rubric feedback"
            : "Review the reasoning"}
        </h3>
        {score != null && (
          <Badge tone={score >= points * 0.8 ? "good" : "warm"}>
            {score} / {points}
          </Badge>
        )}
      </div>
      <p>{value.explanation || value.feedback}</p>
      {value.options?.map((o) => (
        <div className="rationale" key={o.label}>
          <strong>{o.label}</strong>
          <span>{o.why}</span>
        </div>
      ))}
      {value.prompts?.map((p) => (
        <p key={p.id}>
          <strong>{p.id}:</strong> {p.why}
        </p>
      ))}
      {value.criteria?.map((c) => (
        <div className="criterion" key={c.name}>
          <strong>
            {c.name} · {percent(c.score)}
          </strong>
          {c.evidence_quote && <blockquote>{c.evidence_quote}</blockquote>}
          <p>{c.explanation}</p>
        </div>
      ))}
      {value.next_step && (
        <p>
          <strong>Next step:</strong> {value.next_step}
        </p>
      )}
      {value.uncertainty && <p className="muted">{value.uncertainty}</p>}
      <small>
        {value.ref ||
          (value.kind === "provisional_model_judgment"
            ? "Attributed model judgment; open to correction."
            : "Answer-key feedback; report any error for review.")}
      </small>
    </div>
  );
}

function Session({ ident, act, busy, done }) {
  const [session, reload, error] = useLoad("/sessions/" + ident),
    [index, setIndex] = useState(0),
    [answerDrafts, setAnswerDrafts] = useState({}),
    [confidence, setConfidence] = useState(""),
    [aid, setAid] = useState(null),
    [report, setReport] = useState(false),
    [reason, setReason] = useState(""),
    [finishOpen, setFinishOpen] = useState(false),
    [blocker, setBlocker] = useState("");
  const item = session?.items[index],
    prior = session?.answers[item?.id],
    remaining = session?.remaining_seconds;
  useEffect(() => {
    setIndex(0);
  }, [ident]);
  const draftKey = `experience-answer:${ident}:${item?.id}`;
  let storedDraft;
  try {
    storedDraft = JSON.parse(workspaceStorage.getItem(draftKey) || "null");
  } catch {
    storedDraft = null;
  }
  const answer =
    prior?.answer ??
    answerDrafts[draftKey] ??
    storedDraft ??
    (item?.type === "matching" ? {} : "");
  const setAnswer = (value) => {
    setAnswerDrafts((current) => ({ ...current, [draftKey]: value }));
    workspaceStorage.setItem(draftKey, JSON.stringify(value));
  };
  useEffect(() => {
    setConfidence("");
    setAid(null);
  }, [item?.id, prior?.id]);
  useEffect(() => {
    if (!session || session.status !== "active" || !item) return;
    const beat = () =>
      api("/sessions/" + ident + "/timer", {
        action: document.hidden ? "pause" : "heartbeat",
        item_id: item.id,
      }).catch(() => {});
    beat();
    const timer = setInterval(beat, 10000);
    const visible = () => {
      if (document.hidden)
        api("/sessions/" + ident + "/timer", {
          action: "pause",
          item_id: item.id,
        })
          .then(reload)
          .catch(() => {});
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [ident, item?.id, session?.status]);
  useEffect(() => {
    if (session?.status !== "active" && !session?.pending_assessments) return;
    const t = setInterval(reload, 5000);
    return () => clearInterval(t);
  }, [session?.status, session?.pending_assessments, reload]);
  if (!session)
    return (
      <>
        <ErrorBox message={error} />
        <div className="loading">Opening your session…</div>
      </>
    );
  if (session.status === "finished")
    return (
      <>
        <PageHead
          title="Keep the useful part."
          actions={<Action onClick={done}>View learning evidence</Action>}
        >
          The score is an observation. The reasoning tells you what to practice
          next.
        </PageHead>
        <div className="result-band">
          <div>
            <strong>
              {session.score} <span>/ {session.max_score}</span>
            </strong>
            <p>
              Points earned{" "}
              {session.pending_assessments > 0 &&
                `· ${session.pending_assessments} assessments pending`}
            </p>
          </div>
          <div>
            <h3>{minutes(session.active_seconds)}</h3>
            <p>Active work · {session.completion}</p>
          </div>
          <div>
            <h3>{session.mode}</h3>
            <p>
              {session.mode === "simulation"
                ? "Fixed form, unaided"
                : "Assistance recorded separately"}
            </p>
          </div>
        </div>
        {session.review.map((r, i) => (
          <details key={r.item.id} className="review-item">
            <summary>
              {i + 1}. {r.item.stem.slice(0, 100)}…{" "}
              <Badge>
                {r.attempt?.score ?? "—"} / {r.item.points}
              </Badge>
            </summary>
            <p>{r.item.stem}</p>
            <p>
              <strong>Your answer:</strong>{" "}
              {typeof r.attempt?.answer === "object"
                ? JSON.stringify(r.attempt.answer)
                : r.attempt?.answer || "Unanswered"}
            </p>
            <Feedback
              value={r.attempt?.feedback || r.feedback}
              score={r.attempt?.score}
              points={r.item.points}
            />
          </details>
        ))}
      </>
    );
  const submit = () =>
    act(async () => {
      await workspaceClient.answer(
        ident,
        item.id,
        answer,
        confidence === "" ? null : +confidence,
      );
      workspaceStorage.removeItem(draftKey);
      await reload();
    });
  const requestAid = (kind) =>
    act(async () =>
      setAid(
        await api("/sessions/" + ident + "/aid", { item_id: item.id, kind }),
      ),
    );
  return (
    <>
      <div className="session-toolbar">
        <div className="row">
          <Badge>{session.mode}</Badge>
          <span>
            Question {index + 1} of {session.items.length}
          </span>
        </div>
        <div className="row">
          <Clock3 size={16} />
          {remaining != null
            ? `${Math.ceil(remaining / 60)} min remaining`
            : minutes(session.active_seconds)}
          <button
            className="icon"
            aria-label={session.running ? "Pause session" : "Resume session"}
            onClick={() =>
              act(async () => {
                await api("/sessions/" + ident + "/timer", {
                  action: session.running ? "pause" : "resume",
                  item_id: item.id,
                });
                reload();
              })
            }
          >
            {session.running ? <Pause size={17} /> : <Play size={17} />}
          </button>
          <button className="text-button" onClick={() => setFinishOpen(true)}>
            Finish session
          </button>
        </div>
      </div>
      <div className="session-progress">
        <span
          style={{
            width: `${(Object.keys(session.answers).length / session.items.length) * 100}%`,
          }}
        />
      </div>
      {!session.running && (
        <div className="notice">
          The active-work timer is paused. Resume when you are ready; a
          simulation’s time limit still runs.
        </div>
      )}
      <div className="study-layout">
        <article className="question">
          <div className="row between">
            <span className="topic-label">{item.module}</span>
            <span className="muted">{item.points} points</span>
          </div>
          <Vignette value={item.vignette} />
          <h2 className="question-stem">{item.stem}</h2>
          {item.type === "mcq" ? (
            <div className="options">
              {item.options.map((o) => (
                <label
                  key={o.label}
                  className={"option " + (answer === o.label ? "chosen" : "")}
                >
                  <input
                    type="radio"
                    name={"answer-" + item.id}
                    value={o.label}
                    checked={answer === o.label}
                    disabled={!!prior}
                    onChange={() => setAnswer(o.label)}
                  />
                  <span className="option-letter">{o.label}</span>
                  <span>{o.text}</span>
                  {answer === o.label && <Check size={18} />}
                </label>
              ))}
            </div>
          ) : item.type === "matching" ? (
            <div className="matching">
              {item.prompts.map((p) => (
                <Field key={p.id} label={p.text}>
                  <select
                    disabled={!!prior}
                    value={answer[p.id] || ""}
                    onChange={(e) =>
                      setAnswer({ ...answer, [p.id]: e.target.value })
                    }
                  >
                    <option value="">Choose a match</option>
                    {item.terms.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.text}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
            </div>
          ) : (
            <>
              <textarea
                className="open-answer"
                aria-label="Your reasoning"
                placeholder="State your claim, assumptions, evidence and the strongest objection…"
                value={answer}
                disabled={!!prior}
                onChange={(e) => setAnswer(e.target.value)}
              />
              {item.rubric && (
                <details>
                  <summary>Assessment rubric</summary>
                  {item.rubric.map((c) => (
                    <p key={c.name}>
                      <strong>
                        {c.name} ({percent(c.weight)})
                      </strong>
                      <br />
                      {c.anchors.join(" → ")}
                    </p>
                  ))}
                </details>
              )}
            </>
          )}
          {!prior ? (
            <div className="answer-actions">
              <Field label="How confident are you? (optional)">
                <select
                  value={confidence}
                  onChange={(e) => setConfidence(e.target.value)}
                >
                  <option value="">Not recorded</option>
                  <option value="0.25">25% · tentative</option>
                  <option value="0.5">50% · uncertain</option>
                  <option value="0.75">75% · fairly confident</option>
                  <option value="1">100% · certain</option>
                </select>
              </Field>
              <Action
                disabled={
                  busy ||
                  !answer ||
                  (item.type === "matching" &&
                    Object.keys(answer).length !== item.prompts.length)
                }
                onClick={submit}
              >
                {session.mode === "simulation"
                  ? "Save answer"
                  : "Check my reasoning"}
              </Action>
            </div>
          ) : (
            <>
              {session.mode === "simulation" ? (
                <div className="notice">
                  <Check size={17} />
                  Answer saved. Feedback opens when you finish.
                </div>
              ) : prior.status === "pending" ? (
                <div className="notice">
                  Independent rubric assessment is queued. Your attempt is
                  saved.
                </div>
              ) : (
                <Feedback
                  value={prior.feedback}
                  score={prior.score}
                  points={item.points}
                />
              )}
            </>
          )}
          <div className="row between question-bottom">
            <button
              className="text-button"
              disabled={index === 0}
              onClick={() => setIndex((i) => i - 1)}
            >
              <ArrowLeft size={16} />
              Previous
            </button>
            <button
              className="text-button muted"
              onClick={() => setReport(true)}
            >
              Report a problem
            </button>
            {index < session.items.length - 1 ? (
              <Action
                className="secondary"
                onClick={() => setIndex((i) => i + 1)}
              >
                Next question
                <ChevronRight size={16} />
              </Action>
            ) : (
              <Action className="secondary" onClick={() => setFinishOpen(true)}>
                Finish & review
              </Action>
            )}
          </div>
        </article>
        <aside className="context-rail">
          <h3>Your practice contract</h3>
          {session.guided_activity_id && (
            <p className="import-note">
              Guided lesson preparation is recorded for these attempts. This
              session contributes evidence of supported practice.
            </p>
          )}
          <p>
            {session.mode === "simulation"
              ? "Complete this fixed form independently. No answers or aids are shown before submission."
              : "Try first, then use help deliberately. Each aid becomes part of the evidence for this attempt."}
          </p>
          <div className="question-map">
            {session.items.map((q, i) => (
              <button
                key={q.id}
                className={
                  (i === index ? "current " : "") +
                  (session.answers[q.id] ? "answered" : "")
                }
                onClick={() => setIndex(i)}
              >
                {i + 1}
              </button>
            ))}
          </div>
          {session.mode !== "simulation" && (
            <>
              <h3>When you need a hand</h3>
              <div className="aid-buttons">
                <button onClick={() => requestAid("hint")}>
                  <Lightbulb size={17} />A thinking hint
                </button>
                <button onClick={() => requestAid("plain")}>
                  <FileText size={17} />
                  Plain English
                </button>
                <button onClick={() => requestAid("terms")}>
                  <BookOpen size={17} />
                  Key terms
                </button>
              </div>
              {aid && (
                <div className="aid-content">
                  {aid.kind === "terms" ? (
                    aid.content.length ? (
                      aid.content.map((t) => (
                        <p key={t.id}>
                          <strong>{t.term}</strong>
                          <br />
                          {t.def}
                        </p>
                      ))
                    ) : (
                      <p>No glossary terms are attached to this item.</p>
                    )
                  ) : typeof aid.content === "object" ? (
                    <>
                      <p>{aid.content.stem}</p>
                      {aid.content.options &&
                        Object.entries(aid.content.options).map(([k, v]) => (
                          <p key={k}>
                            <strong>{k}.</strong> {v}
                          </p>
                        ))}
                    </>
                  ) : (
                    <p>{aid.content}</p>
                  )}
                </div>
              )}
            </>
          )}
          <div className="rail-note">
            <ShieldCheck size={20} />
            <p>
              Answer keys live on the server. Independent work and supported
              work remain distinguishable.
            </p>
          </div>
        </aside>
      </div>
      {report && (
        <Modal title="Report an item problem" close={() => setReport(false)}>
          <p>
            This quarantines the item and flags any evaluations that depend on
            it.
          </p>
          <textarea
            aria-label="Problem description"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="What is incorrect, ambiguous or unsupported?"
          />
          <Action
            disabled={busy || reason.length < 5}
            onClick={() =>
              act(async () => {
                await api("/items/" + item.id + "/report", { reason });
                setReport(false);
                setIndex(Math.min(index + 1, session.items.length - 1));
              })
            }
          >
            Quarantine item
          </Action>
        </Modal>
      )}
      {finishOpen && (
        <Modal title="Finish this session" close={() => setFinishOpen(false)}>
          <p>
            {Object.keys(session.answers).length} of {session.items.length}{" "}
            answers submitted. Unanswered work stays marked as unfinished.
          </p>
          <Field label="Anything that blocked you? (optional)">
            <select
              value={blocker}
              onChange={(e) => setBlocker(e.target.value)}
            >
              <option value="">Nothing to add</option>
              {[
                "Time ran out",
                "Unclear next step",
                "Conceptual difficulty",
                "Interruption",
                "Priority changed",
              ].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </Field>
          <Action
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api("/sessions/" + ident + "/finish", {
                  blocker: blocker || null,
                });
                setFinishOpen(false);
                reload();
              })
            }
          >
            Finish & review
          </Action>
        </Modal>
      )}
    </>
  );
}

function CreateGym({ overview, act, busy, refresh, start }) {
  const [courseId, setCourseId] = useState(overview.courses[0]?.id || ""),
    [sources, loadSources, sourceError] = useLoad("/sources"),
    [generations, loadGenerations] = useLoad("/generations"),
    [coursework, loadCoursework] = useLoad("/coursework");
  const [newCourse, setNewCourse] = useState(false),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState(""),
    [role, setRole] = useState("instruction"),
    [selected, setSelected] = useState([]),
    [preview, setPreview] = useState(null),
    [topic, setTopic] = useState(""),
    [count, setCount] = useState(4),
    [duration, setDuration] = useState(30),
    [sharedCase, setSharedCase] = useState(0),
    [mix, setMix] = useState({}),
    [mode, setMode] = useState("practice"),
    [types, setTypes] = useState(["mcq"]),
    [instructions, setInstructions] = useState(""),
    [profileId, setProfileId] = useState(""),
    [rubricId, setRubricId] = useState(""),
    [profileEdit, setProfileEdit] = useState(null);
  const courseSources =
    sources?.filter((s) => s.course_id === courseId && s.latest) || [];
  const selectedSources = courseSources.filter((s) => selected.includes(s.id));
  const instructionIds = selectedSources
    .filter((s) =>
      ["instruction", "research"].includes(s.role || "instruction"),
    )
    .map((s) => s.id);
  const assessmentIds = selectedSources
    .filter((s) => ["assessment", "rubric"].includes(s.role))
    .map((s) => s.id);
  useEffect(() => {
    setSelected([]);
    setProfileId("");
    setRubricId("");
  }, [courseId]);
  useEffect(() => {
    if (
      !generations?.some((g) =>
        ["queued", "generating", "retrying"].includes(g.status),
      ) &&
      !coursework?.assessment_profile.some((p) => p.status === "queued")
    )
      return;
    const t = setInterval(() => {
      loadGenerations();
      loadCoursework();
      refresh();
    }, 6000);
    return () => clearInterval(t);
  }, [generations, coursework]);
  const upload = (e) => {
    const files = Array.from(e.target.files);
    act(async () => {
      for (const file of files) {
        const f = new FormData();
        f.append("course_id", courseId);
        f.append("role", role);
        f.append("file", file);
        await api("/sources", f);
      }
      await loadSources();
      e.target.value = "";
    });
  };
  const toggle = (id) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id],
    );
  return (
    <>
      <PageHead
        title="Build practice from real material."
        actions={
          <Action className="secondary" onClick={() => setNewCourse(true)}>
            <Plus size={17} />
            New gym
          </Action>
        }
      >
        Teach the gym what to cover and what your course expects you to do.
      </PageHead>
      <ErrorBox message={sourceError} />
      <div className="creation-steps">
        <div>
          <span>1</span>
          <strong>Add material</strong>
          <small>Sources and assessment examples</small>
        </div>
        <div>
          <span>2</span>
          <strong>Define the target</strong>
          <small>Profile, rubric and practice format</small>
        </div>
        <div>
          <span>3</span>
          <strong>Generate & verify</strong>
          <small>Source-grounded, reviewable items</small>
        </div>
      </div>
      <Field label="Learning environment">
        <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">Choose a gym</option>
          {overview.courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>
      </Field>
      <div className="two-column">
        <section className="panel">
          <h2>Material library</h2>
          <p>
            Lectures supply content. Real assignments and quizzes supply the
            assessment profile.
          </p>
          <Field label="What are you uploading?">
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="instruction">
                Instruction: lectures, slides, readings
              </option>
              <option value="assessment">
                Assessment: homework, quiz, worksheet, lab
              </option>
              <option value="rubric">
                Official rubric or grading instructions
              </option>
              <option value="research">Research paper or notes</option>
              <option value="submission">
                Your submission or graded feedback
              </option>
            </select>
          </Field>
          <label className={"upload-area " + (!courseId ? "disabled" : "")}>
            <Upload size={23} />
            <strong>Choose files to upload</strong>
            <span>PDF, DOCX, PPTX, Markdown, text, CSV, notebooks</span>
            <input
              type="file"
              multiple
              disabled={!courseId || busy}
              onChange={upload}
            />
          </label>
          <div className="source-list">
            {courseSources.length ? (
              courseSources.map((s) => (
                <div className="source-row" key={s.id}>
                  <input
                    aria-label={"Select " + s.name}
                    type="checkbox"
                    checked={selected.includes(s.id)}
                    onChange={() => toggle(s.id)}
                  />
                  <button
                    className="source-name"
                    onClick={() =>
                      act(async () =>
                        setPreview({
                          source: s,
                          fragments: await api(
                            "/sources/" + s.id + "/fragments",
                          ),
                        }),
                      )
                    }
                  >
                    <strong>{s.name}</strong>
                    <span>
                      {s.role || "instruction"} · v{s.version} ·{" "}
                      {s.fragment_count} fragments
                    </span>
                  </button>
                  <Badge
                    tone={s.reconstruction_status === "confirmed" ? "good" : ""}
                  >
                    {s.reconstruction_status === "confirmed"
                      ? "Reviewed"
                      : "Review"}
                  </Badge>
                </div>
              ))
            ) : (
              <Empty title="Add your first source">
                Keep the original files and review the extracted text before
                deriving a profile.
              </Empty>
            )}
          </div>
          {assessmentIds.length > 0 && (
            <div className="notice stack">
              <strong>
                {assessmentIds.length} assessment sources selected
              </strong>
              <p>
                Review each extraction, then infer an archetype. The profile
                carries form and reasoning demands into new practice.
              </p>
              <Action
                disabled={
                  busy ||
                  selectedSources
                    .filter((s) => assessmentIds.includes(s.id))
                    .some((s) => s.reconstruction_status !== "confirmed")
                }
                onClick={() =>
                  act(async () => {
                    await api("/profiles", {
                      course_id: courseId,
                      source_ids: assessmentIds,
                    });
                    loadCoursework();
                  })
                }
              >
                Infer assessment profile
              </Action>
            </div>
          )}
        </section>
        <section className="panel">
          <h2>Practice blueprint</h2>
          <p>
            Use {instructionIds.length} selected instructional source
            {instructionIds.length === 1 ? "" : "s"} to create fresh material.
          </p>
          <Field label="Topic or capability to practice">
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Defend a causal identification strategy"
            />
          </Field>
          <div className="form-row">
            <Field label="Mode">
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="practice">Practice with feedback</option>
                <option value="simulation">Fixed simulation</option>
                <option value="transfer">Unfamiliar transfer tasks</option>
              </select>
            </Field>
            <Field label="Items">
              <input
                type="number"
                min="1"
                max="40"
                value={count}
                onChange={(e) => setCount(+e.target.value)}
              />
            </Field>
          </div>
          <fieldset>
            <legend>Question or task formats</legend>
            <div className="check-grid">
              {[
                ["mcq", "Multiple choice"],
                ["matching", "Matching"],
                ["open", "Open response"],
                ["case", "Case analysis"],
                ["counterfactual", "Counterfactual"],
                ["coding", "Coding task"],
              ].map(([id, name]) => (
                <label key={id}>
                  <input
                    type="checkbox"
                    checked={types.includes(id)}
                    onChange={() =>
                      setTypes((s) =>
                        s.includes(id) ? s.filter((x) => x !== id) : [...s, id],
                      )
                    }
                  />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>
          <Field label="Items using one shared case (0 for none)">
            <input
              type="number"
              min="0"
              max={count}
              value={sharedCase}
              onChange={(e) => setSharedCase(+e.target.value)}
            />
          </Field>
          <Field label="Session duration (minutes)">
            <input
              type="number"
              min="5"
              max="180"
              value={duration}
              onChange={(e) => setDuration(+e.target.value)}
            />
          </Field>
          <details>
            <summary>Exact format mix (optional)</summary>
            <p>
              Leave every count blank for an even mix. Otherwise, counts must
              add up to the total items.
            </p>
            {types.map((type) => (
              <Field key={type} label={type + " count"}>
                <input
                  type="number"
                  min="0"
                  max="40"
                  value={mix[type] ?? ""}
                  onChange={(e) => setMix({ ...mix, [type]: e.target.value })}
                />
              </Field>
            ))}
          </details>
          <Field label="Assessment profile (optional)">
            <select
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
            >
              <option value="">Use this blueprint directly</option>
              {coursework?.assessment_profile
                .filter(
                  (p) => p.course_id === courseId && p.status === "confirmed",
                )
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.profile.title}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Required rubric for open tasks (optional)">
            <select
              value={rubricId}
              onChange={(e) => setRubricId(e.target.value)}
            >
              <option value="">Propose an explicit task rubric</option>
              {coursework?.rubric
                .filter((r) => !r.course_id || r.course_id === courseId)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title} · v{r.version}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Assessment instructions or constraints">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="State time limits, permitted tools, scoring rules, expected reasoning and difficulty."
            />
          </Field>
          <Action
            disabled={
              busy ||
              !instructionIds.length ||
              topic.length < 2 ||
              !types.length ||
              count < types.length
            }
            onClick={() =>
              act(async () => {
                await api("/generations", {
                  course_id: courseId,
                  source_ids: instructionIds,
                  topic,
                  count,
                  mode,
                  question_types: types,
                  minutes: duration,
                  shared_case_items: sharedCase,
                  type_counts: types.some(
                    (t) => mix[t] !== undefined && mix[t] !== "",
                  )
                    ? Object.fromEntries(
                        types.map((t) => [t, Number(mix[t] || 0)]),
                      )
                    : null,
                  instructions,
                  profile_id: profileId || null,
                  rubric_id: rubricId || null,
                });
                loadGenerations();
              })
            }
          >
            <FlaskConical size={17} />
            Generate & verify
          </Action>
          <p className="small muted">
            Selected source excerpts go to your configured design and
            verification models. Original files remain in this workspace.
          </p>
        </section>
      </div>
      <section className="section">
        <h2>Assessment profiles</h2>
        {coursework?.assessment_profile
          .filter((p) => p.course_id === courseId)
          .map((p) => (
            <div className="list-row" key={p.id}>
              <div>
                <strong>
                  {p.profile?.title || "Inferring an assessment archetype…"}
                </strong>
                <p>
                  {p.profile?.difficulty_anchor ||
                    "The background worker will save a reviewable proposal."}
                </p>
              </div>
              <Badge>{p.status}</Badge>
              {p.profile && (
                <Action className="secondary" onClick={() => setProfileEdit(p)}>
                  Review & edit
                </Action>
              )}
            </div>
          ))}
        {!coursework?.assessment_profile.length && (
          <p className="muted">
            A profile can describe an essay, a lab, a problem set or an exam.
            Multiple-choice rules are only one archetype.
          </p>
        )}
      </section>
      <section className="section">
        <div className="section-title">
          <h2>Generation runs</h2>
          <button className="text-button" onClick={loadGenerations}>
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
        {generations
          ?.filter((g) => g.course_id === courseId)
          .reverse()
          .map((g) => (
            <div className="list-row" key={g.id}>
              <div>
                <strong>{g.topic}</strong>
                <p>
                  {g.count} {g.mode} tasks · {g.question_types.join(", ")}
                  {g.error && <span className="error-text"> · {g.error}</span>}
                </p>
                {g.quarantined_count > 0 && (
                  <small>
                    {g.quarantined_count} items quarantined. The remaining
                    verified practice items are available.
                  </small>
                )}
              </div>
              <Badge
                tone={
                  g.status === "ready"
                    ? "good"
                    : g.status === "failed"
                      ? "warm"
                      : ""
                }
              >
                {g.status.replaceAll("_", " ")}
              </Badge>
              {["ready", "review_required"].includes(g.status) && (
                <Action
                  className="secondary"
                  onClick={() =>
                    start({
                      course_id: courseId,
                      mode: g.mode,
                      module: g.topic,
                      count: g.count,
                      form: g.mode === "simulation" ? g.id : null,
                    })
                  }
                >
                  Practice
                </Action>
              )}
            </div>
          ))}
      </section>
      {newCourse && (
        <Modal title="Create a learning gym" close={() => setNewCourse(false)}>
          <Field label="Name">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Causal understanding"
            />
          </Field>
          <Field label="What do you want to become capable of?">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Field>
          <Action
            disabled={busy || title.length < 2}
            onClick={() =>
              act(async () => {
                const c = await api("/courses", { title, description });
                setCourseId(c.id);
                setNewCourse(false);
                refresh();
              })
            }
          >
            Create gym
          </Action>
        </Modal>
      )}
      {preview && (
        <Modal title={preview.source.name} close={() => setPreview(null)}>
          <p>
            Review the faithful extraction. Confirm only after checking missing
            equations, diagrams, tables and instructions.
          </p>
          {preview.source.quality_flags?.map((x, i) => (
            <div className="notice" key={i}>
              {x}
            </div>
          ))}
          <div className="source-preview">
            {preview.fragments.map((f) => (
              <section key={f.id}>
                <Badge>{f.anchor}</Badge>
                <textarea
                  aria-label={"Reconstruction: " + f.anchor}
                  rows={Math.min(18, Math.max(4, f.text.split("\n").length))}
                  value={f.text}
                  onChange={(e) =>
                    setPreview({
                      ...preview,
                      changed: true,
                      fragments: preview.fragments.map((x) =>
                        x.id === f.id ? { ...x, text: e.target.value } : x,
                      ),
                    })
                  }
                />
              </section>
            ))}
          </div>
          <Action
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api(
                  "/sources/" +
                    preview.source.id +
                    (preview.changed ? "/correction" : "/confirm"),
                  {
                    expected_revision: preview.source.revision,
                    ...(preview.changed
                      ? {
                          fragments: preview.fragments.map(
                            ({ anchor, text }) => ({ anchor, text }),
                          ),
                        }
                      : {}),
                  },
                );
                setPreview(null);
                loadSources();
              })
            }
          >
            {preview.changed
              ? "Save corrected reconstruction"
              : "Confirm reconstruction"}
          </Action>
          {preview.source.role === "rubric" &&
            preview.source.reconstruction_status === "confirmed" &&
            !preview.changed && (
              <Action
                className="secondary"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api("/sources/" + preview.source.id + "/rubric", {});
                    setPreview(null);
                    loadCoursework();
                  })
                }
              >
                Extract editable rubric
              </Action>
            )}
        </Modal>
      )}
      {profileEdit && (
        <Modal
          title="Edit the assessment archetype"
          close={() => setProfileEdit(null)}
        >
          <p>
            Keep reusable form and reasoning demands. Remove any source question
            content before confirming.
          </p>
          {Object.entries(profileEdit.profile)
            .filter(([k]) => k !== "supporting_fragment_ids")
            .map(([k, v]) => (
              <Field key={k} label={k.replaceAll("_", " ")}>
                <textarea
                  value={
                    Array.isArray(v)
                      ? v.join("\n")
                      : typeof v === "object"
                        ? JSON.stringify(v)
                        : v
                  }
                  onChange={(e) =>
                    setProfileEdit({
                      ...profileEdit,
                      profile: {
                        ...profileEdit.profile,
                        [k]: Array.isArray(v)
                          ? e.target.value.split("\n")
                          : e.target.value,
                      },
                    })
                  }
                />
              </Field>
            ))}
          <Action
            onClick={() =>
              act(async () => {
                await api(
                  "/profiles/" + profileEdit.id,
                  {
                    profile: profileEdit.profile,
                    expected_revision: profileEdit.revision,
                  },
                  "PUT",
                );
                setProfileEdit(null);
                loadCoursework();
              })
            }
          >
            Confirm this profile
          </Action>
        </Modal>
      )}
    </>
  );
}

const initialCriteria = [
  {
    name: "Reasoning and method",
    weight: 0.4,
    anchors: [
      "Method is missing or inappropriate",
      "Method is justified and correctly applied",
    ],
  },
  {
    name: "Evidence and execution",
    weight: 0.4,
    anchors: [
      "Evidence is absent or incorrect",
      "Evidence is accurate, traceable and sufficient",
    ],
  },
  {
    name: "Interpretation and limitations",
    weight: 0.2,
    anchors: [
      "Conclusion exceeds the evidence",
      "Conclusion follows and limitations are explicit",
    ],
  },
];
function RubricEditor({ value, onSave, close, busy, courses }) {
  const [rubric, setRubric] = useState(
    value || {
      title: "",
      criteria: initialCriteria,
      authority: "learner",
      course_id: null,
      permitted_assistance: "Follow the course policy",
      capabilities: [],
    },
  );
  const set = (k, v) => setRubric({ ...rubric, [k]: v });
  const total = rubric.criteria.reduce((s, c) => s + (+c.weight || 0), 0);
  return (
    <Modal title={value ? "Revise rubric" : "Create a rubric"} close={close}>
      <Field label="Rubric name">
        <input
          value={rubric.title}
          onChange={(e) => set("title", e.target.value)}
        />
      </Field>
      <div className="form-row">
        <Field label="Shared scope">
          <select
            value={rubric.course_id || ""}
            onChange={(e) => set("course_id", e.target.value || null)}
          >
            <option value="">All learning environments</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Rubric authority">
          <select
            value={rubric.authority}
            onChange={(e) => set("authority", e.target.value)}
          >
            <option value="learner">My own rubric</option>
            <option value="instructor">Instructor's rubric</option>
            <option value="proposed">Unconfirmed proposal</option>
          </select>
        </Field>
      </div>
      <Field label="Permitted assistance">
        <input
          value={rubric.permitted_assistance}
          onChange={(e) => set("permitted_assistance", e.target.value)}
        />
      </Field>
      <Field label="Capabilities (comma-separated)">
        <input
          value={rubric.capabilities.join(", ")}
          onChange={(e) =>
            set(
              "capabilities",
              e.target.value
                .split(",")
                .map((x) => x.trim())
                .filter(Boolean),
            )
          }
        />
      </Field>
      {rubric.criteria.map((c, i) => (
        <div className="rubric-edit" key={i}>
          <div className="form-row">
            <Field label="Criterion">
              <input
                value={c.name}
                onChange={(e) =>
                  set(
                    "criteria",
                    rubric.criteria.map((x, j) =>
                      j === i ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
            </Field>
            <Field label="Weight (%)">
              <input
                type="number"
                min="1"
                max="100"
                value={Math.round(c.weight * 100)}
                onChange={(e) =>
                  set(
                    "criteria",
                    rubric.criteria.map((x, j) =>
                      j === i ? { ...x, weight: +e.target.value / 100 } : x,
                    ),
                  )
                }
              />
            </Field>
            <button
              className="icon"
              aria-label="Remove criterion"
              onClick={() =>
                set(
                  "criteria",
                  rubric.criteria.filter((_, j) => j !== i),
                )
              }
            >
              <X size={16} />
            </button>
          </div>
          <Field label="Score anchors, from weak to strong (one per line)">
            <textarea
              value={c.anchors.join("\n")}
              onChange={(e) =>
                set(
                  "criteria",
                  rubric.criteria.map((x, j) =>
                    j === i ? { ...x, anchors: e.target.value.split("\n") } : x,
                  ),
                )
              }
            />
          </Field>
        </div>
      ))}
      <div className="row between">
        <button
          className="text-button"
          onClick={() =>
            set("criteria", [
              ...rubric.criteria,
              { name: "", weight: 0.1, anchors: ["", ""] },
            ])
          }
        >
          <Plus size={16} />
          Add criterion
        </button>
        <Badge tone={Math.abs(total - 1) < 0.001 ? "good" : "warm"}>
          Total: {Math.round(total * 100)}%
        </Badge>
      </div>
      <p className="muted">
        Saving creates a new version. Historical submissions retain the exact
        rubric they used. Assignments that follow this shared rubric use the
        revision for future work.
      </p>
      <Action
        disabled={busy || Math.abs(total - 1) > 0.001 || !rubric.title}
        onClick={() => onSave(rubric)}
      >
        Save rubric version
      </Action>
    </Modal>
  );
}

function Coursework({ overview, act, busy, initialAssignmentId }) {
  const [data, reload, error] = useLoad("/coursework"),
    [sources] = useLoad("/sources"),
    [rubricEdit, setRubricEdit] = useState(undefined),
    [newAssignment, setNewAssignment] = useState(false),
    [active, setActive] = useState(initialAssignmentId || null);
  const [draft, setDraft] = useState({
    title: "",
    course_id: overview.courses[0]?.id || "",
    kind: "homework",
    prompt: "",
    rubric_id: "",
    source_ids: [],
    follow_shared_rubric: false,
    deadline: null,
    points: 100,
    individual: true,
    effort_minutes: 60,
  });
  const set = (k, v) => setDraft({ ...draft, [k]: v });
  if (active && data && data.assignment.some((x) => x.id === active)) {
    const a = data.assignment.find((x) => x.id === active);
    return (
      <AssignmentWorkbench
        assignment={a}
        data={data}
        reload={reload}
        act={act}
        busy={busy}
        back={() => setActive(null)}
      />
    );
  }
  return (
    <>
      <PageHead
        title="Do the real work here."
        actions={
          <div className="row">
            <Action className="secondary" onClick={() => setRubricEdit(null)}>
              Create rubric
            </Action>
            <Action onClick={() => setNewAssignment(true)}>
              <Plus size={17} />
              Add coursework
            </Action>
          </div>
        }
      >
        Assignments, practice quizzes, worksheets and labs share the same
        evidence trail.
      </PageHead>
      <ErrorBox message={error} />
      <section className="section">
        <h2>Coursework</h2>
        {data?.assignment.length ? (
          data.assignment.map((a) => (
            <button
              className="assignment-row"
              key={a.id}
              onClick={() => setActive(a.id)}
            >
              <FileText size={24} />
              <div>
                <h3>{a.title}</h3>
                <p>
                  {a.kind.replace("_", " ")} · {a.points} points ·{" "}
                  {fmtDate(a.deadline)}
                </p>
              </div>
              <Badge>
                {data.submission.filter((s) => s.assignment_id === a.id).length}{" "}
                submissions
              </Badge>
              <ChevronRight size={19} />
            </button>
          ))
        ) : (
          <Empty title="Bring an assignment into the loop">
            Upload its instructions and rubric, work on a draft, save
            submissions, then add the actual feedback or grade.
          </Empty>
        )}
      </section>
      <section className="section">
        <h2>Reusable rubrics</h2>
        <p className="muted">
          Use one rubric across related assignments, or give a task its own
          rubric. Official criteria remain yours to edit.
        </p>
        {data?.rubric.map((r) => (
          <div className="list-row" key={r.id}>
            <div>
              <strong>{r.title}</strong>
              <p>{r.criteria.map((c) => c.name).join(" · ")}</p>
            </div>
            <Badge>
              {r.authority} · v{r.version}
            </Badge>
            <Action className="secondary" onClick={() => setRubricEdit(r)}>
              Edit rubric
            </Action>
          </div>
        ))}
      </section>
      {rubricEdit !== undefined && (
        <RubricEditor
          value={rubricEdit}
          close={() => setRubricEdit(undefined)}
          busy={busy}
          courses={overview.courses}
          onSave={(r) =>
            act(async () => {
              const payload = {
                title: r.title,
                criteria: r.criteria,
                course_id: r.course_id,
                source_id: r.source_id || null,
                authority: r.authority,
                permitted_assistance: r.permitted_assistance,
                capabilities: r.capabilities,
                ...(r.id ? { expected_revision: r.revision } : {}),
              };
              await api(
                "/rubrics" + (r.id ? "/" + r.id : ""),
                payload,
                r.id ? "PUT" : "POST",
              );
              setRubricEdit(undefined);
              reload();
            })
          }
        />
      )}
      {newAssignment && (
        <Modal title="Add coursework" close={() => setNewAssignment(false)}>
          <Field label="Title">
            <input
              value={draft.title}
              onChange={(e) => set("title", e.target.value)}
            />
          </Field>
          <div className="form-row">
            <Field label="Gym">
              <select
                value={draft.course_id}
                onChange={(e) => set("course_id", e.target.value)}
              >
                {overview.courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Assignment type">
              <select
                value={draft.kind}
                onChange={(e) => set("kind", e.target.value)}
              >
                {[
                  "homework",
                  "practice_quiz",
                  "worksheet",
                  "lab",
                  "essay",
                  "coding",
                  "project",
                ].map((x) => (
                  <option value={x} key={x}>
                    {x.replace("_", " ")}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Assignment prompt or instructions">
            <textarea
              rows={7}
              value={draft.prompt}
              onChange={(e) => set("prompt", e.target.value)}
            />
          </Field>
          <Field label="Attach existing source instructions">
            <select
              multiple
              value={draft.source_ids}
              onChange={(e) =>
                set(
                  "source_ids",
                  Array.from(e.target.selectedOptions, (o) => o.value),
                )
              }
            >
              {sources
                ?.filter((s) => s.course_id === draft.course_id && s.latest)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </Field>
          {draft.source_ids.length > 0 && (
            <Action
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const blocks = await Promise.all(
                    draft.source_ids.map((id) =>
                      api("/sources/" + id + "/fragments"),
                    ),
                  );
                  set(
                    "prompt",
                    blocks
                      .flat()
                      .map((f) => f.anchor + "\n" + f.text)
                      .join("\n\n")
                      .slice(0, 30000),
                  );
                })
              }
            >
              Use selected source instructions
            </Action>
          )}
          <Field label="Rubric">
            <select
              value={draft.rubric_id}
              onChange={(e) => set("rubric_id", e.target.value)}
            >
              <option value="">Select a rubric</option>
              {data?.rubric
                .filter((r) => !r.course_id || r.course_id === draft.course_id)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title} · v{r.version}
                  </option>
                ))}
            </select>
          </Field>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={draft.follow_shared_rubric}
              onChange={(e) => set("follow_shared_rubric", e.target.checked)}
            />
            Follow future revisions of this shared rubric
          </label>
          <div className="form-row">
            <Field label="Due date (optional)">
              <input
                type="datetime-local"
                onChange={(e) =>
                  set(
                    "deadline",
                    e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null,
                  )
                }
              />
            </Field>
            <Field label="Points">
              <input
                type="number"
                value={draft.points}
                onChange={(e) => set("points", +e.target.value)}
              />
            </Field>
            <Field label="Initial effort (min)">
              <input
                type="number"
                value={draft.effort_minutes}
                onChange={(e) => set("effort_minutes", +e.target.value)}
              />
            </Field>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={draft.individual}
              onChange={(e) => set("individual", e.target.checked)}
            />
            Individual work (a team grade is not individual capability evidence)
          </label>
          <Action
            disabled={busy || !draft.rubric_id || draft.prompt.length < 10}
            onClick={() =>
              act(async () => {
                const a = await api("/assignments", draft);
                await reload();
                setNewAssignment(false);
                setActive(a.id);
              })
            }
          >
            Create assignment
          </Action>
        </Modal>
      )}
    </>
  );
}

function AssignmentWorkbench({ assignment: a, data, reload, act, busy, back }) {
  const saved = data.assignment_draft.find((d) => d.id === a.id),
    [body, setBody] = useState(saved?.body || ""),
    [running, setRunning] = useState(false),
    [ai, setAi] = useState(saved?.assistance?.at(-1) || "none"),
    [attached, setAttached] = useState(saved?.file_source_ids || []),
    [grade, setGrade] = useState(null),
    [score, setScore] = useState(""),
    [feedback, setFeedback] = useState(""),
    [saveLabel, setSaveLabel] = useState(
      saved ? "Draft saved" : "Not saved yet",
    );
  const last = useRef(Date.now()),
    bodyRef = useRef(body),
    attachedRef = useRef(attached),
    saving = useRef(Promise.resolve());
  bodyRef.current = body;
  attachedRef.current = attached;
  const rubric = data.rubric_version.find((r) => r.id === a.rubric_version_id);
  const submissions = data.submission.filter((s) => s.assignment_id === a.id);
  const save = (event) => {
    const operation = saving.current
      .catch(() => {})
      .then(async () => {
        const elapsed =
          running && !document.hidden
            ? Math.min(45, (Date.now() - last.current) / 1000)
            : 0;
        last.current = Date.now();
        await api("/assignments/" + a.id + "/draft", {
          body: bodyRef.current,
          file_source_ids: attachedRef.current,
          active_seconds_delta: elapsed,
          assistance: ai === "none" ? [] : [ai],
          event,
        });
        setSaveLabel(
          "Saved " +
            new Date().toLocaleTimeString([], {
              hour: "numeric",
              minute: "2-digit",
            }),
        );
      });
    saving.current = operation;
    return operation;
  };
  useEffect(() => {
    const timer = setInterval(
      () => save().catch(() => setSaveLabel("Save failed — use Save draft")),
      15000,
    );
    return () => clearInterval(timer);
  }, [running, ai]);
  return (
    <>
      <button
        className="text-button"
        onClick={() =>
          act(async () => {
            await save("save");
            back();
          })
        }
      >
        <ArrowLeft size={16} />
        All coursework
      </button>
      <PageHead
        title={a.title}
        actions={
          <Badge>
            {a.kind.replace("_", " ")} · {a.points} points
          </Badge>
        }
      >
        {fmtDate(a.deadline)} · Work is saved locally; you control submission to
        your institution.
      </PageHead>
      <div className="study-layout">
        <section>
          <details className="vignette" open>
            <summary>Assignment instructions</summary>
            <p className="preserve">{a.prompt}</p>
          </details>
          <div className="editor-toolbar">
            <span>{saveLabel}</span>
            <button
              className="text-button"
              onClick={() =>
                act(async () => {
                  await save(running ? "pause" : "start");
                  last.current = Date.now();
                  setRunning(!running);
                })
              }
            >
              {running ? <Pause size={16} /> : <Play size={16} />}{" "}
              {running ? "Pause work timer" : "Start work timer"}
            </button>
          </div>
          <textarea
            className="assignment-editor"
            aria-label="Assignment draft"
            placeholder="Develop your answer, derivation, code or analysis here…"
            value={body}
            onChange={(e) => {
              setBody(e.target.value);
              setSaveLabel("Unsaved changes");
            }}
          />
          <div className="form-row">
            <Field label="AI contribution to this version">
              <select value={ai} onChange={(e) => setAi(e.target.value)}>
                <option value="none">No AI contribution</option>
                <option value="hints">Hints or conceptual coaching</option>
                <option value="editing">Editing or language assistance</option>
                <option value="substantive">
                  Substantive generated content or code
                </option>
              </select>
            </Field>
            <label className="button secondary">
              <Upload size={16} />
              Attach file
              <input
                hidden
                type="file"
                onChange={(e) =>
                  act(async () => {
                    const f = new FormData();
                    f.append("course_id", a.course_id);
                    f.append("role", "submission");
                    f.append("file", e.target.files[0]);
                    const result = await api("/sources", f);
                    setAttached([...attached, result.id]);
                  })
                }
              />
            </label>
          </div>
          {attached.length > 0 && (
            <p>{attached.length} file(s) attached to the next submission.</p>
          )}
          <div className="row">
            <Action
              className="secondary"
              onClick={() => act(() => save("save"))}
            >
              Save draft
            </Action>
            <Action
              disabled={busy || (body.length < 10 && !attached.length)}
              onClick={() =>
                act(async () => {
                  await save("save");
                  await api("/assignments/" + a.id + "/submit", {
                    idempotency_key: crypto.randomUUID(),
                    ai_contribution: ai,
                    file_source_ids: attached,
                  });
                  setRunning(false);
                  await reload();
                })
              }
            >
              Record submission version
            </Action>
          </div>
          <section className="section">
            <h2>Submissions & feedback</h2>
            {submissions
              .slice()
              .reverse()
              .map((s, i) => (
                <div className="submission" key={s.id}>
                  <div className="row between">
                    <h3>Version {submissions.length - i}</h3>
                    <span>{fmtDate(s.created_at)}</span>
                  </div>
                  <p>
                    {minutes(s.active_seconds)} active work · AI:{" "}
                    {s.ai_contribution} · rubric {s.rubric_snapshot.title} v
                    {s.rubric_snapshot.version}
                  </p>
                  <details>
                    <summary>Read this submission</summary>
                    <p className="preserve">{s.body}</p>
                    {s.attachment_snapshots?.map((f) => (
                      <section key={f.source_id}>
                        <h4>{f.name}</h4>
                        {f.quality_flags.map((flag, i) => (
                          <p key={i}>{flag}</p>
                        ))}
                        <pre className="preserve">{f.text}</pre>
                      </section>
                    ))}
                  </details>
                  <div className="row">
                    <Action
                      className="secondary"
                      onClick={() =>
                        act(async () => {
                          await api("/submissions/" + s.id + "/assess", {});
                          setSaveLabel(
                            "Rubric review queued. Refresh feedback in a moment.",
                          );
                          reload();
                        })
                      }
                    >
                      Request rubric review
                    </Action>
                    <button className="text-button" onClick={() => setGrade(s)}>
                      Add instructor grade
                    </button>
                  </div>
                  {data.submission_assessment
                    .filter((x) => x.submission_id === s.id)
                    .map((x) => (
                      <div key={x.id}>
                        {x.stale_for_current_rubric && (
                          <Badge tone="warm">Historical rubric version</Badge>
                        )}
                        <Feedback
                          value={x.feedback}
                          score={x.score}
                          points={x.max_score}
                        />
                      </div>
                    ))}
                  {data.official_grade
                    .filter((g) => g.submission_id === s.id)
                    .map((g) => (
                      <div className="official-grade" key={g.id}>
                        <strong>
                          Instructor grade: {g.score} / {g.max_score}
                        </strong>
                        <p>{g.feedback}</p>
                        <small>
                          Entered by you ·{" "}
                          {g.individual ? "Individual" : "Team"} outcome
                        </small>
                      </div>
                    ))}
                </div>
              ))}
            <button className="text-button" onClick={reload}>
              <RefreshCw size={15} />
              Refresh feedback
            </button>
          </section>
        </section>
        <aside className="context-rail">
          <h3>{rubric?.title}</h3>
          <Badge>
            {a.follow_shared_rubric
              ? "Follows shared rubric"
              : "Pinned rubric version"}
          </Badge>
          <p>{rubric?.permitted_assistance}</p>
          {rubric?.criteria.map((c) => (
            <div className="rubric-criterion" key={c.name}>
              <strong>
                {c.name} · {percent(c.weight)}
              </strong>
              <ul>
                {c.anchors.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          ))}
          <div className="rail-note">
            <ShieldCheck size={20} />
            <p>
              AI rubric feedback and official grades are separate records. Old
              submissions keep their original rubric.
            </p>
          </div>
        </aside>
      </div>
      {grade && (
        <Modal
          title="Record the instructor's feedback"
          close={() => setGrade(null)}
        >
          <Field label={`Grade (out of ${a.points})`}>
            <input
              type="number"
              min="0"
              max={a.points}
              value={score}
              onChange={(e) => setScore(e.target.value)}
            />
          </Field>
          <Field label="Instructor feedback">
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
          </Field>
          <Action
            disabled={busy || score === ""}
            onClick={() =>
              act(async () => {
                await api("/submissions/" + grade.id + "/grade", {
                  score: +score,
                  feedback,
                });
                setGrade(null);
                reload();
              })
            }
          >
            Save official outcome
          </Action>
        </Modal>
      )}
    </>
  );
}

function Planner({ act, busy, overview }) {
  const [data, reload, error] = useLoad("/planning"),
    [taskOpen, setTaskOpen] = useState(false),
    [eventOpen, setEventOpen] = useState(false),
    [goalOpen, setGoalOpen] = useState(false),
    [proposal, setProposal] = useState(null),
    [complete, setComplete] = useState(null),
    [actual, setActual] = useState("");
  const [settings, setSettings] = useState({
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    days: 7,
    daily_minutes: 120,
    slack: 0.2,
    day_start: "09:00",
    day_end: "18:00",
    weekdays: [0, 1, 2, 3, 4],
  });
  const [task, setTask] = useState({
    title: "",
    category: "academic",
    deadline: null,
    effort_minutes: 60,
    min_block: 20,
    max_block: 60,
    splittable: true,
    definition_of_done: "",
    prerequisites: [],
    at_risk: false,
  });
  const [event, setEvent] = useState({
      title: "",
      start: "",
      end: "",
      kind: "commitment",
    }),
    [goal, setGoal] = useState({
      title: "",
      horizon: "2026-12-31",
      target: "",
      acceptance_criteria: [],
      evidence_requirements: [],
      capabilities: [],
      priority: "academic",
    });
  const change = (k, v) => setTask({ ...task, [k]: v });
  const shown = proposal || data?.schedule;
  return (
    <>
      <PageHead
        title="One calendar. Real constraints."
        actions={
          <div className="row">
            <Action className="secondary" onClick={() => setEventOpen(true)}>
              Add commitment
            </Action>
            <Action onClick={() => setTaskOpen(true)}>
              <Plus size={17} />
              Add work
            </Action>
          </div>
        }
      >
        Protect deadlines, advance research, and leave room for the unexpected.
      </PageHead>
      <ErrorBox message={error} />
      <div className="planner-layout">
        <section>
          <div className="section-title">
            <h2>Work to allocate</h2>
            <button className="text-button" onClick={() => setGoalOpen(true)}>
              Add a goal
            </button>
          </div>
          {data?.tasks
            .filter((t) => t.status !== "complete")
            .map((t) => {
              const p = data.predictions
                .filter((p) => p.target_id === t.id && !p.stale_reason)
                .at(-1);
              return (
                <div className="task-row" key={t.id}>
                  <div className={"category-mark " + t.category} />
                  <div>
                    <h3>{t.title}</h3>
                    <p>
                      {t.category} · {fmtDate(t.deadline)}
                      {t.blocked_reason && ` · Blocked: ${t.blocked_reason}`}
                    </p>
                    <small>{t.definition_of_done}</small>
                  </div>
                  <div className="task-time">
                    <strong>
                      {p
                        ? `${p.distribution.p50}–${p.distribution.p80}`
                        : t.effort_minutes}{" "}
                      min
                    </strong>
                    <button
                      className="text-button"
                      onClick={() => {
                        setComplete(t);
                        setActual("");
                      }}
                    >
                      Update work
                    </button>
                  </div>
                </div>
              );
            })}
          {!data?.tasks.length && (
            <Empty title="What needs your attention?">
              Add a work package or an assignment. Give it a completion
              criterion and an initial estimate.
            </Empty>
          )}
          <div className="section-title section">
            <h2>{proposal ? "Proposed allocation" : "Accepted plan"}</h2>
            {proposal && (
              <Badge tone={proposal.feasible ? "good" : "warm"}>
                {proposal.feasible ? "Fits constraints" : "Needs a decision"}
              </Badge>
            )}
          </div>
          {shown?.conflicts?.map((c, i) => (
            <div className="error" key={i}>
              <strong>{c.title}</strong>
              <p>
                {c.reason}
                {c.unscheduled_minutes
                  ? ` (${c.unscheduled_minutes} min remain)`
                  : ""}
              </p>
            </div>
          ))}
          {shown?.blocks?.length ? (
            shown.blocks.map((b) => (
              <div className="schedule-block" key={b.id}>
                <div className="block-time">
                  <strong>
                    {new Date(b.start).toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </strong>
                  <span>
                    {new Date(b.start).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                    –
                    {new Date(b.end).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div>
                  <strong>{b.title}</strong>
                  <p>
                    {b.work_minutes} min active work
                    {b.setup_minutes ? ` + ${b.setup_minutes} min setup` : ""}
                  </p>
                </div>
                {!proposal && (
                  <button
                    className={"icon " + (b.pinned ? "pinned" : "")}
                    aria-label={b.pinned ? "Unpin block" : "Pin block"}
                    onClick={() =>
                      act(async () => {
                        await api("/blocks/" + b.id + "/pin", {
                          pinned: !b.pinned,
                        });
                        reload();
                      })
                    }
                  >
                    <Pin size={17} />
                  </button>
                )}
              </div>
            ))
          ) : (
            <p className="muted">
              A proposal will explain what fits and which obligations need a
              change.
            </p>
          )}
          {proposal && (
            <div className="row section">
              <Action
                disabled={busy || !proposal.feasible}
                onClick={() =>
                  act(async () => {
                    await api("/schedules/" + proposal.id + "/accept", {});
                    setProposal(null);
                    reload();
                  })
                }
              >
                Accept this plan
              </Action>
              <button className="text-button" onClick={() => setProposal(null)}>
                Keep current plan
              </button>
            </div>
          )}
          {data?.schedule && !proposal && (
            <button
              className="text-button"
              onClick={() =>
                act(async () => {
                  const token = workspaceStorage.getItem("gym-token");
                  const r = await fetch("/api/schedule.ics", {
                    headers: token ? { Authorization: "Bearer " + token } : {},
                  });
                  if (!r.ok) throw new Error("Calendar export failed");
                  const u = URL.createObjectURL(await r.blob());
                  const a = document.createElement("a");
                  a.href = u;
                  a.download = "learning-plan.ics";
                  a.click();
                  URL.revokeObjectURL(u);
                })
              }
            >
              Download approved calendar blocks (.ics)
            </button>
          )}
          <section className="section">
            <h2>Your goal contracts</h2>
            {data?.goals.map((g) => (
              <details key={g.id}>
                <summary>
                  {g.title}
                  <Badge>{g.priority}</Badge>
                </summary>
                <p>{g.target}</p>
                <ul>
                  {g.acceptance_criteria.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
                <small>Horizon: {g.horizon}</small>
              </details>
            ))}
            {!data?.goals.length && (
              <p className="muted">
                No academic or research targets have been assumed. Add the
                targets and acceptance criteria you actually want.
              </p>
            )}
          </section>
        </section>
        <aside className="panel planning-controls">
          <h2>Available study time</h2>
          <Field label="Planning horizon">
            <select
              value={settings.days}
              onChange={(e) =>
                setSettings({ ...settings, days: +e.target.value })
              }
            >
              <option value="7">Next 7 days</option>
              <option value="14">Next 14 days</option>
            </select>
          </Field>
          <Field label="Timezone">
            <input
              value={settings.timezone}
              onChange={(e) =>
                setSettings({ ...settings, timezone: e.target.value })
              }
            />
          </Field>
          <div className="form-row">
            <Field label="From">
              <input
                type="time"
                value={settings.day_start}
                onChange={(e) =>
                  setSettings({ ...settings, day_start: e.target.value })
                }
              />
            </Field>
            <Field label="Until">
              <input
                type="time"
                value={settings.day_end}
                onChange={(e) =>
                  setSettings({ ...settings, day_end: e.target.value })
                }
              />
            </Field>
          </div>
          <div className="weekdays">
            {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
              <button
                key={i}
                aria-label={
                  [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                  ][i]
                }
                className={settings.weekdays.includes(i) ? "active" : ""}
                onClick={() =>
                  setSettings({
                    ...settings,
                    weekdays: settings.weekdays.includes(i)
                      ? settings.weekdays.filter((x) => x !== i)
                      : [...settings.weekdays, i],
                  })
                }
              >
                {d}
              </button>
            ))}
          </div>
          <Field label="Daily workload ceiling (minutes)">
            <input
              type="number"
              min="15"
              max="720"
              value={settings.daily_minutes}
              onChange={(e) =>
                setSettings({ ...settings, daily_minutes: +e.target.value })
              }
            />
          </Field>
          <Field label="Leave free for uncertainty">
            <select
              value={settings.slack}
              onChange={(e) =>
                setSettings({ ...settings, slack: +e.target.value })
              }
            >
              <option value="0.1">10% slack</option>
              <option value="0.2">20% slack</option>
              <option value="0.3">30% slack</option>
            </select>
          </Field>
          <Action
            disabled={busy}
            onClick={() =>
              act(async () => {
                setProposal(await api("/schedules", settings));
                reload();
              })
            }
          >
            Build a feasible proposal
          </Action>
          <p className="small muted">
            Endangered academic obligations come first, followed by research
            bottlenecks and shared capabilities. No time is booked externally.
          </p>
          <hr />
          <h3>Calendar constraints</h3>
          <label className="button secondary">
            <Upload size={16} />
            Import calendar (.ics)
            <input
              hidden
              type="file"
              accept=".ics"
              onChange={(e) =>
                act(async () => {
                  const f = new FormData();
                  f.append("file", e.target.files[0]);
                  f.append("source", "ics:calendar");
                  await api("/calendar/import", f);
                  reload();
                })
              }
            />
          </label>
          {data?.calendar
            .filter((e) => !e.cancelled)
            .slice(0, 10)
            .map((e) => (
              <p key={e.id}>
                <strong>{e.title}</strong>
                <br />
                <small>{fmtDate(e.start || e.due)}</small>
              </p>
            ))}
          <p className="small muted">
            Calendar imports are snapshots. Reimport when dates change; direct
            calendar synchronization is not connected.
          </p>
        </aside>
      </div>
      {taskOpen && (
        <Modal title="Define a work package" close={() => setTaskOpen(false)}>
          <Field label="Task">
            <input
              value={task.title}
              onChange={(e) => change("title", e.target.value)}
            />
          </Field>
          <Field label="What counts as done?">
            <textarea
              value={task.definition_of_done}
              onChange={(e) => change("definition_of_done", e.target.value)}
              placeholder="A reproducible baseline with a checked result, or a completed timed simulation…"
            />
          </Field>
          <div className="form-row">
            <Field label="Contribution">
              <select
                value={task.category}
                onChange={(e) => change("category", e.target.value)}
              >
                {["academic", "research", "capability", "exploration"].map(
                  (x) => (
                    <option key={x}>{x}</option>
                  ),
                )}
              </select>
            </Field>
            <Field label="Initial remaining effort (min)">
              <input
                type="number"
                value={task.effort_minutes}
                onChange={(e) => change("effort_minutes", +e.target.value)}
              />
            </Field>
          </div>
          <Field label="Deadline (optional)">
            <input
              type="datetime-local"
              onChange={(e) =>
                change(
                  "deadline",
                  e.target.value
                    ? new Date(e.target.value).toISOString()
                    : null,
                )
              }
            />
          </Field>
          <Field label="Must follow">
            <select
              multiple
              value={task.prerequisites}
              onChange={(e) =>
                change(
                  "prerequisites",
                  Array.from(e.target.selectedOptions, (o) => o.value),
                )
              }
            >
              {data?.tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
          </Field>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={task.splittable}
              onChange={(e) => change("splittable", e.target.checked)}
            />
            Can split at useful checkpoints
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={task.at_risk}
              onChange={(e) => change("at_risk", e.target.checked)}
            />
            An academic obligation is genuinely at risk
          </label>
          <Action
            disabled={
              busy ||
              task.title.length < 2 ||
              task.definition_of_done.length < 5
            }
            onClick={() =>
              act(async () => {
                await api("/tasks", task);
                setTaskOpen(false);
                reload();
              })
            }
          >
            Add work package
          </Action>
        </Modal>
      )}
      {eventOpen && (
        <Modal title="Add a fixed commitment" close={() => setEventOpen(false)}>
          <Field label="Event title">
            <input
              value={event.title}
              onChange={(e) => setEvent({ ...event, title: e.target.value })}
            />
          </Field>
          <Field label="Starts">
            <input
              type="datetime-local"
              onChange={(e) =>
                setEvent({
                  ...event,
                  start: e.target.value
                    ? new Date(e.target.value).toISOString()
                    : "",
                })
              }
            />
          </Field>
          <Field label="Ends">
            <input
              type="datetime-local"
              onChange={(e) =>
                setEvent({
                  ...event,
                  end: e.target.value
                    ? new Date(e.target.value).toISOString()
                    : "",
                })
              }
            />
          </Field>
          <Action
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api("/calendar", event);
                setEventOpen(false);
                reload();
              })
            }
          >
            Save commitment
          </Action>
        </Modal>
      )}
      {goalOpen && (
        <Modal title="Set a goal contract" close={() => setGoalOpen(false)}>
          {[
            ["title", "Goal"],
            ["target", "Operational target"],
            ["horizon", "Horizon"],
          ].map(([k, label]) => (
            <Field key={k} label={label}>
              <input
                value={goal[k]}
                onChange={(e) => setGoal({ ...goal, [k]: e.target.value })}
              />
            </Field>
          ))}
          <Field label="Acceptance criteria (one per line)">
            <textarea
              value={goal.acceptance_criteria.join("\n")}
              onChange={(e) =>
                setGoal({
                  ...goal,
                  acceptance_criteria: e.target.value.split("\n"),
                })
              }
            />
          </Field>
          <Field label="Priority">
            <select
              value={goal.priority}
              onChange={(e) => setGoal({ ...goal, priority: e.target.value })}
            >
              {["academic", "research", "capability", "exploration"].map(
                (x) => (
                  <option key={x}>{x}</option>
                ),
              )}
            </select>
          </Field>
          <Action
            onClick={() =>
              act(async () => {
                await api("/goals", goal);
                setGoalOpen(false);
                reload();
              })
            }
          >
            Approve goal contract
          </Action>
        </Modal>
      )}
      {complete && (
        <Modal title="Update remaining work" close={() => setComplete(null)}>
          <h3>{complete.title}</h3>
          <Field label="Active minutes since the last scope estimate">
            <input
              type="number"
              min="0"
              value={actual}
              onChange={(e) => setActual(e.target.value)}
            />
          </Field>
          <p>
            Completion means the defined criterion is met. If work remains, give
            a new estimate; elapsed time is not automatically subtracted.
          </p>
          <div className="row">
            <Action
              disabled={busy || actual === ""}
              onClick={() =>
                act(async () => {
                  await api(
                    "/tasks/" + complete.id,
                    {
                      status: "complete",
                      active_minutes: +actual,
                      expected_revision: complete.revision,
                    },
                    "PATCH",
                  );
                  setComplete(null);
                  reload();
                })
              }
            >
              Mark complete
            </Action>
            <Action
              className="secondary"
              onClick={() =>
                act(async () => {
                  await api(
                    "/tasks/" + complete.id,
                    {
                      effort_minutes: complete.effort_minutes,
                      active_minutes: +actual,
                      expected_revision: complete.revision,
                    },
                    "PATCH",
                  );
                  setComplete(null);
                  reload();
                })
              }
            >
              Save remaining work
            </Action>
          </div>
          <Field label="Remaining active effort (min)">
            <input
              type="number"
              value={complete.effort_minutes}
              onChange={(e) =>
                setComplete({ ...complete, effort_minutes: +e.target.value })
              }
            />
          </Field>
        </Modal>
      )}
    </>
  );
}

function Research({ act, busy, overview }) {
  const [data, reload, error] = useLoad("/artifacts"),
    [draft, setDraft] = useState({
      title: "",
      body: "",
      claim: "",
      objection: "",
      kind: "argument",
      ai_contribution: "none",
      relations: [],
    }),
    [editing, setEditing] = useState(false);
  const set = (k, v) => setDraft({ ...draft, [k]: v });
  return (
    <>
      <PageHead
        title="Make a claim you can defend."
        actions={
          <Action
            onClick={() => {
              setDraft({
                title: "",
                body: "",
                claim: "",
                objection: "",
                kind: "argument",
                ai_contribution: "none",
                relations: [],
              });
              setEditing(true);
            }}
          >
            <Plus size={17} />
            New artifact
          </Action>
        }
      >
        Turn course capabilities into arguments, experiments and reproducible
        results.
      </PageHead>
      <ErrorBox message={error} />
      {editing ? (
        <div className="study-layout">
          <section>
            <Field label="Artifact title">
              <input
                value={draft.title}
                onChange={(e) => set("title", e.target.value)}
              />
            </Field>
            <div className="form-row">
              <Field label="Artifact type">
                <select
                  value={draft.kind}
                  onChange={(e) => set("kind", e.target.value)}
                >
                  {[
                    "argument",
                    "derivation",
                    "code",
                    "experiment",
                    "results",
                    "review",
                  ].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </Field>
              <Field label="AI contribution">
                <select
                  value={draft.ai_contribution}
                  onChange={(e) => set("ai_contribution", e.target.value)}
                >
                  <option value="none">None</option>
                  <option value="hints">Coaching</option>
                  <option value="substantive">Substantive generation</option>
                </select>
              </Field>
            </div>
            <Field label="What is the claim?">
              <textarea
                value={draft.claim}
                onChange={(e) => set("claim", e.target.value)}
              />
            </Field>
            <Field label="Strongest unresolved objection">
              <textarea
                value={draft.objection}
                onChange={(e) => set("objection", e.target.value)}
              />
            </Field>
            <Field label="Your working artifact">
              <textarea
                className="assignment-editor"
                value={draft.body}
                onChange={(e) => set("body", e.target.value)}
              />
            </Field>
            <div className="row">
              <Action
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api("/artifacts", draft);
                    setEditing(false);
                    reload();
                  })
                }
              >
                Save a new version
              </Action>
              <button className="text-button" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          </section>
          <aside className="context-rail">
            <h3>Bridge mission</h3>
            <p>
              Use a course capability to challenge a live research claim.
              Produce a revised analysis and a short explanation of what
              changed.
            </p>
            <h3>Make progress assessable</h3>
            <ul>
              <li>State what you expect and under which assumptions.</li>
              <li>Compare with a credible baseline.</li>
              <li>Record a discriminating test.</li>
              <li>Identify evidence that could change your conclusion.</li>
            </ul>
            <Field label="Derived from another artifact">
              <select
                value={draft.relations[0]?.target_id || ""}
                onChange={(e) =>
                  set(
                    "relations",
                    e.target.value
                      ? [{ type: "derived_from", target_id: e.target.value }]
                      : [],
                  )
                }
              >
                <option value="">No linked artifact</option>
                {data?.artifacts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            </Field>
          </aside>
        </div>
      ) : (
        <>
          {data?.artifacts.length ? (
            data.artifacts.map((a) => (
              <section className="artifact panel" key={a.id}>
                <div className="row between">
                  <h2>{a.title}</h2>
                  <Badge>
                    {a.kind} · v{a.version}
                  </Badge>
                </div>
                <p>
                  <strong>Claim:</strong> {a.claim || "Not specified"}
                </p>
                <p>
                  <strong>Objection:</strong> {a.objection || "Not specified"}
                </p>
                <details>
                  <summary>Read artifact and provenance</summary>
                  <p className="preserve">{a.body}</p>
                  <p>AI contribution: {a.ai_contribution}</p>
                  {a.relations.map((r, i) => (
                    <small key={i}>
                      {r.type}: {r.target_id}
                    </small>
                  ))}
                </details>
                <div className="row">
                  <Action
                    className="secondary"
                    onClick={() => {
                      setDraft({
                        ...a,
                        artifact_id: a.id,
                        expected_revision: a.revision,
                      });
                      setEditing(true);
                    }}
                  >
                    Revise
                  </Action>
                  <button
                    className="text-button"
                    onClick={() =>
                      act(async () => {
                        await api(
                          "/artifacts/" + a.version_id + "/critique",
                          {},
                        );
                        reload();
                      })
                    }
                  >
                    Request independent critique
                  </button>
                </div>
                {data.reviews
                  .filter((r) => r.version_id === a.version_id)
                  .map((r) => (
                    <Feedback
                      key={r.id}
                      value={r.feedback}
                      score={r.score}
                      points={100}
                    />
                  ))}
              </section>
            ))
          ) : (
            <Empty title="Start with one research bottleneck">
              A derivation, failed experiment, code fragment or rough argument
              can be useful evidence. It does not need to be polished.
            </Empty>
          )}
          <button className="text-button" onClick={reload}>
            <RefreshCw size={15} />
            Refresh critiques
          </button>
        </>
      )}
    </>
  );
}

function Progress({ act, start }) {
  const [data, reload, error] = useLoad("/progress"),
    [evidence, loadEvidence] = useLoad("/evidence"),
    [showJournal, setShowJournal] = useState(false);
  const valid =
    data?.attempts.filter((a) => !a.invalidated && a.score != null) || [];
  const independent = valid.filter((a) => !a.assistance?.length),
    assisted = valid.filter((a) => a.assistance?.length);
  const meanTime = valid.length
    ? valid.reduce((s, a) => s + a.active_seconds, 0) / valid.length
    : 0;
  return (
    <>
      <PageHead
        title="What the evidence actually says."
        actions={
          <button
            className="text-button"
            onClick={() => {
              reload();
              loadEvidence();
            }}
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        }
      >
        A capability profile, with uncertainty and the observations behind it.
      </PageHead>
      <ErrorBox message={error} />
      <div className="evidence-summary">
        <div>
          <strong>{valid.length}</strong>
          <span>Assessed attempts</span>
        </div>
        <div>
          <strong>{independent.length}</strong>
          <span>Without recorded help</span>
        </div>
        <div>
          <strong>{assisted.length}</strong>
          <span>With recorded help</span>
        </div>
        <div>
          <strong>{minutes(meanTime)}</strong>
          <span>Mean active time per attempt</span>
        </div>
      </div>
      <p className="small muted">
        No prior telemetry is inferred from imported demos. These counts
        describe work recorded here, not a mastery percentage.
      </p>
      <section className="section">
        <h2>Guided activity and assessed outcomes</h2>
        <p>
          Time, experiments, and reflections describe your preparation. Linked
          practice supplies scored evidence. These observations do not establish
          the causal effect of a teaching method.
        </p>
        {data?.lab_activities?.length ? (
          data.lab_activities
            .slice(-10)
            .reverse()
            .map((activity) => (
              <div className="panel" key={activity.id}>
                <div className="row between">
                  <strong>
                    {activity.lab_title ||
                      activity.course_title ||
                      "Guided lab"}{" "}
                    / {activity.lesson_title || activity.module} ·{" "}
                    {activity.status === "finished"
                      ? "Study activity finished"
                      : "Study activity unfinished"}
                  </strong>
                  <Badge>
                    {activity.running ? "Timer running" : "Timer stopped"}
                  </Badge>
                </div>
                <p>
                  {activityDuration(activity.active_seconds)} active study ·{" "}
                  {activityDuration(activity.elapsed_seconds)} elapsed ·{" "}
                  {activity.experiment_count} experiment runs ·{" "}
                  {activity.reading_count} reading exposures
                </p>
                {activity.practice_outcome ? (
                  <p>
                    Linked practice: {activity.practice_outcome.attempt_count}{" "}
                    attempts; {activity.practice_outcome.score}/
                    {activity.practice_outcome.max_score} points so far;{" "}
                    {activity.practice_outcome.pending_count} awaiting
                    assessment.{" "}
                    {activity.practice_outcome.assisted_attempt_count} attempts
                    with recorded support.
                  </p>
                ) : (
                  <p>No scored practice linked yet.</p>
                )}
                {activity.practice_outcome?.invalidated_count > 0 && (
                  <p className="notice">
                    {activity.practice_outcome.invalidated_count} invalidated
                    attempts are excluded from the points shown.
                  </p>
                )}
                {activity.reflection && (
                  <details>
                    <summary>Saved reasoning</summary>
                    <p className="preserve">{activity.reflection}</p>
                  </details>
                )}
                {Object.keys(activity.responses || {}).length > 0 && (
                  <details>
                    <summary>
                      Saved activity responses (
                      {Object.keys(activity.responses).length})
                    </summary>
                    {Object.values(activity.responses).map(
                      (response, index) => (
                        <div key={index}>
                          <strong>Response {index + 1}</strong>
                          <p className="preserve">{response.value}</p>
                        </div>
                      ),
                    )}
                  </details>
                )}
              </div>
            ))
        ) : (
          <p className="muted">
            Start a guided learning session to record this connection.
          </p>
        )}
      </section>
      <section className="section">
        <h2>Capabilities to investigate</h2>
        {data?.learner_states.length ? (
          data.learner_states.map((s) => (
            <div className="capability panel" key={s.id}>
              <div className="row between">
                <h3>{s.capability}</h3>
                <Badge>{s.evidence_ids.length} observations</Badge>
              </div>
              {Object.entries(s.dimensions).map(([name, d]) => (
                <div className="dimension" key={name}>
                  <span>{name}</span>
                  <div className="estimate-track">
                    <span
                      className="estimate-interval"
                      style={{
                        left: percent(d.interval[0]),
                        width: percent(d.interval[1] - d.interval[0]),
                      }}
                    />
                    <span
                      className="estimate-point"
                      style={{ left: percent(d.estimate) }}
                    />
                  </div>
                  <small>
                    {percent(d.interval[0])}–{percent(d.interval[1])}
                  </small>
                </div>
              ))}
              <p>{s.hypotheses.join(" ")}</p>
              <div className="row between">
                <small>
                  {s.independent_attempts} independent · {s.assisted_attempts}{" "}
                  assisted · {s.unseen_checks} unseen simulation/transfer checks
                </small>
                <button
                  className="text-button"
                  onClick={() =>
                    start({
                      course_id: s.course_id,
                      mode: "practice",
                      module: "all",
                      count: 5,
                    })
                  }
                >
                  Practice again
                </button>
              </div>
              <details>
                <summary>Evidence and model assumptions</summary>
                <p>
                  Beta-prior evidence summary with broad uncertainty. Assisted,
                  repeated and model-judged attempts receive less weight. This
                  interval is not a validated forecast of mastery.
                </p>
                <p>
                  Model: {s.model_version}. Check due:{" "}
                  {fmtDate(s.next_check_at)}.
                </p>
                {s.evidence_ids.slice(-5).map((id) => (
                  <small className="evidence-id" key={id}>
                    {id}
                  </small>
                ))}
              </details>
            </div>
          ))
        ) : (
          <Empty title="You are not a guessed profile">
            Make an attempt to start collecting evidence. The system will
            describe uncertainty until enough independent observations exist.
          </Empty>
        )}
      </section>
      <div className="two-column">
        <section className="panel">
          <h2>Patterns by task type</h2>
          {data?.execution.map((x) => (
            <div className="list-row" key={x.type}>
              <strong>{x.type}</strong>
              <span>{x.count} attempts</span>
              <span>{minutes(x.mean_active_seconds)} mean active time</span>
            </div>
          ))}
          <p className="small muted">
            Time is compared within task types. Interruptions and unfinished
            sessions remain separate from completed performance.
          </p>
        </section>
        <section className="panel">
          <div className="row between">
            <h2>Adaptation review</h2>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={data?.adaptation.enabled ?? true}
                onChange={(e) =>
                  act(async () => {
                    await api("/adaptation/settings", {
                      enabled: e.target.checked,
                    });
                    reload();
                  })
                }
              />
              Enabled
            </label>
          </div>
          <p>
            Evaluate predictions against later outcomes. Keep the baseline when
            evidence is insufficient.
          </p>
          <Action
            className="secondary"
            onClick={() =>
              act(async () => {
                await api("/adaptation/evaluate", {});
                reload();
              })
            }
          >
            Evaluate current evidence
          </Action>
          {data?.evaluations.slice(-1).map((e) => (
            <div key={e.id}>
              <p>
                <strong>{e.decision}</strong>
              </p>
              <p>{e.count} matched effort outcomes.</p>
              <small>{e.causal_claim}</small>
            </div>
          ))}
          <p className="small muted">
            Disabling adaptation leaves practice, evidence capture and planning
            available.
          </p>
        </section>
      </div>
      <section className="section">
        <div className="section-title">
          <h2>Recent attempts</h2>
          <button
            className="text-button"
            onClick={() => setShowJournal(!showJournal)}
          >
            {showJournal ? "Hide" : "Inspect"} evidence journal
          </button>
        </div>
        {data?.attempts
          .slice(-12)
          .reverse()
          .map((a) => (
            <div className="list-row" key={a.id}>
              <div>
                <strong>
                  {a.item_type} · {a.mode}
                </strong>
                <p>
                  {fmtDate(a.created_at)} · {minutes(a.active_seconds)} active
                  {a.confidence != null
                    ? ` · ${percent(a.confidence)} confidence`
                    : ""}
                </p>
              </div>
              <span>
                {a.assistance?.length
                  ? a.assistance.join(", ")
                  : "No help recorded"}
              </span>
              <Badge tone={a.invalidated ? "warm" : ""}>
                {a.invalidated
                  ? "Invalidated"
                  : a.score == null
                    ? "Pending"
                    : `${a.score} points`}
              </Badge>
            </div>
          ))}
        {showJournal && (
          <div className="journal">
            {evidence?.map((e) => (
              <details key={e.id}>
                <summary>
                  {e.event_type}
                  <small>{fmtDate(e.received_at)}</small>
                </summary>
                <p>
                  Occurred: {fmtDate(e.occurred_at)} · Received:{" "}
                  {fmtDate(e.received_at)}
                </p>
                <pre>{JSON.stringify(e.payload, null, 2)}</pre>
              </details>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function System({ act, health, refresh }) {
  const [token, setToken] = useState("");
  if (!health) return <div className="loading">Loading system health…</div>;
  const failed = health.jobs.filter((j) => j.status === "failed"),
    pending = health.jobs.filter((j) =>
      ["queued", "running"].includes(j.status),
    );
  return (
    <>
      <PageHead
        title="Keep the loop dependable."
        actions={
          <Action className="secondary" onClick={refresh}>
            <RefreshCw size={16} />
            Refresh health
          </Action>
        }
      >
        Visible freshness, recoverable work, and model choices for each job.
      </PageHead>
      <div className="two-column">
        <section className="panel">
          <h2>Operational state</h2>
          <div className="list-row">
            <strong>Storage</strong>
            <Badge tone="good">{health.database}</Badge>
            <span>{health.dialect}</span>
          </div>
          <div className="list-row">
            <strong>Background work</strong>
            <span>{pending.length} pending</span>
            <span>{failed.length} failed</span>
          </div>
          <div className="list-row">
            <strong>Historical stale estimates</strong>
            <span>{health.stale_estimates}</span>
          </div>
          {health.job_health.map((h) => (
            <p key={h.id}>
              <strong>{h.id.replace("_", " ")}</strong>
              <br />
              <small>{fmtDate(h.last_success_at || h.heartbeat_at)}</small>
            </p>
          ))}
          <h3>Calendar freshness</h3>
          {health.connectors.length ? (
            health.connectors.map((c) => (
              <p key={c.id}>
                {c.source}
                <br />
                <small>Last import: {fmtDate(c.last_success_at)}</small>
              </p>
            ))
          ) : (
            <p className="muted">
              No calendar is connected. Add commitments or import an ICS
              snapshot in Plan my time.
            </p>
          )}
        </section>
        <section className="panel">
          <h2>Model routing</h2>
          <p>
            Each role has its own provider, model, reasoning and token budget.
          </p>
          {Object.entries(health.models.roles).map(([role, r]) => (
            <div className="model-route" key={role}>
              <strong>{role.replace("_", " ")}</strong>
              <span>
                {r.model}
                <small>
                  {r.provider} · reasoning:{" "}
                  {r.reasoning_effort || "provider default"}
                </small>
              </span>
              <Badge
                tone={
                  health.models.providers[r.provider].configured
                    ? "good"
                    : "warm"
                }
              >
                {health.models.providers[r.provider].configured
                  ? "Configured"
                  : "Needs key"}
              </Badge>
            </div>
          ))}
          <p className="small muted">
            Edit config/models.json on the server to change routes. Credentials
            are environment variables and never sent to the browser. Daily
            limit: {health.models.limits.max_calls_per_day} model calls.
          </p>
        </section>
      </div>
      <section className="section">
        <h2>Jobs requiring attention</h2>
        {failed.length ? (
          failed.map((j) => (
            <div className="list-row" key={j.id}>
              <div>
                <strong>{j.kind}</strong>
                <p>{j.last_error}</p>
              </div>
              <Action
                className="secondary"
                onClick={() =>
                  act(async () => {
                    await api("/jobs/" + j.id + "/retry", {});
                    refresh();
                  })
                }
              >
                Retry
              </Action>
            </div>
          ))
        ) : (
          <p className="muted">No failed jobs.</p>
        )}
      </section>
      <section className="section">
        <h2>Model history & rollback</h2>
        {health.model_versions.map((m) => (
          <div className="list-row" key={m.id}>
            <div>
              <strong>{m.role}</strong>
              <p>
                {m.holdout_count || 0} holdout observations · {m.id}
              </p>
            </div>
            <Badge>{m.status}</Badge>
            {["shadow", "retired"].includes(m.status) &&
              m.promotion_eligible && (
                <Action
                  className="secondary"
                  onClick={() =>
                    act(async () => {
                      await api("/models/" + m.id + "/activate", {});
                      refresh();
                    })
                  }
                >
                  {m.status === "retired"
                    ? "Restore version"
                    : "Activate candidate"}
                </Action>
              )}
          </div>
        ))}
        {!health.model_versions.length && (
          <p className="muted">
            The initial transparent baselines are active. A replacement needs a
            chronological evaluation and your approval.
          </p>
        )}
      </section>
      <section className="section">
        <h2>Recent model calls</h2>
        {health.calls.map((c) => (
          <div className="list-row" key={c.id}>
            <strong>{c.role}</strong>
            <span>
              {c.provider} / {c.model}
            </span>
            <span>{c.elapsed_seconds || "…"} s</span>
            <Badge>{c.status}</Badge>
          </div>
        ))}
      </section>
      <details>
        <summary>Access token for a protected server</summary>
        <Field label="Server access token">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </Field>
        <Action
          onClick={() => {
            workspaceStorage.setItem("gym-token", token);
            refresh();
          }}
        >
          Use token for this browser session
        </Action>
      </details>
    </>
  );
}

const root = createRoot(document.getElementById("root"));
initializeWorkspace()
  .then(() => root.render(<App />))
  .catch((error) =>
    root.render(
      <main>
        <h1>Cannot open this workspace</h1>
        <p role="alert">{error.message}</p>
        <button onClick={() => location.reload()}>Try again</button>
      </main>,
    ),
  );
