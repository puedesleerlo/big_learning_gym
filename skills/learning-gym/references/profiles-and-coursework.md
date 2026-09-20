# Goal-directed profiles and actual coursework

Use live `gym_capabilities` and `gym_schema` first. Generic MCP `gym_request`
performs the same REST operations; `gym_read` reads their results. Keep the
course/gym identity consistent across the entire workflow.

## Separate purpose from evidence

- Teaching labs explain and explore course material. They are authored through
  `/api/labs`, with previews that create no learner evidence.
- `/api/sources` preserves uploaded course material. It does not create duties.
- `/api/assignments` records actual coursework (including a real course-assigned
  lab), deadlines, available rubrics and point scales. Use `purpose=self_study`
  for optional generated exercises; they create no scheduling obligation.
  Missing official rubrics stay `rubric_id=null`. Do not invent one to import a
  historical grade. `status=completed` records an already completed external duty.
- Research artifacts are the learner's arguments, drafts or experiments.
  Instructor/TA feedback is an attributed coursework outcome, not an artifact
  to critique as if it were learner writing.

## Create a profile for a particular goal

Read `/api/coursework` and `/api/sources`. Identify the intended task separately
from prior examples. Inspect fragments and confirm their reconstruction before
using them. Use `POST /api/profiles` with the live `ProfileInput` schema:

```json
{
  "course_id": "course-id",
  "title": "Quiz 2 preparation",
  "target": "Prepare for Quiz 2: conditional probability, assumptions and uncertain cases",
  "target_assignment_id": "future-coursework-id",
  "assignment_ids": ["prior-quiz-coursework-id"],
  "source_ids": ["confirmed-prior-assessment-source-version"],
  "material_source_ids": ["confirmed-prior-lecture-source-version"],
  "emergent_source_ids": ["confirmed-new-task-clarification-source-version"],
  "rubric_ids": []
}
```

These IDs are placeholders; select existing same-course references. The future
coursework field is optional when the user has a specific goal without a task
entry. Prior coursework must not include the intended task itself. Prior and
emergent source selections are disjoint. Emergent material may be instruction,
research, assessment or rubric material. Grades, feedback sources, learner
submissions and attempts are never profile inputs. Course-assignment points are
format information, not an observed learner grade.

A model-backed proposal is asynchronous. Read `/api/coursework` and `/api/health`
until it is `needs_review` or fails. Review the actual content scope, purpose,
source references, known requirements and uncertainty. The `practice_rubric`
needs explicit criteria, weights summing to one and observable score anchors;
its authority is `proposed` or `learner`, and `rubric_basis` explains copied,
derived and invented parts. Unknown official criteria stay unknown. Manually
supplied proposals may use the `profile` object to avoid a model call, but still
require this review. Confirmation uses `PUT /api/profiles/{id}` with the current
`expected_revision` and the reviewed structured `profile`. Existing authorization
to prepare and review content is sufficient; do not manufacture another approval
step. Readback verifies the confirmed revision, not scientific validity.

## Evolve the profile as evidence arrives

Inspect `GET /api/profiles/{id}/versions` before changing a profile. Each saved
revision is immutable; `run_version` groups revisions from one profiling run.
After reviewing newly available source versions or updated coursework, call
`POST /api/profiles/{id}/rerun` with:

```json
{
  "expected_revision": 3,
  "idempotency_key": "unique-key-for-this-profile-rerun",
  "emergent_source_ids": ["existing-new-evidence-source-version"]
}
```

Omitted input selections are preserved. Supplied arrays replace selections;
include all evidence you intend to retain. Rerunning refreshes the selected
coursework and rubric snapshots, queues a new model proposal, and requires
review/confirmation again. It does not automatically replace material with the
latest source version; select the new version explicitly. A new run is a new
interpretation, not a demonstrated improvement. Exact retries reuse the key;
changed payloads need a new key. On 409 read current state and reconcile. On model
failure inspect the cause before retrying. Do not keep issuing paid reruns to
hide missing evidence or an unavailable provider.

## Generate and regenerate practice

`POST /api/generations` uses a confirmed `profile_id`, optionally a specific
confirmed `profile_version_id`. Its instructional `source_ids` must be within
the profile's `generation_source_ids`. Rubric and profile snapshots stay pinned.
`counterfactual_count` reserves items inside the total count and requested
formats for changed assumptions, derivations from course premises, and explicit
uncertainty. Use it for both practice and mock exams when that matches the user's
goal; it does not require a separate transfer product. The verifier must accept
these derivations, and all simulation items must pass before publication.

`POST /api/generations/{id}/rerun` takes an `idempotency_key`, optionally a
`profile_id`, `profile_version_id`, narrowed `source_ids`, topic or instructions.
It creates a new set from the latest confirmed profile by default. An explicit
historical version reproduces the prior target; it does not promise identical
model output. Existing questions, attempts and forms remain available. Read back
the new blueprint, its `parent_blueprint_id`, pinned profile and verification
status. A session may use `blueprint_id` to select that particular question set;
only the learner should start or answer it. Practice includes the existing
transfer bank while fixed simulations retain their sealed workflow.

## Record actual instructor outcomes before learner work is uploaded

When explicitly asked to record a real grade or feedback, use
`POST /api/assignments/{id}/outcomes` with the live `CourseworkOutcomeInput`.
Supply actual score or feedback, attribution, observation timestamp and source
URL/source ID. Leave the score null if no grade exists. `occurred_at` stays null
if the original feedback date is unknown; never substitute today's date as the
original event. Keep the learner's disagreement in `learner_comment`, and record
review limits. Use `mark_completed=true` only for explicitly completed external
coursework. This closes the obligation without inventing work time, a local
submission or mastery. Existing submission-linked grades still use their route.

A misplaced feedback artifact can be preserved through `artifact_version_id`.
Set `reclassify_artifact=true` when moving that record to Coursework is requested;
the original version is preserved and its current projection leaves research.
Use a new outcome with `supersedes` for corrections. Stable keys give one stored
outcome on exact retries. Verify coursework, historical records and the absence
of fabricated learner submissions through the API.
