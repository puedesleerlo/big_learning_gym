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

## Adding or revising a decision

Append the next `D-NNN` entry with status `Proposed`, context, decision, alternatives, consequences, affected algorithm versions, migration, checks, rollback and the decisions it supersedes. Link the exact user request or maintainer review covering the revision. A request already authorizing the specific change is sufficient; do not request permission again. Only mark acceptance when that authorization exists. A JSON change record or a checked box is not proof of approval.
