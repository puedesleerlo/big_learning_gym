import pytest

from gym.assignments import (
    create_assignment,
    official_grade,
    request_profile,
    save_draft,
    save_rubric,
    submit,
)
from gym.ingestion import ingest


def rubric(store):
    return save_rubric(
        store,
        {
            "title": "Shared rubric",
            "criteria": [
                {"name": "Reasoning", "weight": 0.6, "anchors": ["Unsupported", "Justified"]},
                {"name": "Evidence", "weight": 0.4, "anchors": ["Absent", "Verified"]},
            ],
        },
    )


def test_submission_and_draft_keep_their_rubric_version(store):
    r = rubric(store)
    a = create_assignment(
        store,
        {
            "title": "Write a case",
            "course_id": "course",
            "prompt": "Write a defensible answer to the case",
            "rubric_id": r["id"],
            "follow_shared_rubric": True,
        },
    )
    save_draft(
        store,
        a["id"],
        {"body": "My initial claim with supporting evidence.", "event": "save", "active_seconds_delta": 15},
    )
    s = submit(store, a["id"], {"idempotency_key": "submission-key"})
    assert s["rubric_snapshot"]["version"] == 1
    updated = save_rubric(
        store,
        {"title": "Shared rubric revised", "criteria": r["criteria"], "expected_revision": r["revision"]},
        r["id"],
    )
    with store.tx() as c:
        assert store.get(c, "assignment", a["id"])["rubric_version_id"] == updated["version_id"]
        assert store.get(c, "submission", s["id"])["rubric_snapshot"]["version"] == 1
        assert store.get(c, "assignment_draft", a["id"])["body"].startswith("My initial")
    assert submit(store, a["id"], {"idempotency_key": "submission-key"})["id"] == s["id"]


def test_team_grade_does_not_become_individual_mastery(store):
    r = rubric(store)
    a = create_assignment(
        store,
        {
            "title": "Team lab",
            "course_id": "course",
            "prompt": "Implement and test this shared lab",
            "rubric_id": r["id"],
            "individual": False,
        },
    )
    save_draft(store, a["id"], {"body": "Our team produced a working system."})
    s = submit(store, a["id"], {"idempotency_key": "team-submit"})
    g = official_grade(store, s["id"], {"score": 95, "feedback": "Good collective work"})
    assert not g["individual"]
    with store.tx() as c:
        assert store.list(c, "learner") == []


def test_profile_requires_reviewed_assessment_source(store):
    source = ingest(store, "course", "quiz.md", b"# Quiz\nA real question with rubric.", role="assessment")
    with pytest.raises(ValueError, match="confirm"):
        request_profile(store, "course", [source["id"]])
    with store.tx() as c:
        store.put(c, "source", source["id"], {**source, "reconstruction_status": "confirmed"})
    assert request_profile(store, "course", [source["id"]])["status"] == "queued"


def test_pinned_rubric_does_not_change(store):
    r = rubric(store)
    a = create_assignment(
        store,
        {
            "title": "Essay",
            "course_id": "course",
            "prompt": "Defend your argument in a concise essay",
            "rubric_id": r["id"],
        },
    )
    save_rubric(store, {"title": "New shared version", "criteria": r["criteria"]}, r["id"])
    with store.tx() as c:
        assert store.get(c, "assignment", a["id"])["rubric_version_id"] == r["version_id"]


def test_uploaded_homework_is_preserved_and_assessed(store):
    from gym.assignments import assess_submission

    r = rubric(store)
    a = create_assignment(
        store,
        {
            "title": "File submission",
            "course_id": "course",
            "prompt": "Defend the comparison in the attached response",
            "rubric_id": r["id"],
        },
    )
    source = ingest(
        store,
        "course",
        "answer.md",
        b"Random assignment addresses confounding in expectation.",
        role="submission",
    )
    save_draft(store, a["id"], {"body": ""})
    submission = submit(store, a["id"], {"idempotency_key": "file-only", "file_source_ids": [source["id"]]})
    assert "Random assignment" in submission["assessment_text"]
    assert submission["attachment_snapshots"][0]["source_id"] == source["id"]

    class Assessor:
        def complete(self, role, system, prompt):
            import json

            answer = json.loads(prompt)["answer"]
            assert "Random assignment addresses confounding" in answer
            return {
                "criteria": [
                    {
                        "name": name,
                        "score": 0.5,
                        "evidence_quote": "Random assignment",
                        "explanation": "Needs a boundary condition",
                    }
                    for name in ["Reasoning", "Evidence"]
                ],
                "uncertainty": "Only one claim is available",
                "feedback": "Add the missing identification assumptions",
                "next_step": "Explain a limitation of randomization",
            }, {"model": "fixture"}

    assess_submission(store, Assessor(), submission["id"])
    from gym.learning import recommend

    with store.tx() as c:
        assert recommend(store, c)["mode"] == "coursework"
    official_grade(store, submission["id"], {"score": 95, "feedback": "Official revised assessment"})
    with store.tx() as c:
        assert recommend(store, c)["mode"] != "coursework"


def test_autosave_keeps_attachment_and_assistance_history(store):
    r = rubric(store)
    a = create_assignment(
        store,
        {
            "title": "Persistent draft",
            "course_id": "course",
            "prompt": "Defend a causal interpretation",
            "rubric_id": r["id"],
        },
    )
    source = ingest(
        store, "course", "draft.txt", b"A draft response with recorded assistance.", role="submission"
    )
    save_draft(
        store,
        a["id"],
        {
            "body": "My draft has AI assistance.",
            "assistance": ["substantive"],
            "file_source_ids": [source["id"]],
        },
    )
    later = save_draft(store, a["id"], {"body": "My edited draft.", "assistance": []})
    assert later["assistance"] == ["substantive"]
    assert later["file_source_ids"] == [source["id"]]
