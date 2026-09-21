import React, { useEffect, useState } from "react";

// Search at the point of use; selected evidence stays visible even in a large library.
export function EvidencePicker({
  label,
  options,
  value,
  onChange,
  multiple = true,
  hint,
}) {
  const id = React.useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const ids = multiple ? value : value ? [value] : [];
  const matches = options.filter(
    (o) =>
      !ids.includes(o.id) &&
      `${o.title || o.name} ${o.description || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const results = matches.slice(0, 8);
  const choose = (o) => {
    onChange(multiple ? [...ids, o.id] : o.id);
    setQuery("");
    setOpen(false);
    setActive(-1);
  };
  return (
    <div
      className="evidence-picker"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
    >
      <label className="field" htmlFor={id}>
        <span>{label}</span>
      </label>
      {hint && (
        <p className="small muted" id={id + "-hint"}>
          {hint}
        </p>
      )}
      {ids.length > 0 && (
        <ul className="evidence-chips" aria-label={label + " selected"}>
          {ids.map((key) => (
            <li key={key}>
              <span>
                {options.find((o) => o.id === key)?.title ||
                  options.find((o) => o.id === key)?.name ||
                  "Previously selected evidence"}
              </span>
              <button
                type="button"
                aria-label={
                  "Remove " +
                  (options.find((o) => o.id === key)?.title ||
                    options.find((o) => o.id === key)?.name ||
                    "evidence")
                }
                onClick={() =>
                  onChange(multiple ? ids.filter((v) => v !== key) : "")
                }
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={id + "-results"}
        aria-describedby={hint ? id + "-hint" : undefined}
        aria-activedescendant={
          open && active >= 0 ? id + "-" + active : undefined
        }
        placeholder={
          multiple ? "Type to find and add…" : "Type to find coursework…"
        }
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            setActive(-1);
          }
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            setActive((i) =>
              Math.max(
                results.length ? 0 : -1,
                Math.min(
                  results.length - 1,
                  i + (e.key === "ArrowDown" ? 1 : -1),
                ),
              ),
            );
          }
          if (e.key === "Enter" && open && results[active]) {
            e.preventDefault();
            choose(results[active]);
          }
        }}
      />
      {open && (
        <div className="evidence-results">
          <ul
            id={id + "-results"}
            role="listbox"
            aria-label={label + " matches"}
          >
            {results.map((o, i) => (
              <li
                id={id + "-" + i}
                role="option"
                aria-selected={active === i}
                key={o.id}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(o)}
              >
                <strong>{o.title || o.name}{o.version ? ` · v${o.version}` : ""}</strong>
                {o.description && <small>{o.description}</small>}
              </li>
            ))}
          </ul>
          <p className="small muted" role="status">
            {matches.length
              ? `${matches.length} match${matches.length === 1 ? "" : "es"}${matches.length > 8 ? "; type more to narrow the results" : ""}`
              : "No matching evidence. Try another name or add material to this gym."}
          </p>
        </div>
      )}
    </div>
  );
}

function InlineCoursework({ courseId, api, act, busy, onSaved, close }) {
  const [draft, setDraft] = useState({
    title: "",
    prompt: "",
    deadline: "",
    effort_minutes: "",
    kind: "practice_quiz",
  });
  const set = (key, value) => setDraft({ ...draft, [key]: value });
  return (
    <div className="inline-coursework" aria-label="New coursework">
      <h3>Add the task you’re preparing for</h3>
      <p>
        Use the actual assignment instructions and deadline. You can attach its
        documents and official rubric in Coursework later.
      </p>
      <label className="field">
        <span>Coursework title</span>
        <input
          value={draft.title}
          onChange={(e) => set("title", e.target.value)}
        />
      </label>
      <label className="field">
        <span>Assignment instructions</span>
        <textarea
          value={draft.prompt}
          onChange={(e) => set("prompt", e.target.value)}
        />
      </label>
      <label className="field">
        <span>Coursework type</span>
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
          ].map((kind) => (
            <option value={kind} key={kind}>
              {kind.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <div className="form-row">
        <label className="field">
          <span>Deadline (required)</span>
          <input
            type="datetime-local"
            required
            value={draft.deadline}
            onChange={(e) => set("deadline", e.target.value)}
          />
        </label>
        <label className="field">
          <span>Estimated time in minutes (required)</span>
          <input
            type="number"
            min="5"
            max="10000"
            required
            value={draft.effort_minutes}
            onChange={(e) => set("effort_minutes", e.target.value)}
          />
        </label>
      </div>
      <p className="small muted">
        Deadline timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}.
      </p>
      <div className="row">
        <button
          className="button"
          disabled={
            busy ||
            draft.title.trim().length < 2 ||
            draft.prompt.trim().length < 10 ||
            !draft.deadline ||
            !Number.isInteger(+draft.effort_minutes) ||
            +draft.effort_minutes < 5 ||
            +draft.effort_minutes > 10000
          }
          onClick={() =>
            act(async () =>
              onSaved(
                await api("/assignments", {
                  ...draft,
                  course_id: courseId,
                  purpose: "coursework",
                  deadline: new Date(draft.deadline).toISOString(),
                  effort_minutes: +draft.effort_minutes,
                }),
              ),
            )
          }
        >
          Save coursework and select it
        </button>
        <button className="button secondary" onClick={close}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export function ProfileBuilder({
  courseId,
  coursework,
  sources,
  onCreated,
  openLibrary,
  api,
  act,
  busy,
  reload,
}) {
  const [assignmentIds, setAssignmentIds] = useState([]);
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [manual, setManual] = useState(false);
  const [targetAssignmentId, setTargetAssignmentId] = useState("");
  const [materialIds, setMaterialIds] = useState([]);
  const [assessmentIds, setAssessmentIds] = useState([]);
  const [addingCoursework, setAddingCoursework] = useState(false);
  useEffect(() => {
    setAssignmentIds([]);
    setTitle("");
    setTarget("");
    setTargetAssignmentId("");
    setMaterialIds([]);
    setAssessmentIds([]);
    setAddingCoursework(false);
  }, [courseId]);
  const assignments =
    coursework?.assignment.filter((a) => a.course_id === courseId) || [];
  const rubrics =
    coursework?.rubric.filter(
      (r) => !r.course_id || r.course_id === courseId,
    ) || [];
  const targetAssignment = assignments.find((a) => a.id === targetAssignmentId);
  const available = (sources || []).filter(
    (s) =>
      s.course_id === courseId &&
      (s.latest || [...materialIds, ...assessmentIds].includes(s.id)) &&
      s.reconstruction_status === "confirmed",
  );
  const selectTarget = (id) => {
    setTargetAssignmentId(id);
    setAssignmentIds((ids) => ids.filter((key) => key !== id));
    const a = assignments.find((item) => item.id === id);
    if (a) {
      setTitle(a.title + " preparation");
      setTarget(a.prompt.slice(0, 3000));
    }
  };
  const unreviewed = [...materialIds, ...assessmentIds].some(
    (id) =>
      sources?.find((s) => s.id === id)?.reconstruction_status !== "confirmed",
  );
  const create = () =>
    act(async () => {
      const payload = {
        course_id: courseId,
        assignment_ids: assignmentIds,
        source_ids: assessmentIds,
        material_source_ids: materialIds,
        target_assignment_id: targetAssignmentId || null,
        title,
        target,
      };
      if (manual) {
        const rubric = rubrics.find(
          (r) => r.id === targetAssignment?.rubric_id,
        );
        payload.profile = {
          title: title || target,
          content_scope: target,
          assessment_kinds: ["practice_quiz", "exam"],
          question_types: ["mcq", "open"],
          structure: "Review and describe the desired format.",
          length_and_time: "Specify in each blueprint.",
          scoring_rules:
            "Apply the reviewed practice rubric to open responses.",
          reasoning_demands: [
            "Explain the reasoning",
            "Defend conclusions under changed assumptions",
          ],
          difficulty_anchor: "Review against the selected coursework.",
          uncertainty: [
            "Author proposal; no claim of official exam equivalence.",
          ],
          supporting_fragment_ids: [],
          rubric_basis: rubric
            ? `Proposed practice adaptation of ${rubric.title}; review applicability.`
            : "Author-proposed criteria and weights; review against the selected coursework and material.",
          practice_rubric: {
            title: title + " · proposed practice rubric",
            authority: "proposed",
            course_id: courseId,
            criteria: rubric?.criteria || [
              {
                name: "Reasoning and method",
                weight: 0.4,
                anchors: [
                  "Unsupported method",
                  "Justified method with sound reasoning",
                ],
              },
              {
                name: "Evidence and execution",
                weight: 0.4,
                anchors: [
                  "Missing evidence",
                  "Accurate execution grounded in course concepts",
                ],
              },
              {
                name: "Assumptions and uncertainty",
                weight: 0.2,
                anchors: [
                  "Unqualified conclusion",
                  "States assumptions, changes and remaining uncertainty",
                ],
              },
            ],
            permitted_assistance:
              "Record assistance; proposed practice scoring only.",
            capabilities: [],
          },
        };
      }
      await api("/profiles", payload);
      await reload();
      onCreated();
    });
  return (
    <section className="profile-builder" aria-label="Create a targeted profile">
      <h2>Prepare for a real task</h2>
      <p>
        A profile defines what your practice should cover and how answers will
        be judged. Start with the coursework, then choose the material it draws
        on.
      </p>
      <div className="authoring-step">
        <h3>1. Choose your coursework</h3>
        <EvidencePicker
          label="Coursework to prepare for"
          multiple={false}
          options={assignments
            .filter((a) => a.purpose !== "self_study" && a.deadline)
            .map((a) => ({
              ...a,
              description: `Due ${new Date(a.deadline).toLocaleString()} · ${a.status}`,
            }))}
          value={targetAssignmentId}
          onChange={selectTarget}
          hint="Required. Choose an existing task with a deadline, or add one below."
        />
        {targetAssignment && (
          <p className="small muted">
            {targetAssignment.rubric_version_id
              ? "The assignment’s rubric is included automatically."
              : "No official rubric attached. The profile will propose practice criteria for your review."}
          </p>
        )}
        <button
          className="text-button"
          onClick={() => setAddingCoursework(!addingCoursework)}
        >
          {addingCoursework ? "Close coursework form" : "Add coursework here"}
        </button>
        {assignments.some((a) => a.purpose !== "self_study" && !a.deadline) && (
          <p className="small muted">
            Tasks without a deadline need to be updated in Coursework before you
            can select them.
          </p>
        )}
        {addingCoursework && (
          <InlineCoursework
            courseId={courseId}
            api={api}
            act={act}
            busy={busy}
            close={() => setAddingCoursework(false)}
            onSaved={async (a) => {
              await reload();
              setTargetAssignmentId(a.id);
              setTitle(a.title + " preparation");
              setTarget(a.prompt.slice(0, 3000));
              setAddingCoursework(false);
            }}
          />
        )}
      </div>
      <div className="authoring-step">
        <h3>2. Choose the evidence</h3>
        <p>
          Find the lectures and readings that teach the content. Add earlier
          assignments or example questions if they help show what will be
          expected.
        </p>
        <EvidencePicker
          label="Course material"
          options={available.filter((s) =>
            ["instruction", "research"].includes(s.role),
          )}
          value={materialIds}
          onChange={setMaterialIds}
          hint="Required. Add at least one reviewed lecture, reading or set of notes."
        />
        <EvidencePicker
          label="Earlier coursework (optional)"
          options={assignments.filter(
            (a) => a.id !== targetAssignmentId && a.purpose !== "self_study",
          )}
          value={assignmentIds}
          onChange={setAssignmentIds}
        />
        <EvidencePicker
          label="Example questions or rubric documents (optional)"
          options={available.filter((s) =>
            ["assessment", "rubric"].includes(s.role),
          )}
          value={assessmentIds}
          onChange={setAssessmentIds}
        />
        <button className="text-button" onClick={openLibrary}>
          Upload or review material
        </button>
        <p className="small muted">
          Only reviewed material appears here. Your answers, grades and
          instructor feedback are excluded.
        </p>
      </div>
      <div className="authoring-step">
        <h3>3. Set the focus</h3>
        <label className="field">
          <span>Profile title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className="field">
          <span>What should your practice focus on?</span>
          <textarea
            aria-label="What should your practice focus on?"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        </label>
        <p className="small muted">
          Starts with the assignment instructions. Narrow the topics or
          reasoning skills if needed.
        </p>
        <details>
          <summary>Prepare a proposal without a model</summary>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={manual}
              onChange={(e) => setManual(e.target.checked)}
            />
            Write and review a profile manually (no model call)
          </label>
        </details>
        {unreviewed && (
          <p className="error-text">
            Review and confirm the selected material first.
          </p>
        )}
        <button
          className="button"
          disabled={
            busy ||
            !targetAssignment?.deadline ||
            !materialIds.length ||
            target.trim().length < 5 ||
            title.trim().length < 2 ||
            unreviewed
          }
          onClick={create}
        >
          Create profile proposal
        </button>
        <p className="small muted">
          Next: review its scope and proposed rubric before generating
          questions. When new material arrives, update this profile with a new
          version.
        </p>
      </div>
    </section>
  );
}

export function ProfileReview({ value, onSave, busy }) {
  const [profile, setProfile] = useState(value.profile);
  const [rawRubric, setRawRubric] = useState(
    JSON.stringify(value.profile.practice_rubric || null, null, 2),
  );
  const [error, setError] = useState("");
  const set = (k, v) => setProfile({ ...profile, [k]: v });
  const fields = Object.entries(profile).filter(
    ([k]) => !["practice_rubric", "supporting_fragment_ids"].includes(k),
  );
  return (
    <>
      <p>
        Target: {value.target || "Legacy style profile"}.{" "}
        {value.assignment_ids?.length || 0} coursework references;{" "}
        {value.material_source_ids?.length || 0} instructional sources.
      </p>
      {value.assignment_snapshots?.map((a) => (
        <p key={a.id}>
          <strong>{a.title}</strong> ·{" "}
          {a.rubric_version_id
            ? "Rubric pinned"
            : "Official rubric unavailable"}
        </p>
      ))}
      {fields.map(([k, v]) => (
        <label className="field" key={k}>
          <span>{k.replaceAll("_", " ")}</span>
          <textarea
            value={
              Array.isArray(v)
                ? v.join("\n")
                : typeof v === "object"
                  ? JSON.stringify(v)
                  : v || ""
            }
            onChange={(e) =>
              set(
                k,
                Array.isArray(v) ? e.target.value.split("\n") : e.target.value,
              )
            }
          />
        </label>
      ))}
      {profile.practice_rubric && (
        <>
          <h3>Proposed practice rubric</h3>
          <p>
            Criteria, weights and observable anchors are explicit. The
            derivation above explains which parts come from coursework and which
            were proposed.
          </p>
          {profile.practice_rubric.criteria?.map((c) => (
            <div className="rubric-criterion" key={c.name}>
              <strong>
                {c.name} · {Math.round(c.weight * 100)}%
              </strong>
              <ul>
                {c.anchors.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          ))}
          <details>
            <summary>Edit structured rubric</summary>
            <textarea
              rows={18}
              aria-label="Practice rubric JSON"
              value={rawRubric}
              onChange={(e) => setRawRubric(e.target.value)}
            />
          </details>
        </>
      )}
      {error && <p className="error-text">{error}</p>}
      <button
        className="button"
        disabled={busy}
        onClick={() => {
          try {
            const next = { ...profile };
            if (profile.practice_rubric)
              next.practice_rubric = JSON.parse(rawRubric);
            setError("");
            onSave(next);
          } catch {
            setError(
              "The rubric must be valid JSON. Check the edited criteria before confirming.",
            );
          }
        }}
      >
        Confirm this profile
      </button>
    </>
  );
}

export function CourseworkFile({ sourceId, sources, api, act }) {
  const [fragments, setFragments] = useState(null);
  const source = sources?.find((s) => s.id === sourceId);
  useEffect(() => setFragments(null), [sourceId]);
  if (!sourceId) return null;
  return (
    <details className="vignette">
      <summary>{source?.name || "Attached coursework document"}</summary>
      <p className="small muted">
        Preserved document · version {source?.version || 1}
      </p>
      {source?.quality_flags?.map((flag, i) => (
        <p key={i}>{flag}</p>
      ))}
      {fragments ? (
        fragments.map((f) => (
          <p className="preserve" key={f.id}>
            {f.text}
          </p>
        ))
      ) : (
        <button
          className="text-button"
          onClick={() =>
            act(async () => {
              setFragments(await api(`/sources/${sourceId}/fragments`));
            })
          }
        >
          Read document text
        </button>
      )}
    </details>
  );
}

export function courseworkGrades(data, assignmentId) {
  const records = [
    ...(data.coursework_outcome || []),
    ...(data.official_grade || []),
  ].filter((o) => o.assignment_id === assignmentId);
  const superseded = new Set(records.map((o) => o.supersedes).filter(Boolean));
  return records
    .filter((o) => !superseded.has(o.id))
    .sort((a, b) => (a.received_at || "").localeCompare(b.received_at || ""))
    .slice(-1);
}

export function CourseworkOutcomes({
  assignment,
  data,
  api,
  act,
  busy,
  reload,
  sources,
  reloadSources,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const current = courseworkGrades(data, assignment.id)[0];
  const history = [
    ...(data.coursework_outcome || []),
    ...(data.official_grade || []),
  ]
    .filter((o) => o.assignment_id === assignment.id && o.id !== current?.id)
    .sort((a, b) => (b.received_at || "").localeCompare(a.received_at || ""));
  const set = (k, v) => setDraft({ ...draft, [k]: v });
  const open = (previous = null) => {
    setDraft({
      idempotency_key: crypto.randomUUID(),
      score: previous?.score ?? "",
      feedback: previous?.feedback || "",
      attribution:
        previous?.attribution || "Instructor / TA feedback entered by learner",
      source_url: previous?.source_url || "",
      source_id: previous?.source_id || null,
      artifact_version_id: previous?.artifact_version_id || null,
      observed_at: new Date().toISOString(),
      occurred_at: previous?.occurred_at || null,
      learner_comment: previous?.learner_comment || "",
      limitations: previous?.limitations || "",
      mark_completed: assignment.status === "completed",
      supersedes: previous?.submission_id ? null : previous?.id || null,
    });
    setEditing(true);
  };
  return (
    <section className="section" aria-label="Instructor grades and feedback">
      <div className="row between">
        <h2>Instructor grade & feedback</h2>
        <button className="button secondary" onClick={() => open(current)}>
          {current ? "Edit grade & feedback" : "Add grade or feedback"}
        </button>
      </div>
      {current ? (
        <div className="official-grade" key={current.id}>
          <strong>
            {current.score == null
              ? "No grade reported"
              : `Instructor grade: ${current.score} / ${current.max_score}`}
          </strong>
          <p className="preserve">
            {current.feedback || "No written feedback recorded."}
          </p>
          <details>
            <summary>Record details & history</summary>
            <p>{current.attribution || "Instructor grade entered by you"}</p>
            {current.source_url && (
              <a href={current.source_url} target="_blank" rel="noreferrer">
                Original course record
              </a>
            )}
            <p className="small muted">
              Recorded{" "}
              {new Date(
                current.observed_at || current.received_at,
              ).toLocaleString()}
            </p>
            {current.occurred_at && (
              <p className="small muted">
                Feedback dated {new Date(current.occurred_at).toLocaleString()}
              </p>
            )}
            {current.learner_comment && (
              <>
                <h3>Your comments</h3>
                <p className="preserve">{current.learner_comment}</p>
              </>
            )}
            {current.limitations && (
              <p className="muted">{current.limitations}</p>
            )}
            <CourseworkFile
              sourceId={current.source_id}
              sources={sources}
              api={api}
              act={act}
            />
            {current.original_record_snapshot && (
              <details>
                <summary>Imported grade and feedback record</summary>
                <p className="preserve">
                  {current.original_record_snapshot.body}
                </p>
              </details>
            )}
            {history.length > 0 && (
              <details>
                <summary>Previous versions ({history.length})</summary>
                {history.map((o) => (
                  <div key={o.id}>
                    <h3>
                      {o.score == null
                        ? "Feedback only"
                        : `Previous grade: ${o.score} / ${o.max_score}`}
                    </h3>
                    <p className="preserve">{o.feedback}</p>
                    <p>{o.attribution}</p>
                    <p className="small muted">
                      Recorded{" "}
                      {new Date(
                        o.observed_at || o.received_at,
                      ).toLocaleString()}
                    </p>
                    {o.source_url && (
                      <a href={o.source_url} target="_blank" rel="noreferrer">
                        Original course record
                      </a>
                    )}
                    <p className="preserve">{o.learner_comment}</p>
                    <p>{o.limitations}</p>
                    <CourseworkFile
                      sourceId={o.source_id}
                      sources={sources}
                      api={api}
                      act={act}
                    />
                    {o.original_record_snapshot && (
                      <details>
                        <summary>Imported record</summary>
                        <p className="preserve">
                          {o.original_record_snapshot.body}
                        </p>
                      </details>
                    )}
                  </div>
                ))}
              </details>
            )}
          </details>
        </div>
      ) : (
        <p className="muted">No instructor grade or feedback recorded yet.</p>
      )}
      {editing && draft && (
        <div className="panel">
          <h3>
            {draft.supersedes
              ? "Update grade & feedback"
              : "Add grade & feedback"}
          </h3>
          <label className="field">
            <span>Upload instructor feedback or grade file</span>
            <input
              type="file"
              aria-label="Upload instructor feedback or grade file"
              accept=".pdf,.docx,.pptx,.txt,.md,.csv,.ipynb"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files[0];
                if (!file) return;
                act(async () => {
                  const form = new FormData();
                  form.append("course_id", assignment.course_id);
                  form.append("role", "feedback");
                  form.append("file", file);
                  const source = await api("/sources", form);
                  if (source.role !== "feedback")
                    throw new Error(
                      "This file was previously uploaded for another purpose. Give the feedback copy a distinct filename and upload it here.",
                    );
                  setDraft((d) => ({ ...d, source_id: source.id }));
                  await reloadSources();
                });
              }}
            />
            <small>
              Attach the instructor's document here, then enter its grade or
              comments below. File text is not automatically treated as a grade.
              Text-based PDFs, Word files or text are supported; scans need a
              text extraction.
            </small>
          </label>
          {sources?.some(
            (s) =>
              s.course_id === assignment.course_id && s.role === "feedback",
          ) && (
            <label className="field">
              <span>Saved feedback file (optional)</span>
              <select
                aria-label="Saved feedback file (optional)"
                value={draft.source_id || ""}
                onChange={(e) => set("source_id", e.target.value || null)}
              >
                <option value="">No file attached</option>
                {sources
                  .filter(
                    (s) =>
                      s.course_id === assignment.course_id &&
                      s.role === "feedback" &&
                      (s.latest || s.id === draft.source_id),
                  )
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · v{s.version}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <CourseworkFile
            sourceId={draft.source_id}
            sources={sources}
            api={api}
            act={act}
          />
          <label className="field">
            <span>
              Grade (out of {assignment.points}; leave blank for feedback only)
            </span>
            <input
              type="number"
              min="0"
              max={assignment.points}
              step="any"
              value={draft.score}
              onChange={(e) => set("score", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Instructor / TA feedback</span>
            <textarea
              rows={6}
              aria-label="Instructor / TA feedback"
              value={draft.feedback}
              onChange={(e) => set("feedback", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Attribution</span>
            <input
              value={draft.attribution}
              onChange={(e) => set("attribution", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Original course record URL</span>
            <input
              type="url"
              value={draft.source_url}
              onChange={(e) => set("source_url", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Your comment or disagreement</span>
            <textarea
              value={draft.learner_comment}
              onChange={(e) => set("learner_comment", e.target.value)}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={draft.mark_completed}
              onChange={(e) => set("mark_completed", e.target.checked)}
            />
            This coursework is already completed externally
          </label>
          <div className="row">
            <button
              className="button"
              disabled={
                busy ||
                (current?.submission_id && draft.score === "") ||
                (draft.score === "" && !draft.feedback.trim())
              }
              onClick={() =>
                act(async () => {
                  const payload = {
                    ...draft,
                    score: draft.score === "" ? null : Number(draft.score),
                  };
                  if (current?.submission_id) {
                    await api(`/submissions/${current.submission_id}/grade`, {
                      ...payload,
                      supersedes: current.id,
                    });
                  } else {
                    await api(
                      `/assignments/${assignment.id}/outcomes`,
                      payload,
                    );
                  }
                  setEditing(false);
                  await reload();
                })
              }
            >
              Save grade & feedback
            </button>
            <button
              className="button secondary"
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

export function ProfileEvolution({
  profile,
  coursework,
  sources,
  api,
  act,
  busy,
  reload,
  close,
}) {
  const [history, setHistory] = useState(null);
  const [draft, setDraft] = useState({
    title: profile.title || profile.profile?.title || "",
    target: profile.target || "",
    target_assignment_id: profile.target_assignment_id || null,
    assignment_ids: profile.assignment_ids || [],
    source_ids: profile.source_ids || [],
    material_source_ids: profile.material_source_ids || [],
    emergent_source_ids: profile.emergent_source_ids || [],
    rubric_ids: profile.rubric_ids || [],
  });
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  useEffect(() => {
    act(async () => setHistory(await api(`/profiles/${profile.id}/versions`)));
  }, [profile.id]);
  const set = (key, value) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setRequestKey(crypto.randomUUID());
  };
  const assignments =
    coursework?.assignment.filter((a) => a.course_id === profile.course_id) ||
    [];
  const available =
    sources?.filter(
      (s) =>
        s.course_id === profile.course_id &&
        s.reconstruction_status === "confirmed" &&
        (s.latest ||
          [
            ...draft.source_ids,
            ...draft.material_source_ids,
            ...draft.emergent_source_ids,
          ].includes(s.id)) &&
        ["instruction", "research", "assessment", "rubric"].includes(s.role),
    ) || [];
  const pick = (label, key, options) => (
    <EvidencePicker
      label={label}
      options={options}
      value={draft[key]}
      onChange={(ids) => set(key, ids)}
    />
  );
  return (
    <>
      <p>
        Run {profile.run_version || 1} · revision {profile.revision} ·{" "}
        {profile.status}. Rerunning creates a new proposal from the selected
        evidence; existing question sets keep their original profile.
      </p>
      <h3>Intention</h3>
      <label className="field">
        <span>Specific assessment goal</span>
        <textarea
          value={draft.target}
          onChange={(e) => set("target", e.target.value)}
        />
      </label>
      <EvidencePicker
        label="Coursework to prepare for"
        multiple={false}
        options={assignments.filter(
          (a) => a.purpose !== "self_study" && a.deadline,
        )}
        value={draft.target_assignment_id || ""}
        onChange={(id) => {
          setDraft((d) => ({
            ...d,
            target_assignment_id: id,
            assignment_ids: d.assignment_ids.filter((a) => a !== id),
          }));
          setRequestKey(crypto.randomUUID());
        }}
      />
      <h3>Prior evidence</h3>
      {pick(
        "Prior coursework examples",
        "assignment_ids",
        assignments.filter(
          (a) =>
            a.id !== draft.target_assignment_id && a.purpose !== "self_study",
        ),
      )}
      {pick(
        "Prior instructional material",
        "material_source_ids",
        available.filter(
          (s) =>
            ["instruction", "research"].includes(s.role) &&
            !draft.emergent_source_ids.includes(s.id),
        ),
      )}
      {pick(
        "Prior assessment examples or rubrics",
        "source_ids",
        available.filter(
          (s) =>
            ["assessment", "rubric"].includes(s.role) &&
            !draft.emergent_source_ids.includes(s.id),
        ),
      )}
      <h3>What’s new since the last profile?</h3>
      <p>
        Add newly available slides, task clarifications, example questions or
        rubric updates. Rerunning combines them with the existing evidence and
        creates a new version to review.
      </p>
      {pick(
        "New information about the task",
        "emergent_source_ids",
        available.filter(
          (s) =>
            !draft.source_ids.includes(s.id) &&
            !draft.material_source_ids.includes(s.id),
        ),
      )}
      <p>
        Each source belongs in one evidence category. Select reviewed source
        versions; new source versions are never substituted silently.
      </p>
      <button
        className="button"
        disabled={
          busy ||
          draft.target.trim().length < 5 ||
          !assignments.find(
            (a) =>
              a.id === draft.target_assignment_id &&
              a.deadline &&
              a.purpose !== "self_study",
          )
        }
        onClick={() =>
          act(async () => {
            await api(`/profiles/${profile.id}/rerun`, {
              ...draft,
              expected_revision: profile.revision,
              idempotency_key: requestKey,
            });
            await reload();
            close();
          })
        }
      >
        Rerun profile with updated evidence
      </button>
      <h3>Profile version history</h3>
      {history?.versions.length ? (
        [...history.versions].reverse().map((v) => (
          <details key={v.id}>
            <summary>
              Run {v.run_version || 1} · revision {v.profile_revision} ·{" "}
              {v.status} · {v.target || v.profile?.title}
            </summary>
            <p>
              Intended coursework:{" "}
              {v.target_assignment_snapshot?.title || "Assessment goal"}
            </p>
            <p>
              Prior:{" "}
              {v.assignment_snapshots?.map((a) => a.title).join(", ") ||
                "No prior coursework"}
            </p>
            <p>
              Emergent:{" "}
              {v.emergent_fragments
                ?.map((f) => f.source_name)
                .filter((name, i, arr) => arr.indexOf(name) === i)
                .join(", ") || "None"}
            </p>
            {v.profile && (
              <pre className="preserve">
                {JSON.stringify(v.profile, null, 2)}
              </pre>
            )}
            {v.error && <p className="error-text">{v.error}</p>}
          </details>
        ))
      ) : (
        <p>Legacy profile: history begins with its next recorded revision.</p>
      )}
    </>
  );
}

export function RegeneratePractice({
  blueprint,
  profiles,
  api,
  act,
  busy,
  reload,
}) {
  const [profileId, setProfileId] = useState(blueprint.profile_id || "");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [versionId, setVersionId] = useState("");
  const [versions, setVersions] = useState([]);
  const confirmed = profiles.filter(
    (p) => p.course_id === blueprint.course_id && p.status === "confirmed",
  );
  return (
    <details>
      <summary>Regenerate practice questions</summary>
      <p>
        Create a new verified set. Original questions, mock exams and learner
        attempts remain available.
      </p>
      <label className="field">
        <span>Profile for new question set</span>
        <select
          value={profileId}
          onChange={(e) => {
            setProfileId(e.target.value);
            setVersionId("");
            setVersions([]);
            setKey(crypto.randomUUID());
          }}
        >
          <option value="">Select a confirmed profile</option>
          {confirmed.map((p) => (
            <option key={p.id} value={p.id}>
              {p.profile?.title} · run {p.run_version || 1} · r{p.revision}
            </option>
          ))}
        </select>
      </label>
      <button
        className="text-button"
        disabled={busy || !profileId}
        onClick={() =>
          act(async () => {
            const h = await api(`/profiles/${profileId}/versions`);
            setVersions(h.versions.filter((v) => v.status === "confirmed"));
          })
        }
      >
        Choose a historical profile version
      </button>
      {versions.length > 0 && (
        <label className="field">
          <span>Confirmed profile version</span>
          <select
            value={versionId}
            onChange={(e) => {
              setVersionId(e.target.value);
              setKey(crypto.randomUUID());
            }}
          >
            <option value="">Latest confirmed profile</option>
            {versions.map((v) => (
              <option value={v.id} key={v.id}>
                Run {v.run_version || 1} · r{v.profile_revision}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        className="button secondary"
        disabled={busy || !profileId}
        onClick={() =>
          act(async () => {
            await api(`/generations/${blueprint.id}/rerun`, {
              idempotency_key: key,
              profile_id: profileId,
              ...(versionId ? { profile_version_id: versionId } : {}),
            });
            setKey(crypto.randomUUID());
            await reload();
          })
        }
      >
        Generate a new question set
      </button>
    </details>
  );
}
