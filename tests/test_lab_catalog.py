"""D-002/D-004/D-005/D-009: generalized labs preserve evidence and course scope.

All records are fixtures in the temporary test Store. No live curriculum or
learner database is opened, and authoring never substitutes for learner work.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from gym import lab_activity, sessions
from gym.assignments import create_assignment, save_rubric
from gym.store import events, jobs, records


@pytest.fixture
def catalog_clock(monkeypatch):
    timestamp = [datetime.now(timezone.utc)]
    clock = lambda: timestamp[0].isoformat()  # noqa: E731
    monkeypatch.setattr(lab_activity, "now", clock)
    monkeypatch.setattr(sessions, "now", clock)

    def advance(seconds=1):
        timestamp[0] += timedelta(seconds=seconds)
        return clock()

    return advance


@pytest.fixture
def catalog_client(store, catalog_clock):
    with store.tx() as c:
        for course_id, module in (("math-course", "modeling"), ("writing-course", "argument")):
            store.put(c, "course", course_id, {"title": course_id, "description": "Keep this metadata",
                                               "modules": [{"id": module}, {"id": module + "-advanced"}]})
            store.put(c, "source", course_id + "-notes", {"course_id": course_id, "role": "instruction",
                                                         "reconstruction_status": "confirmed"})
    app = FastAPI()
    lab_activity.register_lab_api(app, store)
    with TestClient(app) as client:
        yield client


def bundle(course_id="math-course", module="modeling"):
    return {
        "course_id": course_id, "expected_revision": 0, "title": "Build an interpretable model",
        "description": "A topic-independent lab with explicit inputs and reasoning.",
        "objectives": ["Explain a prediction and inspect the assumptions"], "prerequisite_lab_ids": [],
        "provenance": {"author": "Fixture author", "method": "import", "rationale": "Verified original lesson"},
        "lessons": [{
            "id": "estimate-and-explain", "module": module, "title": "Prediction before observation", "minutes": 10,
            "source_ids": [course_id + "-notes"], "activities": [
                {"type": "reading", "id": "background", "title": "Read the setup", "body": "Output is a weighted sum of two inputs."},
                {"type": "prediction", "id": "predict", "title": "Predict first", "prompt": "What happens when the first input increases?"},
                {"type": "worked_example", "id": "example", "title": "One input at a time", "body": "Increasing the first input by one adds three output units."},
                {"type": "parameter_experiment", "id": "weighted-model", "title": "Change inputs",
                 "description": "A stated arithmetic model, not a causal discovery engine.",
                 "inputs": [
                     {"key": "hours", "label": "Study hours", "min": 0, "max": 10, "step": 1, "initial": 2, "coefficient": 3},
                     {"key": "distractions", "label": "Distractions", "min": 0, "max": 6, "step": 1, "initial": 1, "coefficient": -2},
                 ], "offset": 5, "output_label": "Illustrative output", "unit": "points"},
                {"type": "reflection", "id": "explain", "title": "Explain the comparison", "prompt": "Which model assumption mattered?"},
                {"type": "assessment", "id": "practice", "title": "Check reasoning", "mode": "practice", "count": 2},
            ],
        }],
    }


def publish(client, ident, payload=None):
    response = client.put("/api/labs/" + ident, json=payload or bundle())
    assert response.status_code == 200, response.text
    return response.json()


def start(client, lab_id, *, lesson="estimate-and-explain", module="modeling", key="first-visit"):
    data = {"module": module, "idempotency_key": key}
    if lesson is not None:
        data["lesson_id"] = lesson
    response = client.post(f"/api/labs/{lab_id}/activities", json=data)
    assert response.status_code == 200, response.text
    return response.json()


def observe(client, visit, action, parameters, key="observation"):
    return client.post(f"/api/lab-activities/{visit['id']}/events", json={
        "action": action, "parameters": parameters, "idempotency_key": key,
    })


def database_snapshot(store):
    with store.tx() as c:
        return {
            "state_revision": store.revision(c),
            "records": [dict(row) for row in c.execute(select(records).order_by(records.c.kind, records.c.id)).mappings()],
            "events": [dict(row) for row in c.execute(select(events).order_by(events.c.id)).mappings()],
            "jobs": [dict(row) for row in c.execute(select(jobs).order_by(jobs.c.id)).mappings()],
        }


def add_question(store, module="modeling"):
    with store.tx() as c:
        store.put(c, "item", "model-question", {
            "course_id": "math-course", "module": module, "type": "mcq", "pool": "practice",
            "status": "active", "stem": "Which term changes when the first input increases by one?",
            "points": 5, "options": [{"label": "A", "text": "Three units"}, {"label": "B", "text": "No change"}],
            "key": "A", "explanation": "The first coefficient equals three.", "hint": "Inspect its coefficient",
            "plain": "What does the first coefficient mean?", "family_id": "weighted-sum-family",
            "capabilities": ["model-reasoning"], "cognitive_operation": "application", "rubric_version": "v1",
        })


def test_multiple_labs_share_course_without_merging_visits(catalog_client, store):
    first = publish(catalog_client, "math-intro")
    second = publish(catalog_client, "math-extension")
    third = publish(catalog_client, "writing-workshop", bundle("writing-course", "argument"))
    assert {first["id"], second["id"], third["id"]} == {"math-intro", "math-extension", "writing-workshop"}
    assert first["course_id"] == second["course_id"] == "math-course"
    catalog = catalog_client.get("/api/labs").json()
    assert {entry["id"] for entry in catalog} == {"math-intro", "math-extension", "writing-workshop"}
    own = catalog_client.get("/api/labs", params={"course_id": "math-course"}).json()
    assert {entry["id"] for entry in own} == {"math-intro", "math-extension"}
    one = start(catalog_client, "math-intro")
    two = start(catalog_client, "math-extension")  # Same idempotency key is scoped to its lab.
    assert one["id"] != two["id"]
    assert one["lab_id"] == "math-intro" and one["lesson_id"] == "estimate-and-explain"
    assert [a["id"] for a in catalog_client.get("/api/labs/math-intro").json()["activities"]] == [one["id"]]
    assert [a["id"] for a in catalog_client.get("/api/labs/math-extension").json()["activities"]] == [two["id"]]
    with store.tx() as c:
        course = store.get(c, "course", "math-course")
        assert course["description"] == "Keep this metadata" and course["has_lab"]
        assert not store.list(c, "attempt") and not store.list(c, "learner")


@pytest.mark.parametrize("operation", ["validate", "preview"])
def test_preview_and_validation_normalize_without_any_writes(catalog_client, store, operation):
    before = database_snapshot(store)
    response = catalog_client.post(f"/api/labs/not-published/{operation}", json=bundle())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["valid"] is True and isinstance(data["warnings"], list)
    assert data["lab"]["id"] == "not-published" and data["lab"]["course_id"] == "math-course"
    assert data["lab"]["activities"] == [] and data["lab"]["preview"] is True
    assert data["lab"]["lessons"][0]["module"] == "modeling"
    # No active practice items is an authoring warning, not a reason to mutate or fail.
    assert data["warnings"]
    assert database_snapshot(store) == before
    assert catalog_client.get("/api/labs/not-published").status_code == 404


def test_assessment_count_is_compatible_with_existing_session_contract(catalog_client, store):
    payload = bundle()
    payload["lessons"][0]["activities"][-1]["count"] = 30
    assert catalog_client.post("/api/labs/count-boundary/validate", json=payload).status_code == 200
    payload["lessons"][0]["activities"][-1]["count"] = 31
    before = database_snapshot(store)
    assert catalog_client.post("/api/labs/count-boundary/validate", json=payload).status_code == 422
    assert catalog_client.put("/api/labs/count-boundary", json=payload).status_code == 422
    assert database_snapshot(store) == before


def test_course_owner_is_immutable_and_revisions_pin_experiment(catalog_client, store):
    published = publish(catalog_client, "math-intro")
    visit = start(catalog_client, "math-intro")
    stolen = bundle("writing-course", "argument")
    stolen["expected_revision"] = published["revision"]
    assert catalog_client.put("/api/labs/math-intro", json=stolen).status_code == 409
    revised = bundle()
    revised["expected_revision"] = published["revision"]
    revised["lessons"][0]["activities"][3]["inputs"][0]["coefficient"] = 30
    assert publish(catalog_client, "math-intro", revised)["revision"] == 2
    assert catalog_client.put("/api/labs/math-intro", json=revised).status_code == 409
    measured = observe(catalog_client, visit, "experiment", {"activity_id": "weighted-model", "inputs": {"hours": 4, "distractions": 1}})
    assert measured.status_code == 200, measured.text
    assert measured.json()["experiment_results"]["weighted-model"]["output"] == 15
    newer = start(catalog_client, "math-intro", key="new-version")
    updated = observe(catalog_client, newer, "experiment", {"activity_id": "weighted-model", "inputs": {"hours": 4, "distractions": 1}})
    assert updated.json()["experiment_results"]["weighted-model"]["output"] == 123
    with store.tx() as c:
        assert store.get(c, "lab_version", visit["lab_version_id"])["lab_revision"] == 1
        assert store.get(c, "lab", "math-intro")["course_id"] == "math-course"


def test_resumed_visit_retains_presentation_when_latest_lesson_is_replaced(catalog_client):
    original = bundle()
    original["sources"] = [{"id": "reference", "title": "Original reference", "url": "https://example.org/first"}]
    publish(catalog_client, "versioned-lab", original)
    visit = start(catalog_client, "versioned-lab")
    replacement = deepcopy(original)
    replacement.update(expected_revision=1, title="Replacement lab presentation")
    replacement["lessons"][0].update(id="replacement-lesson", title="New lesson")
    replacement["lessons"][0]["activities"][3]["inputs"][0]["coefficient"] = 30
    replacement["sources"][0]["title"] = "Replacement reference"
    publish(catalog_client, "versioned-lab", replacement)
    resumed = catalog_client.get(f"/api/lab-activities/{visit['id']}").json()
    assert resumed["lab_title"] == original["title"]
    assert resumed["lesson_snapshot"]["id"] == "estimate-and-explain"
    assert resumed["lesson_snapshot"]["activities"][3]["inputs"][0]["coefficient"] == 3
    assert resumed["source_catalog_snapshot"][0]["title"] == "Original reference"
    experiment = observe(catalog_client, resumed, "experiment", {
        "activity_id": "weighted-model", "inputs": {"hours": 4, "distractions": 1},
    })
    assert experiment.status_code == 200, experiment.text
    assert experiment.json()["experiment_results"]["weighted-model"]["output"] == 15
    latest = catalog_client.get("/api/labs/versioned-lab").json()
    assert latest["lessons"][0]["id"] == "replacement-lesson"
    assert "lesson_snapshot" not in latest["activities"][0]


def test_lesson_identity_is_not_module_identity_and_ambiguity_is_rejected(catalog_client):
    payload = bundle()
    second = deepcopy(payload["lessons"][0])
    second.update(id="compare-alternatives", title="A second lesson in the same module")
    payload["lessons"].append(second)
    publish(catalog_client, "two-lessons", payload)
    assert catalog_client.post("/api/labs/two-lessons/activities", json={"module": "modeling", "idempotency_key": "ambiguous"}).status_code == 400
    for lesson_id in ("estimate-and-explain", "compare-alternatives"):
        visit = start(catalog_client, "two-lessons", lesson=lesson_id, key=lesson_id)
        assert visit["module"] == "modeling" and visit["lesson_id"] == lesson_id
    mismatch = catalog_client.post("/api/labs/two-lessons/activities", json={
        "module": "modeling-advanced", "lesson_id": "estimate-and-explain", "idempotency_key": "mismatch",
    })
    assert mismatch.status_code == 400


@pytest.mark.parametrize("bad_source, expected", [
    ("writing-course-notes", 400), ("unconfirmed", 400), ("assessment-example", 400), ("missing-source", 404),
])
def test_reference_validation_rejects_wrong_unreviewed_or_assessment_sources(catalog_client, store, bad_source, expected):
    with store.tx() as c:
        store.put(c, "source", "unconfirmed", {"course_id": "math-course", "role": "instruction", "reconstruction_status": "pending"})
        store.put(c, "source", "assessment-example", {"course_id": "math-course", "role": "assessment", "reconstruction_status": "confirmed"})
    payload = bundle()
    payload["lessons"][0]["source_ids"] = [bad_source]
    before = database_snapshot(store)
    assert catalog_client.post("/api/labs/rejected/validate", json=payload).status_code == expected
    assert catalog_client.put("/api/labs/rejected", json=payload).status_code == expected
    assert database_snapshot(store) == before


def test_coursework_requires_same_course_and_matching_rubric_version(catalog_client, store):
    rubric = save_rubric(store, {"title": "Explain reasoning", "course_id": "math-course", "criteria": [
        {"name": "Reasoning", "weight": 1, "anchors": ["Unsupported", "Mechanism and evidence explained"]},
    ]})
    assignment = create_assignment(store, {"title": "Model critique", "course_id": "math-course",
                                          "prompt": "Explain and critique the assumptions in your model.", "rubric_id": rubric["id"]})
    payload = bundle()
    payload["lessons"][0]["activities"].append({"type": "coursework", "id": "essay", "title": "Write your critique", "assignment_id": assignment["id"]})
    assert catalog_client.post("/api/labs/with-coursework/validate", json=payload).status_code == 200
    with store.tx() as c:
        store.put(c, "assignment", assignment["id"], {**assignment, "course_id": "writing-course"})
    assert catalog_client.post("/api/labs/wrong-owner/validate", json=payload).status_code == 400
    with store.tx() as c:
        store.put(c, "assignment", assignment["id"], assignment)
        version = store.get(c, "rubric_version", rubric["version_id"])
        store.put(c, "rubric_version", rubric["version_id"], {**version, "course_id": "writing-course"})
    assert catalog_client.post("/api/labs/wrong-rubric/validate", json=payload).status_code == 400
    with store.tx() as c:
        store.put(c, "assignment", assignment["id"], {**assignment, "rubric_version_id": "missing-version"})
    assert catalog_client.post("/api/labs/missing-rubric/validate", json=payload).status_code == 404


def test_prerequisite_lab_validation_uses_ids_and_rejects_cycles(catalog_client):
    publish(catalog_client, "intro")
    advanced = bundle()
    advanced["prerequisite_lab_ids"] = ["intro"]
    publish(catalog_client, "advanced", advanced)
    missing = bundle()
    missing["prerequisite_lab_ids"] = ["does-not-exist"]
    assert catalog_client.post("/api/labs/missing-prerequisite/validate", json=missing).status_code == 404
    cyclic = bundle()
    cyclic.update(expected_revision=1, prerequisite_lab_ids=["advanced"])
    assert catalog_client.put("/api/labs/intro", json=cyclic).status_code == 400


def test_prediction_and_experiment_are_recorded_without_becoming_assessment(catalog_client, store):
    publish(catalog_client, "model-lab")
    visit = start(catalog_client, "model-lab")
    response = observe(catalog_client, visit, "response", {"activity_id": "predict", "value": "I predict three more points."})
    assert response.status_code == 200, response.text
    assert response.json()["responses"]["predict"]["value"] == "I predict three more points."
    assert response.json()["responses"]["predict"]["recorded_at"]
    parameters = {"activity_id": "weighted-model", "inputs": {"hours": 4, "distractions": 1}}
    experiment = observe(catalog_client, visit, "experiment", parameters, key="experiment-1")
    assert experiment.status_code == 200, experiment.text
    assert experiment.json()["experiment_results"]["weighted-model"] == {"inputs": parameters["inputs"], "output": 15}
    assert observe(catalog_client, visit, "experiment", parameters, key="experiment-1").json()["experiment_count"] == 1
    altered = {"activity_id": "weighted-model", "inputs": {"hours": 6, "distractions": 1}}
    assert observe(catalog_client, visit, "experiment", altered, key="experiment-1").status_code == 409
    with store.tx() as c:
        evidence = store.evidence(c, visit["id"])
        experiment_event = next(entry for entry in evidence if entry["event_type"] == "lab.activity.experiment")
        assert experiment_event["payload"]["parameters"]["output"] == 15
        assert experiment_event["payload"]["lab_id"] == "model-lab"
        assert experiment_event["payload"]["lesson_id"] == "estimate-and-explain"
        assert experiment_event["payload"]["assessed"] is False
        assert not store.list(c, "attempt") and not store.list(c, "learner")


@pytest.mark.parametrize("parameters", [
    {"activity_id": "weighted-model", "inputs": {"hours": 11, "distractions": 1}},
    {"activity_id": "weighted-model", "inputs": {"hours": "4", "distractions": 1}},
    {"activity_id": "weighted-model", "inputs": {"hours": True, "distractions": 1}},
    {"activity_id": "weighted-model", "inputs": {"hours": 4}},
    {"activity_id": "weighted-model", "inputs": {"hours": 4, "distractions": 1, "unpublished": 9}},
    {"activity_id": "background", "inputs": {}},
    {"inputs": {"hours": 4, "distractions": 1}},
])
def test_experiments_enforce_published_input_contract(catalog_client, store, parameters):
    publish(catalog_client, "model-lab")
    visit = start(catalog_client, "model-lab")
    before = database_snapshot(store)
    response = observe(catalog_client, visit, "experiment", parameters)
    assert response.status_code in {400, 422}, response.text
    assert database_snapshot(store) == before


def test_experiment_output_is_recomputed_even_when_client_claims_a_result(catalog_client, store):
    publish(catalog_client, "model-lab")
    visit = start(catalog_client, "model-lab")
    response = observe(catalog_client, visit, "experiment", {
        "activity_id": "weighted-model", "inputs": {"hours": 4, "distractions": 1}, "output": 999,
    })
    assert response.status_code == 200, response.text
    assert response.json()["experiment_results"]["weighted-model"]["output"] == 15
    with store.tx() as c:
        experiment_event = next(entry for entry in store.evidence(c, visit["id"])
                                if entry["event_type"] == "lab.activity.experiment")
        assert experiment_event["payload"]["parameters"]["output"] == 15


def test_course_edit_cannot_orphan_a_published_lab_lesson(catalog_client, client, store):
    publish(catalog_client, "math-intro")
    current = client.get("/api/authoring/courses/math-course").json()
    before = database_snapshot(store)
    response = client.put("/api/authoring/courses/math-course", json={
        "title": current["title"], "description": current["description"],
        "expected_revision": current["revision"],
        "modules": [{"id": "modeling-advanced", "title": "Advanced modeling"}],
        "provenance": bundle()["provenance"],
    })
    assert response.status_code == 400, response.text
    assert "published labs" in response.json()["detail"]
    assert database_snapshot(store) == before


def test_responses_cannot_target_readings_or_other_lab_blocks(catalog_client, store):
    publish(catalog_client, "first-lab")
    other = bundle()
    other["lessons"][0]["activities"][1]["id"] = "other-lab-prediction"
    publish(catalog_client, "other-lab", other)
    visit = start(catalog_client, "first-lab")
    for block_id in ("background", "weighted-model", "other-lab-prediction", "unknown"):
        before = database_snapshot(store)
        response = observe(catalog_client, visit, "response", {"activity_id": block_id, "value": "Not valid for this activity."}, key=block_id)
        assert response.status_code == 400
        assert database_snapshot(store) == before


def test_linked_assessment_uses_existing_practice_and_discloses_preparation(catalog_client, catalog_clock, store):
    add_question(store)
    publish(catalog_client, "math-intro")
    visit = start(catalog_client, "math-intro")
    assert observe(catalog_client, visit, "reading", {"activity_id": "background"}).status_code == 200
    catalog_clock()
    practice = sessions.create_session(store, {"course_id": "math-course", "module": "modeling", "mode": "practice", "count": 1})
    linked = catalog_client.post(f"/api/lab-activities/{visit['id']}/link-session", json={"session_id": practice["id"]})
    assert linked.status_code == 200, linked.text
    assert linked.json()["lab_id"] == "math-intro" and linked.json()["status"] == "finished"
    sessions.submit_answer(store, practice["id"], {"item_id": "model-question", "answer": "A", "confidence": .7, "idempotency_key": "actual-response"})
    outcome = catalog_client.get(f"/api/lab-activities/{visit['id']}").json()["practice_outcome"]
    assert outcome["score"] == 5 and outcome["assisted_attempt_count"] == 1
    assert outcome["attempts"][0]["assistance"] == ["lab_materials"]
    assert "answer" not in outcome["attempts"][0]


def test_reported_question_is_excluded_from_lab_score_but_history_is_preserved(catalog_client, client, store):
    add_question(store)
    with store.tx() as c:
        original = store.get(c, "item", "model-question")
        store.put(c, "item", "still-valid-question", {**original, "points": 3, "family_id": "second-family"})
    publish(catalog_client, "math-intro")
    visit = start(catalog_client, "math-intro")
    practice = client.post("/api/sessions", json={
        "course_id": "math-course", "module": "modeling", "mode": "practice", "count": 2,
    }).json()
    linked = catalog_client.post(f"/api/lab-activities/{visit['id']}/link-session", json={"session_id": practice["id"]})
    assert linked.status_code == 200, linked.text
    for item in practice["items"]:
        answered = client.post(f"/api/sessions/{practice['id']}/answers", json={
            "item_id": item["id"], "answer": "A", "confidence": .7, "idempotency_key": item["id"],
        })
        assert answered.status_code == 200, answered.text
    before = catalog_client.get(f"/api/lab-activities/{visit['id']}").json()["practice_outcome"]
    assert before["score"] == before["max_score"] == 8
    reported = client.post("/api/items/model-question/report", json={"reason": "Its answer key has a verified error."})
    assert reported.status_code == 200 and reported.json()["affected_attempts"] == 1
    after = catalog_client.get(f"/api/lab-activities/{visit['id']}").json()["practice_outcome"]
    assert after["score"] == after["max_score"] == 3
    assert after["assessed_count"] == after["invalidated_count"] == 1
    assert after["attempt_count"] == 2
    invalid = next(attempt for attempt in after["attempts"] if attempt["item_id"] == "model-question")
    assert invalid["invalidated"] is True
    with store.tx() as c:
        evidence = next(event for event in store.evidence(c, invalid["id"])
                        if event["event_type"] == "attempt.submitted")
        assert evidence["payload"]["score"] == 5


def test_legacy_course_identified_lab_and_activity_remain_readable(catalog_client, catalog_clock, store):
    legacy = bundle()
    legacy.pop("course_id")
    legacy["lessons"][0].pop("module")
    legacy["lessons"][0]["id"] = "modeling"
    assert publish(catalog_client, "math-course", legacy)["course_id"] == "math-course"
    timestamp = catalog_clock()
    with store.tx() as c:
        store.put(c, "lab_activity", "legacy-visit", {
            "course_id": "math-course", "module": "modeling", "lab_revision": 1,
            "lab_version_id": "lab:math-course:1", "source_ids": ["math-course-notes"],
            "experiment": "", "status": "active", "running": False, "active_seconds": 12,
            "started_at": timestamp, "last_tick": timestamp, "reading_count": 1,
            "experiment_count": 0, "help_count": 0, "reflection": "Existing learner writing", "session_id": None,
        })
    old = catalog_client.get("/api/lab-activities/legacy-visit")
    assert old.status_code == 200, old.text
    assert old.json()["active_seconds"] == 12 and old.json()["reflection"] == "Existing learner writing"
    own = catalog_client.get("/api/labs/math-course").json()
    assert [entry["id"] for entry in own["activities"]] == ["legacy-visit"]
    publish(catalog_client, "new-math-lab")
    assert catalog_client.get("/api/labs/new-math-lab").json()["activities"] == []
    finished = observe(catalog_client, {"id": "legacy-visit"}, "finish", {}, key="legacy-finish")
    assert finished.status_code == 200 and finished.json()["status"] == "finished"
