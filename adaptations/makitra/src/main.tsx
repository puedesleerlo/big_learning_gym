import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  MakitraRoot,
  Button,
  Display,
  Tag,
  TextField,
  Illustration,
  SearchField,
} from "@makitra/react";
import {
  connectGym,
  standardGymLink,
  type GymClient,
  type Lab,
  type Lesson,
  type LabBlock,
  type Visit,
  type Session,
  type Json,
} from "@learning-gym/frontend";
import {
  useLabVisit,
  usePracticeSession,
  useResource,
} from "@learning-gym/frontend/react";
import {
  MediaActivity,
  VisualizationActivity,
  DiscussionActivity,
} from "@learning-gym/frontend/rich-activities";
import { createPreviewClient } from "@learning-gym/frontend/preview";
import "@makitra/react/fonts.css";
import "@makitra/react/makitra.css";
import "./style.css";

const minutes = (seconds: number) =>
  `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
const parseRoute = () =>
  Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
const go = (params: Record<string, string> = {}) => {
  location.hash = new URLSearchParams(params).toString();
};
function useAction() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  return {
    busy,
    error,
    async act<T>(fn: () => Promise<T>) {
      setBusy(true);
      setError(null);
      try {
        return await fn();
      } catch (e) {
        setError(e as Error);
        return undefined;
      } finally {
        setBusy(false);
      }
    },
  };
}
function ErrorPanel({
  error,
  client,
  retry,
}: {
  error?: Error | null;
  client: GymClient;
  retry?: () => unknown;
}) {
  const [token, setToken] = useState("");
  if (!error) return null;
  const needsToken = "status" in error && error.status === 401;
  return (
    <section className="notice error" role="alert">
      <p>{error.message}</p>
      {needsToken ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            client.setToken(token);
            retry ? retry() : location.reload();
          }}
        >
          <TextField
            label="Server access token"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <Button variant="primary" type="submit">
            Unlock workspace
          </Button>
        </form>
      ) : (
        retry && (
          <Button variant="quiet" onClick={() => retry()}>
            Try again
          </Button>
        )
      )}
    </section>
  );
}
function App({ client }: { client: GymClient }) {
  const [route, setRoute] = useState(parseRoute);
  useEffect(() => {
    const onHash = () => {
      setRoute(parseRoute());
      window.scrollTo(0, 0);
    };
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);
  return (
    <MakitraRoot className="kitchen">
      <a
        className="skip"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <header className="masthead">
        <a className="wordmark" href="#" onClick={() => go()}>
          <Illustration name="makitra-bowl" width={52} height={52} />
          <span>
            Practice
            <br />
            <strong>kitchen</strong>
          </span>
        </a>
        <nav aria-label="Main">
          <a href="#">Your labs</a>
          <a href={standardGymLink()}>Full learning gym</a>
        </nav>
        <Tag>
          {client.config.preview ? "Design preview" : "Personal workspace"}
        </Tag>
      </header>
      {client.config.preview && (
        <aside className="preview-notice">
          Synthetic design preview. Responses and example scores stay in this
          tab; they are not learning evidence.
        </aside>
      )}
      <main id="main-content" tabIndex={-1}>
        {route.session ? (
          <Practice key={route.session} client={client} id={route.session} />
        ) : route.lab ? (
          <LabScreen
            key={route.lab}
            client={client}
            id={route.lab}
            lessonId={route.lesson}
          />
        ) : (
          <Catalog client={client} />
        )}
      </main>
      <footer>
        <span>A little practice. A clearer idea.</span>
        <a href={standardGymLink("progress")}>View learning evidence</a>
      </footer>
    </MakitraRoot>
  );
}
function Catalog({ client }: { client: GymClient }) {
  const resource = useResource(() => client.labs(), [client]);
  const [search, setSearch] = useState("");
  const last = client.storage.getItem("gym-session");
  return (
    <>
      <section className="welcome">
        <div>
          <p className="eyebrow">Make room for an idea</p>
          <Display as="h1" size="4xl">
            Good questions
            <br />
            take practice.
          </Display>
          <p className="lede">
            Pick a lab. Try something small. Keep a record of how your thinking
            changes.
          </p>
          {last && (
            <Button
              variant="quiet"
              icon="play"
              onClick={() => go({ session: last })}
            >
              Resume practice
            </Button>
          )}
        </div>
        <Illustration
          className="welcome-art"
          name="makitra-bowl"
          width={270}
          height={240}
        />
      </section>
      <div className="section-heading">
        <h2>Your learning labs</h2>
        <SearchField
          label="Search labs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <ErrorPanel
        error={resource.error}
        client={client}
        retry={resource.reload}
      />
      {resource.loading && <p role="status">Opening your labs…</p>}
      <div className="lab-list">
        {resource.data
          ?.filter((l) =>
            `${l.title} ${l.course_title}`
              .toLowerCase()
              .includes(search.toLowerCase()),
          )
          .map((lab, i) => (
            <article key={lab.id} className="lab-card">
              <div className="lab-number" aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div>
                <Tag>{lab.course_title}</Tag>
                <Display as="h3" size="xl">
                  {lab.title}
                </Display>
                <p>{lab.description}</p>
                <span className="meta">{lab.lesson_count} lessons</span>
              </div>
              <Button
                variant="secondary"
                icon="play"
                onClick={() => go({ lab: lab.id })}
              >
                Open lab
              </Button>
            </article>
          ))}
      </div>
      {resource.data?.length === 0 && (
        <section className="notice">
          <h3>Your first lab starts with a source.</h3>
          <p>
            Add a course and publish a lab in the full Gym, then come back here.
          </p>
          <a href={standardGymLink("labs")}>Create a lab</a>
        </section>
      )}
      {!!resource.data?.length &&
        !resource.data.some((l) =>
          `${l.title} ${l.course_title}`
            .toLowerCase()
            .includes(search.toLowerCase()),
        ) && <p>No labs match “{search}”. Try another word.</p>}
    </>
  );
}
function LabScreen({
  client,
  id,
  lessonId,
}: {
  client: GymClient;
  id: string;
  lessonId?: string;
}) {
  const resource = useResource(() => client.lab(id), [client, id]);
  if (!resource.data)
    return (
      <>
        <a href="#">Back to labs</a>
        <ErrorPanel
          error={resource.error}
          client={client}
          retry={resource.reload}
        />
        {resource.loading && <p role="status">Opening this lab…</p>}
      </>
    );
  const lab = resource.data;
  if (!lab.lessons.length)
    return (
      <section className="notice">
        <h1>This lab has no lessons</h1>
        <a href={standardGymLink("labs")}>Browse in the full Gym</a>
      </section>
    );
  const lesson = lab.lessons.find((l) => l.id === lessonId) || lab.lessons[0];
  return (
    <>
      <a className="back-link" href="#">
        Back to labs
      </a>
      <header className="lab-title">
        <Tag>{lab.course_title}</Tag>
        <Display as="h1" size="3xl">
          {lab.title}
        </Display>
        <p>{lab.description}</p>
      </header>
      <div className="lesson-layout">
        <nav className="lesson-nav" aria-label="Lessons">
          <h2>In this lab</h2>
          {lab.lessons.map((l, i) => (
            <a
              href={`#${new URLSearchParams({ lab: lab.id, lesson: l.id })}`}
              key={l.id}
              aria-current={lesson.id === l.id ? "step" : undefined}
            >
              <span>{i + 1}</span>
              <div>
                {l.title}
                <small>{l.minutes} min of planned practice</small>
              </div>
            </a>
          ))}
        </nav>
        <LessonView key={lesson.id} client={client} lab={lab} lesson={lesson} />
      </div>
    </>
  );
}
function LessonView({
  client,
  lab,
  lesson: currentLesson,
}: {
  client: GymClient;
  lab: Lab;
  lesson: Lesson;
}) {
  const visit = useLabVisit(client, lab.id, currentLesson.id),
    action = useAction();
  const run = visit.data;
  const lesson = run?.status === "active" ? run.lesson_snapshot : currentLesson;
  const enabled = !!run?.running && run.status === "active";
  const [recovery, setRecovery] = useState<
    { id: string; started_at: string }[] | null
  >(null);
  if (lesson.experiment || !lesson.activities?.length)
    return (
      <article className="lesson">
        <Display as="h2" size="2xl">
          {lesson.title}
        </Display>
        <p>This lesson uses the original interactive presentation.</p>
        <a
          href={standardGymLink("lab", {
            lab_id: lab.id,
            lesson_id: lesson.id,
          })}
        >
          Open this lesson in the full Gym
        </a>
      </article>
    );
  const practice = async (block: Extract<LabBlock, { type: "assessment" }>) => {
    if (run?.session_id) {
      go({ session: run.session_id });
      return;
    }
    const result = await action.act(() =>
      visit.practice({
        course_id: lab.course_id,
        module: lesson.module,
        mode: block.mode,
        count: block.count,
      }),
    );
    if (result) go({ session: result.id });
  };
  return (
    <article className="lesson">
      <div className="lesson-intro">
        <span className="meta">{lesson.minutes} minutes to explore</span>
        <Display as="h2" size="2xl">
          {lesson.title}
        </Display>
        <ul>
          {lesson.objectives.map((o) => (
            <li key={o}>{o}</li>
          ))}
        </ul>
      </div>
      <div className="visit-bar">
        <span>
          {run
            ? `${minutes(run.active_seconds)} of active study`
            : "Ready when you are"}
          <small>
            {run?.status === "finished"
              ? "Study visit saved"
              : enabled
                ? "Study timer running"
                : "Study timer paused"}
          </small>
        </span>
        <Button
          variant="primary"
          icon={enabled ? "pause" : "play"}
          disabled={action.busy || visit.loading}
          onClick={() =>
            action.act(() =>
              enabled ? visit.event("pause") : visit.start(currentLesson),
            )
          }
        >
          {enabled
            ? "Pause lesson"
            : run?.status === "active"
              ? "Resume lesson"
              : "Start lesson"}
        </Button>
      </div>
      <ErrorPanel
        error={visit.error || action.error || visit.clockError}
        client={client}
        retry={visit.reload}
      />
      {run && client.storage.getItem(`gym-lab-pending:${run.id}`) && (
        <div className="notice">
          <p>A practice start needs to be recovered before continuing.</p>
          <Button
            variant="secondary"
            onClick={() =>
              action.act(async () =>
                setRecovery(await client.recoveryCandidates(run)),
              )
            }
          >
            Find interrupted practice
          </Button>
          {recovery?.map((s) => (
            <Button
              key={s.id}
              variant="quiet"
              onClick={() =>
                action.act(async () => {
                  const session = await client.linkPractice(run.id, s.id);
                  go({ session: session.id });
                })
              }
            >
              Recover practice from{" "}
              {new Date(s.started_at).toLocaleTimeString()}
            </Button>
          ))}
          {recovery?.length === 0 && (
            <div>
              <p>
                No matching active session was found. Inspect recent sessions in
                the <a href={standardGymLink()}>full Gym</a> before starting
                another.
              </p>
              <Button
                variant="quiet"
                onClick={() => {
                  client.abandonPendingPractice(run.id);
                  setRecovery(null);
                }}
              >
                I checked; allow a new practice start
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="activity-stack">
        {lesson.activities.map((block) => (
          <Activity
            key={`${run?.id || "browse"}:${block.id}`}
            block={block}
            client={client}
            run={run}
            enabled={enabled && !action.busy}
            event={visit.event}
            discuss={visit.discuss}
            practice={practice}
          />
        ))}
      </div>
      {run?.status === "active" && (
        <div className="lesson-finish">
          <p>
            Finishing saves a study visit. Practice provides separate evidence.
          </p>
          <Button
            variant="secondary"
            disabled={action.busy}
            onClick={() => action.act(() => visit.event("finish"))}
          >
            Finish lesson
          </Button>
        </div>
      )}
    </article>
  );
}
type ActivityProps = {
  block: LabBlock;
  client: GymClient;
  run: Visit | null;
  enabled: boolean;
  event: ReturnType<typeof useLabVisit>["event"];
  discuss: ReturnType<typeof useLabVisit>["discuss"];
  practice: (block: Extract<LabBlock, { type: "assessment" }>) => Promise<void>;
};
function Activity({
  block,
  client,
  run,
  enabled,
  event,
  discuss,
  practice,
}: ActivityProps) {
  const action = useAction();
  const key = `experience-response:${run?.id || "browse"}:${block.id}`;
  const [response, setResponse] = useState(
    () =>
      client.storage.getItem(key) ?? run?.responses?.[block.id]?.value ?? "",
  );
  const [saved, setSaved] = useState(false);
  const inputs = block.type === "parameter_experiment" ? block.inputs : [];
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(
      inputs.map((p) => [
        p.key,
        run?.experiment_results?.[block.id]?.inputs[p.key] ?? p.initial,
      ]),
    ),
  );
  const richProps = { enabled, preview: false, run, onEvent: event };
  if (
    ![
      "reading",
      "worked_example",
      "prediction",
      "reflection",
      "parameter_experiment",
      "assessment",
      "coursework",
      "media",
      "visualization",
      "discussion",
    ].includes(block.type)
  )
    return (
      <section className="notice">
        <h3>{block.title}</h3>
        <p>This activity requires another presentation.</p>
        <a href={standardGymLink("labs")}>Open the full Gym</a>
      </section>
    );
  return (
    <section
      className={`activity activity-${block.type}`}
      aria-label={block.title}
    >
      <div className="activity-heading">
        <h3>{block.title}</h3>
        <span className="meta">{block.type.replaceAll("_", " ")}</span>
      </div>
      {(block.type === "reading" || block.type === "worked_example") && (
        <>
          <p className="prose">{block.body}</p>
          <Button
            variant="quiet"
            disabled={!enabled || action.busy}
            onClick={() =>
              action.act(async () => {
                await event("reading", {
                  parameters: { activity_id: block.id },
                });
                setSaved(true);
              })
            }
          >
            {saved ? "Reading recorded" : "Record this reading"}
          </Button>
        </>
      )}
      {(block.type === "prediction" || block.type === "reflection") && (
        <>
          <label htmlFor={block.id} className="prose">
            {block.prompt}
          </label>
          <textarea
            id={block.id}
            className="mk-field__control"
            value={response}
            maxLength={12000}
            disabled={!enabled}
            onChange={(e) => {
              setResponse(e.target.value);
              client.storage.setItem(key, e.target.value);
              setSaved(false);
            }}
          />
          <Button
            variant="secondary"
            disabled={!enabled || action.busy || !response.trim()}
            onClick={() =>
              action.act(async () => {
                await event("response", {
                  parameters: { activity_id: block.id, value: response },
                });
                setSaved(true);
                client.storage.removeItem(key);
              })
            }
          >
            {saved ? "Response saved" : "Save response"}
          </Button>
          <small>Saved as study evidence; not automatically graded.</small>
        </>
      )}
      {block.type === "parameter_experiment" && (
        <>
          <p>{block.description}</p>
          {block.inputs.map((p) => (
            <label className="range-field" key={p.key}>
              {p.label}: {values[p.key]}
              <input
                type="range"
                min={p.min}
                max={p.max}
                step={p.step}
                value={values[p.key]}
                disabled={!enabled}
                onChange={(e) =>
                  setValues({ ...values, [p.key]: +e.target.value })
                }
              />
            </label>
          ))}
          <Button
            variant="secondary"
            disabled={!enabled || action.busy}
            onClick={() =>
              action.act(() =>
                event("experiment", {
                  parameters: { activity_id: block.id, inputs: values },
                }),
              )
            }
          >
            Run experiment
          </Button>
          {run?.experiment_results?.[block.id] && (
            <output aria-live="polite">
              {block.output_label}: {run.experiment_results[block.id].output}{" "}
              {block.unit}
            </output>
          )}
        </>
      )}
      {block.type === "assessment" && (
        <>
          <p>
            Try {block.count} questions. Your preparation stays attached to this
            practice.
          </p>
          <Button
            variant="secondary"
            icon="play"
            disabled={(!enabled && !run?.session_id) || action.busy}
            onClick={() => practice(block)}
          >
            {run?.session_id ? "Open practice" : "Start practice"}
          </Button>
        </>
      )}
      {block.type === "coursework" && (
        <>
          <p>Continue this assignment with its rubric in the full Gym.</p>
          <a
            href={standardGymLink("coursework", {
              assignment_id: block.assignment_id,
            })}
          >
            Open coursework
          </a>
        </>
      )}
      {block.type === "media" && <MediaActivity {...richProps} block={block} />}
      {block.type === "visualization" && (
        <VisualizationActivity {...richProps} block={block} />
      )}
      {block.type === "discussion" && (
        <DiscussionActivity {...richProps} block={block} onDiscuss={discuss} />
      )}
      <ErrorPanel error={action.error} client={client} />
    </section>
  );
}
function Feedback({ value }: { value?: Record<string, Json> | null }) {
  if (!value) return null;
  const records = (key: string) =>
    Array.isArray(value[key])
      ? value[key].filter(
          (v): v is Record<string, Json> =>
            !!v && typeof v === "object" && !Array.isArray(v),
        )
      : [];
  return (
    <div className="feedback">
      <small>
        {value.kind === "provisional_model_judgment"
          ? "Provisional model feedback — open to correction."
          : "Answer-key feedback"}
      </small>
      {["explanation", "feedback", "summary"].map((key) =>
        value[key] ? <p key={key}>{String(value[key])}</p> : null,
      )}
      {value.key && <p>Answer: {String(value.key)}</p>}
      {records("options").map((o) => (
        <p key={String(o.label)}>
          <strong>{String(o.label)}.</strong> {String(o.why || "")}
        </p>
      ))}
      {records("prompts").map((p) => (
        <p key={String(p.id)}>
          <strong>{String(p.text || p.id)}:</strong> {String(p.why || "")}
        </p>
      ))}
      {records("criteria").map((c) => (
        <section key={String(c.name)}>
          <h3>
            {String(c.name)} · {Math.round(Number(c.score) * 100)}%
          </h3>
          <blockquote>{String(c.evidence_quote || "")}</blockquote>
          <p>{String(c.explanation || "")}</p>
        </section>
      ))}
      {value.next_step && (
        <p>
          <strong>Next step:</strong> {String(value.next_step)}
        </p>
      )}
      {value.uncertainty && <p>{String(value.uncertainty)}</p>}
      {value.ref && <small>{String(value.ref)}</small>}
    </div>
  );
}
function Practice({ client, id }: { client: GymClient; id: string }) {
  const session = usePracticeSession(client, id),
    action = useAction();
  const [index, setIndex] = useState(0),
    [confirmFinish, setConfirmFinish] = useState(false);
  const data = session.data;
  const restored = useRef(false);
  useEffect(() => {
    if (data && !restored.current) {
      setIndex(
        Math.max(
          0,
          data.items.findIndex((i) => i.id === data.current_item),
        ),
      );
      restored.current = true;
    }
  }, [data]);
  useEffect(() => {
    client.storage.setItem("gym-session", id);
  }, [id, client]);
  if (!data)
    return (
      <>
        <a href="#">Back to labs</a>
        <ErrorPanel
          error={session.error}
          client={client}
          retry={session.reload}
        />
        {session.loading && <p role="status">Opening your practice…</p>}
      </>
    );
  if (data.mode === "simulation")
    return (
      <p>
        Continue this simulation in the{" "}
        <a href={standardGymLink("session", { session_id: id })}>full Gym</a>.
      </p>
    );
  if (data.status === "finished")
    return (
      <section className="review">
        <a href="#">Back to labs</a>
        <Display as="h1" size="3xl">
          Practice, reflected.
        </Display>
        <p>
          {data.completion === "complete"
            ? "All questions answered."
            : "Unanswered work remains unfinished."}{" "}
          {minutes(data.active_seconds)} of active work.
        </p>
        <Tag>
          {data.score ?? 0} / {data.max_score ?? 0} points so far
        </Tag>
        {!!data.pending_assessments && (
          <div className="notice">
            <p>
              {data.pending_assessments} model assessments pending. These
              judgments remain provisional.
            </p>
            <Button variant="secondary" onClick={session.reload}>
              Refresh feedback
            </Button>
          </div>
        )}
        {data.review?.map((entry) => (
          <article className="activity" key={entry.item.id}>
            <h2>{entry.item.stem}</h2>
            <p>
              Your answer:{" "}
              {typeof entry.attempt?.answer === "string"
                ? entry.attempt.answer
                : JSON.stringify(entry.attempt?.answer ?? "Unanswered")}
            </p>
            <Feedback
              value={
                (entry.attempt?.feedback as Record<string, Json>) ||
                entry.feedback
              }
            />
          </article>
        ))}
      </section>
    );
  if (!data.items.length)
    return (
      <section className="notice">
        <h1>No questions are available</h1>
        <a href={standardGymLink("session", { session_id: id })}>
          Inspect this session in the full Gym
        </a>
      </section>
    );
  const item = data.items[Math.min(index, data.items.length - 1)];
  return (
    <section className="practice">
      <a href="#">Back to labs</a>
      <div className="practice-heading">
        <div>
          <Tag>{data.mode}</Tag>
          <Display as="h1" size="2xl">
            Give the idea a try.
          </Display>
        </div>
        <span>
          {index + 1} of {data.items.length}
          <small>{minutes(data.active_seconds)} active</small>
        </span>
      </div>
      <progress
        aria-label="Answered questions"
        max={data.items.length}
        value={Object.keys(data.answers).length}
      />
      <ErrorPanel
        error={session.error || session.clockError || action.error}
        client={client}
        retry={session.reload}
      />
      <div className="practice-tools">
        <Button
          variant="quiet"
          icon={data.running ? "pause" : "play"}
          onClick={() =>
            action.act(() =>
              session.timer(data.running ? "pause" : "resume", item.id),
            )
          }
        >
          {data.running ? "Pause practice" : "Resume practice"}
        </Button>
        <Button variant="quiet" onClick={() => setConfirmFinish(true)}>
          Finish practice
        </Button>
      </div>
      {!data.running && (
        <p className="notice">Practice is paused. Resume when you are ready.</p>
      )}
      {data.guided_activity_id && (
        <p className="support-note">
          This practice includes your earlier lesson preparation. It is recorded
          as supported work.
        </p>
      )}
      <Question
        key={item.id}
        client={client}
        session={data}
        item={item}
        save={session.answer}
        refresh={session.reload}
      />
      <nav className="question-nav" aria-label="Questions">
        <Button
          variant="secondary"
          disabled={index === 0 || action.busy}
          onClick={() =>
            action.act(async () => {
              await session.timer("heartbeat", data.items[index - 1].id);
              setIndex(index - 1);
            })
          }
        >
          Previous question
        </Button>
        {index < data.items.length - 1 ? (
          <Button
            variant="secondary"
            disabled={action.busy}
            onClick={() =>
              action.act(async () => {
                await session.timer("heartbeat", data.items[index + 1].id);
                setIndex(index + 1);
              })
            }
          >
            Next question
          </Button>
        ) : (
          <Button variant="secondary" onClick={() => setConfirmFinish(true)}>
            Finish and review
          </Button>
        )}
      </nav>
      {confirmFinish && (
        <section className="notice" aria-label="Finish confirmation">
          <h2>Finish this practice?</h2>
          <p>
            {Object.keys(data.answers).length} of {data.items.length} answers
            saved. Unanswered questions stay unfinished.
          </p>
          <Button
            variant="primary"
            disabled={action.busy}
            onClick={() => action.act(() => session.finish())}
          >
            Save and finish
          </Button>
          <Button variant="quiet" onClick={() => setConfirmFinish(false)}>
            Keep practicing
          </Button>
        </section>
      )}
    </section>
  );
}
function Question({
  client,
  session,
  item,
  save,
  refresh,
}: {
  client: GymClient;
  session: Session;
  item: Session["items"][number];
  save: (
    itemId: string,
    value: string | Record<string, string>,
    confidence?: number | null,
  ) => Promise<unknown>;
  refresh: () => unknown;
}) {
  const key = `experience-answer:${session.id}:${item.id}`;
  const prior = session.answers[item.id];
  const [answer, setAnswer] = useState<string | Record<string, string>>(
    () =>
      prior?.answer ??
      JSON.parse(client.storage.getItem(key) || "null") ??
      (item.type === "matching" ? {} : ""),
  );
  const [confidence, setConfidence] = useState(""),
    [aid, setAid] = useState<Json>();
  const action = useAction();
  const update = (value: typeof answer) => {
    setAnswer(value);
    client.storage.setItem(key, JSON.stringify(value));
  };
  const disabled = !!prior || !session.running || action.busy;
  const valid =
    item.type === "matching"
      ? item.prompts?.every((p) => typeof answer === "object" && answer[p.id])
      : typeof answer === "string" &&
        (item.type === "mcq" ? !!answer : answer.trim().length >= 10);
  return (
    <article className="question">
      <span className="meta">{item.points} points</span>
      {item.vignette && (
        <aside className="notice">
          <h3>{item.vignette.title}</h3>
          <p>{item.vignette.text}</p>
          {item.vignette.table && (
            <div className="table-scroll">
              <table>
                <caption>{item.vignette.table.caption}</caption>
                <thead>
                  <tr>
                    {item.vignette.table.columns.map((column, i) => (
                      <th key={i} scope="col">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {item.vignette.table.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </aside>
      )}
      <h2>{item.stem}</h2>
      {item.type === "mcq" ? (
        <fieldset disabled={disabled}>
          <legend>Choose an answer</legend>
          {item.options?.map((option) => (
            <label className="answer-option" key={option.label}>
              <input
                type="radio"
                name={item.id}
                value={option.label}
                checked={answer === option.label}
                onChange={() => update(option.label)}
              />
              <span>
                {option.label}. {option.text}
              </span>
            </label>
          ))}
        </fieldset>
      ) : item.type === "matching" ? (
        item.prompts?.map((prompt) => (
          <label className="matching-field" key={prompt.id}>
            {prompt.text}
            <select
              className="mk-field__control"
              disabled={disabled}
              value={typeof answer === "object" ? answer[prompt.id] || "" : ""}
              onChange={(e) =>
                update({
                  ...(typeof answer === "object" ? answer : {}),
                  [prompt.id]: e.target.value,
                })
              }
            >
              <option value="">Choose a match</option>
              {item.terms?.map((term) => (
                <option key={term.id} value={term.id}>
                  {term.text}
                </option>
              ))}
            </select>
          </label>
        ))
      ) : (
        <>
          <label htmlFor="reasoning">
            Your reasoning
            {item.type === "coding" ? " (code is saved, not executed)" : ""}
          </label>
          <textarea
            id="reasoning"
            className={`mk-field__control ${item.type === "coding" ? "code-answer" : ""}`}
            value={typeof answer === "string" ? answer : ""}
            disabled={disabled}
            onChange={(e) => update(e.target.value)}
          />
          {!!item.rubric?.length && (
            <details>
              <summary>Assessment rubric</summary>
              {item.rubric.map((c) => (
                <p key={c.name}>
                  {c.name} ({Math.round(c.weight * 100)}%):{" "}
                  {c.anchors.join(" / ")}
                </p>
              ))}
            </details>
          )}
        </>
      )}
      {!prior ? (
        <>
          <label className="matching-field">
            Confidence (optional)
            <select
              className="mk-field__control"
              value={confidence}
              onChange={(e) => setConfidence(e.target.value)}
            >
              <option value="">Not recorded</option>
              {[0.25, 0.5, 0.75, 1].map((v) => (
                <option key={v} value={v}>
                  {v * 100}%
                </option>
              ))}
            </select>
          </label>
          <Button
            variant="primary"
            disabled={disabled || !valid}
            onClick={() =>
              action.act(async () => {
                await save(item.id, answer, confidence ? +confidence : null);
                client.storage.removeItem(key);
              })
            }
          >
            Save answer
          </Button>
        </>
      ) : prior.status === "pending" ? (
        <div className="notice">
          <p>Your answer is saved. Model assessment is pending.</p>
          <Button variant="secondary" onClick={() => refresh()}>
            Refresh feedback
          </Button>
        </div>
      ) : (
        <>
          <Tag>
            {prior.score ?? "Unscored"} / {item.points} points
          </Tag>
          <Feedback value={prior.feedback} />
        </>
      )}
      <div className="aid-row">
        <Button
          variant="quiet"
          disabled={action.busy || !session.running}
          onClick={() =>
            action.act(async () =>
              setAid((await client.aid(session.id, item.id, "hint")).content),
            )
          }
        >
          Get a hint
        </Button>
        <Button
          variant="quiet"
          disabled={action.busy || !session.running}
          onClick={() =>
            action.act(async () =>
              setAid((await client.aid(session.id, item.id, "plain")).content),
            )
          }
        >
          Explain plainly
        </Button>
      </div>
      {aid !== undefined && (
        <aside className="notice">
          <p>{typeof aid === "string" ? aid : JSON.stringify(aid)}</p>
          <small>This help is recorded with your work.</small>
        </aside>
      )}
      <ErrorPanel error={action.error} client={client} />
    </article>
  );
}
const root = createRoot(document.getElementById("root")!);
const preview = new URLSearchParams(location.search).get("preview") === "1";
(preview ? Promise.resolve(createPreviewClient()) : connectGym())
  .then((client) => root.render(<App client={client} />))
  .catch((error) =>
    root.render(
      <MakitraRoot className="kitchen">
        <main>
          <Display as="h1" size="2xl">
            Cannot open your workspace
          </Display>
          <p role="alert">{error.message}</p>
          <Button onClick={() => location.reload()}>Try again</Button>
        </main>
      </MakitraRoot>,
    ),
  );
