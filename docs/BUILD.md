# Implementation brief

Authoritative architecture: [AI research assistantships](https://chatgpt.com/share/6aaf4301-d3a4-83e9-a1a4-784dc03dbf33), read in full on September 19, 2026.

Build a modular monolith with two independent loops. Evidence records what happened;
versioned estimates record beliefs; decisions retain rationale, inputs, alternatives,
acceptance and execution status. No gym reserves calendar time. No LLM calculates
authoritative grades or establishes calendar feasibility.

The operational loop deduplicates events, updates state transactionally, invalidates
affected dependencies, refreshes estimates, and proposes schedule repair. The adaptation
loop evaluates predictions against later outcomes, retains the baseline when evidence
is insufficient, and keeps versioned candidates and rollback. Core work continues with
adaptation disabled.

Reference gym to preserve: AI Strategy's 314 practice items, four sealed 16-item / 100-point
forms, matching questions, case vignettes and tables, explanatory feedback, hints, plain
English aids, eight study guides, 331 glossary entries, weak-item practice, and progress.
The configured causal_know directory was empty at inspection; do not imply it was imported.

## Design plan

A quiet blue study notebook: deep blue #233D63, paper #F7F9FC, ink #182A42,
muted slate #69788D, teal #267B73, and amber #99641B. System humanist sans text
with Georgia for study headings; readable 68-character content measure. Left navigation,
a large working area, and a compact contextual rail for the study contract. The distinctive
element is the question workbench, with comparison-style answer rows and visible reasoning
after submission. Avoid a metrics-card landing page: open with the next useful activity.

## Build sequence

1. Storage, event journal, jobs, versioning, legacy import.
2. Practice and sealed simulation, item-level scoring, assistance and elapsed-time evidence.
3. Source ingestion, retrieval, blueprint-driven generation and separate verification.
4. Tasks, effort distributions, constrained schedule proposals and explicit acceptance.
5. Artifact workbench, independent rubric assessment, shared learner evidence.
6. Adaptation evaluation, operational health, backup/restore, tests and browser verification.

## Scope of the local release

Single-user application. Local SQLite or PostgreSQL. Calendar ingestion through ICS and
manual events; stable event revisions and cancellations; approved plans exported as ICS.
Direct provider OAuth/push synchronization is an extension boundary, not simulated as live.
No arbitrary execution of learner code. Coding artifacts receive rubric feedback and can
record external test results; a sandbox runner is a separate deployment requirement.
