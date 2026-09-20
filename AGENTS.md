# Repository change contract

Applies to every coding agent and every change in this repository.

## Read before editing

1. Read `DECISIONS.md` for accepted constraints and their rationale.
2. Read `docs/ARCHITECTURE.md` for the implemented boundaries and limitations.
3. Read `docs/ALGORITHMS.md` when touching scoring, recommendation, planning, assessment, generation or adaptation.
4. Inspect `git status` and preserve other ongoing work. Do not sweep unrelated changes into a commit.

## Classify the change

- State the applicable decision IDs and whether their behavior is preserved or revised before implementation.
- Implement routine fixes and refactors within the accepted decisions without asking for redundant approval.
- A change to authority, evidence meaning, persistence, module boundaries, public contracts, algorithm semantics, thresholds, model roles or permissions requires an explicit user request covering that change, or approval of a concrete proposal before activation/merge.
- Existing explicit authorization counts. Do not manufacture an approval step for an already authorized change.
- If authorization is missing, prepare the rationale, alternatives, expected effects, validation and rollback in a change proposal; continue independent work that preserves the baseline.
- Never rewrite a decision, lower an acceptance threshold, delete a test, or change expected outputs merely to make a conflicting implementation pass.
- Record a superseding decision rather than erasing the old rationale. The user owns acceptance; an agent cannot approve its own proposal.

## Implement and validate

- Keep `docs/ARCHITECTURE.md` current when the implemented structure or data flow changes.
- Update `docs/ALGORITHMS.md`, version identifiers and behavioral fixtures when an authorized algorithm change alters observable behavior.
- Add one change record under `docs/changes/` for protected changes. Use `docs/changes/TEMPLATE.json`; enumerate affected paths and decision IDs, evidence of authorization when needed, checks and rollback.
- Run `python scripts/check_architecture.py` and the relevant behavioral tests. Before publishing, run the full suite and the frontend build when affected.
- Use `python scripts/check_architecture.py --base <base-commit>` to inspect the actual commit diff. A green check validates structure and declared coverage, not human approval or scientific validity.
- Keep secrets, uploads, learner history and local databases out of commits. Never send real learner data to a new provider without the user's authorization.
- Use feature branches/PRs for future changes unless the user explicitly requests a direct push. Do not change repository protections, ownership, CI gates or approval evidence to bypass review.

## Finish

Report the changed behavior, affected decisions, validation, and remaining limits. Distinguish proposed, implemented and remotely enforced controls. Do not claim a passing test proves compliance with every architectural decision.
