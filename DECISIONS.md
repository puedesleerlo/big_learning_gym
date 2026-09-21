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

## D-013 — Goal-directed authoring and coursework outcomes

Status: Accepted by the user's explicit requests on 2026-09-20 in this task: unify authoring across gyms; distinguish learning labs from actual coursework; derive assessment profiles from actual coursework, material and explicit rubrics without grades; include counterfactual reasoning inside practice/mock exams; record existing TA feedback and grades on coursework before uploading learner work. The follow-up explicitly requires a specific goal (usually future coursework), prior and emergent evidence, versioned profile reruns, practice regeneration, and UI/REST/MCP/prepared-agent exposure.

Decision: distinguish three profile inputs: the intended assessment goal and optional target coursework; prior coursework/examples and instructional material; newly available instructional, assessment or rubric evidence. All inputs use same-course references and reviewed source versions. Pin the selected coursework prompts, available rubric versions and retrieved fragments. Exclude submissions, grades and feedback from profile inputs. Missing official rubrics remain unknown; an explicit proposed practice rubric states criteria, weights, observable anchors and its derivation. Review precedes use. A new profile run refreshes the chosen references and requires review; immutable revisions and run numbers retain prior interpretations. Generations pin their confirmed profile revision, instructional source context and rubric. Regeneration creates a linked new set, preserving original items, forms and attempts.

This supersedes the style-only limitation of D-005: a targeted profile also includes its specific content scope and future-task intent. Actual assessment examples still supply style and reasoning demands; raw assessment prompts and outcomes do not supply new generated question content. Existing legacy style profiles and unprofiled generation API requests remain compatible and visibly distinguishable. New UI authoring uses an explicit reviewed profile. No automatic improvement or statistical equivalence is claimed for additional evidence or reruns.

Counterfactual reasoning is a capability within ordinary practice and simulations. A blueprint reserves a count within its existing format allocation; these items provide source-cited derivations, changed assumptions and uncertainty for independent verification. Invalid items remain quarantined, and incomplete mock exams cannot publish. Derivations stay sealed like solutions. Ordinary practice also samples the existing transfer bank; the legacy focused transfer mode remains callable. Original item and attempt dimensions are preserved.

Coursework denotes actual obligations; optional teaching exercises use an explicit self-study classification and create no task. Historical instructor outcomes can be recorded directly against coursework without inventing a local submission, a learner rubric, work time or mastery. Preserve attribution, point scale, observed and occurrence dates (unknown dates remain null), original import snapshots and versioned corrections. Explicitly completed external work closes the associated obligation through Planning without a measured effort observation or schedule acceptance. Misfiled feedback artifacts can be reclassified with immutable original versions retained; instructor comments cannot then be critiqued as learner research. Existing submission-linked official grades and recommendation eligibility remain unchanged.

D-001–D-004 and D-006–D-012 are preserved. This adds versioned records within shared storage and extends existing domain workflows; it adds no provider, service, calendar authority or institutional submission capability. REST is the mutation authority; MCP delegates to it and both the authoring UI and prepared-agent skill expose the same contracts.

Alternatives: requiring fabricated submissions to unlock grades corrupts evidence; treating a rubric as known when absent misrepresents course authority; one unversioned profile loses the chronology of emerging evidence; a new transfer product fragments practice. The chosen explicit links retain the distinct meanings while making authoring coherent.

Migration: additive records and fields; no automatic rewriting of learner history. Legacy profiles are snapshotted before their first new revision. User-requested live corrections use validated APIs, not database writes. Classification of existing generated study exercises is explicit and attributed. A-001–A-005 and A-007 keep their previous behavior; A-006 records `grounded-practice-v3`, `verify-v3` and `practice-selection-v2`; profiling uses `targeted-profile-v1`.

Validation: goal/prior/emergent input separation, same-course and source-review gates, rubric provenance, immutable revisions, stale/conflicting reruns, duplicate retry effects, retained generated sets, sealed derivations, verifier rejection, external feedback-only and grade imports, artifact reclassification, REST/MCP discovery, disposable browser authoring journeys, full backend suite, frontend builds and committed-diff architecture checks. Results are recorded in `docs/changes/2026-09-20-unified-authoring.json`.

Rollback: use preserved confirmed profile revisions and existing generated sets; revert implementation and UI together. Retain all profile history, outcome records, original artifacts, sources and attempts. Restore a rubric/profile by a new attributed revision, never by overwriting old evidence. Reopen actual obligations only through an explicit new duty, not by undoing recorded historical outcomes.

## D-014 — Required coursework planning inputs and gym scope

Status: Accepted by the user's explicit browser comment in this task: separate coursework and rubrics by gym with an All option; deadlines and estimated time are required, including existing coursework.

Decision: new actual coursework and revisions of its details require a valid timezone-aware deadline and an explicit integer estimated duration (5–10,000 minutes). Remove the implicit 60-minute assignment estimate. These requirements apply to completed coursework too. Optional self-study exercises remain outside actual obligations and may omit deadlines, but still require an estimate. The same AssignmentInput validation applies through REST and generic MCP; the UI prevents incomplete saves and pre-fills existing dates in local time. A gym filter scopes coursework and rubrics together; globally shared rubrics remain visible and labeled in each gym.

This tightens D-013's optional planning inputs while preserving D-002 source fidelity, D-003 scheduling authority and D-004's distinction between estimates and observed work. Older incomplete records remain readable and visibly flagged, but must be completed before their details can be revised. Backfill only from verified sources or explicit learner clarification; a requirement never authorizes invented institutional dates. Existing estimates remain estimates. Grades, submissions and other historical evidence do not require rewriting. Original source text and uncertainty remain preserved.

Alternatives: UI-only validation would allow agent/API bypass; arbitrary dates or automatic 60-minute values would conceal missing information. Rejecting all reads of historical incomplete records would prevent feedback access. The chosen contract enforces future writes while exposing gaps for sourced repair.

Algorithms: A-001–A-007 and their versions are unchanged. Planning receives explicit inputs through existing workflows; no scheduling heuristic, measured time or active-schedule acceptance changes. The teaching-lab installer explicitly creates self-study exercises under D-013.

Validation: API missing/invalid/null/date-only/timezone/estimate checks, partial revisions retaining planning fields, optional self-study isolation, MCP workflow fixtures, browser gym/shared-rubric filtering, existing date editing, full backend suite and frontend build. Rollback: revert paired validation/UI changes and rebuild/restart; keep verified backfilled dates and all historical records. No destructive database migration.

## Adding or revising a decision

Append the next `D-NNN` entry with status `Proposed`, context, decision, alternatives, consequences, affected algorithm versions, migration, checks, rollback and the decisions it supersedes. Link the exact user request or maintainer review covering the revision. A request already authorizing the specific change is sufficient; do not request permission again. Only mark acceptance when that authorization exists. A JSON change record or a checked box is not proof of approval.
