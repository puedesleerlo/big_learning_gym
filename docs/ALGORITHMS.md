# Algorithm contracts

This is the current behavioral baseline, read with D-003 through D-007 in `../DECISIONS.md`. Values below describe implemented heuristics, not established learning-science constants. An authorized change must update the relevant version, behavioral fixtures, this document and its change record. A refactor preserving inputs/outputs does not require a new algorithm version.

## A-001 — Capability evidence: `capability-beta-v1`

Implementation: `gym/learning.py::update_learner`.

For each course-scoped capability and cognitive dimension, start with alpha = beta = 1. Let r = earned / available points. Evidence weight w is 1 for unaided work or 0.25 for assisted work; multiply by 0.25 for a previously exposed item family and by 0.5 for model-assessed work. Update alpha by r*w and beta by (1-r)*w. Invalidated or unscored attempts have no effect; replaying the same evidence ID has no effect.

The display estimate is alpha/(alpha+beta), with a clipped normal approximation of ±1.96 standard deviations, rounded to three decimals. This broad interval is not a calibrated mastery probability. Successful unaided work (r >= 0.8) gets a delayed check after three days; other assessed work after one day. Simulation updates are deferred until the session finishes. Preserve assistance and prior exposure when presenting evidence.

Tests: `tests/test_architecture_contracts.py`, `tests/test_sessions.py`.

## A-002 — Activity recommendation baseline

Implementation: `gym/learning.py::recommend`; currently a deterministic policy without a persisted version ID.

Check the latest submission per assignment. Instructor outcomes take precedence over model judgments. A score below 80% recommends revising that assignment; it does not update general mastery. Otherwise, prefer unresolved recent item-family errors, then overdue delayed checks, then starting/unseen practice. Exclude invalidated work and feedback from active simulations. Recommendations state evidence and alternatives; they do not reserve calendar time.

Changing ranking, cutoffs, evidence eligibility or the meaning of a score requires an explicit policy-version strategy rather than silently reusing this baseline.

## A-003 — Effort prior: `effort-prior-v1`

Implementation: `gym/planning.py::estimate`, baseline seeded by `gym/store.py`.

For the user's remaining-scope estimate b, p50 = max(5, round(b * multiplier)) and p80 = max(p50, ceil(b * upper_multiplier)). The initial multipliers are 1.0 and 1.4. Predictions include scope version, input revision/evidence and active model version. Scope changes invalidate effort; changing only the deadline does not redefine work. Completion observations are remaining active minutes since that scope's forecast, not lifetime effort.

Tests: `tests/test_planning.py`, `tests/test_recovery_adaptation.py`.

## A-004 — Scheduling: `hierarchical-greedy-v1`

Implementation: `gym/planning.py::propose_schedule` and `accept_schedule`.

Allocate p80 effort rounded up to five-minute units, with useful minimum blocks and setup costs. Respect availability, fixed commitments, workload ceilings, configured slack, deadlines, dependencies and preserved pins. Category priority is endangered academic work, research, other academic work, capability work, then exploration; deadline and creation time break ties. Dependencies can constrain this order.

Exploration is limited to 10% of usable horizon budgets, rounded down to five minutes, including setup time. User-pinned conflicts are reported rather than silently removed. An infeasible or stale proposal cannot be accepted. This greedy policy is a feasible-plan heuristic, not a global optimizer or proof of impossibility. Acceptance is a separate action.

Tests: `tests/test_planning.py`, `tests/test_architecture_contracts.py`.

## A-005 — Effort calibration and promotion

Implementation: `gym/adaptation.py::evaluate`, `activate_model`.

Match positive completion effort to the last same-scope forecast preceding both occurrence and receipt. Sort outcomes by receipt. Require at least 12 pairs. Reserve the later observations after max(8, floor(0.7*n)) as holdout; at least eight training outcomes must have arrived before the earliest held-out prediction. Normalize historical forecasts by their recorded model multipliers before fitting a median correction and empirical 80th-percentile upper factor.

A candidate passes only when holdout mean absolute error is strictly below 90% of the original forecast error and p80 pinball loss does not worsen. Passing creates a shadow model, not an activation. Only eligible shadow or previously active/retired models can be activated. Historical forecasts remain unchanged. The original prior remains available for rollback. Fewer observations or invalid timing retain the baseline. Independent performance score error is descriptive, not a causal effect estimate.

Tests: `tests/test_llm_adaptation.py`, `tests/test_recovery_adaptation.py`.

## A-006 — Scoring and publication

Implementations: `gym/sessions.py`, `gym/assessment.py`, `gym/generation.py`, `gym/contracts.py`.

MCQ uses one exact key; matching earns the fraction of correctly matched prompts. Open work uses criterion scores in [0,1], weighted by the pinned rubric and scaled to points. Every criterion must be covered exactly once and evidence quotes must occur in the submitted body/attachment text. Model assessments remain provisional and carry their provenance.

Generate up to 40 items in batches of four, enforcing requested format counts and source references. A shared case is reused for the configured trailing items. A separate verifier must agree on MCQ keys/matching mappings and return no issues. Unsupported, ambiguous or duplicate items are quarantined. Fixed simulations publish only if every item passes. These checks do not establish psychometric equivalence to an official exam.

Tests: `tests/test_generation.py`, `tests/test_coursework.py`, `tests/test_sessions.py`.
