import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import {
  connectGym,
  standardGymLink,
  type GymClient,
  type Lesson,
} from "@learning-gym/frontend";
import {
  useLabVisit,
  useResource,
  usePracticeSession,
} from "@learning-gym/frontend/react";
import { createPreviewClient } from "@learning-gym/frontend/preview";
import "./style.css";

function App({ client }: { client: GymClient }) {
  const labs = useResource(() => client.labs(), [client]);
  const [id, setId] = useState(""),
    [sessionId, setSessionId] = useState(""),
    [token, setToken] = useState("");
  return (
    <main>
      <h1>Your learning practice</h1>
      {client.config.preview && (
        <p role="status">
          Synthetic preview. Illustrative feedback; no learning evidence is
          saved.
        </p>
      )}
      <a href={standardGymLink()}>Open full Gym</a>
      {labs.error && (
        <section role="alert">
          <p>{labs.error.message}</p>
          {labs.error.status === 401 && (
            <label>
              Server access token
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
            </label>
          )}
          <button
            onClick={() => {
              if (token) client.setToken(token);
              labs.reload();
            }}
          >
            Retry connection
          </button>
        </section>
      )}
      {sessionId ? (
        <Session
          key={sessionId}
          client={client}
          id={sessionId}
          back={() => setSessionId("")}
        />
      ) : id ? (
        <Lab client={client} id={id} openSession={setSessionId} />
      ) : (
        <>
          {labs.loading && <p>Loading labs…</p>}
          {labs.data?.map((l) => (
            <article key={l.id}>
              <h2>{l.title}</h2>
              <p>{l.description}</p>
              <button onClick={() => setId(l.id)}>Open lab</button>
            </article>
          ))}
          {labs.data?.length === 0 && (
            <p>Publish a lab in the full Gym to start.</p>
          )}
        </>
      )}
    </main>
  );
}
function Lab({
  client,
  id,
  openSession,
}: {
  client: GymClient;
  id: string;
  openSession: (id: string) => void;
}) {
  const lab = useResource(() => client.lab(id), [client, id]);
  const [selected, setSelected] = useState(0);
  if (!lab.data)
    return (
      <p role={lab.error ? "alert" : "status"}>
        {lab.error?.message || "Loading lesson…"}
      </p>
    );
  return (
    <section>
      <h2>{lab.data.title}</h2>
      <nav>
        {lab.data.lessons.map((l, i) => (
          <button key={l.id} onClick={() => setSelected(i)}>
            {l.title}
          </button>
        ))}
      </nav>
      <Study
        key={lab.data.lessons[selected].id}
        client={client}
        labId={id}
        courseId={lab.data.course_id}
        lesson={lab.data.lessons[selected]}
        openSession={openSession}
      />
    </section>
  );
}
function Study({
  client,
  labId,
  courseId,
  lesson,
  openSession,
}: {
  client: GymClient;
  labId: string;
  courseId: string;
  lesson: Lesson;
  openSession: (id: string) => void;
}) {
  const visit = useLabVisit(client, labId, lesson.id),
    [error, setError] = useState("");
  const run = visit.data;
  const active = run?.status === "active";
  const pinned = active ? run.lesson_snapshot : lesson;
  const act = async (fn: () => Promise<unknown>) => {
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <article>
      <h3>{pinned.title}</h3>
      <p>{Math.round(run?.active_seconds || 0)} seconds of active study</p>
      <p role="alert">
        {error || visit.error?.message || visit.clockError?.message}
      </p>
      <button
        disabled={visit.loading}
        onClick={() =>
          act(() => (run?.running ? visit.event("pause") : visit.start(lesson)))
        }
      >
        {run?.running
          ? "Pause lesson"
          : active
            ? "Resume lesson"
            : "Start lesson"}
      </button>
      {pinned.activities.map((block) => (
        <section key={block.id}>
          <h4>{block.title}</h4>
          {"body" in block && <p>{block.body}</p>}
          {block.type === "assessment" ? (
            <button
              disabled={!active && !run?.session_id}
              onClick={() =>
                act(async () => {
                  const s = run?.session_id
                    ? await client.session(run.session_id)
                    : await visit.practice({
                        course_id: courseId,
                        module: lesson.module,
                        mode: block.mode,
                        count: block.count,
                      });
                  openSession(s.id);
                })
              }
            >
              Start practice
            </button>
          ) : (
            !["reading", "worked_example"].includes(block.type) && (
              <p>
                Add this block using the labs journey reference.{" "}
                <a
                  href={standardGymLink("lab", {
                    lab_id: labId,
                    lesson_id: lesson.id,
                  })}
                >
                  Use full Gym
                </a>
              </p>
            )
          )}
        </section>
      ))}
    </article>
  );
}
function Session({
  client,
  id,
  back,
}: {
  client: GymClient;
  id: string;
  back: () => void;
}) {
  const session = usePracticeSession(client, id),
    [answer, setAnswer] = useState(""),
    [error, setError] = useState("");
  const s = session.data;
  if (!s)
    return <p role="alert">{session.error?.message || "Loading practice…"}</p>;
  const item = s.items.find((i) => !s.answers[i.id]);
  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      setAnswer("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <article>
      <h2>Practice</h2>
      <p role="alert">{error || session.clockError?.message}</p>
      {s.status === "finished" ? (
        <>
          <p>
            {s.completion}. {s.score} / {s.max_score} points so far.
          </p>
          <button onClick={back}>Back to lesson</button>
        </>
      ) : (
        <>
          {item && (
            <>
              <h3>{item.stem}</h3>
              {item.type === "mcq" ? (
                item.options?.map((o) => (
                  <label key={o.label}>
                    <input
                      type="radio"
                      name="answer"
                      checked={answer === o.label}
                      onChange={() => setAnswer(o.label)}
                    />
                    {o.text}
                  </label>
                ))
              ) : item.type === "matching" ? (
                <p>
                  Implement matching from the practice reference.{" "}
                  <a href={standardGymLink("session", { session_id: id })}>
                    Continue in full Gym
                  </a>
                </p>
              ) : (
                <label>
                  Your reasoning
                  <textarea
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                  />
                </label>
              )}
              <button
                disabled={!answer}
                onClick={() => act(() => session.answer(item.id, answer))}
              >
                Save answer
              </button>
            </>
          )}
          <button onClick={() => act(() => session.finish())}>
            Finish practice ({Object.keys(s.answers).length}/{s.items.length}{" "}
            answered)
          </button>
        </>
      )}
    </article>
  );
}
const root = createRoot(document.getElementById("root")!);
const preview = new URLSearchParams(location.search).get("preview") === "1";
(preview ? Promise.resolve(createPreviewClient()) : connectGym())
  .then((client) => root.render(<App client={client} />))
  .catch((error) =>
    root.render(
      <main>
        <h1>Cannot open workspace</h1>
        <p role="alert">{error.message}</p>
      </main>,
    ),
  );
