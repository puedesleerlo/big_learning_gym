import React, { useEffect, useRef, useState } from "react";
import { visualizationDocument } from "./labVisualization.js";

function Text({ children }) {
  return <p className="lab-preserve-lines">{children}</p>;
}

export function MediaActivity({ block, enabled, preview, onEvent }) {
  const [loaded, setLoaded] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const player = useRef(null);
  useEffect(() => {
    if (!enabled) {
      player.current?.pause();
      setLoaded(false);
    }
  }, [enabled]);
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      if (!preview)
        await onEvent("media", { parameters: { activity_id: block.id } });
      setLoaded(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const mediaUrl = () => {
    const url = new URL(block.url);
    if (block.provider === "youtube") {
      url.searchParams.set("start", block.start_seconds || 0);
      if (block.end_seconds != null)
        url.searchParams.set("end", block.end_seconds);
    } else if (block.provider === "vimeo") {
      url.searchParams.set("dnt", "1");
      url.hash = `t=${block.start_seconds || 0}s`;
    }
    return url.toString();
  };
  const props = {
    ref: player,
    src: block.url,
    controls: true,
    preload: "metadata",
    onLoadedMetadata: (e) => {
      e.currentTarget.currentTime = block.start_seconds || 0;
    },
    onTimeUpdate: (e) => {
      if (
        block.end_seconds != null &&
        e.currentTarget.currentTime >= block.end_seconds
      )
        e.currentTarget.pause();
    },
    onPlay: (e) => {
      if (
        block.end_seconds != null &&
        e.currentTarget.currentTime >= block.end_seconds
      )
        e.currentTarget.currentTime = block.start_seconds || 0;
    },
    onError: () =>
      setError(
        "This media could not load. Check its URL and hosting access; the transcript remains available.",
      ),
    ...(block.captions_url ? { crossOrigin: "anonymous" } : {}),
    "aria-label": block.title,
  };
  const captions = block.captions_url ? (
    <track
      kind="captions"
      src={block.captions_url}
      srcLang={block.captions_language}
      label={block.captions_language}
      default
    />
  ) : null;
  return (
    <div className="lab-media">
      {block.description && <Text>{block.description}</Text>}
      {!loaded ? (
        <div className="lab-rich-placeholder">
          <button
            className="button secondary"
            disabled={!enabled || busy}
            onClick={load}
          >
            Load {block.kind === "audio" ? "audio" : "video"}
          </button>
          <small>Loads from {new URL(block.url).hostname} when selected.</small>
        </div>
      ) : block.provider === "native" ? (
        block.kind === "audio" ? (
          <audio {...props}>{captions}</audio>
        ) : (
          <video {...props} playsInline>
            {captions}
          </video>
        )
      ) : (
        <iframe
          className="lab-video-frame"
          title={block.title}
          src={mediaUrl()}
          sandbox="allow-scripts allow-same-origin allow-presentation"
          referrerPolicy="no-referrer"
          allow="fullscreen; encrypted-media; picture-in-picture"
          allowFullScreen
        />
      )}
      {block.transcript && (
        <details>
          <summary>Transcript</summary>
          <Text>{block.transcript}</Text>
        </details>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function VisualizationActivity({
  block,
  enabled,
  preview,
  run,
  onEvent,
}) {
  const initial = Object.fromEntries(
    (block.parameters || []).map((p) => [
      p.key,
      run?.visualization_inputs?.[block.id]?.[p.key] ?? p.initial,
    ]),
  );
  const [values, setValues] = useState(initial),
    [document, setDocument] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (!enabled) setDocument(null);
  }, [enabled]);
  const launch = async () => {
    setBusy(true);
    setError("");
    try {
      if (!preview)
        await onEvent("visualization", {
          parameters: { activity_id: block.id, inputs: values },
        });
      setDocument(visualizationDocument(block, values));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="lab-visualization">
      {block.description && <Text>{block.description}</Text>}
      <div className="lab-controls">
        {(block.parameters || []).map((p) => (
          <label key={p.key}>
            {p.label}: <strong>{values[p.key]}</strong>
            <input
              aria-label={p.label}
              type="range"
              min={p.min}
              max={p.max}
              step={p.step}
              value={values[p.key]}
              disabled={!enabled || busy}
              onChange={(e) => {
                setValues({ ...values, [p.key]: +e.target.value });
                setDocument(null);
              }}
            />
          </label>
        ))}
      </div>
      <div className="row">
        <button
          className="button secondary"
          disabled={!enabled || busy}
          onClick={launch}
        >
          {preview ? "Try visualization" : "Run visualization"}
        </button>
        {document && (
          <button className="text-button" onClick={() => setDocument(null)}>
            Stop visualization
          </button>
        )}
      </div>
      {document && (
        <iframe
          className="lab-visualization-frame"
          title={block.title}
          height={block.height}
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          allow="camera 'none'; microphone 'none'; geolocation 'none'; clipboard-read 'none'; clipboard-write 'none'"
          srcDoc={document}
        />
      )}
      <details open={!document}>
        <summary>Text explanation</summary>
        <Text>{block.fallback}</Text>
      </details>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function DiscussionActivity({
  block,
  enabled,
  preview,
  run,
  onDiscuss,
}) {
  const thread = run?.discussions?.[block.id] || { turns: [] };
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pendingRequest = useRef(null);
  const send = async () => {
    setBusy(true);
    setError("");
    const request = pendingRequest.current || {
      activity_id: block.id,
      message,
      expected_turn: thread.turns.length,
      idempotency_key: crypto.randomUUID(),
    };
    pendingRequest.current = request;
    try {
      await onDiscuss(request);
      pendingRequest.current = null;
      setMessage("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="lab-discussion">
      <Text>{block.prompt}</Text>
      {!!block.objectives?.length && (
        <details>
          <summary>Discussion goals</summary>
          <ul>
            {block.objectives.map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ul>
        </details>
      )}
      <div className="lab-discussion-turns" aria-live="polite">
        {thread.turns.map((turn, i) => (
          <div key={i} className="lab-discussion-turn">
            <div className="lab-learner-message">
              <strong>You</strong>
              <Text>{turn.message}</Text>
            </div>
            <div className="lab-tutor-message">
              <strong>Tutor</strong>
              <Text>{turn.reply}</Text>
              <small>
                {turn.provenance?.model} · Study support, not a grade
              </small>
              {!!turn.citations?.length && (
                <details>
                  <summary>Source passages</summary>
                  {turn.citations.map((id) => {
                    const source = turn.sources.find((s) => s.id === id);
                    return source ? (
                      <blockquote key={id}>
                        <small>
                          {source.anchor} · {source.source_version_id}
                        </small>
                        <Text>{source.text}</Text>
                      </blockquote>
                    ) : null;
                  })}
                </details>
              )}
            </div>
          </div>
        ))}
      </div>
      {preview ? (
        <small>
          The tutor is available during a study visit. Preview makes no model
          calls.
        </small>
      ) : (
        <>
          <label>
            Your message
            <textarea
              aria-label={`Message to ${block.title}`}
              maxLength={4000}
              value={message}
              disabled={
                !enabled ||
                busy ||
                thread.pending ||
                thread.turns.length >= block.max_turns
              }
              onChange={(e) => {
                setMessage(e.target.value);
                pendingRequest.current = null;
              }}
            />
          </label>
          <div className="row between">
            <button
              className="button"
              disabled={
                !enabled ||
                busy ||
                thread.pending ||
                !message.trim() ||
                thread.turns.length >= block.max_turns
              }
              onClick={send}
            >
              {busy || thread.pending ? "Tutor is thinking…" : "Send to tutor"}
            </button>
            <small>
              {thread.turns.length} / {block.max_turns} turns
            </small>
          </div>
          <small>
            Your message and this lesson’s source context go to the configured
            tutoring model.
          </small>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}{" "}
          <button
            className="text-button"
            onClick={() => {
              pendingRequest.current = null;
              setError("");
            }}
          >
            Prepare a new request
          </button>
        </p>
      )}
    </div>
  );
}
