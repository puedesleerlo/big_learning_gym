import React, { useEffect, useRef, useState, useId } from "react";
import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronRight,
  Clock3,
  FlaskConical,
  Pause,
  Play,
} from "lucide-react";
import "./guided-lab.css";

const key = () => crypto.randomUUID();
const elapsed = (seconds) =>
  `${Math.floor((seconds || 0) / 60)}:${String(Math.floor((seconds || 0) % 60)).padStart(2, "0")}`;

function Graph({ mode = "fork", intervention = false, result = false }) {
  const marker = useId().replaceAll(":", "");
  const points = { X: [75, 145], Z: [240, 55], Y: [405, 145] };
  const edges =
    mode === "chain"
      ? [
          ["X", "Z"],
          ["Z", "Y"],
        ]
      : mode === "collider"
        ? [
            ["X", "Z"],
            ["Y", "Z"],
          ]
        : [
            ["Z", "X"],
            ["Z", "Y"],
          ];
  if (mode === "intervention") edges.push(["X", "Y"]);
  return (
    <svg
      viewBox="0 0 480 205"
      role="img"
      aria-label={`${mode} graph${intervention ? "; the incoming arrow to X is cut" : ""}${result && mode !== "collider" ? "; directions unresolved" : ""}`}
    >
      <defs>
        <marker
          id={marker}
          markerWidth="10"
          markerHeight="8"
          refX="8"
          refY="4"
          orient="auto-start-reverse"
        >
          <path
            d="M0,0 L9,4 L0,8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
        </marker>
      </defs>
      {edges.map(([from, to]) => {
        const [x1, y1] = points[from],
          [x2, y2] = points[to],
          distance = Math.hypot(x2 - x1, y2 - y1);
        const cut = intervention && to === "X";
        return (
          <line
            key={from + to}
            x1={x1 + ((x2 - x1) * 32) / distance}
            y1={y1 + ((y2 - y1) * 32) / distance}
            x2={x2 - ((x2 - x1) * 37) / distance}
            y2={y2 - ((y2 - y1) * 37) / distance}
            stroke={cut ? "#b0bdce" : "#386db1"}
            strokeWidth="2.5"
            strokeDasharray={cut ? "6 6" : undefined}
            markerEnd={
              !cut && (!result || mode === "collider")
                ? `url(#${marker})`
                : undefined
            }
          />
        );
      })}
      {Object.entries(points).map(([name, [x, y]]) => (
        <g key={name}>
          <circle
            cx={x}
            cy={y}
            r="28"
            fill={name === "X" && intervention ? "#d9efea" : "#fff"}
            stroke={name === "X" && intervention ? "#23776b" : "#7d96b5"}
            strokeWidth="2"
          />
          <text
            x={x}
            y={y + 6}
            textAnchor="middle"
            fill="#203958"
            fontSize="20"
            fontWeight="600"
          >
            {name}
          </text>
        </g>
      ))}
      <text x="240" y="200" textAnchor="middle" fill="#687b91" fontSize="12">
        {mode === "intervention"
          ? "Z = preparation   X = practice   Y = score"
          : "Arrows are assumptions about how the world works."}
      </text>
    </svg>
  );
}

function Bar({ label, value, color = "#386db1" }) {
  return (
    <div className="lab-bar">
      <span>{label}</span>
      <div>
        <i
          style={{
            width: `${Math.max(0, Math.min(100, value))}%`,
            background: color,
          }}
        />
      </div>
      <strong>{value.toFixed(1)}%</strong>
    </div>
  );
}

function Experiment({ type, onRun, disabled }) {
  const [effect, setEffect] = useState(2),
    [confounding, setConfounding] = useState(6);
  const [intervention, setIntervention] = useState(false),
    [balanced, setBalanced] = useState(false);
  const [selection, setSelection] = useState(false),
    [shape, setShape] = useState("collider");
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false);
  const params =
    type === "intervention"
      ? { effect, confounding, intervention }
      : type === "simpson"
        ? { balanced }
        : type === "collider"
          ? { selection }
          : { shape };
  const run = async () => {
    setError("");
    setPending(true);
    try {
      await onRun({ kind: type, ...params });
      setResult({ ...params });
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  };
  return (
    <section className="lab-experiment" aria-label="Interactive experiment">
      <fieldset disabled={pending} className="lab-experiment-fields">
        <div className="row between">
          <h3>
            <FlaskConical size={19} /> Change one thing
          </h3>
          <span className="badge">Toy model</span>
        </div>
        {type === "intervention" && (
          <>
            <Graph mode="intervention" intervention={intervention} />
            <div className="lab-controls">
              <label>
                Actual effect of X on Y: <strong>{effect}</strong>
                <input
                  type="range"
                  min="-4"
                  max="6"
                  step="1"
                  value={effect}
                  onChange={(e) => {
                    setEffect(+e.target.value);
                    setResult(null);
                  }}
                />
              </label>
              <label>
                Effect of preparation Z on Y: <strong>{confounding}</strong>
                <input
                  type="range"
                  min="0"
                  max="10"
                  value={confounding}
                  onChange={(e) => {
                    setConfounding(+e.target.value);
                    setResult(null);
                  }}
                />
              </label>
            </div>
            <label className="lab-checkbox">
              <input
                type="checkbox"
                checked={intervention}
                onChange={(e) => {
                  setIntervention(e.target.checked);
                  setResult(null);
                }}
              />{" "}
              Randomize X, cutting the incoming arrow from preparation
            </label>
            <p>
              Model:{" "}
              {intervention
                ? "X is randomly assigned independently of Z"
                : "X = Z + independent noise"}
              ; Y = {effect}X + {confounding}Z + independent noise. Z and the
              noises are Gaussian with variance 1. Predict the observed score
              difference for a one-unit increase in X.
            </p>
            {result && (
              <div className="lab-result" role="status">
                <strong>
                  Observed regression slope:{" "}
                  {(
                    result.effect +
                    (result.intervention ? 0 : result.confounding / 2)
                  ).toFixed(1)}
                  . Intervention effect: {result.effect.toFixed(1)}.
                </strong>
                <p>
                  {result.intervention
                    ? "Randomizing X removes the backdoor path through preparation in this toy model."
                    : "The observational slope combines the effect of practice with differences in preparation. Changing X does not change Z."}{" "}
                  These are exact population values for the stated model, not
                  estimates from real people.
                </p>
              </div>
            )}
          </>
        )}
        {type === "simpson" && (
          <>
            <p>
              Two study groups have different starting preparation. The app
              improves the pass rate by 10 percentage points within each
              preparation group. App users, however, include more beginners.
            </p>
            <div className="lab-small-table">
              <div>
                <strong>Group</strong>
                <strong>App</strong>
                <strong>No app</strong>
              </div>
              <div>
                <span>Prepared</span>
                <span>90% pass</span>
                <span>80% pass</span>
              </div>
              <div>
                <span>Beginners</span>
                <span>30% pass</span>
                <span>20% pass</span>
              </div>
            </div>
            <label className="lab-checkbox">
              <input
                type="checkbox"
                checked={balanced}
                onChange={(e) => {
                  setBalanced(e.target.checked);
                  setResult(null);
                }}
              />{" "}
              Compare both groups with the same 50/50 preparation mix
            </label>
            <p>
              {balanced
                ? "Both comparisons now use 50% prepared learners and 50% beginners."
                : "App group: 10% prepared, 90% beginners. No-app group: 90% prepared, 10% beginners."}{" "}
              Predict whether the pooled comparison will agree with both
              within-group comparisons.
            </p>
            {result && (
              <div className="lab-result" role="status">
                <Bar label="App" value={result.balanced ? 60 : 36} />
                <Bar
                  label="No app"
                  value={result.balanced ? 50 : 74}
                  color="#74849c"
                />
                <p>
                  {result.balanced
                    ? "Standardizing to one target population gives a +10 percentage point difference."
                    : "The raw difference is −38 percentage points even though both within-group differences are +10. Different group composition reverses the comparison."}{" "}
                  Causal interpretation still needs exchangeability given
                  preparation, positivity, and a well-defined intervention.
                </p>
              </div>
            )}
          </>
        )}
        {type === "collider" && (
          <>
            <Graph mode="collider" />
            <p>
              X = skill and Y = luck are independent fair coin flips. Admission
              Z happens when either skill or luck is high. Does looking only at
              admitted people make skill and luck appear related?
            </p>
            <label className="lab-checkbox">
              <input
                type="checkbox"
                checked={selection}
                onChange={(e) => {
                  setSelection(e.target.checked);
                  setResult(null);
                }}
              />{" "}
              Select only admitted people (Z = 1)
            </label>
            {result && (
              <div className="lab-result" role="status">
                <Bar
                  label="High luck given low skill"
                  value={result.selection ? 100 : 50}
                />
                <Bar
                  label="High luck given high skill"
                  value={50}
                  color="#74849c"
                />
                <p>
                  {result.selection
                    ? "Among admitted people with low skill, luck must be high. Among those with high skill, luck is still high half the time. Selection creates an association although neither skill nor luck causes the other."
                    : "Before selection, high luck is equally common at both skill levels. Independent inputs can become associated when conditioning on their shared effect."}
                </p>
              </div>
            )}
          </>
        )}
        {type === "discovery" && (
          <>
            <label>
              Choose a known causal structure
              <select
                value={shape}
                onChange={(e) => {
                  setShape(e.target.value);
                  setResult(null);
                }}
              >
                <option value="chain">Chain: X → Z → Y</option>
                <option value="fork">Fork: X ← Z → Y</option>
                <option value="collider">Collider: X → Z ← Y</option>
              </select>
            </label>
            <Graph mode={shape} />
            <p>
              Predict which arrows an ideal independence-based search could
              orient if the assumptions hold and conditional independence were
              known exactly.
            </p>
            {result && (
              <div className="lab-result" role="status">
                <Graph mode={result.shape} result />
                <strong>
                  {result.shape === "collider"
                    ? "The unshielded collider can be oriented."
                    : "The direction remains unresolved: X — Z — Y."}
                </strong>
                <p>
                  {result.shape === "collider"
                    ? "X and Y are marginally independent and become associated after conditioning on Z. The separating set does not include Z."
                    : "X and Y become independent given Z. A chain and a fork can imply the same conditional independences; these cannot distinguish their directions."}{" "}
                  This is an idealized graph explanation, not an execution of PC
                  or a finite-sample guarantee.
                </p>
              </div>
            )}
          </>
        )}
        <button className="button" disabled={disabled || pending} onClick={run}>
          Run this comparison
        </button>
        {disabled && (
          <small>
            Start or resume the learning session to run and record a comparison.
          </small>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </fieldset>
    </section>
  );
}

export default function GuidedLab({ courseId, api, start, navigate }) {
  const [lab, setLab] = useState(null),
    [module, setModule] = useState("C01"),
    [run, setRun] = useState(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [reflection, setReflection] = useState("");
  const [tick, setTick] = useState(Date.now());
  const currentRun = useRef(null),
    queue = useRef(Promise.resolve()),
    autoResume = useRef(false),
    mounted = useRef(true);
  currentRun.current = run;
  const load = () => api(`/labs/${courseId}`).then(setLab);
  useEffect(() => {
    let live = true;
    mounted.current = true;
    load().catch((e) => setError(e.message));
    const saved = sessionStorage.getItem(`gym-lab-run:${courseId}`);
    if (saved)
      api(`/lab-activities/${saved}`)
        .then((record) => {
          if (live && record.status !== "finished") {
            setRun(record);
            setModule(record.module);
            setReflection(
              sessionStorage.getItem(
                `gym-lab-note:${courseId}:${record.module}`,
              ) ??
                record.reflection ??
                "",
            );
          }
        })
        .catch(() => sessionStorage.removeItem(`gym-lab-run:${courseId}`));
    return () => {
      live = false;
      mounted.current = false;
    };
  }, [courseId]);
  const event = (action, extra = {}) => {
    const id = currentRun.current?.id;
    if (!id)
      return Promise.reject(new Error("Start a learning session first."));
    const request = { action, idempotency_key: key(), ...extra };
    const next = queue.current
      .catch(() => {})
      .then(() => api(`/lab-activities/${id}/events`, request));
    queue.current = next;
    return next.then((record) => {
      if (mounted.current) setRun(record);
      currentRun.current = record;
      return record;
    });
  };
  useEffect(() => {
    const interval = setInterval(() => {
      if (currentRun.current?.running && !document.hidden)
        event("heartbeat").catch((e) => setError(e.message));
    }, 15000);
    const displayTimer = setInterval(() => setTick(Date.now()), 1000);
    const visibility = () => {
      if (document.hidden && currentRun.current?.running) {
        autoResume.current = true;
        event("pause").catch((e) => setError(e.message));
      } else if (
        !document.hidden &&
        autoResume.current &&
        currentRun.current?.status !== "finished"
      ) {
        autoResume.current = false;
        event("resume").catch((e) => setError(e.message));
      }
    };
    document.addEventListener("visibilitychange", visibility);
    return () => {
      clearInterval(interval);
      clearInterval(displayTimer);
      document.removeEventListener("visibilitychange", visibility);
      if (currentRun.current?.running) event("pause").catch(() => {});
    };
  }, []);
  const act = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const lesson = lab?.lessons.find((entry) => entry.id === module);
  const active = run?.module === module && run.status !== "finished";
  const running = active && run.running;
  const activeSeconds = active
    ? run.active_seconds +
      (running
        ? Math.min(
            45,
            Math.max(0, (tick - new Date(run.last_tick).getTime()) / 1000),
          )
        : 0)
    : 0;
  const startRun = () =>
    act(async () => {
      if (active) {
        await event("resume");
        return;
      }
      const record = await api(`/labs/${courseId}/activities`, {
        module,
        idempotency_key: key(),
      });
      setRun(record);
      currentRun.current = record;
      sessionStorage.setItem(`gym-lab-run:${courseId}`, record.id);
      await event("reading", { parameters: { section: "lesson" } });
    });
  const choose = (next) =>
    act(async () => {
      if (next === module) return;
      if (active) await event("pause", { reflection });
      const refreshed = await api(`/labs/${courseId}`);
      setLab(refreshed);
      const previous =
        (refreshed.activities || [])
          .slice()
          .reverse()
          .find(
            (activity) =>
              activity.module === next && activity.status === "active",
          ) || null;
      setModule(next);
      setRun(previous);
      currentRun.current = previous;
      setReflection(
        sessionStorage.getItem(`gym-lab-note:${courseId}:${next}`) ??
          previous?.reflection ??
          "",
      );
      if (previous)
        sessionStorage.setItem(`gym-lab-run:${courseId}`, previous.id);
      else sessionStorage.removeItem(`gym-lab-run:${courseId}`);
    });
  const practice = () =>
    act(async () => {
      if (active)
        await event("reading", {
          parameters: { section: "lesson_before_practice" },
        });
      if (active) await event("pause", { reflection });
      const linked = currentRun.current?.id;
      await start(
        { course_id: courseId, mode: "practice", module, count: 3 },
        linked,
      );
    });
  if (!lab)
    return (
      <div className="section">
        {error ? <p role="alert">{error}</p> : "Loading the guided lab…"}
      </div>
    );
  if (!lesson)
    return (
      <p role="alert">
        This lesson could not be found. Return to the workbench.
      </p>
    );
  const paper = lab.sources.find((s) => s.id === lesson.paper_bridge.source_id);
  const sessions = lab.activities || [];
  return (
    <div className="guided-lab">
      <button className="text-button" onClick={() => navigate("home")}>
        <ArrowLeft size={16} /> Workbench
      </button>
      <div className="lab-heading">
        <div>
          <p className="muted">Your causality learning path</p>
          <h1>Learn to ask “what would change?”</h1>
          <p>
            Explore a small model, explain your reasoning, then connect it to a
            research paper.
          </p>
        </div>
        <BookOpen size={34} />
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="lab-layout">
        <aside className="lab-path" aria-label="Lesson sequence">
          {lab.lessons.map((entry, index) => (
            <React.Fragment key={entry.id}>
              {(index === 0 ||
                lab.lessons[index - 1].stage !== entry.stage) && (
                <h3>{entry.stage}</h3>
              )}
              <button
                className={module === entry.id ? "current" : ""}
                onClick={() => choose(entry.id)}
                disabled={busy}
                aria-current={module === entry.id ? "step" : undefined}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <span>
                  {entry.title.replace(/^\d+\.\s*/, "")}
                  <small>{entry.minutes} min suggested</small>
                </span>
                <ChevronRight size={14} />
              </button>
            </React.Fragment>
          ))}
          <p>
            Use the sequence as a guide. You can revisit any lesson; reading
            alone does not mark it mastered.
          </p>
          <button className="text-button" onClick={() => navigate("progress")}>
            Inspect learning evidence
          </button>
        </aside>
        <div className="lab-content">
          <div className="lab-session-bar">
            <div>
              <Clock3 size={18} />
              <strong>
                {active ? elapsed(activeSeconds) : "Ready when you are"}
              </strong>
              <span>
                {active
                  ? `${running ? "Recording active time" : "Paused"} · ${elapsed(Math.max(0, (tick - new Date(run.started_at).getTime()) / 1000))} elapsed`
                  : "Start to record lab time; hiding this tab pauses it."}
              </span>
            </div>
            {running ? (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => act(() => event("pause", { reflection }))}
              >
                <Pause size={15} /> Pause
              </button>
            ) : (
              <button className="button" disabled={busy} onClick={startRun}>
                <Play size={15} />
                {active ? "Resume" : "Start learning session"}
              </button>
            )}
          </div>
          <article className="lab-lesson">
            <p className="muted">
              {lesson.stage} · {module}
            </p>
            <h2>{lesson.question}</h2>
            {!!lesson.prerequisites.length && (
              <p className="lab-prerequisites">
                Builds on{" "}
                {lesson.prerequisites.map((prerequisite) => (
                  <button
                    key={prerequisite}
                    className="text-button"
                    onClick={() => choose(prerequisite)}
                    disabled={busy}
                  >
                    {prerequisite}
                  </button>
                ))}
              </p>
            )}
            <details>
              <summary>What you will be able to explain</summary>
              <ul>
                {lesson.objectives.map((value) => (
                  <li key={value}>{value}</li>
                ))}
              </ul>
            </details>
            <h3>The idea in everyday language</h3>
            {lesson.intuition.map((value, i) => (
              <p key={i}>{value}</p>
            ))}
            <div className="lab-example">
              <h3>{lesson.worked_example.title}</h3>
              <p>{lesson.worked_example.body}</p>
            </div>
            {lesson.experiment && (
              <p>
                <strong>Warm-up:</strong> Explore the concept in a small
                illustrative model, then apply it to this lesson’s exercise.
              </p>
            )}
            {lesson.experiment && (
              <Experiment
                key={module}
                type={lesson.experiment}
                disabled={!running || busy}
                onRun={(parameters) => event("experiment", { parameters })}
              />
            )}
            <p>
              <strong>Apply it to this lesson:</strong> {lesson.experiment_task}
            </p>
            <div className="lab-reflection">
              <label htmlFor="lab-reflection">
                <h3>Leave a piece of reasoning</h3>
                <p>
                  {lesson.reflection ||
                    "What changed, why did it change, and which assumption matters?"}
                </p>
              </label>
              <textarea
                id="lab-reflection"
                placeholder="My prediction was… What changed was… The assumption that matters is…"
                value={reflection}
                onChange={(e) => {
                  setReflection(e.target.value);
                  sessionStorage.setItem(
                    `gym-lab-note:${courseId}:${module}`,
                    e.target.value,
                  );
                }}
              />
              <button
                className="button secondary"
                disabled={!active || busy}
                onClick={() =>
                  act(async () => {
                    await event("heartbeat", { reflection });
                    await load();
                  })
                }
              >
                <Check size={16} /> Save reflection
              </button>
              <small>
                {active
                  ? "Your reflection is an artifact of this activity; it is not automatically graded."
                  : "Your draft stays in this tab. Start a learning session to save it to the gym."}
              </small>
            </div>
            <h3>Keep these distinctions</h3>
            <ul>
              {lesson.takeaways.map((value) => (
                <li key={value}>{value}</li>
              ))}
            </ul>
            <p className="lab-pitfall">
              <strong>Common mistake:</strong> {lesson.pitfall}
            </p>
            <section className="lab-paper">
              <div className="row">
                <BookOpen size={21} />
                <h3>Your bridge to the paper</h3>
              </div>
              {paper && (
                <p>
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => {
                      if (active)
                        event("reading", {
                          parameters: { source_id: paper.id },
                        }).catch((e) => setError(e.message));
                    }}
                  >
                    {paper.title}
                  </a>
                  <small>
                    {paper.year} · {paper.status || paper.kind}
                  </small>
                </p>
              )}
              <p>{lesson.paper_bridge.why_it_matters}</p>
              <p>
                <strong>Read first:</strong> {lesson.paper_bridge.read_first}
              </p>
              <details>
                <summary>Claim, assumptions, and limits</summary>
                <p>{lesson.paper_bridge.claim}</p>
                <h4>What it assumes</h4>
                <ul>
                  {lesson.paper_bridge.assumptions.map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
                <h4>What it does not establish</h4>
                <ul>
                  {lesson.paper_bridge.limits.map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
              </details>
              <p>
                <strong>Reading task:</strong> {lesson.paper_bridge.exercise}
              </p>
            </section>
            <div className="lab-next">
              <h3>Now test your explanation</h3>
              <p>
                Three questions use the gym’s existing timers, confidence,
                hints, and scoring. A session linked to this guided lesson is
                recorded as supported practice. Revisit later for an independent
                check.
              </p>
              <button
                className="button"
                disabled={busy || !active}
                onClick={practice}
              >
                <Play size={16} /> Start linked practice
              </button>
              <button
                className="text-button"
                onClick={() => navigate("coursework")}
              >
                Open longer coursework exercises
              </button>
              {active && (
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await event("finish", { reflection });
                      sessionStorage.removeItem(`gym-lab-run:${courseId}`);
                      await load();
                    })
                  }
                >
                  Finish this study activity
                </button>
              )}
            </div>
          </article>
          <details className="lab-history">
            <summary>
              Activity evidence for this gym ({sessions.length})
            </summary>
            <p>
              Study duration and later scores are linked observations. They do
              not establish that a teaching method caused improvement.
            </p>
            {sessions.length ? (
              sessions
                .slice()
                .reverse()
                .slice(0, 10)
                .map((activity) => (
                  <div key={activity.id}>
                    <strong>{activity.module}</strong> ·{" "}
                    {elapsed(activity.active_seconds)} active ·{" "}
                    {activity.status}
                    {activity.practice_outcome && (
                      <span>
                        {" "}
                        · {activity.practice_outcome.attempt_count} practice
                        attempts, {activity.practice_outcome.score}/
                        {activity.practice_outcome.max_score} points so far
                        {activity.practice_outcome.pending_count
                          ? `, ${activity.practice_outcome.pending_count} awaiting assessment`
                          : ""}
                      </span>
                    )}
                  </div>
                ))
            ) : (
              <p>No activity recorded yet.</p>
            )}
          </details>
        </div>
      </div>
    </div>
  );
}
