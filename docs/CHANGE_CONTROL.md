# Keeping architecture and algorithms under control

The control model is: **instructions → explicit decisions → behavioral checks → independent merge authority**. No one layer guarantees the others. This setup adds repository files; it does not silently enable GitHub settings or change credentials.

## What belongs where

- `AGENTS.md`: the mandatory working procedure for coding agents. `.cursor/rules/architecture.mdc` points Cursor agents to the same procedure.
- `DECISIONS.md`: accepted constraints and why they exist. Append proposed/superseding decisions when changing a constraint; retain the old rationale and authorization reference.
- `docs/ARCHITECTURE.md`: the implemented structure, ownership boundaries, data flow and limitations. Update it in the same change that changes those facts.
- `docs/ALGORITHMS.md`: current formulas, thresholds, eligibility, ranking, versions and validation contracts. Baselines are revisable; they are not scientific facts just because they are documented.
- `docs/changes/*.json`: a concise, path-specific record for each protected change. Copy `TEMPLATE.json` to a new name. State affected decisions, whether behavior changes, checks and rollback. Ordinary fixes declare preservation; semantic changes reference the user's specific authorization and a decision revision.

Examples: extracting a function with unchanged outputs is preserving. Increasing the evidence weight for assisted work, lowering the model-promotion threshold, letting a tutor book time, exposing simulation answers, or adding a provider with a new data destination is a revision. Do not use a broad feature request as implicit approval to change unrelated constraints.

## What checks actually enforce

`python scripts/check_architecture.py` checks required references and selected AST boundaries: deterministic core modules do not import provider/transport modules, and direct writes to the active schedule belong to the planner. These checks are intentionally limited; they are not a Python sandbox or proof that indirect SQL obeys every rule.

`python scripts/check_architecture.py --base <commit>` also checks the committed merge-base-to-HEAD diff. New path-specific change records must cover protected code, configuration, tests and governance changes. Existing records cannot be edited into blanket waivers. Deleted and renamed files are still checked. A declared revision requires a decision-file change; declared architecture/algorithm changes require the corresponding document changes. The checker does not judge the truth of the explanation or authenticate its approval.

Behavioral tests protect evidence weighting, the exploration budget, schedule acceptance, sealed simulations, source/rubric versions, point-in-time adaptation, rollback, outbox semantics and credential boundaries. Tests deliberately use frozen contracts: changing an expected value needs the same decision review as changing the algorithm. Removing tests, editing CI or weakening the checker is itself protected.

The CI workflow runs architecture checks, backend tests on SQLite and PostgreSQL, and the frontend build. No provider credentials or learner data are supplied. It uses `pull_request`, not privileged `pull_request_target`, and its token has read-only contents permission. Local paid model tests remain opt-in.

## Activate enforcement on GitHub

At inspection on 2026-09-20, `main` was unprotected and the repository had no rulesets. That observation is a dated baseline, not a live status indicator.

1. Review and merge the governance files. Run CI once so the check names exist.
2. Protect `main` with a ruleset requiring pull requests, resolved discussions, and the checks **Architecture**, **Backend (sqlite)**, **Backend (postgres)** and **Frontend**. Require an up-to-date branch, block force pushes and deletion, and do not grant the agent a bypass role.
3. Require code-owner review for the protected paths. `.github/CODEOWNERS` assigns @puedesleerlo and includes itself, CI, agent instructions, decision files and tests. Dismiss stale approvals when new commits arrive so a later push cannot reuse an older architectural approval.
4. Give the agent a separate GitHub App/bot identity with only the repository permissions needed to push a feature branch and open a PR. Keep repository administration, review acceptance and ruleset changes in the human identity. Do not hand the agent the human's admin token or an unrestricted `gh` login if independent enforcement is the goal.
5. Merge after the human reviews the actual diff, the decision record and the evidence. A label, JSON `authorization` field, comment authored by the agent, or green workflow is not a substitute for that review.

The current local `gh` login is the same `puedesleerlo` identity used to administer the repository. An agent using it acts as that account; GitHub cannot distinguish a human operation from an agent operation. A pull-request author cannot approve their own PR. Requiring @puedesleerlo approval while also using @puedesleerlo as the agent author therefore needs a separate contributor identity or another authorized human reviewer. Do not enable that combination blindly and then add a broad bypass to get unstuck.

For stronger separation, run agents in worktrees/sandboxes without access to the human's keychain or admin credentials. Keep rule administration outside that environment. Repository files help cooperative agents; credential and merge boundaries provide the independent control.

GitHub references: [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [ruleset enforcement and bypass](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository).
