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

Use `POST /api/assignments` with the manifest's `AssignmentInput` schema. Save an
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
.venv/bin/pytest -q tests/test_authoring.py tests/test_agent_mcp.py
```

Authoring tests exercise stale revision rejection, module/reference validation,
HTML sanitation, atomic rollback, repeated imports, glossary aids, preserved
session scores, pinned rubric versions, and solution redaction. MCP tests use a
real SDK client/server protocol session and the Gym ASGI app to discover schemas,
create a course, upload/read source fragments, detect conflicts, and reject
foreign URLs and disallowed file paths. No paid model calls are required.
