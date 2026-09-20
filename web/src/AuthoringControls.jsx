import React, { useEffect, useState } from "react";

export function ProfileBuilder({
  courseId,
  coursework,
  sources,
  materialIds,
  assessmentIds,
  api,
  act,
  busy,
  reload,
}) {
  const [assignmentIds, setAssignmentIds] = useState([]);
  const [rubricIds, setRubricIds] = useState([]);
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [manual, setManual] = useState(false);
  const [targetAssignmentId, setTargetAssignmentId] = useState("");
  const [emergentIds, setEmergentIds] = useState([]);
  useEffect(() => {
    setAssignmentIds([]);
    setRubricIds([]);
    setTitle("");
    setTarget("");
    setTargetAssignmentId("");
    setEmergentIds([]);
  }, [courseId]);
  const assignments =
    coursework?.assignment.filter((a) => a.course_id === courseId) || [];
  const rubrics =
    coursework?.rubric.filter(
      (r) => !r.course_id || r.course_id === courseId,
    ) || [];
  const checked = (ids, setter, id) =>
    setter(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  const unreviewed = [...materialIds, ...assessmentIds, ...emergentIds].some(
    (id) =>
      sources?.find((s) => s.id === id)?.reconstruction_status !== "confirmed",
  );
  const create = () =>
    act(async () => {
      const payload = {
        course_id: courseId,
        assignment_ids: assignmentIds,
        source_ids: assessmentIds.filter((id) => !emergentIds.includes(id)),
        material_source_ids: materialIds.filter(
          (id) => !emergentIds.includes(id),
        ),
        emergent_source_ids: emergentIds,
        target_assignment_id: targetAssignmentId || null,
        rubric_ids: rubricIds,
        title,
        target,
      };
      if (manual) {
        const rubric = rubrics.find((r) => rubricIds.includes(r.id));
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
    });
  return (
    <section className="panel section" aria-label="Create a targeted profile">
      <h2>Create an assessment profile</h2>
      <p>
        Start with the future task you intend to prepare for. Prior material
        provides a baseline; emergent material refines it as the course
        progresses. Grades, TA feedback and your answers are excluded.
      </p>
      <label className="field">
        <span>Profile title</span>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Quiz 1 · probability and sampling"
        />
      </label>
      <h3>1. Intention · the future task</h3>
      <label className="field">
        <span>Intended coursework (optional)</span>
        <select
          aria-label="Intended coursework (optional)"
          value={targetAssignmentId}
          onChange={(e) => {
            setTargetAssignmentId(e.target.value);
            setAssignmentIds((ids) =>
              ids.filter((id) => id !== e.target.value),
            );
          }}
        >
          <option value="">
            A specific assessment goal without a coursework entry
          </option>
          {assignments
            .filter((a) => a.purpose !== "self_study")
            .map((a) => (
              <option key={a.id} value={a.id}>
                {a.title} · {a.status}
              </option>
            ))}
        </select>
      </label>
      <label className="field">
        <span>Specific assessment target</span>
        <textarea
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="What should this profile assess? Name the concepts, reasoning demands and topic boundaries."
        />
      </label>
      <fieldset>
        <legend>2. Prior evidence · coursework examples</legend>
        {assignments.length ? (
          assignments
            .filter((a) => a.id !== targetAssignmentId)
            .map((a) => (
              <label className="checkbox" key={a.id}>
                <input
                  type="checkbox"
                  checked={assignmentIds.includes(a.id)}
                  onChange={() =>
                    checked(assignmentIds, setAssignmentIds, a.id)
                  }
                />
                {a.title} ·{" "}
                {a.purpose === "self_study" ? "self-study" : "coursework"}
                {!a.rubric_version_id && " · rubric unavailable"}
              </label>
            ))
        ) : (
          <p>
            No coursework yet. A profile based on instructional material will be
            explicitly proposed.
          </p>
        )}
      </fieldset>
      <fieldset>
        <legend>Additional rubric references</legend>
        {rubrics.map((r) => (
          <label className="checkbox" key={r.id}>
            <input
              type="checkbox"
              checked={rubricIds.includes(r.id)}
              onChange={() => checked(rubricIds, setRubricIds, r.id)}
            />
            {r.title} · {r.authority}
          </label>
        ))}
      </fieldset>
      <p>
        {materialIds.length} instructional sources and {assessmentIds.length}{" "}
        assessment/rubric sources selected in the library above. Coursework
        rubrics are included automatically.
      </p>
      <fieldset>
        <legend>3. Emergent evidence · newly available material</legend>
        <p>
          Select task clarifications, new slides, examples or rubric updates.
          These keep their own evidence role.
        </p>
        {sources
          ?.filter(
            (s) =>
              s.course_id === courseId &&
              s.latest &&
              ["instruction", "research", "assessment", "rubric"].includes(
                s.role,
              ),
          )
          .map((s) => (
            <label className="checkbox" key={s.id}>
              <input
                type="checkbox"
                checked={emergentIds.includes(s.id)}
                onChange={() => checked(emergentIds, setEmergentIds, s.id)}
              />
              {s.name} · {s.role}
            </label>
          ))}
      </fieldset>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={manual}
          onChange={(e) => setManual(e.target.checked)}
        />
        Write and review a profile manually (no model call)
      </label>
      {unreviewed && (
        <p className="error-text">
          Review and confirm the selected source reconstructions first.
        </p>
      )}
      <button
        className="button"
        disabled={
          busy ||
          !(
            materialIds.length ||
            emergentIds.some((id) =>
              ["instruction", "research"].includes(
                sources?.find((s) => s.id === id)?.role,
              ),
            )
          ) ||
          target.trim().length < 5 ||
          title.trim().length < 2 ||
          unreviewed
        }
        onClick={create}
      >
        Create profile proposal
      </button>
      <p className="small muted">
        Review the proposal below, including its explicit practice rubric,
        before using it in a blueprint.
      </p>
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
    .sort((a, b) => (a.received_at || "").localeCompare(b.received_at || ""));
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
  const outcomes =
    data.coursework_outcome?.filter((o) => o.assignment_id === assignment.id) ||
    [];
  const superseded = new Set(outcomes.map((o) => o.supersedes).filter(Boolean));
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
      supersedes: previous?.id || null,
    });
    setEditing(true);
  };
  return (
    <section className="section" aria-label="Instructor grades and feedback">
      <div className="row between">
        <h2>Instructor grades & feedback</h2>
        <button className="button secondary" onClick={() => open()}>
          Add grade or feedback
        </button>
      </div>
      <p>
        {assignment.status === "completed"
          ? "Coursework completed externally. "
          : ""}
        Grades and TA comments are saved here. You can add them before uploading
        your submitted work.
      </p>
      {courseworkGrades(data, assignment.id)
        .filter((o) => o.submission_id)
        .map((o) => (
          <div className="official-grade" key={o.id}>
            <strong>
              Instructor grade: {o.score} / {o.max_score}
            </strong>
            <p className="preserve">{o.feedback}</p>
            <p className="small muted">
              Entered by you · {o.individual ? "Individual" : "Team"} outcome ·
              Linked to a saved submission
            </p>
            <CourseworkFile
              sourceId={o.source_id}
              sources={sources}
              api={api}
              act={act}
            />
          </div>
        ))}
      {outcomes.map((o) => (
        <details
          className="official-grade"
          key={o.id}
          open={!superseded.has(o.id)}
        >
          <summary>
            <strong>
              {o.score == null
                ? "Feedback received · no grade reported"
                : `Instructor grade: ${o.score} / ${o.max_score}`}
            </strong>
            {superseded.has(o.id) && (
              <span className="badge">Superseded · retained history</span>
            )}
          </summary>
          {o.feedback ? (
            <p className="preserve">{o.feedback}</p>
          ) : (
            <p className="muted">No written feedback recorded.</p>
          )}
          <p>{o.attribution}</p>
          {o.source_url && (
            <a href={o.source_url} target="_blank" rel="noreferrer">
              Original course record
            </a>
          )}
          <p className="small muted">
            Observed {new Date(o.observed_at).toLocaleString()} ·{" "}
            {o.occurred_at
              ? `Feedback dated ${new Date(o.occurred_at).toLocaleString()}`
              : "Original feedback date not recorded"}{" "}
            · Saved in Coursework
          </p>
          {o.learner_comment && (
            <details>
              <summary>
                Your comments (separate from instructor feedback)
              </summary>
              <p className="preserve">{o.learner_comment}</p>
            </details>
          )}
          {o.limitations && <p className="muted">{o.limitations}</p>}
          <CourseworkFile
            sourceId={o.source_id}
            sources={sources}
            api={api}
            act={act}
          />
          {o.original_record_snapshot && (
            <details>
              <summary>Imported grade and feedback record</summary>
              <p className="preserve">{o.original_record_snapshot.body}</p>
            </details>
          )}
          {!superseded.has(o.id) && (
            <button className="text-button" onClick={() => open(o)}>
              Update grade, feedback or attachment
            </button>
          )}
        </details>
      ))}
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
              disabled={busy || (draft.score === "" && !draft.feedback.trim())}
              onClick={() =>
                act(async () => {
                  await api(`/assignments/${assignment.id}/outcomes`, {
                    ...draft,
                    score: draft.score === "" ? null : Number(draft.score),
                  });
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
        ["instruction", "research", "assessment", "rubric"].includes(s.role),
    ) || [];
  const pick = (label, key, options) => (
    <label className="field">
      <span>{label}</span>
      <select
        aria-label={label}
        multiple
        size={Math.min(6, Math.max(2, options.length))}
        value={draft[key]}
        onChange={(e) =>
          set(
            key,
            [...e.target.selectedOptions].map((o) => o.value),
          )
        }
      >
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.title || o.name}
            {o.role ? ` · ${o.role} · ${o.reconstruction_status}` : ""}
          </option>
        ))}
      </select>
    </label>
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
      <label className="field">
        <span>Intended future coursework</span>
        <select
          value={draft.target_assignment_id || ""}
          onChange={(e) => set("target_assignment_id", e.target.value || null)}
        >
          <option value="">Goal without a coursework entry</option>
          {assignments
            .filter((a) => a.purpose !== "self_study")
            .map((a) => (
              <option key={a.id} value={a.id}>
                {a.title}
              </option>
            ))}
        </select>
      </label>
      <h3>Prior evidence</h3>
      {pick(
        "Prior coursework examples",
        "assignment_ids",
        assignments.filter((a) => a.id !== draft.target_assignment_id),
      )}
      {pick(
        "Prior instructional material",
        "material_source_ids",
        available.filter((s) => ["instruction", "research"].includes(s.role)),
      )}
      {pick(
        "Prior assessment examples or rubrics",
        "source_ids",
        available.filter((s) => ["assessment", "rubric"].includes(s.role)),
      )}
      <h3>Emergent evidence</h3>
      {pick("New information about the task", "emergent_source_ids", available)}
      <p>
        Each source belongs in one evidence category. Select reviewed source
        versions; new source versions are never substituted silently.
      </p>
      <button
        className="button"
        disabled={busy || draft.target.trim().length < 5}
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
