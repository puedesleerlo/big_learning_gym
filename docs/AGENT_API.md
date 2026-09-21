# Learning Gym agent interface

Agents operate the running Gym through the same HTTP API as its UI. The authoring
routes add missing course/module, guide, glossary, and question editing; the existing
source, rubric, assignment, session, planning, artifact, and health routes remain the
canonical services. No database edits or second platform are needed.

## Connect and discover

The local server defaults to `http://127.0.0.1:8787`. Set `GYM_BASE_URL` to override
it. `GYM_ACCESS_TOKEN` supplies the existing API's bearer token when configured;
the clients also load the project's `.env`. Never put credentials in commands or
request JSON.

```sh
.venv/bin/python -m gym.agent_client capabilities
.venv/bin/python -m gym.agent_client schema --output /tmp/gym-openapi.json
.venv/bin/python -m gym.agent_client GET /api/overview
```

`GET /api/agent/capabilities` lists **every registered API operation** and workflow
instructions. `GET /api/agent/schema` returns the live OpenAPI schema, including
all typed authoring bodies. Existing routes with freeform dictionaries have
supplemental rubric/assignment schemas and workflow field instructions in the
capability response. The HTTP client supports every HTTP method, JSON from a file
or stdin, multipart uploads, query strings, response downloads, and nonzero error
exit codes. It does not retry mutations or follow redirects.

## Author material

1. Read the course and its current revision from
   `GET /api/authoring/courses/{id}`. Create or replace its title, description, and
   ordered modules with `PUT` to that path. `expected_revision: 0` creates a record;
   updating requires the returned revision. Module prerequisites must form an
   acyclic graph of existing module IDs. Referenced modules cannot be removed.
2. Upload sources with the existing multipart endpoint, inspect the returned
   fragments, and confirm only reconstructions you have reviewed. Source version
   IDs and fragment IDs are distinct. Cite fragment IDs in authored material.
3. Write guides with `PUT /api/authoring/guides/{id}`, glossary entries with
   `PUT /api/authoring/terms/{id}`, and questions with
   `POST /api/authoring/items` or `PUT /api/authoring/items/{id}`. Use a stable ID
   for repeatable creation. All material references a valid module, confirmed
   source fragments from its own course, and explicit author provenance.
4. Read back `GET /api/authoring/courses/{id}/materials` and
   `GET /api/library/{id}` to verify what the learner will receive. Item reads
   omit keys and distractor explanations by default. `include_solutions=true`
   permits author review, except while a simulation in that course is active.

```sh
.venv/bin/python -m gym.agent_client POST /api/sources \
  --field course_id=causality --field role=research --file file=/absolute/path/paper.md
.venv/bin/python -m gym.agent_client GET /api/sources/SOURCE_VERSION_ID/fragments
.venv/bin/python -m gym.agent_client POST /api/sources/SOURCE_VERSION_ID/confirm \
  --json /tmp/reviewed-source.json
.venv/bin/python -m gym.agent_client PUT /api/authoring/guides/causality-intro \
  --json /tmp/lesson.json
```

Every authored record includes a provenance object:

```json
{
  "author": "Learning Gym assistant",
  "method": "agent",
  "rationale": "Teach intervention before interpreting causal discovery results",
  "reference_urls": ["https://causal-learn.readthedocs.io/en/latest/"]
}
```

`method` is `agent`, `human`, or `import`. Provenance records authorship and
references, **not independent verification**. Questions are visibly labeled
`authored`. Confirming extraction establishes readable source text, not the
truth of a paper or blog claim. An agent should label its synthesis, inspect
the cited source, and distinguish research findings from product commentary.

Guide fields follow the existing UI: `code` is the module ID, `subtitle` is the
lesson title, and `blocks` contain `{id, h, html}`. HTML is sanitized using the
existing safe markup policy. Glossary entries use `term`, `def`, `module`,
`distinguish`, and `why`. Items use the `GeneratedItem` contract plus `course_id`,
`module`, `pool` (`practice` or `transfer`), optional `term_ids`, optional
`rubric_version_id`, and provenance. Linked glossary terms appear in the existing
session's Key terms aid; taking the aid remains recorded as assistance.

## Named labs: validate, preview, publish

A course can contain multiple named labs. Each lab has a globally unique
`lab_id` in `/api/labs/{lab_id}` and an explicit `course_id` in its write body.
Do not assume the two IDs are equal. Existing default labs keep their existing
IDs and URLs. A lesson's `id` identifies a step within a lab; its `module`
references an existing course module and defaults to the lesson ID only when
omitted. Multiple lessons may intentionally share one module.

Discover the existing content and supported blocks before authoring:

```sh
.venv/bin/python -m gym.agent_client GET /api/labs
.venv/bin/python -m gym.agent_client GET '/api/labs?course_id=COURSE_ID'
.venv/bin/python -m gym.agent_client GET /api/lab-activity-types
.venv/bin/python -m gym.agent_client GET /api/labs/LAB_ID
```

The list route returns summaries. The registry returns activity schemas and
templates; the live OpenAPI schema is authoritative for current field limits.
`LabWrite` contains `course_id`, `expected_revision`, `title`, `description`,
`objectives`, `prerequisite_lab_ids`, `lessons`, optional external `sources`,
and provenance. Lesson fields include `id`, `module`, `title`, `stage`,
`minutes`, `objectives`, `prerequisites`, `source_ids`, and `activities`.
Legacy lesson fields remain compatible, and `paper_bridge` is optional.

Keep the reference namespaces distinct:

- Lesson `source_ids` contain confirmed **source-version IDs** from the same
  course, with instructional or research roles. They are not fragment IDs.
- Guides, glossary terms, and questions cite **fragment IDs** through their
  existing authoring contracts.
- The lab's optional external `sources` catalog holds bibliographic records.
  A `paper_bridge.source_id` refers to this catalog. A catalog entry does not
  upload, review, or confirm a source document.
- Lesson `prerequisites` refer to lesson IDs in that lab. Top-level
  `prerequisite_lab_ids` refer to already-existing labs in the same course.
  Both dependency graphs must be acyclic.

Each activity has its own `id`, `title`, and discriminating `type`. Supported
types are:

- `reading` and `worked_example`: authored `body` text.
- `prediction` and `reflection`: a `prompt` for the learner to answer.
- `parameter_experiment`: `description`, bounded `inputs`, `offset`,
  `output_label`, and `unit`. Each input has `key`, `label`, `min`, `max`,
  `step`, `initial`, and `coefficient`. Its output is the declared affine sum
  `offset + sum(coefficient * input)`. This does not execute arbitrary
  expressions, products of inputs, user code, or an external simulation.
- `assessment`: `mode` (`practice` or `transfer`) and `count`. This opens the
  existing session workflow using the lesson's course/module question bank.
  Author suitable items in that pool first; a block does not contain questions
  or solutions and does not create learner attempts when published. A lesson
  supports at most one assessment block, with 1–30 questions.
- `coursework`: `assignment_id`, referring to an existing same-course
  assignment. Create its rubric and assignment through the normal routes first.
- `media`: `kind` (video/audio), `provider` (native/youtube/vimeo), HTTPS `url`,
  optional `description`, plain-text `transcript`, `start_seconds`, and optional
  `end_seconds`. Native players also accept HTTPS WebVTT `captions_url` and
  `captions_language`. YouTube uses `https://www.youtube-nocookie.com/embed/ID`
  and Vimeo uses `https://player.vimeo.com/video/ID`, without query parameters.
  Vimeo supports starts only; native media and YouTube support end bounds.
  Hosts must permit playback/embedding; authenticated course recordings may
  need their own browser login. Loading is user-initiated. URLs are references,
  not a copy or immutable snapshot of the hosted recording.
- `visualization`: self-contained `html`, `css`, `javascript`, an object `data`,
  numeric `parameters`, frame `height`, and required plain-text `fallback`.
  Each parameter has `key`, `label`, `min`, `max`, `step`, and `initial`.
  Code reads `gym.parameters` and `gym.data`. Changing a control and running
  reloads the frame with those values. HTML/SVG/canvas and bundled libraries can
  implement arbitrary teaching visuals; external scripts, fetch, workers and
  frame navigation are blocked. Code stays in the browser's sandbox, not the
  Gym application or server. There is no postMessage/API bridge for results.
  Supply teaching data only, never credentials, learner history or private
  institutional documents. Use preview's “Try visualization” to review behavior
  without recording study activity; visual correctness remains an author review.
- `discussion`: `prompt`, `objectives`, `style` (socratic/explain/debate),
  `max_turns` (1–24, default 8), and `response_words` (target 50–500, default 180).
  Inherits the lesson's pinned confirmed sources and the existing `tutor` role
  from `config/models.json`. A block cannot choose a new provider, system prompt
  or scoring method. Preview shows the prompt and goals without calling a model.

Copy the `activities` entries from
[`content/examples/rich-lab-blocks.json`](../content/examples/rich-lab-blocks.json)
into an existing lesson, replace media URLs/content, and use the same
validate → preview → publish workflow. No dedicated MCP tool is required;
`gym_request` accepts the normal LabWrite payload. The registry supplies a
complete normalized template and schema for every block, including the new types.

### Learner discussion and rich activity events

During an actual running study visit, send:

```json
{
  "activity_id": "discussion-1",
  "message": "Why does doubling the frequency add cycles?",
  "expected_turn": 0,
  "idempotency_key": "a-unique-request-id"
}
```

to `POST /api/lab-activities/{visit_id}/discussion`. This is a model-backed
learner action, not an authoring operation. Read the visit's `discussions`
mapping first; `expected_turn` is the number of completed exchanges for this
block. Successful responses contain the updated visit and turns, source snippets,
citations and provider/model/prompt provenance. Replay a completed request using
the exact same key/payload. A failed key cannot be reused for a new call; read
current turns and use a new key. Competing requests return 409. A pending call
after process interruption becomes retryable after one hour; do not assume that
an interrupted provider call consumed no budget. Active course simulations,
paused/finished visits and missing readable sources reject new calls.

`media` events accept only `parameters: {"activity_id": "..."}`. Visualization
events use action `visualization` and `parameters: {"activity_id": "...",
"inputs": {"frequency": 2}}`. Both use the normal event idempotency key and
validate against the visit's pinned block. They record preparation exposure;
media duration, completion, visualization output and grades cannot be asserted
through these events. Tutor replies count as help. Existing practice linking
discloses this assistance; tutor conversation is excluded from assessor inputs.

The non-causal [ideal-spring example](../content/examples/general-lab.json)
uses two lessons in one module, with reading, prediction, a worked example,
a bounded parameter experiment, and reflection. Its course, module, and source
IDs are explicit placeholders. It intentionally has no assessment or coursework
dependency, so those blocks can be added after their underlying material exists.
This is a template, not an already-published or independently validated lab.

### Copyable example workflow

These commands create an example course in the selected Gym. Use a development
workspace when trying the example; for actual authoring, use the intended
existing course and its current revision. Check that your chosen course and lab
IDs are unused before creating new records. Run commands from the repository.

Create a course with one module using the existing authoring route:

```sh
.venv/bin/python -m gym.agent_client PUT /api/authoring/courses/physics-foundations-example --json - <<'JSON'
{
  "expected_revision": 0,
  "title": "Physics foundations example",
  "description": "Practice proportional reasoning with a declared ideal-spring model.",
  "modules": [
    {
      "id": "springs",
      "title": "Ideal springs and model limits",
      "objectives": ["Reason about proportional relationships and model assumptions"],
      "estimated_minutes": 25,
      "level": "beginner"
    }
  ],
  "provenance": {
    "author": "Learning Gym example author",
    "method": "agent",
    "rationale": "Create a course for the original ideal-spring teaching example",
    "reference_urls": []
  }
}
JSON
```

Prepare an instructional source from the example's original teaching text.
This is transparently authored material, not an imported textbook or a record
of real measurements:

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path

lab = json.loads(Path('content/examples/general-lab.json').read_text())
parts = ['# Original ideal-spring teaching notes',
         'Declared model: restoring-force magnitude F = 40 N/m × extension.',
         'These are original explanations and hypothetical values, not measured data.']
for lesson in lab['lessons']:
    parts.append('## ' + lesson['title'])
    for block in lesson['activities']:
        if block['type'] in {'reading', 'worked_example'}:
            parts.extend(['### ' + block['title'], block['body']])
Path('/tmp/gym-spring-notes.md').write_text('\n\n'.join(parts) + '\n')
PY
.venv/bin/python -m gym.agent_client POST /api/sources \
  --field course_id=physics-foundations-example --field role=instruction \
  --file file=/tmp/gym-spring-notes.md --output /tmp/gym-spring-source.json
```

Read the upload response. Replace `SOURCE_VERSION_ID` below with its returned
`id`, inspect the reconstructed fragments against the notes, and correct any
extraction problem before confirming. The confirmation body must contain the
actual current source `revision`; the number below is a placeholder to replace
if the response reports a different value.

```sh
.venv/bin/python -m gym.agent_client GET /api/sources/SOURCE_VERSION_ID/fragments
.venv/bin/python -m gym.agent_client POST /api/sources/SOURCE_VERSION_ID/confirm \
  --output /tmp/gym-spring-source.json --json - <<'JSON'
{"expected_revision": 1}
JSON
```

Fill the template from the confirmed response. Both lessons map to `springs`,
while their lesson IDs remain different. The external catalog stays empty:

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path

lab = json.loads(Path('content/examples/general-lab.json').read_text())
source = json.loads(Path('/tmp/gym-spring-source.json').read_text())
assert source['course_id'] == 'physics-foundations-example'
assert source['reconstruction_status'] == 'confirmed', 'Review and confirm the source first'
lab['course_id'] = source['course_id']
for lesson in lab['lessons']:
    lesson['module'] = 'springs'
    lesson['source_ids'] = [source['id']]
Path('/tmp/gym-spring-lab.json').write_text(json.dumps(lab, indent=2) + '\n')
PY
.venv/bin/python -m gym.agent_client POST /api/labs/ideal-spring-example/validate \
  --json /tmp/gym-spring-lab.json
.venv/bin/python -m gym.agent_client POST /api/labs/ideal-spring-example/preview \
  --json /tmp/gym-spring-lab.json --output /tmp/gym-spring-preview.json
```

Validation and preview use the same write schema and return
`{"valid": true, "lab": <normalized lab>, "warnings": [...]}` on success.
Neither call publishes content, starts a visit, nor creates learner evidence.
Inspect the normalized preview and warnings; fix validation errors and review
any warnings before publishing the same candidate payload:

```sh
.venv/bin/python -m gym.agent_client PUT /api/labs/ideal-spring-example \
  --json /tmp/gym-spring-lab.json
.venv/bin/python -m gym.agent_client GET /api/labs/ideal-spring-example
.venv/bin/python -m gym.agent_client GET '/api/labs?course_id=physics-foundations-example'
```

Readback verifies the published lab's ID, course, revision, lesson-to-module
mapping, blocks, and source references. Preview is not a reservation: an update
requires the current lab revision, and publication can still conflict if the
lab changes after preview. On a conflict, fetch and reconcile the current lab,
then validate and preview the revised candidate before publishing. Do not
automatically replace `expected_revision` and overwrite another edit.

The same workflow needs no specialized MCP tool. Use `gym_read` for discovery
and readback, `gym_upload` for the source, and `gym_request` with `method`,
`path`, and the candidate `body` for confirmation, validation, preview, and
publication. For example, validation uses `method: "POST"` and
`path: "/api/labs/ideal-spring-example/validate"`; publication uses `PUT` at
the lab path. Read the live schemas rather than assuming the example captures
every current field.

### Actual learner activity is a separate workflow

The learner's UI starts a visit through
`POST /api/labs/{lab_id}/activities`, identifying both `module` and `lesson_id`
with an idempotency key. `POST /api/lab-activities/{id}/events` records observed
activity, including responses associated with individual published blocks.
Read the live event schema for the specific action. A prompt in an authored
block is not a learner response, and a default parameter value is not evidence
that the learner performed an experiment.

For an actual learner event, `parameters.activity_id` is the published block
ID, distinct from the study-visit ID in the URL. A `response` action supplies
`parameters: {"activity_id": "BLOCK_ID", "value": "LEARNER_RESPONSE"}` for
a prediction or reflection block. A parameter `experiment` action supplies
`parameters: {"activity_id": "BLOCK_ID", "inputs": {"extension_m": 0.1}}`;
the server checks the exact input keys and bounds against the version studied,
then computes the output itself. These shapes describe observed learner
actions, not authoring or preview steps. Use a stable idempotency key for a
retry of the same event; a changed action or response needs a new key.

The platform records active and elapsed time separately and keeps guided
preparation separate from assessment. Link a same-course, same-module practice
or transfer session through `/api/lab-activities/{id}/link-session` before any
answers, so the existing assessment workflow can disclose preparation. Inspect
the activity's linked outcome rather than copying scores into the lab record.
Finishing a visit does not grant mastery or prove an intervention improved
learning. Agents must not start study timers, submit block responses, or take
practice on the learner's behalf merely to test or populate curriculum. Verify
those behavioral flows using isolated test data.

## Revise and import safely

Authoring conflicts return HTTP 409. Read the latest record and reconcile the
intended change; do not blindly retry with a newer revision. Validation failures
return 422 for schema violations and 400 for invalid references or domain rules.

Revising a question **returns a new item ID**. The old item retires from new
session selection, retains its family identity, and continues supporting
already-open session snapshots and historical attempts. Use the returned new ID
for further revisions. `POST /api/authoring/items/{id}/retire` takes
`expected_revision` and provenance to remove an item from future sessions.
Retirement does not erase performance. If a defective question should invalidate
past scores, use the existing `POST /api/items/{id}/report` route with a reason.

`POST /api/authoring/import` atomically applies a `MaterialImport` body:

```json
{
  "idempotency_key": "causality-materials-v1",
  "course_id": "causality",
  "course": null,
  "guides": [],
  "terms": [],
  "items": []
}
```

Replace the empty arrays with the appropriate write bodies, each containing an
`id`; at least one material or `course` is required. Optional `course` is a
`CourseWrite` payload. Sources must already exist and be confirmed. Terms are
written before items so a question can reference terms from its own import.
Every write validates its expected revision. A failed reference or revision
rolls back the entire batch. Repeating the same key and exact payload returns
the original receipt without new writes; reusing a key for different content
returns 409. Import accepts curriculum content, never attempts or learner state.

## Rubrics, assignments, and other UI actions

Use `GET /api/coursework` to discover rubric IDs, current versions, assignments,
drafts, and submissions. Create with `POST /api/rubrics`; revise with
`PUT /api/rubrics/{id}` and `expected_revision`. Revisions produce immutable
rubric versions. Assignments may explicitly follow the shared rubric; submitted
work retains the version captured at submission. Authored open response items
can pin a `rubric_version_id`; the supplied criteria must exactly match it.

Use `POST /api/assignments` with the manifest's `AssignmentInput` schema.
Actual coursework requires `deadline` as an ISO timestamp with timezone offset
and explicit `effort_minutes` (integer, 5–10,000). Completed coursework has the
same requirements. Self-study exercises may omit the deadline. A revision may
retain existing values, but cannot leave actual coursework without a deadline
or estimate. Obtain missing dates from source records or the learner; never
invent dates to satisfy validation. Estimates are not observed work time. Save an
authorized draft with `POST /api/assignments/{id}/draft`, including `body`,
`assistance`, optional `file_source_ids`, and the existing draft's revision.
Agent composition uses `active_seconds_delta: 0`. When the user requests a
submission, `POST /api/assignments/{id}/submit` accepts an idempotency key,
truthful `ai_contribution`, and optional attachment IDs. This records work
locally; it does not send it to an institution. Do not fabricate official grades,
responses, confidence, study time, or mastery as part of curriculum setup.

The capability manifest and live schema also expose source corrections,
assessment profiles, question generation, sessions and aids, goals/tasks,
calendar import, schedule proposal/acceptance, artifacts, adaptation, and job
health/retry. Model-backed routes are identified in the manifest. Authoring and
import themselves make no model calls. Session open response assessment and
explicit generation/critique requests may use the configured model router.

## MCP server

The optional MCP adapter uses the official Python SDK's maintained v1 API,
pinned below its breaking v2 release. Its five tools are `gym_capabilities`,
`gym_schema`, `gym_read`, `gym_request`, and `gym_upload`. They proxy to the same
HTTP API, so revision checks, provenance, authentication, source validation,
and transactional writes behave identically. The adapter has no direct storage
access, shell tool, or ability to choose a different destination per request.

```sh
uv sync --extra agent
.venv/bin/python -m gym.mcp_server
```

Stdio is reserved for MCP protocol messages. Read operations are annotated as
read-only; JSON mutations are labeled as modifying state. Uploads accept only
the source/calendar endpoints and files inside `GYM_UPLOAD_ROOTS` (a
platform-path-separator list of directories, default current working directory).
Symlinks are resolved before checking those roots. Set this to the authorized
material folders when books or papers live elsewhere. HTTP credentials come
from `GYM_ACCESS_TOKEN`, never tool arguments. Redirects and non-API URLs are
rejected. HTTP errors reach the tool caller without bearer-token output.

A generic MCP host can use this configuration, with the real project path:

```json
{
  "mcpServers": {
    "learning-gym": {
      "command": "/absolute/path/big_learning_gym/.venv/bin/python",
      "args": ["-m", "gym.mcp_server"],
      "cwd": "/absolute/path/big_learning_gym",
      "env": {
        "GYM_BASE_URL": "http://127.0.0.1:8787",
        "GYM_UPLOAD_ROOTS": "/absolute/path/to/authorized/materials"
      }
    }
  }
}
```

Host configuration formats differ; this file does not install or overwrite any
client configuration. Pass the token through the host's environment/secret
handling or the project `.env`.

SDK references: [official v1 source and compatibility policy](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x),
[official in-memory protocol testing guide](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/testing.md).

## Verification

```sh
.venv/bin/pytest -q tests/test_authoring.py tests/test_agent_mcp.py tests/test_lab_activity.py tests/test_lab_catalog.py
```

Authoring tests exercise stale revision rejection, module/reference validation,
HTML sanitation, atomic rollback, repeated imports, glossary aids, preserved
session scores, pinned rubric versions, and solution redaction. MCP tests use a
real SDK client/server protocol session and the Gym ASGI app to discover schemas,
create a course, upload/read source fragments, detect conflicts, and reject
foreign URLs and disallowed file paths. No paid model calls are required.

Lab tests cover definition validation, named-lab scope, activity references,
versioned study records, and the separation between preparation and assessed
evidence. The ideal-spring example was also exercised through an isolated API
workflow: course creation, source upload/review/confirmation, validation,
preview, publication, and readback. Preview left the lab unpublished; the final
lab contained two distinct lessons mapped to one module, with no sessions,
attempts, study visits, submissions, or learner-state records created.


## Goal-directed authoring and profile evolution (D-013)

The standard UI's Authoring workspace, this REST API and generic MCP calls share
one workflow. Uploading `/api/sources` creates source material; adding coursework
uses `/api/assignments`. Teaching labs use `/api/labs`; course-assigned lab duties
use assignments. Optional teaching exercises use `purpose=self_study`. Missing
rubrics remain null and never block importing an actual external outcome.

`POST /api/profiles` accepts the live `ProfileInput`: a specific `target`, optional
`target_assignment_id` for the intended future duty, prior `assignment_ids`,
prior assessment/rubric `source_ids`, prior `material_source_ids`,
`emergent_source_ids`, and optional explicit rubric references. Source IDs are
reviewed same-course versions. No grades, feedback or learner responses enter
profiling. The reviewable proposal includes its content scope, explicit
`practice_rubric` and `rubric_basis`; proposed criteria are not official criteria.
An optional manual `profile` proposal avoids the model call. Confirm with the
current revision using `PUT /api/profiles/{id}`.

`GET /api/profiles/{id}/versions` returns the current profile and immutable saved
revisions. `POST /api/profiles/{id}/rerun` requires `expected_revision` and
`idempotency_key`, with optional input replacements using `ProfileRerunInput`.
Omitted inputs persist; supplied arrays replace them. Each run pins refreshed
coursework/rubric snapshots and selected source versions and needs review.

`POST /api/generations` pins the confirmed profile and instructional context.
Optional `profile_version_id` chooses a historical confirmed revision.
`counterfactual_count` reserves changed-assumption and uncertainty reasoning
inside the existing total/format allocation for practice or simulations.
`POST /api/generations/{id}/rerun` uses `GenerationRerunInput` and an exact-payload
idempotency key, creating a new blueprint with `parent_blueprint_id` and retaining
old sets. A session's optional `blueprint_id` selects a specific set (up to 40
items). Simulation publication and solution sealing are unchanged.

`POST /api/assignments/{id}/outcomes` uses `CourseworkOutcomeInput` for actual
instructor grades and/or feedback before local work is uploaded. Attribution,
observation time, nullable original occurrence time, source reference, separate
learner comment, limitations, optional completion and versioned correction are
explicit. `artifact_version_id` preserves a previous import; explicitly setting
`reclassify_artifact` moves its current projection out of research. No learner
submission, timer, mastery or measured effort is fabricated. These unlinked
outcomes remain outside the existing submission-based recommendation algorithm.

The prepared-agent procedure and example payloads are in
[`skills/learning-gym/references/profiles-and-coursework.md`](../skills/learning-gym/references/profiles-and-coursework.md).
MCP `gym_schema`, `gym_read` and `gym_request` expose each REST workflow without a
second implementation. Read capability schemas for field requirements and retry
semantics; do not bypass them with direct database writes.
