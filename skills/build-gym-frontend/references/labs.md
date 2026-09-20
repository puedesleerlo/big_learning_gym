# Browse and study

Read `client.labs()` for summaries and `client.lab(id)` for lessons and visit summaries. Empty catalogs direct the learner to `standardGymLink('labs')`. A lesson has its own ID and a course module ID; they are not interchangeable.

Use `useLabVisit(client, labId, lessonId)` in a component keyed by the lesson ID. It loads the previous visit, keeps mutation order, and handles 15-second heartbeats, background pausing, and resume. Display `visit.error` and `visit.clockError` with a retry action.

`visit.start(lesson)` starts or resumes an explicit learner visit. `visit.data.lesson_snapshot` is the presentation during an active visit, even when the lab was revised. Browsing or designing does not start a visit. Reading exposure on start follows the standard Gym; it is preparation, not graded evidence.

Block capabilities, bounds, and examples are in `contracts/activity-registry.json`. Read the entry for the block you are implementing:

- Reading/worked example: text plus `event('reading', {parameters:{activity_id}})` when the learner records reading.
- Prediction/reflection: `event('response', {parameters:{activity_id,value}})`. Keep drafts in `client.storage`, scoped by visit and block. They remain ungraded.
- Parameter experiment: `event('experiment', {parameters:{activity_id,inputs}})`. Display the returned `experiment_results`; the backend computes the result.
- Assessment: use the practice journey; its mode is practice or transfer.
- Coursework: link to `standardGymLink('coursework', {assignment_id})`. A link is not a submission.
- Media/visualization/discussion: use the exports of `@learning-gym/frontend/rich-activities`, passing the block, run, enabled state, and visit callbacks. The stylesheet is yours. The renderer intentionally ships no visual stylesheet.

`enabled` means a running, active visit. Pausing unloads rich media. Visualization execution stays in its nested sandbox and accepts no API bridge. Discussion requires a configured tutor; failed calls show errors and do not fabricate replies.

`event('finish')` records study completion, not mastery. Legacy lessons with `experiment` or no declarative activities should link to `standardGymLink('lab', {lab_id})`. Unknown future block types need an explicit unsupported-state link, not a blank section.
