# Architecture and invariants

This is the descriptive source of truth for the implemented system. Read the accepted constraints in [`DECISIONS.md`](../DECISIONS.md) and the current behavioral contracts in [`ALGORITHMS.md`](ALGORITHMS.md). Update this file when implementation boundaries or data flows change; do not use a documentation edit as authorization to change a decision.

This is an event-driven modular monolith with shared transactional storage and a React client. The implementation is intentionally small enough to inspect and operate for one learner. It implements the two loops and authority boundaries in the supplied architecture; it does not claim every long-term connector, training method or research workflow is implemented.

## Authority and memory

`gym/store.py` separates the append-oriented evidence journal, versioned predictions and decisions. Current records are replaceable projections with identity scoped by record kind. Predictions retain input evidence, state revision, model version and invalidation dependencies. Schedule decisions retain inputs, rationale, alternatives, approval and execution state. Source versions, submission versions and rubric versions preserve historical interpretation.

A database transaction serializes a mutation with its evidence and outgoing job. SQLite uses `BEGIN IMMEDIATE`; PostgreSQL locks the singleton state row. No LLM output is authoritative about deadlines, instructor grades, calendar feasibility or a learner's psychological traits. Core operation does not depend on adaptation or a model provider being available.

## Module responsibilities

- `ingestion.py` preserves originals and extracts anchored text from PDFs, slide decks, documents, text, CSV and notebooks. Learner corrections create versions. Instructional content, assessment examples, rubrics, submissions and research sources have distinct roles.
- `assignments.py` handles reconstruction-confirmed style profiles, editable rubric proposals, rubric versions, assignment drafts, attachment snapshots, local submissions and separately attributed instructor outcomes. Review recommendations are scoped to the actual assignment.
- `generation.py` keeps a blueprint, source/profile/rubric snapshots, role provenance and independent verification. Up to 40 items are generated in batches of four; optional shared cases are created once and reused. Invalid or duplicate items are quarantined. A simulation cannot be partially published.
- `sessions.py` seals answer keys, records attempts and permitted aids, caps active-time heartbeats, tracks prior exposure and defers simulation feedback and learner updates until completion. Reopening an item does not erase evidence of prior assistance.
- `assessment.py` judges the submitted work against the frozen rubric. Every evidence quotation must exist in the submitted text. It excludes tutor conversation, confidence and predicted score from the assessor input. Open-response scores are provisional model judgments.
- `learning.py` maintains course-scoped, dimension-specific evidence summaries, delayed-check dates, revisable hypotheses and recommendations. Its weighted beta summaries are transparent heuristics, not calibrated mastery probabilities. Official grades remain scoped outcomes.
- `planning.py` owns scheduling. Remaining effort comes from the current completion criterion, not elapsed-time subtraction. The deterministic planner respects availability, commitments, deadlines, prerequisites, splitting, setup time, pins, workload and slack, with a ten-percent exploration budget. Failure to fit under its greedy policy is reported as a conflict; it is not a proof that no possible schedule exists.
- `calendar.py` treats fixed commitments, authoritative deadlines and app-owned study blocks differently. ICS identities, sequences, cancellations, recurring instances and date-only deadlines retain provenance. Missing entries in an import are not silent deletions.
- `adaptation.py` evaluates predicted effort and independent performance against later observed outcomes. Late arrival and target scope are checked. Effort candidates use point-in-time chronological validation, shadow status, explicit activation and rollback. Predictions made with different historical model multipliers are normalized before candidate fitting. An intervention ledger can record alternatives and assignment probabilities; causal effect estimation is not implemented.
- `worker.py` handles priorities, leases with renewal, bounded retries/backoff, idempotency and failed-job inspection. Schedule repairs debounce over 30-second windows. Daily planning and weekly deterministic evaluation catch up while the worker runs. These are application jobs, not desktop app automations.
- `llm.py` routes each role independently, bounds input/calls/retries, validates responses and records redacted provenance. OpenAI-compatible and native Anthropic transports are separate adapters. Providers cannot manipulate the calendar or execute learner code.
- `backup.py` produces a coherent portable snapshot and checksums referenced originals. Restore refuses a nonempty destination and recovers interrupted leases.
- `authoring.py` validates curriculum, guides, terms and authored items with provenance, revision checks and atomic imports. Item replacement preserves historical identities. Authoring produces content, not learner evidence.
- `agent_api.py` exposes live capabilities, schemas and validated authoring routes through the existing API. `agent_client.py` is an HTTP client. Agent transport extensions must delegate to these workflows and must not introduce direct database writes or independent domain rules (D-009).

## Change control

`AGENTS.md` and the always-applied Cursor rule instruct coding agents to read the decision register and this architecture before edits. `docs/ALGORITHMS.md` records formulas, cutoffs, versions and validation expectations. Protected changes require a path-specific record under `docs/changes/`; the architecture checker and behavioral tests detect selected boundary violations and unrecorded changes. These are repository controls, not a substitute for independent review.

The proposed CI workflow runs the checker, backend tests on SQLite/PostgreSQL and the frontend build. GitHub enforcement is separate: required checks, owner review, protected `main`, and limited agent credentials must be configured by the maintainer. See [`CHANGE_CONTROL.md`](CHANGE_CONTROL.md) for the activation procedure and its limits. Adding these files does not itself enable GitHub protection.

## Operational sequence

An attempt or source/task/calendar change enters a transaction. Evidence is appended, relevant projections change, state advances and a job is committed. The worker invalidates dependent estimates and proposes repair. The learner reviews and accepts an applicable schedule proposal. Replaying the same idempotency key has one stored effect.

The adaptation process runs independently: select eligible prediction/outcome pairs, enforce timestamp and scope validity, fit on past evidence, test against later observations, retain the baseline when evidence is insufficient, and save a candidate in shadow only when the gates pass. Activation never rewrites historical forecasts.

## Extension boundaries and current limits

Calendar connectors currently use manual entries and ICS snapshots/import/export; there is no OAuth or live bidirectional calendar sync. Scanned PDFs, complex diagrams and damaged equations need learner correction: no OCR or vision extraction is included. Retrieval uses anchored lexical ranking, not an embedding service, and uses a bounded subset of long source packs.

The coding workbench stores code and notebook output; it does not execute arbitrary code. Research critique does not verify cited papers externally. Learner-state parameters use a transparent baseline; no deep knowledge tracing, reinforcement learning or causal personalization claims are made. Shared-case questions use a fixed trailing section; precise section arrangements and nuanced stylistic constraints require review. Simulation answers are committed individually and cannot yet be edited after saving; completion seals the assessment and releases feedback.

This is a local, single-user release. Public multi-user deployment, tenant isolation, automated encrypted backups and institutional submission integrations need additional work. Token authentication, same-origin mutation checks and trusted host validation are included, but the application should remain bound to localhost in this configuration.
