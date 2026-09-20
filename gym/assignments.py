"""Real coursework: versioned rubrics, submissions, official feedback, and style profiles."""

import json

from .assessment import judge
from .contracts import AssignmentInput, RubricInput
from .generation import SYSTEM
from .ingestion import retrieve
from .store import now, uid


def save_rubric(store, data, ident=None):
    expected = data.pop("expected_revision", None)
    data = RubricInput.model_validate(data).model_dump()
    with store.tx() as c:
        ident = ident or uid("rubric_")
        old = store.get(c, "rubric", ident, False)
        version = (old["version"] if old else 0) + 1
        result = store.put(
            c,
            "rubric",
            ident,
            {**data, "version": version, "version_id": ident + f":v{version}", "created_at": now()},
            expected_revision=expected,
        )
        store.put(c, "rubric_version", result["version_id"], result)
        if old:
            for assignment in store.list(c, "assignment"):
                if assignment["rubric_id"] == ident and assignment["follow_shared_rubric"]:
                    store.put(
                        c,
                        "assignment",
                        assignment["id"],
                        {**assignment, "rubric_version_id": result["version_id"]},
                    )
                    store.invalidate(c, "rubric:" + ident, "Shared rubric revised")
                    for assessment in store.list(c, "submission_assessment"):
                        if assessment["assignment_id"] == assignment["id"]:
                            store.put(
                                c,
                                "submission_assessment",
                                assessment["id"],
                                {**assessment, "stale_for_current_rubric": True},
                            )
        store.emit(
            c,
            "rubric.revised" if old else "rubric.created",
            ident,
            {"version_id": result["version_id"], "previous_version_id": old["version_id"] if old else None},
        )
        return result


def create_assignment(store, data):
    data = AssignmentInput.model_validate(data).model_dump()
    with store.tx() as c:
        course = store.get(c, "course", data["course_id"])
        rubric = store.get(c, "rubric", data["rubric_id"])
        if rubric.get("course_id") and rubric["course_id"] != course["id"]:
            raise ValueError("Rubric belongs to another course")
        for sid in data["source_ids"]:
            source = store.get(c, "source", sid)
            if source["course_id"] != course["id"]:
                raise ValueError("Source belongs to another course")
        ident = uid("assignment_")
        record = store.put(
            c,
            "assignment",
            ident,
            {**data, "rubric_version_id": rubric["version_id"], "status": "open", "created_at": now()},
        )
        store.emit(
            c,
            "assignment.created",
            ident,
            {"rubric_version_id": rubric["version_id"], "source_ids": data["source_ids"]},
        )
        # Create the associated task in the same transaction as the assignment and its outbox event.
        task_id = uid("task_")
        task = {
            "title": data["title"],
            "course_id": data["course_id"],
            "category": "academic",
            "deadline": data["deadline"],
            "deadline_kind": "hard",
            "effort_minutes": data["effort_minutes"],
            "min_block": 20,
            "max_block": 60,
            "splittable": True,
            "setup_minutes": 0,
            "definition_of_done": "Complete and verify submission against rubric " + rubric["title"],
            "prerequisites": [],
            "blocked_reason": None,
            "at_risk": False,
            "scope_version": 1,
            "status": "open",
            "created_at": now(),
            "progress": [],
            "assignment_id": ident,
        }
        store.put(c, "task", task_id, task)
        store.put(c, "assignment", ident, {**record, "task_id": task_id})
        store.emit(c, "task.created", task_id, {"assignment_id": ident})
        from .planning import estimate

        estimate(store, c, store.get(c, "task", task_id))
        return store.get(c, "assignment", ident)


def save_draft(store, assignment_id, data):
    body = data.get("body", "")
    if len(body) > 100000:
        raise ValueError("Draft exceeds the text limit")
    with store.tx() as c:
        assignment = store.get(c, "assignment", assignment_id)
        old = store.get(c, "assignment_draft", assignment_id, False) or {
            "active_seconds": 0,
            "body": "",
            "assistance": [],
        }
        file_ids = data.get("file_source_ids", old.get("file_source_ids", []))
        if not isinstance(file_ids, list) or len(file_ids) > 20:
            raise ValueError("A draft supports up to 20 attached sources")
        for sid in file_ids:
            if store.get(c, "source", sid)["course_id"] != assignment["course_id"]:
                raise ValueError("Draft attachment belongs to another course")
        # Explicit work intervals are bounded heartbeats, not keystroke surveillance.
        delta = max(0, min(float(data.get("active_seconds_delta", 0)), 45))
        result = store.put(
            c,
            "assignment_draft",
            assignment_id,
            {
                **old,
                "body": body,
                "active_seconds": old["active_seconds"] + delta,
                "assistance": list(dict.fromkeys([*old["assistance"], *data.get("assistance", [])])),
                "file_source_ids": file_ids,
                "saved_at": now(),
            },
            expected_revision=data.get("expected_revision"),
        )
        if data.get("event") in {"start", "pause", "resume", "save"}:
            store.emit(
                c, "assignment." + data["event"], assignment_id, {"active_seconds": result["active_seconds"]}
            )
        return result


def submit(store, assignment_id, data):
    with store.tx() as c:
        a = store.get(c, "assignment", assignment_id)
        draft = store.get(c, "assignment_draft", assignment_id, False)
        if not draft or (len(draft["body"].strip()) < 10 and not data.get("file_source_ids")):
            raise ValueError("Save a substantive draft first")
        key = data.get("idempotency_key")
        if not key:
            raise ValueError("Submission needs an idempotency key")
        previous = next(
            (
                s
                for s in store.list(c, "submission")
                if s["assignment_id"] == assignment_id and s["idempotency_key"] == key
            ),
            None,
        )
        if previous:
            return previous
        rubric = store.get(c, "rubric_version", a["rubric_version_id"])
        attachment_text = []
        for sid in data.get("file_source_ids", []):
            source = store.get(c, "source", sid)
            if source["course_id"] != a["course_id"]:
                raise ValueError("Submission file belongs to another course")
            fragments = [f for f in store.list(c, "fragment") if f["source_version_id"] == sid]
            attachment_text.append(
                {
                    "source_id": sid,
                    "name": source["name"],
                    "text": "\n\n".join(f["anchor"] + "\n" + f["text"] for f in fragments),
                    "quality_flags": source.get("quality_flags", []),
                }
            )
        assessment_text = (
            draft["body"] + "\n\n" + "\n\n".join(x["name"] + "\n" + x["text"] for x in attachment_text)
        )
        if len(assessment_text) > 80000:
            raise ValueError(
                "Submission text exceeds 80,000 characters; split the work into separately rubriced parts"
            )
        ident = uid("submission_")
        result = store.put(
            c,
            "submission",
            ident,
            {
                "assignment_id": assignment_id,
                "course_id": a["course_id"],
                "body": draft["body"],
                "active_seconds": draft["active_seconds"],
                "assistance": draft["assistance"],
                "ai_contribution": data.get("ai_contribution", "none"),
                "file_source_ids": data.get("file_source_ids", []),
                "attachment_snapshots": attachment_text,
                "assessment_text": assessment_text,
                "rubric_snapshot": rubric,
                "rubric_version_id": a["rubric_version_id"],
                "prompt_snapshot": a["prompt"],
                "created_at": now(),
                "idempotency_key": key,
                "status": "recorded",
                "delivery": "local; not submitted to the institution",
            },
        )
        store.emit(
            c,
            "submission.recorded",
            ident,
            {
                "assignment_id": assignment_id,
                "rubric_version_id": a["rubric_version_id"],
                "active_seconds": draft["active_seconds"],
                "assistance": draft["assistance"],
            },
            key="submission:" + assignment_id + ":" + key,
        )
        return result


def assess_submission(store, router, ident):
    with store.tx() as c:
        submission = store.get(c, "submission", ident)
        a = store.get(c, "assignment", submission["assignment_id"])
        previous = store.get(c, "submission_assessment", "assessment:" + ident, False)
        if previous:
            return previous
    item = {
        "stem": submission["prompt_snapshot"],
        "rubric": submission["rubric_snapshot"]["criteria"],
        "points": a["points"],
    }
    score, feedback = judge(router, item, submission.get("assessment_text", submission["body"]))
    with store.tx() as c:
        result = store.put(
            c,
            "submission_assessment",
            "assessment:" + ident,
            {
                "submission_id": ident,
                "assignment_id": a["id"],
                "score": score,
                "max_score": a["points"],
                "feedback": feedback,
                "rubric_version_id": submission["rubric_version_id"],
                "stale_for_current_rubric": submission["rubric_version_id"] != a["rubric_version_id"],
                "created_at": now(),
            },
        )
        store.emit(
            c,
            "submission.assessed",
            ident,
            {"assessment_id": result["id"], "assessor": "llm"},
            quality_flags=["provisional_model_judgment"],
        )
        return result


def official_grade(store, submission_id, data):
    with store.tx() as c:
        s = store.get(c, "submission", submission_id)
        a = store.get(c, "assignment", s["assignment_id"])
        score = float(data["score"])
        if not 0 <= score <= a["points"]:
            raise ValueError("Grade must be within the assignment's point range")
        source_id = data.get("source_id")
        if source_id:
            source = store.get(c, "source", source_id)
            if source["course_id"] != a["course_id"]:
                raise ValueError("Grade source belongs to another course")
        result = store.put(
            c,
            "official_grade",
            uid("grade_"),
            {
                "submission_id": submission_id,
                "assignment_id": a["id"],
                "score": score,
                "max_score": a["points"],
                "feedback": data.get("feedback", ""),
                "source_id": source_id,
                "occurred_at": data.get("occurred_at") or now(),
                "received_at": now(),
                "individual": a["individual"],
                "authority": "instructor_grade_entered_by_learner",
                "supersedes": data.get("supersedes"),
            },
        )
        store.emit(
            c,
            "grade.recorded",
            submission_id,
            result,
            occurred_at=result["occurred_at"],
            source_id=source_id,
            supersedes=data.get("supersedes"),
            quality_flags=[] if source_id else ["Grade source not attached"],
        )
        return result


def request_profile(store, course_id, source_ids):
    with store.tx() as c:
        for ident in source_ids:
            s = store.get(c, "source", ident)
            if s["course_id"] != course_id or s.get("role") not in {"assessment", "rubric"}:
                raise ValueError("Profiles need assessment examples or rubrics from this course")
            if s.get("reconstruction_status") != "confirmed":
                raise ValueError("Review and confirm each source reconstruction first")
        if not source_ids:
            raise ValueError("Choose at least one assessment source")
        ident = uid("profile_")
        record = store.put(
            c,
            "assessment_profile",
            ident,
            {"course_id": course_id, "source_ids": source_ids, "status": "queued", "created_at": now()},
        )
        job = store.enqueue(c, "profile", {"profile_id": ident}, key="profile:" + ident, priority=5)
        return {**record, "job_id": job}


def generate_profile(store, router, ident):
    with store.tx() as c:
        profile = store.get(c, "assessment_profile", ident)
        fragments = retrieve(
            store,
            c,
            profile["course_id"],
            "question rubric points instructions assessment",
            profile["source_ids"],
            20,
        )
    output, provenance = router.complete(
        "designer",
        SYSTEM,
        json.dumps(
            {
                "assessment_examples": fragments,
                "instruction": "Infer a reusable assessment archetype for practice generation. Return {profile:{title:'', "
                "assessment_kinds:[], question_types:[], structure:'', length_and_time:'', scoring_rules:'', "
                "reasoning_demands:[], difficulty_anchor:'', distractor_patterns:[], rubric_dimensions:[], "
                "source_emphasis:'', uncertainty:[], supporting_fragment_ids:[]}}. "
                "Support open questions, labs, essays, coding and complete assignments. Only describe multiple-choice "
                "distractors if present. Preserve official rubric requirements. Identify unknowns rather than guessing. "
                "Output STYLE and reasoning demands only: exclude actual question stems, answers, firms, numbers, "
                "scenarios, course-specific concept names and question order. This is a profile proposal for user review.",
            }
        ),
    )
    result = output.get("profile")
    required = {
        "title",
        "assessment_kinds",
        "question_types",
        "structure",
        "scoring_rules",
        "reasoning_demands",
        "difficulty_anchor",
        "uncertainty",
        "supporting_fragment_ids",
    }
    if not isinstance(result, dict) or not required <= set(result):
        raise ValueError("Incomplete assessment profile")
    if not set(result["supporting_fragment_ids"]) <= {f["id"] for f in fragments}:
        raise ValueError("Profile cited an unknown source fragment")
    with store.tx() as c:
        stored = store.put(
            c,
            "assessment_profile",
            ident,
            {**profile, "status": "needs_review", "profile": result, "provenance": provenance},
        )
        store.emit(c, "profile.proposed", ident, {"source_ids": profile["source_ids"]})
        return stored


def extract_rubric(store, router, source_id):
    with store.tx() as c:
        source = store.get(c, "source", source_id)
        if source.get("role") != "rubric" or source.get("reconstruction_status") != "confirmed":
            raise ValueError("Review and confirm a rubric source first")
        fragments = retrieve(
            store, c, source["course_id"], "rubric criteria scoring points weight", [source_id], 20
        )
    result, provenance = router.complete(
        "extractor",
        SYSTEM,
        json.dumps(
            {
                "sources": fragments,
                "schema": RubricInput.model_json_schema(),
                "instruction": "Return a rubric matching this schema. "
                "Preserve criterion names and score anchors from the source. Convert explicit point weights to "
                "fractions summing to 1. If weights are not supplied, propose equal weights and state that fact "
                "in the title. Set authority to proposed. Do not invent instructor requirements. "
                "This is a draft that the learner must review.",
            }
        ),
    )
    result.update(authority="proposed", source_id=source_id, course_id=source["course_id"])
    rubric = save_rubric(store, result)
    with store.tx() as c:
        store.emit(
            c,
            "rubric.extracted",
            rubric["id"],
            {"source_id": source_id, "provenance": provenance},
            quality_flags=["Review before using as an official rubric"],
        )
    return rubric
