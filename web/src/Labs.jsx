import React, { useEffect, useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  BookOpen,
  Check,
  ChevronRight,
  Eye,
  FlaskConical,
  Plus,
  Trash2,
} from "lucide-react";
import { LabPreview } from "./GuidedLab.jsx";
import { activityLabels } from "./LabActivities.jsx";
import "./guided-lab.css";

const id = (prefix) =>
  `${prefix}_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
const lines = (text) =>
  text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
const move = (items, from, delta) => {
  const next = [...items];
  [next[from], next[from + delta]] = [next[from + delta], next[from]];
  return next;
};
function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function ListField({ label, value = [], onChange }) {
  return (
    <Field label={label} hint="One per line">
      <textarea
        value={value.join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))}
      />
    </Field>
  );
}
function ChoiceList({ legend, choices, selected = [], onChange, empty }) {
  return (
    <fieldset className="lab-choice-list">
      <legend>{legend}</legend>
      {choices.length ? (
        choices.map((choice) => (
          <label key={choice.id}>
            <input
              type="checkbox"
              checked={selected.includes(choice.id)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, choice.id]
                    : selected.filter((v) => v !== choice.id),
                )
              }
            />
            <span>
              {choice.title}
              {choice.detail && <small>{choice.detail}</small>}
            </span>
          </label>
        ))
      ) : (
        <small>{empty || "No choices available yet."}</small>
      )}
    </fieldset>
  );
}
const initialLesson = (module) => ({
  id: id("lesson"),
  module: module || "",
  title: "New lesson",
  minutes: 20,
  stage: "",
  prerequisites: [],
  objectives: [],
  source_ids: [],
  activities: [],
});

export default function Labs({
  api,
  courses,
  initialCourseId = "",
  navigate,
  editLab,
  onEdit,
  onPublished,
}) {
  const [filter, setFilter] = useState(initialCourseId),
    [labs, setLabs] = useState(null),
    [error, setError] = useState("");
  const [editing, setEditing] = useState(editLab || null),
    [creating, setCreating] = useState(false),
    [loadingEdit, setLoadingEdit] = useState(false);
  const [registry, setRegistry] = useState([]);
  useEffect(() => {
    setFilter(initialCourseId);
  }, [initialCourseId]);
  useEffect(() => {
    let live = true;
    setLabs(null);
    api(`/labs${filter ? `?course_id=${encodeURIComponent(filter)}` : ""}`)
      .then((result) => {
        if (live) setLabs(result);
      })
      .catch((e) => {
        if (live) {
          setError(e.message);
          setLabs([]);
        }
      });
    return () => {
      live = false;
    };
  }, [filter]);
  useEffect(() => {
    setEditing(editLab || null);
  }, [editLab]);
  useEffect(() => {
    api("/lab-activity-types")
      .then((r) => setRegistry(r.types || []))
      .catch((e) => setError(e.message));
  }, []);
  if (creating || editing)
    return (
      <LabEditor
        key={editing?.id || "new"}
        api={api}
        courses={courses}
        initialCourseId={filter}
        initialLab={editing}
        registry={registry}
        onCancel={() => {
          setCreating(false);
          setEditing(null);
          onEdit?.(null);
        }}
        onPublished={(labId) => {
          setCreating(false);
          setEditing(null);
          onEdit?.(null);
          onPublished?.();
          navigate("lab", labId);
        }}
        navigate={navigate}
      />
    );
  return (
    <div className="labs-catalog">
      <header className="page-head">
        <div>
          <h1>Your labs</h1>
          <p>
            Follow a lesson, try an activity, then test what you understand.
          </p>
        </div>
        <button
          className="button"
          disabled={!courses.length}
          onClick={() => setCreating(true)}
        >
          <Plus size={17} />
          Create lab
        </button>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="lab-catalog-filter">
        <Field label="Gym">
          <select
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setError("");
            }}
          >
            <option value="">All gyms</option>
            {courses.map((course) => (
              <option value={course.id} key={course.id}>
                {course.title}
              </option>
            ))}
          </select>
        </Field>
        <p>
          Each lab belongs to a gym and shares its sources, practice questions,
          and learning evidence.
        </p>
      </div>
      {labs === null ? (
        <p>Loading labs…</p>
      ) : !labs.length ? (
        <div className="empty">
          <FlaskConical size={30} />
          <h3>
            {filter
              ? "No labs in this gym yet"
              : "Create a path through your material"}
          </h3>
          <p>
            Add lessons, choose activities, and preview the learning experience
            before publishing.
          </p>
          {courses.length ? (
            <button className="button" onClick={() => setCreating(true)}>
              Create the first lab
            </button>
          ) : (
            <button className="button" onClick={() => navigate("create")}>
              Create a gym first
            </button>
          )}
        </div>
      ) : (
        <div className="lab-catalog-list">
          {labs.map((lab) => (
            <article className="lab-catalog-row" key={lab.id}>
              <div className="lab-catalog-mark">
                <BookOpen size={23} />
              </div>
              <div className="lab-catalog-description">
                <small>
                  {lab.course_title ||
                    courses.find((c) => c.id === lab.course_id)?.title}
                </small>
                <h2>
                  <button
                    className="lab-title-link"
                    onClick={() => navigate("lab", lab.id)}
                  >
                    {lab.title}
                  </button>
                </h2>
                <p>{lab.description}</p>
                <span className="muted">
                  {lab.lesson_count}{" "}
                  {lab.lesson_count === 1 ? "lesson" : "lessons"}
                  {lab.activity_count > 0
                    ? ` · ${lab.activity_count} reusable ${lab.activity_count === 1 ? "activity" : "activities"}`
                    : ""}
                </span>
              </div>
              <div className="lab-catalog-actions">
                <button
                  className="button"
                  onClick={() => navigate("lab", lab.id)}
                >
                  Open lab <ChevronRight size={15} />
                </button>
                <button
                  className="text-button"
                  disabled={loadingEdit}
                  onClick={async () => {
                    setLoadingEdit(true);
                    setError("");
                    try {
                      setEditing(
                        await api(`/labs/${encodeURIComponent(lab.id)}`),
                      );
                    } catch (e) {
                      setError(e.message);
                    } finally {
                      setLoadingEdit(false);
                    }
                  }}
                >
                  Edit lab
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function ActivityEditor({ block, onChange, assignments }) {
  const set = (name, value) => onChange({ ...block, [name]: value });
  const setInput = (index, name, value) =>
    set(
      "inputs",
      block.inputs.map((input, i) =>
        i === index ? { ...input, [name]: value } : input,
      ),
    );
  return (
    <div className="lab-block-fields">
      <Field label="Activity title">
        <input
          value={block.title || ""}
          onChange={(e) => set("title", e.target.value)}
        />
      </Field>
      {["reading", "worked_example"].includes(block.type) && (
        <Field
          label={block.type === "reading" ? "Reading" : "Worked example"}
          hint="Plain text; use blank lines between paragraphs."
        >
          <textarea
            className="lab-long-text"
            value={block.body || ""}
            onChange={(e) => set("body", e.target.value)}
          />
        </Field>
      )}
      {["prediction", "reflection"].includes(block.type) && (
        <Field label="Prompt">
          <textarea
            value={block.prompt || ""}
            onChange={(e) => set("prompt", e.target.value)}
          />
        </Field>
      )}
      {block.type === "parameter_experiment" && (
        <>
          <Field label="What should the learner explore?">
            <textarea
              value={block.description || ""}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          <div className="form-row">
            <Field label="Starting value">
              <input
                type="number"
                step="any"
                value={block.offset ?? 0}
                onChange={(e) => set("offset", +e.target.value)}
              />
            </Field>
            <Field label="Result label">
              <input
                value={block.output_label || ""}
                onChange={(e) => set("output_label", e.target.value)}
              />
            </Field>
            <Field label="Unit (optional)">
              <input
                value={block.unit || ""}
                onChange={(e) => set("unit", e.target.value)}
              />
            </Field>
          </div>
          <p className="muted">
            The model adds each input × its contribution to the starting value.
            Describe the assumptions in the activity text.
          </p>
          {(block.inputs || []).map((input, index) => (
            <fieldset className="lab-input-editor" key={input.key}>
              <legend>Input {index + 1}</legend>
              <div className="form-row">
                <Field label="Label">
                  <input
                    value={input.label}
                    onChange={(e) => setInput(index, "label", e.target.value)}
                  />
                </Field>
                <Field label="Contribution per unit">
                  <input
                    type="number"
                    step="any"
                    value={input.coefficient ?? 1}
                    onChange={(e) =>
                      setInput(index, "coefficient", +e.target.value)
                    }
                  />
                </Field>
              </div>
              <div className="lab-number-grid">
                {[
                  ["min", "Minimum"],
                  ["max", "Maximum"],
                  ["step", "Step"],
                  ["initial", "Starting input"],
                ].map(([name, label]) => (
                  <Field label={label} key={name}>
                    <input
                      type="number"
                      step="any"
                      value={input[name] ?? 1}
                      onChange={(e) => setInput(index, name, +e.target.value)}
                    />
                  </Field>
                ))}
              </div>
              <button
                className="text-button"
                disabled={block.inputs.length <= 1}
                onClick={() =>
                  set(
                    "inputs",
                    block.inputs.filter((_, i) => i !== index),
                  )
                }
              >
                Remove input
              </button>
            </fieldset>
          ))}
          <button
            className="text-button"
            onClick={() =>
              set("inputs", [
                ...(block.inputs || []),
                {
                  key: id("input"),
                  label: "New input",
                  min: 0,
                  max: 10,
                  step: 1,
                  initial: 5,
                  coefficient: 1,
                },
              ])
            }
          >
            <Plus size={15} />
            Add input
          </button>
        </>
      )}
      {block.type === "assessment" && (
        <div className="form-row">
          <Field label="Question pool">
            <select
              value={block.mode || "practice"}
              onChange={(e) => set("mode", e.target.value)}
            >
              <option value="practice">Practice</option>
              <option value="transfer">Transfer</option>
            </select>
          </Field>
          <Field label="Questions">
            <input
              type="number"
              min="1"
              max="30"
              value={block.count || 3}
              onChange={(e) => set("count", +e.target.value)}
            />
          </Field>
        </div>
      )}
      {block.type === "coursework" && (
        <Field label="Assignment">
          <select
            value={block.assignment_id || ""}
            onChange={(e) => set("assignment_id", e.target.value)}
          >
            <option value="">Choose coursework in this gym</option>
            {assignments.map((a) => (
              <option value={a.id} key={a.id}>
                {a.title}
              </option>
            ))}
          </select>
          {!assignments.length && (
            <small>
              Create an assignment under Coursework & rubrics first.
            </small>
          )}
        </Field>
      )}
    </div>
  );
}

function LegacyEditor({ lesson, onChange, sources }) {
  const set = (key, value) => onChange({ ...lesson, [key]: value });
  return (
    <details className="lab-legacy-editor">
      <summary>Existing lesson narrative and paper bridge</summary>
      <p className="muted">
        These sections remain part of the lesson alongside any reusable
        activities you add.
      </p>
      <Field label="Opening question">
        <textarea
          value={lesson.question || ""}
          onChange={(e) => set("question", e.target.value)}
        />
      </Field>
      <ListField
        label="Everyday explanation"
        value={lesson.intuition}
        onChange={(value) => set("intuition", value)}
      />
      {lesson.worked_example && (
        <>
          <Field label="Example title">
            <input
              value={lesson.worked_example.title}
              onChange={(e) =>
                set("worked_example", {
                  ...lesson.worked_example,
                  title: e.target.value,
                })
              }
            />
          </Field>
          <Field label="Example">
            <textarea
              value={lesson.worked_example.body}
              onChange={(e) =>
                set("worked_example", {
                  ...lesson.worked_example,
                  body: e.target.value,
                })
              }
            />
          </Field>
        </>
      )}
      <Field label="Existing illustrative model">
        <select
          value={lesson.experiment || ""}
          onChange={(e) => set("experiment", e.target.value)}
        >
          <option value="">None</option>
          <option value="intervention">Intervention</option>
          <option value="simpson">Group composition</option>
          <option value="collider">Selection bias</option>
          <option value="discovery">Causal discovery</option>
        </select>
      </Field>
      <Field label="Application task">
        <textarea
          value={lesson.experiment_task || ""}
          onChange={(e) => set("experiment_task", e.target.value)}
        />
      </Field>
      <Field label="Reflection prompt">
        <textarea
          value={lesson.reflection || ""}
          onChange={(e) => set("reflection", e.target.value)}
        />
      </Field>
      <ListField
        label="Takeaways"
        value={lesson.takeaways}
        onChange={(value) => set("takeaways", value)}
      />
      <Field label="Common mistake">
        <textarea
          value={lesson.pitfall || ""}
          onChange={(e) => set("pitfall", e.target.value)}
        />
      </Field>
      {lesson.paper_bridge && (
        <>
          <Field label="Paper">
            <select
              value={lesson.paper_bridge.source_id}
              onChange={(e) =>
                set("paper_bridge", {
                  ...lesson.paper_bridge,
                  source_id: e.target.value,
                })
              }
            >
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.title}
                </option>
              ))}
            </select>
          </Field>
          {[
            ["why_it_matters", "Why it matters"],
            ["read_first", "Read first"],
            ["claim", "Claim"],
            ["exercise", "Reading task"],
          ].map(([name, label]) => (
            <Field key={name} label={label}>
              <textarea
                value={lesson.paper_bridge[name]}
                onChange={(e) =>
                  set("paper_bridge", {
                    ...lesson.paper_bridge,
                    [name]: e.target.value,
                  })
                }
              />
            </Field>
          ))}
          {["assumptions", "limits"].map((name) => (
            <ListField
              key={name}
              label={name === "assumptions" ? "Assumptions" : "Limits"}
              value={lesson.paper_bridge[name]}
              onChange={(value) =>
                set("paper_bridge", { ...lesson.paper_bridge, [name]: value })
              }
            />
          ))}
        </>
      )}
    </details>
  );
}

function LabEditor({
  api,
  courses,
  initialCourseId,
  initialLab,
  registry,
  onCancel,
  onPublished,
  navigate,
}) {
  const [labId] = useState(initialLab?.id || id("lab"));
  const [draft, setDraft] = useState(() => {
    const courseId =
      initialLab?.course_id || initialCourseId || courses[0]?.id || "";
    return {
      course_id: courseId,
      expected_revision: initialLab?.revision || 0,
      title: initialLab?.title || "",
      description: initialLab?.description || "",
      objectives: initialLab?.objectives || [],
      prerequisite_lab_ids: initialLab?.prerequisite_lab_ids || [],
      lessons: initialLab?.lessons || [
        initialLesson(courses.find((c) => c.id === courseId)?.modules?.[0]?.id),
      ],
      sources: initialLab?.sources || [],
      provenance: {
        author: "Learner",
        method: "human",
        rationale: initialLab
          ? "Revise the lab through the learning editor"
          : "Create a guided lab from reviewed learning materials",
        reference_urls: initialLab?.provenance?.reference_urls || [],
      },
    };
  });
  const [selected, setSelected] = useState(draft.lessons[0]?.id),
    [activityType, setActivityType] = useState("reading");
  const [sources, setSources] = useState([]),
    [assignments, setAssignments] = useState([]),
    [otherLabs, setOtherLabs] = useState([]);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [validated, setValidated] = useState(null),
    [showPreview, setShowPreview] = useState(false);
  const [courseOverrides, setCourseOverrides] = useState({}),
    [topicName, setTopicName] = useState("");
  const course =
      courseOverrides[draft.course_id] ||
      courses.find((c) => c.id === draft.course_id),
    lesson = draft.lessons.find((l) => l.id === selected) || draft.lessons[0];
  useEffect(() => {
    let live = true;
    Promise.all([
      api(`/sources?course_id=${encodeURIComponent(draft.course_id)}`),
      api("/coursework"),
      api(`/labs?course_id=${encodeURIComponent(draft.course_id)}`),
    ])
      .then(([sourceList, work, labs]) => {
        if (live) {
          setSources(
            sourceList.filter(
              (s) =>
                s.reconstruction_status === "confirmed" &&
                ["instruction", "research"].includes(s.role),
            ),
          );
          setAssignments(
            work.assignment.filter((a) => a.course_id === draft.course_id),
          );
          setOtherLabs(labs);
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [draft.course_id]);
  const change = (next) => {
    setDraft(next);
    setValidated(null);
    setError("");
  };
  const set = (name, value) => change({ ...draft, [name]: value });
  const updateLesson = (next) =>
    set(
      "lessons",
      draft.lessons.map((l) => (l.id === next.id ? next : l)),
    );
  const lessonSet = (name, value) => updateLesson({ ...lesson, [name]: value });
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
  const addTopic = () =>
    act(async () => {
      const title = topicName.trim();
      if (title.length < 2)
        throw new Error("Give the topic a name of at least two characters.");
      const current = await api(
        `/authoring/courses/${encodeURIComponent(draft.course_id)}`,
      );
      const topic = { id: id("topic"), title };
      // Overview can derive topics from legacy practice items when the course has
      // no explicit modules. Keep those topics when persisting the first new one.
      const moduleMap = new Map((course.modules || []).map((m) => [m.id, m]));
      for (const module of current.modules || [])
        moduleMap.set(module.id, module);
      moduleMap.set(topic.id, topic);
      const saved = await api(
        `/authoring/courses/${encodeURIComponent(draft.course_id)}`,
        {
          expected_revision: current.revision,
          title: current.title,
          description: current.description || "",
          modules: [...moduleMap.values()],
          provenance: {
            author: "Learner",
            method: "human",
            rationale: `Add the ${title} topic for guided learning`,
            reference_urls: [],
          },
        },
        "PUT",
      );
      setCourseOverrides((previous) => ({
        ...previous,
        [saved.id]: { ...course, ...saved },
      }));
      updateLesson({ ...lesson, module: topic.id });
      setTopicName("");
    });
  const addActivity = () => {
    if (
      activityType === "assessment" &&
      (lesson.activities || []).some((b) => b.type === "assessment")
    ) {
      setError(
        "A lesson can link one practice check per study visit. Edit the existing check or add another lesson.",
      );
      return;
    }
    const entry = registry.find((r) => r.type === activityType);
    if (!entry) {
      setError("Activity types are still loading. Try again in a moment.");
      return;
    }
    const block = {
      ...JSON.parse(JSON.stringify(entry.template)),
      id: id("activity"),
      type: activityType,
    };
    if (!block.title) block.title = entry.title;
    if (block.type === "coursework") block.assignment_id = "";
    lessonSet("activities", [...(lesson.activities || []), block]);
  };
  const preview = () =>
    act(async () => {
      setValidated(null);
      const payload = structuredClone(draft);
      payload.objectives = lines(payload.objectives.join("\n"));
      for (const entry of payload.lessons) {
        for (const field of ["objectives", "intuition", "takeaways"])
          if (entry[field]) entry[field] = lines(entry[field].join("\n"));
        if (entry.paper_bridge)
          for (const field of ["assumptions", "limits"])
            entry.paper_bridge[field] = lines(
              entry.paper_bridge[field].join("\n"),
            );
        if (!entry.module) entry.module = entry.id;
        for (const block of entry.activities || []) {
          if (block.type === "discussion")
            block.objectives = lines((block.objectives || []).join("\n"));
        }
      }
      const check = await api(
        `/labs/${encodeURIComponent(labId)}/validate`,
        payload,
      );
      if (check.valid === false)
        throw new Error(
          (check.errors || []).join("; ") ||
            "Review the lab fields before publishing.",
        );
      const result = await api(
        `/labs/${encodeURIComponent(labId)}/preview`,
        payload,
      );
      setValidated({
        payload,
        lab: result.lab,
        warnings: result.warnings || [],
      });
      setShowPreview(true);
    });
  const publish = () =>
    act(async () => {
      if (!validated) return;
      await api(`/labs/${encodeURIComponent(labId)}`, validated.payload, "PUT");
      onPublished(labId);
    });
  return (
    <div className="lab-editor">
      <button className="text-button" disabled={busy} onClick={onCancel}>
        <ArrowLeft size={16} />
        Back to labs
      </button>
      <header className="page-head">
        <div>
          <h1>{initialLab ? "Edit lab" : "Create a lab"}</h1>
          <p>Build a sequence of lessons from the gym’s reviewed sources.</p>
        </div>
        <div className="lab-editor-actions">
          {showPreview ? (
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setShowPreview(false)}
            >
              Return to editing
            </button>
          ) : (
            <button
              className="button secondary"
              disabled={busy || !draft.title.trim()}
              onClick={preview}
            >
              <Eye size={16} />
              Validate & preview
            </button>
          )}
          <button
            className="button"
            disabled={busy || !validated}
            onClick={publish}
          >
            <Check size={16} />
            {busy ? "Working…" : "Publish lab"}
          </button>
        </div>
      </header>
      {error && (
        <div className="error" role="alert">
          {error}
          <p>
            Review the fields and current revision before trying again. Your
            edits remain here.
          </p>
        </div>
      )}
      {validated && (
        <div className="notice" role="status">
          <strong>Validation passed.</strong> Review the preview, then publish
          when ready.
          {validated.warnings.map((warning, i) => (
            <p key={i}>{warning}</p>
          ))}
        </div>
      )}
      {showPreview && validated ? (
        <LabPreview lab={{ ...validated.lab, course_title: course?.title }} />
      ) : (
        <fieldset disabled={busy} className="lab-editor-fields">
          <section className="panel lab-editor-overview">
            <h2>Lab details</h2>
            <div className="form-row">
              <Field label="Gym">
                <select
                  value={draft.course_id}
                  disabled={Boolean(initialLab)}
                  onChange={(e) => {
                    const nextCourse = courses.find(
                      (c) => c.id === e.target.value,
                    );
                    change({
                      ...draft,
                      course_id: e.target.value,
                      prerequisite_lab_ids: [],
                      lessons: draft.lessons.map((l) => ({
                        ...l,
                        module: nextCourse?.modules?.[0]?.id || l.id,
                        source_ids: [],
                        activities: (l.activities || []).map((b) =>
                          b.type === "coursework"
                            ? { ...b, assignment_id: "" }
                            : b,
                        ),
                      })),
                    });
                  }}
                >
                  {courses.map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Lab title">
                <input
                  value={draft.title}
                  maxLength={300}
                  onChange={(e) => set("title", e.target.value)}
                  placeholder="For example, Reasoning from experiments"
                />
              </Field>
            </div>
            <Field label="Description">
              <textarea
                value={draft.description}
                maxLength={6000}
                onChange={(e) => set("description", e.target.value)}
                placeholder="Who is this lab for, and what will they explore?"
              />
            </Field>
            <details>
              <summary>Goals and prerequisites</summary>
              <ListField
                label="Lab objectives"
                value={draft.objectives}
                onChange={(v) => set("objectives", v)}
              />
              <ChoiceList
                legend="Suggested earlier labs"
                choices={otherLabs
                  .filter((l) => l.id !== labId)
                  .map((l) => ({ id: l.id, title: l.title }))}
                selected={draft.prerequisite_lab_ids}
                onChange={(v) => set("prerequisite_lab_ids", v)}
              />
            </details>
          </section>
          <div className="lab-editor-layout">
            <aside className="lab-editor-lessons">
              <h2>Lessons</h2>
              {draft.lessons.map((entry, index) => (
                <div
                  key={entry.id}
                  className={entry.id === lesson?.id ? "current" : ""}
                >
                  <button
                    className="lab-lesson-select"
                    onClick={() => setSelected(entry.id)}
                  >
                    <span>{index + 1}</span>
                    <span>
                      {entry.title || "Untitled lesson"}
                      <small>
                        {entry.activities?.length || 0} reusable activities
                      </small>
                    </span>
                  </button>
                  <div className="lab-reorder">
                    <button
                      className="icon"
                      aria-label={`Move ${entry.title} up`}
                      disabled={index === 0}
                      onClick={() =>
                        set("lessons", move(draft.lessons, index, -1))
                      }
                    >
                      <ArrowUp size={15} />
                    </button>
                    <button
                      className="icon"
                      aria-label={`Move ${entry.title} down`}
                      disabled={index === draft.lessons.length - 1}
                      onClick={() =>
                        set("lessons", move(draft.lessons, index, 1))
                      }
                    >
                      <ArrowDown size={15} />
                    </button>
                    <button
                      className="icon"
                      aria-label={`Remove ${entry.title}`}
                      disabled={draft.lessons.length <= 1}
                      onClick={() => {
                        const next = draft.lessons
                          .filter((l) => l.id !== entry.id)
                          .map((l) => ({
                            ...l,
                            prerequisites: (l.prerequisites || []).filter(
                              (p) => p !== entry.id,
                            ),
                          }));
                        set("lessons", next);
                        if (selected === entry.id) setSelected(next[0]?.id);
                      }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))}
              <button
                className="button secondary"
                onClick={() => {
                  const added = initialLesson(course?.modules?.[0]?.id);
                  set("lessons", [...draft.lessons, added]);
                  setSelected(added.id);
                }}
              >
                <Plus size={16} />
                Add lesson
              </button>
            </aside>
            {lesson && (
              <section
                className="panel lab-lesson-editor"
                aria-label="Lesson editor"
              >
                <h2>{lesson.title || "Untitled lesson"}</h2>
                <Field label="Lesson title">
                  <input
                    value={lesson.title}
                    onChange={(e) => lessonSet("title", e.target.value)}
                  />
                </Field>
                <div className="form-row">
                  <Field label="Gym topic">
                    <select
                      value={lesson.module || lesson.id}
                      onChange={(e) => lessonSet("module", e.target.value)}
                    >
                      {!(course?.modules || []).some(
                        (m) => m.id === (lesson.module || lesson.id),
                      ) && (
                        <option value={lesson.module || lesson.id}>
                          {course?.modules?.length
                            ? lesson.module || lesson.id
                            : "Add a topic below"}
                        </option>
                      )}
                      {(course?.modules || []).map((m) => (
                        <option value={m.id} key={m.id}>
                          {m.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Suggested minutes">
                    <input
                      type="number"
                      min="1"
                      max="10000"
                      value={lesson.minutes}
                      onChange={(e) => lessonSet("minutes", +e.target.value)}
                    />
                  </Field>
                  <Field label="Stage (optional)">
                    <input
                      value={lesson.stage || ""}
                      onChange={(e) => lessonSet("stage", e.target.value)}
                      placeholder="Foundations"
                    />
                  </Field>
                </div>
                <details
                  open={!course?.modules?.length || undefined}
                  className="lab-add-topic"
                >
                  <summary>Add a gym topic</summary>
                  <div className="lab-add-activity">
                    <Field label="New topic name">
                      <input
                        value={topicName}
                        maxLength={200}
                        placeholder="For example, Forces and motion"
                        onChange={(e) => setTopicName(e.target.value)}
                      />
                    </Field>
                    <button
                      className="button secondary"
                      disabled={busy || topicName.trim().length < 2}
                      onClick={addTopic}
                    >
                      <Plus size={15} />
                      Add topic
                    </button>
                  </div>
                  <small>
                    The topic is saved to this gym and selected for this lesson.
                  </small>
                </details>
                <ListField
                  label="Lesson objectives"
                  value={lesson.objectives}
                  onChange={(v) => lessonSet("objectives", v)}
                />
                <details>
                  <summary>Prerequisite lessons</summary>
                  <ChoiceList
                    legend="Builds on"
                    choices={draft.lessons
                      .filter((l) => l.id !== lesson.id)
                      .map((l) => ({ id: l.id, title: l.title }))}
                    selected={lesson.prerequisites}
                    onChange={(v) => lessonSet("prerequisites", v)}
                  />
                </details>
                <ChoiceList
                  legend="Reviewed sources for this lesson"
                  choices={sources.map((s) => ({
                    id: s.id,
                    title: s.name,
                    detail: `Version ${s.version} · ${s.role}`,
                  }))}
                  selected={lesson.source_ids}
                  onChange={(v) => lessonSet("source_ids", v)}
                  empty="Upload and review sources in Sources & create before publishing this lesson."
                />
                {lesson.source_ids?.some(
                  (sid) => !sources.some((s) => s.id === sid),
                ) && (
                  <p className="notice">
                    A previously linked source is unavailable in this list.
                    Validation will check its status before publishing.
                  </p>
                )}
                <div className="section-title">
                  <h3>Activities</h3>
                  <span>{lesson.activities?.length || 0} blocks</span>
                </div>
                {(lesson.activities || []).map((block, index) => (
                  <section className="lab-authored-block" key={block.id}>
                    <header>
                      <strong>
                        {index + 1}. {activityLabels[block.type] || block.type}
                      </strong>
                      <div className="lab-reorder">
                        <button
                          className="icon"
                          aria-label={`Move activity ${index + 1} up`}
                          disabled={index === 0}
                          onClick={() =>
                            lessonSet(
                              "activities",
                              move(lesson.activities, index, -1),
                            )
                          }
                        >
                          <ArrowUp size={15} />
                        </button>
                        <button
                          className="icon"
                          aria-label={`Move activity ${index + 1} down`}
                          disabled={index === lesson.activities.length - 1}
                          onClick={() =>
                            lessonSet(
                              "activities",
                              move(lesson.activities, index, 1),
                            )
                          }
                        >
                          <ArrowDown size={15} />
                        </button>
                        <button
                          className="icon"
                          aria-label={`Remove activity ${index + 1}`}
                          onClick={() =>
                            lessonSet(
                              "activities",
                              lesson.activities.filter((_, i) => i !== index),
                            )
                          }
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </header>
                    <ActivityEditor
                      block={block}
                      assignments={assignments}
                      onChange={(next) =>
                        lessonSet(
                          "activities",
                          lesson.activities.map((b) =>
                            b.id === next.id ? next : b,
                          ),
                        )
                      }
                    />
                  </section>
                ))}
                <div className="lab-add-activity">
                  <Field label="Add an activity">
                    <select
                      value={activityType}
                      onChange={(e) => setActivityType(e.target.value)}
                    >
                      {registry.map((entry) => (
                        <option key={entry.type} value={entry.type}>
                          {entry.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <button
                    className="button secondary"
                    disabled={!registry.length}
                    onClick={addActivity}
                  >
                    <Plus size={16} />
                    Add activity
                  </button>
                </div>
                <p className="muted">
                  {registry.find((r) => r.type === activityType)?.description}
                </p>
                {lesson.intuition?.length ||
                lesson.worked_example ||
                lesson.paper_bridge ||
                lesson.experiment ? (
                  <LegacyEditor
                    lesson={lesson}
                    onChange={updateLesson}
                    sources={draft.sources}
                  />
                ) : null}
              </section>
            )}
          </div>
          <section className="panel lab-publish-note">
            <Field
              label="Change note"
              hint="Saved with this lab version so future edits remain attributable."
            >
              <textarea
                value={draft.provenance.rationale}
                onChange={(e) =>
                  set("provenance", {
                    ...draft.provenance,
                    rationale: e.target.value,
                  })
                }
              />
            </Field>
            <p className="muted">
              Publishing updates the learning material. Existing study visits
              and practice evidence remain in the gym.
            </p>
            <button
              className="button"
              disabled={busy || !draft.title.trim()}
              onClick={preview}
            >
              <Eye size={16} />
              Validate & preview
            </button>
          </section>
        </fieldset>
      )}
    </div>
  );
}
