# Validation record

Validation performed September 19–20, 2026. All practice and paid-model exercises used isolated workspaces or temporary databases. The delivered workspace contains the AI Strategy and causality courses; test activity is kept separate from the learner's own recorded work.

## Reusable labs

- **102 tests passed on SQLite** after generalization. Ruff, the architecture boundary check and Vite production build passed. The PostgreSQL checks below predate these additions. No committed-diff coverage or remote CI enforcement is claimed for the current uncommitted workspace.
- Regression tests cover multiple labs per course, multiple courses, arbitrary module and lesson identities, preview without any database writes, immutable ownership, reference and revision validation, source/rubric scope, prerequisite cycles, bounded server-computed experiments, and authentic practice outcomes. Resumed visits keep their original lesson/configuration version; invalidated attempts are excluded from displayed scores without deleting historical evidence.
- A real stdio MCP client created a synthetic course, uploaded and inspected source text, confirmed it, and validated, previewed and published two generic labs in the isolated workspace on port 8788. No practice attempts were manufactured by authoring.
- Browser verification created a third lab and a new topic through ordinary forms, selected a reviewed source, added reading/reflection activities, validated and previewed, then published. A separate study visit saved reasoning. Another lab saved a prediction and ran a configured spring model with input 0.1 and coefficient 40, displaying 4 N. Finished visits appeared separately in Learning evidence with their saved responses and zero assessed attempts from these activities.
- The live causality records need no migration. The pre-change workspace snapshot is `data/before-reusable-labs.zip`; no synthetic physics content is published in the learner's actual workspace. The reusable example and agent skill document the normal course/source/validate/preview/publish workflow.

## Causality lab and agent access

- **75 tests passed on SQLite**, including content import, authoring revision conflicts, preserved question snapshots, MCP protocol operations, guided activity timing and linking, and assistance attribution. Ruff and the Vite production build passed. The PostgreSQL checks below predate these additions.
- The browser exercise in a separate database completed an experiment, saved a reflection, linked practice, submitted a scored answer, and displayed its supported outcome alongside study time. It did not create learner evidence in the delivered database.
- The live HTTP import installed 12 lessons, 13 confirmed source documents, 13 guides, 40 glossary terms, 36 practice items, and four assignments with a proposed rubric. The original AI Strategy course retains its 314 practice and 64 simulation items.
- A real stdio MCP client initialized the installed server, discovered its five tools, and read the 12-lesson course through the running HTTP API. The local skill is installed and the MCP entry is registered in the host configuration.
- Experiments are explicitly labeled exact toy models or idealized graph reasoning. They do not execute causal-learn or establish causal effects of teaching. Study time and exposure remain behavioral evidence; assessed attempts determine learning estimates.
- The two books mentioned by the learner could not be located in the provided context or workspace roots. Public supplemental readings are identified separately and are not presented as those books.

## Automated checks

- **39 tests passed on SQLite.**
- **39 tests passed on PostgreSQL 17**, using a fresh schema per test. Only those generated test schemas were dropped.
- `ruff check gym tests scripts` passed.
- The Vite production build passed.
- The container image built, initialized its PostgreSQL database and ran a durable worker iteration successfully.
- A credential scan found no test key in application code, frontend source, tests, scripts, configuration or documentation. The local `.env` is excluded from Git/container context and has permission mode 0600.

The tests cover answer-key sealing, aid attribution, idempotent submissions, delayed simulation feedback, active-time caps, partial-credit matching, quarantined evidence, course-scoped capability identity, batching and type allocation, shared cases across batch boundaries, source citation validation, preserved source versions, notebook cells, rubric snapshots, attachment assessment and autosave provenance, official versus model feedback, team grades, task dependencies and deadlines, pinned schedules, stale-plan rejection, calendar changes/cancellations, outbox rollback, lease recovery, retry bounds, provider adapters, budgets, token/origin controls, adaptation disablement, point-in-time holdouts, candidate activation/rollback, backup restore and corruption rejection.

Two warnings originate in the Starlette test client dependencies (`httpx` integration and the AnyIO portal alias). They did not produce failing tests.

## Browser exercises

Using the actual production frontend and local API, the following workflows were completed:

- Start AI Strategy practice, request a hint, record confidence, answer, inspect scored reasoning, and finish with remaining items explicitly unfinished.
- Correct an assessment-source reconstruction and create an assignment from its revised instructions.
- Open the assignment with its pinned rubric, write and save a draft, record an AI-attributed submission, and add a separately labeled instructor grade.
- Queue real Kimi rubric assessment from the UI and display its criterion-level evidence quotations beside the official grade.
- Propose a constrained homework schedule and explicitly accept it; accepted blocks expose pins and ICS export.
- Run adaptation evaluation and retain the baseline when there is insufficient evidence.
- Inspect the final workspace: one imported course, 314 practice items, 64 simulation items across four forms, no invented history, and no failed background jobs.

Browser verification found and fixed incorrect HTTP methods on no-payload mutation actions. A save-queue race, cross-course capability collision, and lost attachment/assistance state were also corrected. The test suite guards the storage and evidence regressions.

## Live-provider verification

`scripts/live_smoke.py` is an explicit, bounded integration test using synthetic teaching material. It exercises Kimi K3 for a reviewed assessment profile, fresh MCQ/matching/open items with an optional shared case, independent verification, editable rubric extraction and criterion-level assessment with exact evidence quotations. The machine-readable result is `data/live-validation.json`; no key or prompt body is stored in that report.

An initial shared-case run failed the source-ID guard because a generated item cited outside the instructional context. The generator now distinguishes allowed instructional fragment IDs from generated case IDs and assessment-profile provenance. The source validator remains strict; it was not bypassed to make the model test pass.

The final live run passed all four checks: assessment profile, generation plus independent verification (MCQ, matching and open response; two shared-case items), editable rubric extraction, and attributable rubric assessment.

Only Kimi K3 was tested against a live provider. Other transports were tested with mocked responses. These checks establish a functioning integration and failure handling, not psychometric validity, calibrated learning gains or a causal personalization effect.

## Known release limits

See `ARCHITECTURE.md` for extension boundaries. This is a single-user local application: ICS/manual calendar integration, text extraction with learner correction, no arbitrary code execution, no institutional submission transport, and transparent heuristic learner estimates. Scanned/diagram-heavy documents and exact assessment-style fidelity require review. The statistical adaptation gates need actual longitudinal observations before useful candidates can be evaluated.
