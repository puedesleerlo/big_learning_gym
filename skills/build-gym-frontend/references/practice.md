# Linked practice

Call `visit.practice({course_id,module,mode,count})` from a started visit. This records preparation, pauses study, creates an unanswered session, links it before answering, and resumes its timer. Use `mode: 'practice' | 'transfer'`. Simulation entry remains in the full Gym.

Session creation is not idempotent. Never automatically retry `POST /sessions`. If a start is interrupted, the client preserves its pending intent. Use `client.recoveryCandidates(visit)` and let the learner choose a session; `client.linkPractice(visit.id, session.id)` resumes the connection. If no candidate appears, inspect the full Gym's recent sessions before explicitly abandoning the pending start. Do not silently create another session.

Use `usePracticeSession(client, id)` for data, timer, answer submission, and finish. Answer shapes:

- MCQ: option label string, such as `A`.
- Matching: map every prompt ID to a term ID.
- Open/case/counterfactual/coding: a string of at least 10 trimmed characters. Coding input is saved, not executed.

The optional confidence is 0–1 or null. `answer(itemId, value, confidence)` keeps a receipt across interrupted retries and returns authoritative feedback. Never put answer keys in the initial public-item model. All question types should show supplied case context and rubric when present.

Use `timer('heartbeat', itemId)` on question changes so server time belongs to the appropriate item. Pause/resume are explicit. Display server active seconds; a local visual timer must never become reported evidence.

Hints/plain-language aids use `client.aid()` and must remain visibly attributed. An answer can be assessed or pending. Open work commonly stays pending until the configured worker/model succeeds. Offer refresh and show provisional model feedback distinctly.

Finishing incomplete work requires an explicit learner action and must show the unanswered count. The finish response contains completion, score so far, pending assessments, and review. Never infer mastery or official grades.

All request bodies, public items, visit snapshots, and session responses are described by the package declarations. `contracts/openapi.json` supplies route/request validation; `contracts/examples.json` contains synthetic catalog/items; `contracts/journey-examples.json` shows actual synthetic visit, linking, answer and finish responses, not learner records.
