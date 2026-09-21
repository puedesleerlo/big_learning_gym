"""Real coursework: versioned rubrics, submissions, official feedback, and style profiles."""

import json

from .assessment import judge
from .authoring import RevisionConflict
from .contracts import (
    AssignmentInput,
    CourseworkOutcomeInput,
    ProfileInput,
    ProfileRerunInput,
    ProfileRunInput,
    RubricInput,
)
from .generation import SYSTEM
from .ingestion import retrieve
from .store import digest, now, uid


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
        rubric = store.get(c, "rubric", data["rubric_id"]) if data["rubric_id"] else {}
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
            {**data, "rubric_version_id": rubric.get("version_id"), "created_at": now()},
        )
        store.emit(
            c,
            "assignment.created",
            ident,
            {"rubric_version_id": rubric.get("version_id"), "source_ids": data["source_ids"]},
        )
        if data["purpose"] == "self_study" or data["status"] == "completed":
            return record
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
            "definition_of_done": "Complete and verify submission against "
            + rubric.get("title", "course instructions; rubric not yet available"),
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
        if not a.get("rubric_version_id"):
            raise ValueError("Attach an explicit rubric before recording assessable work")
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


def record_coursework_outcome(store, assignment_id, payload):
    """An attributed external outcome does not require or manufacture local learner work."""
    data = CourseworkOutcomeInput.model_validate(payload).model_dump()
    with store.tx() as c:
        assignment = store.get(c, "assignment", assignment_id)
        ident = "outcome_" + digest([assignment_id, data["idempotency_key"]])[:32]
        previous = store.get(c, "coursework_outcome", ident, False)
        if previous:
            if previous["request_hash"] != digest(data):
                raise RevisionConflict("This outcome key was already used with different content")
            return previous
        if data["score"] is not None and data["score"] > assignment["points"]:
            raise ValueError("Grade must be within the assignment's point range")
        if data["source_id"]:
            source = store.get(c, "source", data["source_id"])
            if source["course_id"] != assignment["course_id"]:
                raise ValueError("Outcome source belongs to another course")
        artifact = None
        if data["artifact_version_id"]:
            artifact = store.get(c, "artifact_version", data["artifact_version_id"])
            if artifact.get("course_id") != assignment["course_id"]:
                raise ValueError("Feedback artifact belongs to another course")
            current = store.get(c, "artifact", artifact["artifact_id"])
            if data["reclassify_artifact"] and current["version_id"] != artifact["version_id"]:
                raise RevisionConflict("Review the current artifact version before reclassifying")
        if data["supersedes"]:
            old = store.get(c, "coursework_outcome", data["supersedes"])
            if old["assignment_id"] != assignment_id:
                raise ValueError("Superseded outcome belongs to another assignment")
            if any(o.get("supersedes") == old["id"] for o in store.list(c, "coursework_outcome")):
                raise RevisionConflict("This outcome has already been superseded")
        result = store.put(
            c,
            "coursework_outcome",
            ident,
            {
                **data,
                "assignment_id": assignment_id,
                "course_id": assignment["course_id"],
                "max_score": assignment["points"],
                "individual": assignment["individual"],
                "authority": "instructor_outcome_transcribed",
                "received_at": now(),
                "submission_id": None,
                "request_hash": digest(data),
                "rubric_version_id": assignment.get("rubric_version_id"),
                "original_record_snapshot": artifact,
            },
        )
        if data["mark_completed"]:
            store.put(
                c,
                "assignment",
                assignment_id,
                {
                    **assignment,
                    "status": "completed",
                    "completion_outcome_id": ident,
                },
            )
            if assignment.get("task_id"):
                from .planning import close_coursework_task

                close_coursework_task(store, c, assignment["task_id"], ident, "external_completion")
        if artifact and data["reclassify_artifact"]:
            store.put(
                c,
                "artifact",
                current["id"],
                {
                    **current,
                    "classification": "coursework_record",
                    "coursework_assignment_id": assignment_id,
                    "coursework_outcome_id": ident,
                },
            )
            store.emit(
                c,
                "artifact.reclassified",
                current["id"],
                {
                    "version_id": artifact["version_id"],
                    "assignment_id": assignment_id,
                    "outcome_id": ident,
                },
            )
        store.emit(
            c,
            "coursework.outcome_recorded",
            assignment_id,
            result,
            occurred_at=data["occurred_at"] or data["observed_at"],
            source_id=data["source_id"],
            supersedes=data["supersedes"],
            quality_flags=["External outcome; local submission not linked"],
        )
        return result


def revise_assignment(store, ident, payload):
    """Revise the obligation or its classification, preserving submissions and source snapshots."""
    data = dict(payload)
    expected = data.pop("expected_revision", None)
    with store.tx() as c:
        old = store.get(c, "assignment", ident)
        if expected != old["revision"]:
            raise RevisionConflict("Coursework changed; reload before editing")
        if "course_id" in data and data["course_id"] != old["course_id"]:
            raise ValueError("Coursework cannot move between courses")
        fields = AssignmentInput.model_fields
        updated = AssignmentInput.model_validate(
            {**{k: v for k, v in old.items() if k in fields}, **data}
        ).model_dump()
        if updated["purpose"] != old.get("purpose", "coursework") and updated["purpose"] != "self_study":
            raise ValueError("Create an explicit coursework obligation to schedule self-study work")
        if old["status"] == "completed" and updated["status"] == "open":
            raise ValueError("Create a new obligation when reopening completed work")
        rubric = store.get(c, "rubric", updated["rubric_id"]) if updated["rubric_id"] else None
        if rubric and rubric.get("course_id") not in {None, old["course_id"]}:
            raise ValueError("Rubric belongs to another course")
        for sid in updated["source_ids"]:
            if store.get(c, "source", sid)["course_id"] != old["course_id"]:
                raise ValueError("Source belongs to another course")
        if updated["points"] != old["points"] and (
            any(s["assignment_id"] == ident for s in store.list(c, "submission"))
            or any(o["assignment_id"] == ident for o in store.list(c, "coursework_outcome"))
        ):
            raise ValueError("Existing submissions/outcomes pin the assignment point scale")
        result = store.put(
            c,
            "assignment",
            ident,
            {
                **old,
                **updated,
                "rubric_version_id": (rubric["version_id"] if rubric else None)
                if updated["rubric_id"] != old.get("rubric_id")
                else old.get("rubric_version_id"),
            },
            expected_revision=expected,
        )
        if old.get("task_id"):
            from .planning import revise_coursework_task

            revise_coursework_task(store, c, old, result)
        store.emit(c, "assignment.revised", ident, {"before": old, "after": result})
        return result


def _profile_sources(store, c, course_id, ids, roles):
    for ident in ids:
        source = store.get(c, "source", ident)
        if source["course_id"] != course_id or source.get("role") not in roles:
            raise ValueError(
                "Profiles need assessment examples or rubrics from this course; context needs instructional material"
            )
        if source.get("reconstruction_status") != "confirmed":
            raise ValueError("Review and confirm each source reconstruction first")


def _profile_rubric(value, course_id):
    if not isinstance(value, dict):
        raise ValueError("Provide an explicit practice_rubric with criteria, weights and anchors")
    rubric = RubricInput.model_validate(value).model_dump()
    if rubric.get("course_id") not in {None, course_id}:
        raise ValueError("Practice rubric belongs to another course")
    if rubric["authority"] == "instructor":
        raise ValueError("A derived practice rubric must be labeled proposed or learner, not instructor")
    return {**rubric, "course_id": course_id}


def _save_profile(store, c, ident, data, expected_revision=None):
    old = store.get(c, "assessment_profile", ident, False)
    if old and not old.get("profile_version_id"):
        version_id = ident + ":r" + str(old["revision"])
        if not store.get(c, "assessment_profile_version", version_id, False):
            store.put(
                c,
                "assessment_profile_version",
                version_id,
                {**old, "profile_id": ident, "profile_revision": old["revision"]},
            )
    revision = (old["revision"] if old else 0) + 1
    version_id = ident + ":r" + str(revision)
    saved = store.put(
        c,
        "assessment_profile",
        ident,
        {**data, "profile_id": ident, "profile_version_id": version_id},
        expected_revision=expected_revision,
    )
    store.put(c, "assessment_profile_version", version_id, {**saved, "profile_revision": saved["revision"]})
    return saved


def request_profile(
    store, course_id, source_ids, _ident=None, _expected=None, _rerun_key=None, _request_hash=None, **options
):
    spec = (
        (ProfileRunInput if _ident else ProfileInput)
        .model_validate({"course_id": course_id, "source_ids": source_ids, **options})
        .model_dump()
    )
    with store.tx() as c:
        old = store.get(c, "assessment_profile", _ident, False) if _ident else None
        receipt_id = "profile_rerun_" + digest([_ident, _rerun_key])[:32] if _rerun_key else None
        if receipt_id:
            receipt = store.get(c, "profile_rerun", receipt_id, False)
            if receipt:
                if receipt["request_hash"] != _request_hash:
                    raise RevisionConflict("Profile rerun key was used with different inputs")
                return receipt["response"]
        if old and old["revision"] != _expected:
            raise RevisionConflict("Profile changed; reload before rerunning")
        store.get(c, "course", course_id)
        _profile_sources(store, c, course_id, source_ids, {"assessment", "rubric"})
        _profile_sources(store, c, course_id, spec["material_source_ids"], {"instruction", "research"})
        _profile_sources(
            store,
            c,
            course_id,
            spec["emergent_source_ids"],
            {"instruction", "research", "assessment", "rubric"},
        )
        if set(spec["emergent_source_ids"]) & set(spec["material_source_ids"] + spec["source_ids"]):
            raise ValueError("Label evidence as prior or emergent, not both")
        if spec["target_assignment_id"] in spec["assignment_ids"]:
            raise ValueError("The intended coursework must be distinct from prior coursework examples")
        assignments = []
        target_assignment = None
        rubrics = {}
        for aid in spec["assignment_ids"] + (
            [spec["target_assignment_id"]] if spec["target_assignment_id"] else []
        ):
            a = store.get(c, "assignment", aid)
            if a["course_id"] != course_id:
                raise ValueError("Profile coursework belongs to another course")
            if aid == spec["target_assignment_id"]:
                if a.get("purpose") == "self_study":
                    raise ValueError(
                        "The profile target must be actual coursework, not a self-study exercise"
                    )
                # Validate legacy records too; a nonempty date string alone is not sufficient.
                try:
                    AssignmentInput.model_validate(
                        {k: v for k, v in a.items() if k in AssignmentInput.model_fields}
                    )
                except ValueError as exc:
                    raise ValueError(
                        "Update the target coursework with a valid deadline and estimated time first"
                    ) from exc
            # An allowlist deliberately excludes deadlines, grades, submissions, feedback and learner history.
            assignments.append(
                {
                    k: a[k]
                    for k in (
                        "id",
                        "revision",
                        "title",
                        "kind",
                        "prompt",
                        "source_ids",
                        "rubric_version_id",
                        "points",
                    )
                }
            )
            if aid == spec["target_assignment_id"]:
                target_assignment = assignments.pop()
            for sid in a["source_ids"]:
                src = store.get(c, "source", sid)
                if src.get("role") in {"assessment", "rubric"}:
                    _profile_sources(store, c, course_id, [sid], {"assessment", "rubric"})
                    source_ids = list(dict.fromkeys([*source_ids, sid]))
            if a.get("rubric_version_id"):
                r = store.get(c, "rubric_version", a["rubric_version_id"])
                rubrics[r["id"]] = r
        for rid in spec["rubric_ids"]:
            r = store.get(c, "rubric", rid)
            if r.get("course_id") not in {None, course_id}:
                raise ValueError("Rubric belongs to another course")
            rubrics[r["version_id"]] = store.get(c, "rubric_version", r["version_id"])
        generation_source_ids = list(
            dict.fromkeys(
                spec["material_source_ids"]
                + [
                    sid
                    for sid in spec["emergent_source_ids"]
                    if store.get(c, "source", sid)["role"] in {"instruction", "research"}
                ]
            )
        )
        targeted = bool(
            assignments or target_assignment or generation_source_ids or spec["target"] or spec["profile"]
        )
        if not source_ids and not assignments and not target_assignment and not generation_source_ids:
            raise ValueError("Choose at least one assessment source, coursework item or instructional source")
        if targeted and (not generation_source_ids or len(spec["target"].strip()) < 5):
            raise ValueError("A targeted profile needs instructional context and a specific practice target")
        ident = _ident or uid("profile_")
        manual = spec.pop("profile")
        record = {
            **spec,
            "assessment_source_ids": source_ids,
            "assignment_snapshots": assignments,
            "target_assignment_snapshot": target_assignment,
            "generation_source_ids": generation_source_ids,
            "run_version": old.get("run_version", 1) + 1 if old else 1,
            "previous_profile_version_id": old.get("profile_version_id") if old else None,
            "rubric_snapshots": list(rubrics.values()),
            "status": "queued",
            "created_at": now(),
            "contract_version": "targeted-profile-v2" if targeted else "legacy-style-v1",
        }
        # Empty source lists must never expand to the entire course in retrieve().
        record["assessment_fragments"] = (
            retrieve(
                store,
                c,
                course_id,
                spec["target"] or "question rubric points instructions assessment",
                source_ids,
                20,
            )
            if source_ids
            else []
        )
        record["material_fragments"] = (
            retrieve(store, c, course_id, spec["target"], spec["material_source_ids"], 20)
            if spec["material_source_ids"]
            else []
        )
        record["emergent_fragments"] = (
            retrieve(store, c, course_id, spec["target"], spec["emergent_source_ids"], 20)
            if spec["emergent_source_ids"]
            else []
        )
        if manual is not None:
            manual["practice_rubric"] = _profile_rubric(manual.get("practice_rubric"), course_id)
            record.update(
                profile=manual, status="needs_review", provenance={"kind": "author_supplied_proposal"}
            )
        saved = _save_profile(store, c, ident, record, expected_revision=_expected)
        store.emit(
            c,
            "profile.requested",
            ident,
            {
                "assignment_ids": spec["assignment_ids"],
                "source_ids": source_ids,
                "material_source_ids": spec["material_source_ids"],
            },
        )
        if manual is not None:
            return saved
        job = store.enqueue(
            c,
            "profile",
            {"profile_id": ident, "run_version": saved["run_version"]},
            key="profile:" + ident + ":" + str(saved["run_version"]),
            priority=5,
        )
        response = {**saved, "job_id": job}
        if receipt_id:
            store.put(c, "profile_rerun", receipt_id, {"request_hash": _request_hash, "response": response})
        return response


def rerun_profile(store, ident, data):
    changes = ProfileRerunInput.model_validate(data).model_dump(exclude_unset=True)
    request_hash = digest(changes)
    key = changes.pop("idempotency_key")
    expected = changes.pop("expected_revision")
    with store.tx() as c:
        previous = store.get(c, "assessment_profile", ident)
        spec = {k: v for k, v in previous.items() if k in ProfileInput.model_fields and k != "profile"}
    spec.update(changes)
    return request_profile(
        store, **spec, _ident=ident, _expected=expected, _rerun_key=key, _request_hash=request_hash
    )


def confirm_profile(store, ident, data):
    with store.tx() as c:
        old = store.get(c, "assessment_profile", ident)
        if old["revision"] != data.get("expected_revision"):
            raise RevisionConflict("Profile changed; reload before confirming")
        if old["status"] == "queued":
            raise ValueError("Wait for the profile proposal before confirming")
        result = data.get("profile")
        if not isinstance(result, dict) or not result.get("title"):
            raise ValueError("Profile must be a structured object with a title")
        if old.get("contract_version", "").startswith("targeted-profile-"):
            result["practice_rubric"] = _profile_rubric(result.get("practice_rubric"), old["course_id"])
            if not result.get("rubric_basis"):
                raise ValueError("Explain how the practice rubric was derived, including unknowns")
            allowed = {
                f["id"]
                for f in old["assessment_fragments"]
                + old["material_fragments"]
                + old.get("emergent_fragments", [])
            }
            if not set(result.get("supporting_fragment_ids", [])) <= allowed:
                raise ValueError("Profile cited an unknown source fragment")
        saved = _save_profile(
            store,
            c,
            ident,
            {
                **old,
                "profile": result,
                "status": "confirmed",
                "confirmed_at": now(),
            },
            expected_revision=data["expected_revision"],
        )
        store.emit(c, "profile.confirmed", ident, {"revision": saved["revision"]})
        return saved


def generate_profile(store, router, ident, run_version=None):
    with store.tx() as c:
        profile = store.get(c, "assessment_profile", ident)
        if profile["status"] not in {"queued", "retrying"} or (
            run_version is not None and run_version != profile.get("run_version", 1)
        ):
            return profile
        fragments = profile.get("assessment_fragments")
        if fragments is None:
            fragments = (
                retrieve(
                    store,
                    c,
                    profile["course_id"],
                    "question rubric points instructions assessment",
                    profile["source_ids"],
                    20,
                )
                if profile["source_ids"]
                else []
            )
    targeted = profile.get("contract_version", "").startswith("targeted-profile-")
    output, provenance = router.complete(
        "designer",
        SYSTEM,
        json.dumps(
            {
                "assessment_examples": fragments,
                "prior_coursework": profile.get("assignment_snapshots", []),
                "intended_coursework": profile.get("target_assignment_snapshot"),
                "emergent_evidence": profile.get("emergent_fragments", []),
                "instructional_context": profile.get("material_fragments", []),
                "rubrics": profile.get("rubric_snapshots", []),
                "target": profile.get("target", ""),
                "title": profile.get("title", ""),
                "practice_rubric_schema": RubricInput.model_json_schema(),
                "instruction": "Infer a reusable assessment profile for the specified target. Return {profile:{title:'', "
                "assessment_kinds:[], question_types:[], structure:'', length_and_time:'', scoring_rules:'', "
                "reasoning_demands:[], difficulty_anchor:'', distractor_patterns:[], rubric_dimensions:[], "
                "source_emphasis:'', uncertainty:[], supporting_fragment_ids:[]}}. "
                "Preserve the style and reasoning demands of the selected coursework and examples. "
                "Separate PRIOR evidence from EMERGENT evidence and the INTENDED future task. Explain how new evidence "
                "changes the target profile and which unknowns remain. Use instructional context to identify the specified concepts and topic boundaries. "
                "Never reproduce question stems, answers, firms, scenario numbers or question order. "
                "Distinguish official requirements from proposed anchors or weights. Identify missing evidence. "
                "No grades, feedback or learner responses may define this target. "
                + (
                    "Also include content_scope (concepts and exclusions), rubric_basis (what was copied, derived or invented and why), "
                    "and practice_rubric matching the schema with authority='proposed'. Reuse applicable source criteria and "
                    "weights faithfully; explain adaptations. Where no official rubric exists, propose explicit criteria, "
                    "weights and weak/strong anchors for review. Include reasoning under changed assumptions and uncertainty "
                    "as part of the same skill, without assuming unseen course facts."
                    if targeted
                    else "Output STYLE only; exclude course-specific concept names. This is a proposal for review."
                ),
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
    available = {
        f["id"]
        for f in fragments + profile.get("material_fragments", []) + profile.get("emergent_fragments", [])
    }
    if not set(result["supporting_fragment_ids"]) <= available:
        raise ValueError("Profile cited an unknown source fragment")
    if targeted:
        result["practice_rubric"] = _profile_rubric(result.get("practice_rubric"), profile["course_id"])
        if not result.get("rubric_basis") or not result.get("content_scope"):
            raise ValueError("Targeted profile needs explicit content scope and rubric derivation")
    with store.tx() as c:
        current = store.get(c, "assessment_profile", ident)
        if current["revision"] != profile["revision"]:
            return current
        stored = _save_profile(
            store,
            c,
            ident,
            {
                **profile,
                "status": "needs_review",
                "profile": result,
                "provenance": {
                    **provenance,
                    "prompt_version": "targeted-profile-v1" if targeted else "style-profile-v1",
                },
            },
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
