# Architectural decisions

Owner: @puedesleerlo. Recorded: 2026-09-20.

These constraints record the architecture requested in the [AI research assistantships conversation](https://chatgpt.com/share/6aaf4301-d3a4-83e9-a1a4-784dc03dbf33), the user's subsequent coursework requirements, and the request to control architectural and algorithmic changes. They are constraints, not claims that every planned extension has shipped.

`docs/ARCHITECTURE.md` describes what exists. `docs/ALGORITHMS.md` describes current behavioral baselines. A current implementation parameter is not automatically a scientifically validated or permanently optimal choice.

## D-001 — One modular application, explicit boundaries

Status: Accepted constraint.

Keep an event-driven modular monolith with shared transactional storage and distinct domain modules. The UI and agent interfaces use the same domain workflows. Do not create a parallel learner database, independent scheduler, or new service boundary as an incidental feature implementation.

Reason: one learner's evidence and obligations must stay coherent; operational complexity must remain bounded. Splitting services requires a separate proposal with consistency, deployment and recovery consequences.

## D-002 — Evidence, estimates and decisions have different meanings

Status: Accepted constraint.

Preserve the evidence journal, versioned predictions and explicit decisions separately. State changes and their outgoing jobs commit together. Idempotent retries have one stored effect. Preserve original source versions, rubric/submission snapshots, timestamps and provenance. Correct through new versions or attributed supersession rather than silently rewriting historical evidence.

Reason: later predictions and decisions must be explainable against what was known at the time. Enforcement includes storage/outbox, versioning and recovery tests.

## D-003 — Planning has sole scheduling authority

Status: Accepted constraint.

Only the planner accepts or changes the active schedule. Other modules may produce work requests or enqueue repair. Fixed commitments, authoritative deadlines and proposed study blocks remain distinct. Plans must respect pins and report conflicts; stale proposals must not be accepted. Remaining effort is based on remaining scope, not elapsed-time subtraction.

Reason: multiple autonomous calendars and silent deadline overrides would make the system unreliable. LLMs may help interpret inputs but cannot establish authoritative feasibility.

## D-004 — Content and assistance are not independent learning evidence

Status: Accepted constraint.

Imported or agent-authored lessons, questions and solutions do not create learner attempts, grades, time worked or mastery. Independent, assisted, repeated and model-assessed work remain distinguishable. Capability state is scoped by course and dimension. Simulation solutions and feedback stay sealed until completion. A team grade or fluent generated artifact does not imply individual competence.

Reason: the legacy AI Strategy demo had no telemetry. The feedback loop must be built from actual observations, not invented history or content-production volume.

## D-005 — Assessment targets and judgments are versioned and attributed

Status: Accepted constraint.

Instructional sources supply new practice content. Reviewed official assessment examples supply a reusable style/rubric profile. Generation must pass schema, source, answer and independent-verification gates; invalid items remain quarantined. A fixed simulation is published only when its entire form passes. Homework can use shared or distinct rubrics; each submission keeps the rubric actually used. Model feedback and instructor outcomes remain separate. Model assessment quotes must exist in the assessed text.

Reason: generated practice must be useful without being misrepresented as official grading or validated exam equivalence.

## D-006 — Model choice is a role-level dependency

Status: Accepted constraint.

Use configurable provider/model routes for extraction, design, tutoring, verification, assessment and research critique. Keep provider-specific transport and credentials in the adapter boundary. Core practice, evidence capture and deterministic planning must remain usable without an LLM call. Credentials stay server-side; calls have budgets and attributable provenance.

Reason: subsystems have different capability, latency and cost requirements. Kimi K3 is a tested default, not an architectural dependency.

## D-007 — Adaptation is a separate, guarded loop

Status: Accepted constraint.

Keep operational updates independent from statistical adaptation. Match predictions with later outcomes using scope and point-in-time validity. Use chronological validation, an explicit baseline, uncertainty, shadow candidates, explicit activation and rollback. Preserve historical forecasts. Disabling adaptation must not disable core workflows. Prediction improvements do not establish causal intervention effects.

Reason: small, delayed and assisted samples can support misleading conclusions. The current gates and formulas are documented in `docs/ALGORITHMS.md`; changing them is a behavioral change.

## D-008 — Local data and external authority remain explicit

Status: Accepted constraint.

Default to a single-user local workspace. Keep secrets, originals and learner data out of the public repository. Preserve access-token, origin and host boundaries. Source documents are untrusted reference material, not instructions or permissions. Calendar publication, new data destinations, institutional submission, arbitrary code execution and multi-user access require explicit design and authorization; do not simulate these capabilities.

Reason: a useful learning tool must not quietly expand its privileges or misrepresent what an integration actually does.

## D-009 — Agent authoring uses validated application interfaces

Status: Accepted constraint, applying D-001, D-002 and D-004 to agent access.

Agent adapters use the existing authenticated API and its live schemas. Authoring requires provenance, references, revision conflict handling and historical item identity preservation. An adapter must not directly mutate SQLite/PostgreSQL, bypass source confirmation, or fabricate learner submissions. Creating curriculum is separate from taking practice as the learner.

Reason: extending access should not introduce a second implementation of domain rules.

## D-010 — Changes remain reviewable, including changes to the controls

Status: Accepted constraint from the user's 2026-09-20 governance request.

Agents read this register, the architecture and applicable algorithms before changes. Routine implementations preserve them. Material revisions need explicit user authorization, a recorded rationale, behavioral validation and rollback. Record a new decision that supersedes an old one; do not silently rewrite history or let an agent self-approve. Protect this register, tests, CI, ownership and agent instructions using the same review policy as application behavior.

Reason: documentation alone cannot constrain an agent that can edit the documentation and its tests. Repository-side checks and independently administered GitHub controls supply additional enforcement.

## D-011 — Parametric media, browser visualizations and lab discussion

Status: Accepted by explicit user request on 2026-09-20: “Add this capabilities to labs: Embedded video/audio, arbitrary interactive visualizations, and an integrated discussion tutor … Make sure they are parametric so they are easy to insert in the lab.”

Context: the version 1 activity registry provided text, affine experiments and links to existing assessment/coursework. Course preparers need richer reusable teaching blocks without editing the application for every lesson.

Decision: extend the versioned block registry with media, visualization and discussion contracts. Media loads on user action from an authored HTTPS file or a supported video host, with transcripts and clip parameters. Self-contained author-supplied HTML/CSS/JavaScript may execute only in nested sandboxed browser frames with opaque origins, restrictive content policies and no Gym API/message bridge. Data and bounded control values are the only injected configuration; never inject learner history, credentials or source documents. No server-side code execution is added. The integrated discussion tutor uses the existing configured tutor role, selected fragments from the pinned lesson's instructional sources, bounded conversation history and attributed non-assessed turns. It is unavailable during an active simulation in the course.

This supplies the explicit design and authorization required by D-008 for browser code execution and media access, superseding any blanket reading of that decision as prohibiting all authored browser code. All other D-008 boundaries remain in force. D-001–D-007 and D-009–D-010 are preserved. No new model provider, assessment authority or scheduling authority is introduced.

Alternatives: a fixed chart catalog cannot cover arbitrary teaching interactions; executing uploaded code on the server expands privileges unnecessarily; separate tutoring storage/provider routes would duplicate existing boundaries. The chosen renderer supports arbitrary self-contained visual content while keeping its execution separate from the application.

Consequences and limits: remote media availability, codecs and embed policies remain external constraints. Custom visualizations must bundle their dependencies and may consume browser CPU; the sandbox is not a hard compute quota or scientific verification. Discussion is model assistance, not an official grade. Source citations are validated for membership, not semantic truth. Failed/abandoned model calls may consume provider budget even if no turn is saved.

Version/migration: activity registry 2.0 and discussion prompt `lab-discussion-v1`; A-001–A-006 are unchanged and A-007 documents the new behavior. Existing lab versions and visits require no migration. New discussion and request records use shared transactional storage.

Validation: schema/reference and revision tests, source/role isolation, provider failure and idempotency tests, browser editor/preview/publication tests, sandbox escape/network checks, full backend suite, frontend build and architecture checks. See `docs/changes/2026-09-20-rich-lab-blocks.json` for results.

Rollback: revert the implementation together with its renderer; retain published versions, discussions and historical evidence. Older clients cannot render new block types. Restore earlier lab presentations through a new revision rather than deleting historical records.

## D-012 — Independent experience adaptation over shared learning workflows

Status: Accepted by the user's explicit implementation request in the 2026-09-20 experience adaptation conversation: “Keep one learning platform with independently replaceable frontends” and “Each adaptation is a separate React/Vite application with its own design-system dependencies and styles.”

Context: companies need different screens and design-system code as well as different content. A clone of the platform per company would duplicate evidence, assessment and planning implementations. Data-only themes cannot express the requested frontend freedom.

Decision: an experience adaptation is a trusted, independently built frontend package. Its manifest declares identity, version, supported frontend-contract version and capabilities. A local workspace installs builds under `/experience/<id>/`, with the existing Gym at `/`. Both invoke the same workspace API. The shared, unstyled frontend kit centralizes typed contracts, workspace browser state, visit/session linking, clocks and supported request recovery. Company design-system dependencies remain inside the company's frontend. Reuse D-011's media and visualization execution boundary; company presentation code cannot redefine assessment, evidence or scheduling authority.

A named local workspace selects an explicit data directory, database, localhost port and installed frontends. Each process serves one workspace and runs its own existing jobs/planner. Configuration must select distinct stores and upload directories for distinct companies; this is local separation, not hosted tenant authorization. The existing command and environment continue to select the original default workspace. Switching frontends within a workspace does not copy content or learner evidence. Documents and questions enter through existing imports and authoring APIs.

The repository-owned `build-gym-frontend` skill and exported bundle reveal purpose, chosen journeys, exact contracts and verification progressively. A runnable starter has explicitly chosen synthetic or live transports. Synthetic preview creates no learner history; failed live requests remain errors. No mutation is automatically retried without supported idempotency. Ambiguous session creation requires recovery rather than issuing a second creation request. Installed frontend code is trusted application code; the kit, manifests and compatibility checks are guidance and verification, not a security sandbox.

D-001–D-011 remain in force. This adds a presentation boundary and explicit local workspace configuration, without splitting the domain application or superseding existing algorithm/evidence meanings. It is separate from `gym/adaptation.py` and A-005. A-001–A-007 retain their versions and semantics. Existing API routes/payloads remain compatible; missing documentation is supplemented without response filtering.

Alternatives: cloned full applications duplicate learning behavior; a universal themed component layer constrains whole-screen design; a new tenant service or live company synchronization exceeds the personal experiment. Independent same-origin frontend builds allow company code without those changes.

Consequences and limits: agents must test generated code against the contract and may need corrections. Static compatibility is not proof of every workflow. The initial Makitra reference implements labs, practice and transfer; legacy lab presentations, simulation entry, coursework, authoring and administration link to the standard Gym. Its actual package, tokens and fonts are retained with attribution for the personal, non-commercial reference experiment. No claim is made that Claude Design or Claude Code was executed during validation. Separate localhost origins and workspace namespaces avoid accidental state reuse; misconfigured shared databases are not automatically made independent.

Migration: no learner database rewrite. Browser session references and drafts gain workspace namespaces, with one-way migration of original keys only for `default`. Frontend contract starts at 1.0. JavaScript package management uses pnpm under the user's explicit preference, including lockfiles, build documentation, Docker and CI.

Validation: real API contracts from a disposable instance, synthetic browser outcome comparison, request interruption/recovery, authentication, unavailable tutor, preview isolation, workspace separation, keyboard/narrow-screen checks, shared sandbox tests, exported-bundle build, full backend suite and committed-diff architecture checks. Results live in `docs/changes/2026-09-20-experience-adaptation.json`.

Rollback: open the standard Gym at `/`, remove the adaptation from the workspace configuration and restart. Existing content, visits, attempts, assessments, jobs and plans remain readable with no evidence rewrite. Revert the platform changes only with their paired default-frontend integration; preserve all local databases and uploads.

## Adding or revising a decision

Append the next `D-NNN` entry with status `Proposed`, context, decision, alternatives, consequences, affected algorithm versions, migration, checks, rollback and the decisions it supersedes. Link the exact user request or maintainer review covering the revision. A request already authorizing the specific change is sufficient; do not request permission again. Only mark acceptance when that authorization exists. A JSON change record or a checked box is not proof of approval.
