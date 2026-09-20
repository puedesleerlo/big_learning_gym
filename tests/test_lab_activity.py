"""Lab study observations must never masquerade as independent assessment."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gym import lab_activity
from gym.sessions import submit_answer


@pytest.fixture
def lab_clock(monkeypatch):
    current = [datetime(2026, 9, 20, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(lab_activity, "now", lambda: current[0].isoformat())

    def advance(seconds):
        current[0] += timedelta(seconds=seconds)
        return current[0].isoformat()

    return advance


@pytest.fixture
def lab_client(store, lab_clock):
    app = FastAPI()
    lab_activity.register_lab_api(app, store)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def presentation(store):
    with store.tx() as c:
        store.put(c, "course", "course", {"title": "Causality", "modules": [
            {"id": "C01"}, {"id": "C02"},
        ]})
        store.put(c, "source", "notes-v1", {
            "course_id": "course", "role": "instruction", "reconstruction_status": "confirmed",
        })
    return {
        "expected_revision": 0, "title": "Causality lab", "description": "Learn through toy experiments.",
        "sources": [{"id": "paper", "title": "Method paper", "url": "https://example.org/paper"}],
        "provenance": {"author": "Test author", "method": "import", "rationale": "Verified teaching content"},
        "lessons": [{
            "id": "C01", "title": "Interventions", "stage": "Foundations", "minutes": 20,
            "question": "What changes when we act?", "objectives": ["Separate observation from intervention"],
            "intuition": ["Setting a switch is different from observing one."],
            "worked_example": {"title": "The switch", "body": "Force the switch on while keeping the wiring fixed."},
            "takeaways": ["Interventions replace a mechanism"], "pitfall": "Confusing observation with intervention",
            "experiment": "intervention", "experiment_task": "Change the switch", "source_ids": ["notes-v1"],
            "paper_bridge": {"source_id": "paper", "why_it_matters": "A foundation for discovery", "read_first": "Introduction",
                             "claim": "Information requires assumptions", "assumptions": ["A stated causal model"],
                             "limits": ["Toy data"], "exercise": "Name one limitation"},
        }],
    }


def publish_and_start(client, presentation, key="visit-1"):
    assert client.put("/api/labs/course", json=presentation).status_code == 200
    response = client.post("/api/labs/course/activities", json={"module": "C01", "idempotency_key": key})
    assert response.status_code == 200, response.text
    return response.json()


def event(client, ident, action, key=None, **extra):
    return client.post(f"/api/lab-activities/{ident}/events", json={
        "action": action, "idempotency_key": key or action, **extra,
    })


def session(store, started_at, **overrides):
    item = {
        "id": "item", "revision": 1, "course_id": "course", "module": "C01", "status": "active",
        "type": "mcq", "key": "B", "options": [{"label": "A", "text": "A"}, {"label": "B", "text": "B"}],
        "explanation": "A private answer explanation.", "points": 5, "family_id": "family", "capabilities": ["causal-reasoning"],
        "cognitive_operation": "application",
    }
    record = {
        "course_id": "course", "module": "C01", "mode": "practice", "status": "active",
        "started_at": started_at, "last_tick": started_at, "running": False, "item_ids": ["item"],
        "snapshots": {"item": item}, "assistance": {}, "exposures": {"item": 0},
        "item_seconds": {}, "active_seconds": 0, "time_limit_seconds": None, "current_item": "item",
        **overrides,
    }
    with store.tx() as c:
        store.put(c, "item", "item", item)
        return store.put(c, "session", "practice-1", record)


def test_presentation_is_typed_key_free_and_versioned(lab_client, presentation, store):
    for forbidden in ("checkpoint", "practice", "key"):
        invalid = deepcopy(presentation)
        invalid["lessons"][0][forbidden] = "answer"
        assert lab_client.put("/api/labs/course", json=invalid).status_code == 422
    first = lab_client.put("/api/labs/course", json=presentation).json()
    assert first["revision"] == 1
    assert lab_client.put("/api/labs/course", json=presentation).status_code == 409
    revised = deepcopy(presentation)
    revised.update(expected_revision=1, title="Revised causal lab")
    assert lab_client.put("/api/labs/course", json=revised).json()["revision"] == 2
    with store.tx() as c:
        assert store.get(c, "lab_version", "lab:course:1")["title"] == "Causality lab"
        course = store.get(c, "course", "course")
        assert course["has_lab"] is True and course["title"] == "Causality"
        assert course["modules"] == [{"id": "C01"}, {"id": "C02"}]
        assert store.list(c, "attempt") == []
        assert store.list(c, "learner") == []
    content = lab_client.get("/api/labs/course").json()
    assert content["activities"] == []
    assert content["activity_summary"]["mastery_awarded"] is False


def test_invalid_module_source_scope_and_prerequisites_are_atomic(lab_client, presentation, store):
    with store.tx() as c:
        store.put(c, "source", "foreign", {"course_id": "other", "role": "instruction", "reconstruction_status": "confirmed"})
    for field, value, status in [("id", "missing", 400), ("source_ids", ["foreign"], 400),
                                  ("prerequisites", ["C01"], 422)]:
        invalid = deepcopy(presentation)
        invalid["lessons"][0][field] = value
        assert lab_client.put("/api/labs/course", json=invalid).status_code == status
    with store.tx() as c:
        assert store.get(c, "lab", "course", False) is None
    assert lab_client.get("/api/labs/missing").status_code == 404


def test_clock_cap_pause_idempotency_and_no_mastery(lab_client, presentation, lab_clock, store):
    activity = publish_and_start(lab_client, presentation)
    ident = activity["id"]
    replay = lab_client.post("/api/labs/course/activities", json={"module": "C01", "idempotency_key": "visit-1"})
    assert replay.json()["id"] == ident
    assert lab_client.post("/api/labs/course/activities", json={"module": "C02", "idempotency_key": "visit-1"}).status_code == 409
    lab_clock(10)
    assert event(lab_client, ident, "reading").json()["active_seconds"] == 10
    lab_clock(3600)
    response = event(lab_client, ident, "heartbeat").json()
    assert response["active_seconds"] == 55
    assert response["elapsed_seconds"] == 3610
    # Retry contributes no time and no duplicate exposure.
    assert event(lab_client, ident, "reading").json()["reading_count"] == 1
    assert event(lab_client, ident, "help", key="reading").status_code == 409
    event(lab_client, ident, "pause")
    lab_clock(100)
    assert event(lab_client, ident, "heartbeat", key="paused-heartbeat").json()["active_seconds"] == 55
    event(lab_client, ident, "resume")
    lab_clock(15)
    finished = event(lab_client, ident, "finish", reflection="I changed the switch mechanism.").json()
    assert finished["active_seconds"] == 70
    assert finished["status"] == "finished" and finished["running"] is False
    lab_clock(600)
    assert lab_client.get(f"/api/lab-activities/{ident}").json()["elapsed_seconds"] == 3725
    assert event(lab_client, ident, "resume", key="too-late").status_code == 409
    with store.tx() as c:
        assert not store.list(c, "learner") and not store.list(c, "attempt")
        evidence = store.evidence(c, ident)
        assert all(e["payload"]["assessed"] is False for e in evidence)
        assert sum(e["event_type"] == "lab.activity.reading" for e in evidence) == 1


def test_experiment_evidence_and_one_running_lab_timer(lab_client, presentation, lab_clock, store):
    first = publish_and_start(lab_client, presentation)
    lab_clock(12)
    parameters = {"switch": 1, "toy_observed_score": 70, "assumption": "fixed motivation"}
    result = event(lab_client, first["id"], "experiment", parameters=parameters, reflection="This is a toy model.").json()
    assert result["experiment_count"] == 1
    second = lab_client.post("/api/labs/course/activities", json={"module": "C01", "idempotency_key": "visit-2"}).json()
    lab_clock(100)
    assert lab_client.get(f"/api/lab-activities/{first['id']}").json()["running"] is False
    assert event(lab_client, second["id"], "heartbeat").json()["active_seconds"] == 45
    with store.tx() as c:
        experiments = [e for e in store.evidence(c, first["id"]) if e["event_type"] == "lab.activity.experiment"]
        assert experiments[0]["payload"]["parameters"] == parameters
        assert experiments[0]["payload"]["source_ids"] == ["notes-v1"]


def test_link_marks_preparation_before_real_attempt_and_exposes_safe_outcome(lab_client, presentation, lab_clock, store):
    activity = publish_and_start(lab_client, presentation)
    ident = activity["id"]
    event(lab_client, ident, "reading")
    record = session(store, lab_clock(10))
    url = f"/api/lab-activities/{ident}/link-session"
    linked = lab_client.post(url, json={"session_id": record["id"]})
    assert linked.status_code == 200, linked.text
    assert linked.json()["status"] == "finished"
    with store.tx() as c:
        assert store.get(c, "session", record["id"])["assistance"]["item"] == ["lab_materials"]
        assert not store.list(c, "attempt") and not store.list(c, "learner")
    submit_answer(store, record["id"], {"item_id": "item", "answer": "B", "confidence": .7, "idempotency_key": "real-answer"})
    # An idempotent link retry remains safe even after answers arrive.
    assert lab_client.post(url, json={"session_id": record["id"]}).status_code == 200
    outcome = lab_client.get(f"/api/lab-activities/{ident}").json()["practice_outcome"]
    assert outcome["score"] == outcome["max_score"] == 5
    assert outcome["assisted_attempt_count"] == 1
    assert outcome["attempts"][0]["assistance"] == ["lab_materials"]
    assert "answer" not in outcome["attempts"][0]
    assert "A private answer explanation" not in str(lab_client.get("/api/labs/course").json())
    assert lab_client.get("/api/labs/course").json()["activity_summary"]["practice_linked_visits"] == 1


@pytest.mark.parametrize("override", [{"course_id": "other"}, {"module": "C02"}, {"mode": "simulation"}, {"status": "finished"}])
def test_link_rejects_wrong_scope_without_finishing_or_mutating_session(lab_client, presentation, lab_clock, store, override):
    activity = publish_and_start(lab_client, presentation)
    record = session(store, lab_clock(10), **override)
    response = lab_client.post(f"/api/lab-activities/{activity['id']}/link-session", json={"session_id": record["id"]})
    assert response.status_code == 400
    assert lab_client.get(f"/api/lab-activities/{activity['id']}").json()["status"] == "active"
    with store.tx() as c:
        assert store.get(c, "session", record["id"])["assistance"] == {}


def test_finish_with_already_answered_session_rolls_back(lab_client, presentation, lab_clock, store):
    activity = publish_and_start(lab_client, presentation)
    record = session(store, lab_clock(10))
    with store.tx() as c:
        store.put(c, "attempt", "existing", {"session_id": record["id"]})
    response = event(lab_client, activity["id"], "finish", session_id=record["id"])
    assert response.status_code == 409
    current = lab_client.get(f"/api/lab-activities/{activity['id']}").json()
    assert current["status"] == "active" and current["session_id"] is None
    assert current["active_seconds"] == 0


def test_opening_only_does_not_invent_assistance_and_versions_stay_pinned(lab_client, presentation, lab_clock, store):
    activity = publish_and_start(lab_client, presentation)
    revised = deepcopy(presentation)
    revised.update(expected_revision=1, title="Updated lab")
    lab_client.put("/api/labs/course", json=revised)
    record = session(store, lab_clock(5))
    linked = lab_client.post(f"/api/lab-activities/{activity['id']}/link-session", json={"session_id": record["id"]}).json()
    assert linked["lab_revision"] == 1 and linked["lab_version_id"] == "lab:course:1"
    with store.tx() as c:
        assert store.get(c, "session", record["id"])["assistance"] == {}
    invalid = {"action": "heartbeat", "idempotency_key": "not-client-time", "active_seconds": 100000}
    assert lab_client.post(f"/api/lab-activities/{activity['id']}/events", json=invalid).status_code == 422
