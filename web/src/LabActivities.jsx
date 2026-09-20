import { workspaceStorage } from "./workspace.js";
import React, { useState } from "react";
import { BookOpen, Check, FlaskConical, Play } from "lucide-react";
import {
  MediaActivity,
  VisualizationActivity,
  DiscussionActivity,
} from "./RichLabActivities.jsx";

export const activityLabels = {
  reading: "Reading",
  prediction: "Prediction",
  worked_example: "Worked example",
  reflection: "Reflection",
  parameter_experiment: "Parameter experiment",
  assessment: "Practice check",
  coursework: "Coursework",
  media: "Video or audio",
  visualization: "Interactive visualization",
  discussion: "Discussion tutor",
};

const Paragraphs = ({ text }) =>
  (text || "")
    .split(/\n\s*\n/)
    .filter(Boolean)
    .map((p, i) => (
      <p key={i} className="lab-preserve-lines">
        {p}
      </p>
    ));

export default function LabActivity({
  block,
  run,
  running,
  preview,
  onEvent,
  onPractice,
  onCoursework,
  onDiscuss,
  draftKey,
}) {
  const [value, setValue] = useState(
    () =>
      (!preview && workspaceStorage.getItem(draftKey)) ||
      run?.responses?.[block.id]?.value ||
      "",
  );
  const [inputs, setInputs] = useState(() =>
    Object.fromEntries(
      (block.inputs || []).map((input) => [
        input.key,
        run?.experiment_results?.[block.id]?.inputs?.[input.key] ??
          input.initial,
      ]),
    ),
  );
  const [result, setResult] = useState(
    run?.experiment_results?.[block.id] || null,
  );
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState(false);
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
  const editable = !preview && running && !busy;
  return (
    <section
      className={`lab-activity-block lab-block-${block.type}`}
      aria-label={block.title}
    >
      <div className="row between">
        <h3>{block.title}</h3>
        <span className="badge">
          {activityLabels[block.type] || block.type}
        </span>
      </div>
      {(block.type === "reading" || block.type === "worked_example") && (
        <>
          <Paragraphs text={block.body} />
          {block.type === "reading" && !preview && (
            <button
              className="text-button"
              disabled={!editable}
              onClick={() =>
                act(async () => {
                  await onEvent("reading", {
                    parameters: { activity_id: block.id },
                  });
                  setSaved(true);
                })
              }
            >
              <BookOpen size={15} />
              {saved ? "Reading recorded" : "Record this reading"}
            </button>
          )}
        </>
      )}
      {(block.type === "prediction" || block.type === "reflection") && (
        <>
          <label htmlFor={`response-${block.id}`}>
            <Paragraphs text={block.prompt} />
          </label>
          <textarea
            id={`response-${block.id}`}
            value={value}
            readOnly={preview}
            maxLength={12000}
            placeholder={
              block.type === "prediction"
                ? "I predict… because…"
                : "What changed in your reasoning?"
            }
            onChange={(e) => {
              setValue(e.target.value);
              setSaved(false);
              if (!preview) workspaceStorage.setItem(draftKey, e.target.value);
            }}
          />
          <button
            className="button secondary"
            disabled={!editable || !value.trim()}
            onClick={() =>
              act(async () => {
                await onEvent("response", {
                  parameters: { activity_id: block.id, value },
                });
                setSaved(true);
              })
            }
          >
            <Check size={15} />
            {saved ? "Response saved" : "Save response"}
          </button>
          <small>
            {preview
              ? "Responses are disabled in preview."
              : "Your reasoning is saved as study evidence; it is not automatically graded."}
          </small>
        </>
      )}
      {block.type === "parameter_experiment" && (
        <>
          <Paragraphs text={block.description} />
          <div className="lab-controls">
            {(block.inputs || []).map((input) => (
              <label key={input.key}>
                {input.label}: <strong>{inputs[input.key]}</strong>
                <input
                  type="range"
                  min={input.min}
                  max={input.max}
                  step={input.step || 1}
                  value={inputs[input.key]}
                  disabled={busy}
                  onChange={(e) => {
                    setInputs({
                      ...inputs,
                      [input.key]: Number(e.target.value),
                    });
                    setResult(null);
                  }}
                />
              </label>
            ))}
          </div>
          <button
            className="button"
            disabled={busy || (!preview && !running)}
            onClick={() =>
              act(async () => {
                if (preview) {
                  setResult({
                    inputs: { ...inputs },
                    output:
                      (block.offset || 0) +
                      block.inputs.reduce(
                        (sum, input) =>
                          sum + input.coefficient * inputs[input.key],
                        0,
                      ),
                  });
                } else {
                  const record = await onEvent("experiment", {
                    parameters: { activity_id: block.id, inputs },
                  });
                  setResult(record.experiment_results?.[block.id] || null);
                }
              })
            }
          >
            <FlaskConical size={16} />
            {preview ? "Preview this model" : "Run comparison"}
          </button>
          {result && (
            <div className="lab-result" role="status">
              <strong>
                {block.output_label || "Result"}:{" "}
                {Number(result.output).toLocaleString(undefined, {
                  maximumFractionDigits: 4,
                })}
                {block.unit ? ` ${block.unit}` : ""}
              </strong>
            </div>
          )}
          <details>
            <summary>How this model works</summary>
            <p>
              Start at {block.offset || 0}, then add each input multiplied by
              its contribution:
            </p>
            <ul>
              {(block.inputs || []).map((input) => (
                <li key={input.key}>
                  {input.label} × {input.coefficient}
                </li>
              ))}
            </ul>
            <small>
              This authored model illustrates its stated assumptions. It does
              not estimate a real-world effect.
            </small>
          </details>
        </>
      )}
      {block.type === "assessment" && (
        <>
          <p>
            {block.count} {block.mode === "transfer" ? "transfer" : "practice"}{" "}
            questions from this lesson’s gym topic. Linked practice records the
            support received here.
          </p>
          <button
            className="button"
            disabled={!editable}
            onClick={() => onPractice(block)}
          >
            <Play size={16} />
            {run?.session_id
              ? "Open linked practice"
              : `Start ${block.mode === "transfer" ? "transfer check" : "practice check"}`}
          </button>
        </>
      )}
      {block.type === "coursework" && (
        <>
          <p>
            Continue with the assignment and its existing rubric in Coursework.
          </p>
          <button
            className="button secondary"
            disabled={preview || busy}
            onClick={() => onCoursework(block.assignment_id)}
          >
            Open coursework
          </button>
        </>
      )}
      {block.type === "media" && (
        <MediaActivity
          block={block}
          enabled={preview || editable}
          preview={preview}
          onEvent={onEvent}
        />
      )}
      {block.type === "visualization" && (
        <VisualizationActivity
          block={block}
          enabled={preview || editable}
          preview={preview}
          run={run}
          onEvent={onEvent}
        />
      )}
      {block.type === "discussion" && (
        <DiscussionActivity
          block={block}
          enabled={editable}
          preview={preview}
          run={run}
          onDiscuss={onDiscuss}
        />
      )}
      {!preview &&
        !running &&
        !["worked_example", "coursework"].includes(block.type) && (
          <small>
            Start or resume the learning session to record this activity.
          </small>
        )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

export { Paragraphs };
