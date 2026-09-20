import React, { useState } from "react";

function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function DataField({ value, onChange }) {
  const [text, setText] = useState(JSON.stringify(value || {}, null, 2)),
    [error, setError] = useState("");
  return (
    <Field
      label="Visualization data (JSON object)"
      hint="Use teaching datasets. This data is available as gym.data inside the visualization."
    >
      <textarea
        className="lab-code-input"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = JSON.parse(e.target.value);
            if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
              throw new Error("Use a JSON object");
            onChange(parsed);
            setError("");
          } catch {
            onChange(null);
            setError(
              "Enter a valid JSON object before previewing or publishing.",
            );
          }
        }}
      />
      {error && (
        <small className="error" role="alert">
          {error}
        </small>
      )}
    </Field>
  );
}

export default function RichLabEditor({ block, onChange }) {
  const set = (key, value) => onChange({ ...block, [key]: value });
  const text = (key, label, hint) => (
    <Field key={key} label={label} hint={hint}>
      <textarea
        className={
          ["html", "css", "javascript"].includes(key) ? "lab-code-input" : ""
        }
        value={block[key] || ""}
        onChange={(e) => set(key, e.target.value)}
      />
    </Field>
  );
  if (block.type === "media")
    return (
      <>
        <div className="form-row">
          <Field label="Media kind">
            <select
              value={block.kind}
              onChange={(e) =>
                onChange({ ...block, kind: e.target.value, provider: "native" })
              }
            >
              <option value="video">Video</option>
              <option value="audio">Audio / podcast</option>
            </select>
          </Field>
          <Field label="Player">
            <select
              value={block.provider}
              onChange={(e) =>
                onChange({
                  ...block,
                  provider: e.target.value,
                  captions_url: null,
                  end_seconds:
                    e.target.value === "vimeo" ? null : block.end_seconds,
                })
              }
            >
              <option value="native">Direct media file</option>
              {block.kind === "video" && (
                <>
                  <option value="youtube">YouTube</option>
                  <option value="vimeo">Vimeo</option>
                </>
              )}
            </select>
          </Field>
        </div>
        <Field
          label="Media URL"
          hint={
            block.provider === "youtube"
              ? "https://www.youtube-nocookie.com/embed/VIDEO_ID"
              : block.provider === "vimeo"
                ? "https://player.vimeo.com/video/VIDEO_ID"
                : "An HTTPS URL for a playable video or audio file."
          }
        >
          <input
            type="url"
            value={block.url}
            onChange={(e) => set("url", e.target.value)}
          />
        </Field>
        {text("description", "Introduction")}
        {text("transcript", "Transcript")}
        <div className="form-row">
          <Field label="Start (seconds)">
            <input
              type="number"
              min="0"
              max="86400"
              value={block.start_seconds ?? 0}
              onChange={(e) => set("start_seconds", +e.target.value)}
            />
          </Field>
          {block.provider !== "vimeo" && (
            <Field label="End (seconds, optional)">
              <input
                type="number"
                min="1"
                max="86400"
                value={block.end_seconds ?? ""}
                onChange={(e) =>
                  set(
                    "end_seconds",
                    e.target.value === "" ? null : +e.target.value,
                  )
                }
              />
            </Field>
          )}
        </div>
        {block.provider === "native" && (
          <div className="form-row">
            <Field
              label="Captions URL (optional)"
              hint="HTTPS WebVTT file; its host must allow cross-origin playback."
            >
              <input
                type="url"
                value={block.captions_url || ""}
                onChange={(e) => set("captions_url", e.target.value || null)}
              />
            </Field>
            <Field label="Caption language">
              <input
                value={block.captions_language || "en"}
                onChange={(e) => set("captions_language", e.target.value)}
              />
            </Field>
          </div>
        )}
      </>
    );
  if (block.type === "discussion")
    return (
      <>
        {text("prompt", "Opening discussion prompt")}
        <Field label="Learning objectives" hint="One objective per line">
          <textarea
            value={(block.objectives || []).join("\n")}
            onChange={(e) => set("objectives", e.target.value.split("\n"))}
          />
        </Field>
        <div className="form-row">
          <Field label="Discussion style">
            <select
              value={block.style}
              onChange={(e) => set("style", e.target.value)}
            >
              <option value="socratic">Socratic questions</option>
              <option value="explain">Explain and check</option>
              <option value="debate">Explore counterarguments</option>
            </select>
          </Field>
          <Field label="Maximum turns">
            <input
              type="number"
              min="1"
              max="24"
              value={block.max_turns}
              onChange={(e) => set("max_turns", +e.target.value)}
            />
          </Field>
          <Field label="Target response words">
            <input
              type="number"
              min="50"
              max="500"
              value={block.response_words}
              onChange={(e) => set("response_words", +e.target.value)}
            />
          </Field>
        </div>
        <small>
          Uses this lesson’s confirmed sources and the configured tutoring
          model. Conversations are study support.
        </small>
      </>
    );
  if (block.type === "visualization")
    return (
      <>
        {text("description", "What should the learner explore?")}
        {text(
          "html",
          "HTML",
          "Self-contained visualization markup. External resources are blocked.",
        )}
        {text("css", "CSS")}
        {text(
          "javascript",
          "JavaScript",
          "Read gym.parameters and gym.data. Runs only inside an isolated browser frame; there is no Gym API bridge.",
        )}
        <DataField
          value={block.data}
          onChange={(value) => set("data", value)}
        />
        {(block.parameters || []).map((p, index) => (
          <fieldset className="lab-input-editor" key={index}>
            <legend>Control {index + 1}</legend>
            <div className="form-row">
              {["key", "label", "min", "max", "initial", "step"].map((name) => (
                <Field key={name} label={name}>
                  <input
                    type={["key", "label"].includes(name) ? "text" : "number"}
                    step="any"
                    value={p[name]}
                    onChange={(e) =>
                      set(
                        "parameters",
                        block.parameters.map((x, i) =>
                          i === index
                            ? {
                                ...x,
                                [name]: ["key", "label"].includes(name)
                                  ? e.target.value
                                  : +e.target.value,
                              }
                            : x,
                        ),
                      )
                    }
                  />
                </Field>
              ))}
            </div>
            <button
              className="text-button"
              onClick={() =>
                set(
                  "parameters",
                  block.parameters.filter((_, i) => i !== index),
                )
              }
            >
              Remove control
            </button>
          </fieldset>
        ))}
        <button
          className="text-button"
          disabled={(block.parameters || []).length >= 20}
          onClick={() =>
            set("parameters", [
              ...(block.parameters || []),
              {
                key: `input_${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`,
                label: "New control",
                min: 0,
                max: 10,
                initial: 5,
                step: 1,
              },
            ])
          }
        >
          Add control
        </button>
        <Field label="Frame height">
          <input
            type="number"
            min="180"
            max="1200"
            value={block.height}
            onChange={(e) => set("height", +e.target.value)}
          />
        </Field>
        {text(
          "fallback",
          "Text explanation",
          "Explain the visualization for learners who cannot use it.",
        )}
      </>
    );
  return null;
}
