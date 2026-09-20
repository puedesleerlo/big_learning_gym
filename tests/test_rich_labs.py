"""Rich blocks preserve source, model, revision and learner-evidence boundaries."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from gym.api import create_app
from gym.lab_blocks import ActivityBlock, activity_types
from gym.llm import ModelError


class Tutor:
    def __init__(self):
        self.calls = []
        self.handler = None

    def complete(self, role, system, prompt):
        context = json.loads(prompt)
        self.calls.append((role, system, context))
        if self.handler:
            return self.handler(context)
        return {"reply": "Which assumption explains the extra cycle?", "citations": ["fragment-1"]}, {
            "role": role, "provider": "test", "model": "mock-tutor", "call_id": "test-call",
        }


def test_copyable_rich_examples_match_the_live_contract():
    examples = json.loads((Path(__file__).parents[1] / "content/examples/rich-lab-blocks.json").read_text())
    for block in examples["activities"]:
        TypeAdapter(ActivityBlock).validate_python(block)


@pytest.fixture
def rich(store, monkeypatch):
    monkeypatch.setenv("GYM_ACCESS_TOKEN", "")
    with store.tx() as c:
        store.put(c, "course", "course", {"title": "Waves", "modules": [{"id": "waves"}]})
        store.put(c, "source", "source-1", {"course_id": "course", "role": "instruction", "reconstruction_status": "confirmed"})
        store.put(c, "fragment", "fragment-1", {"source_version_id": "source-1", "anchor": "page:1", "text": "Frequency is cycles per unit time."})
        store.put(c, "source", "foreign", {"course_id": "other", "role": "instruction", "reconstruction_status": "confirmed"})
        store.put(c, "fragment", "foreign-fragment", {"source_version_id": "foreign", "anchor": "page:1", "text": "FOREIGN PRIVATE MATERIAL"})
    templates = {x["type"]: x["template"] for x in activity_types()["types"]}
    body = {
        "course_id": "course", "expected_revision": 0, "title": "Explore waves", "description": "A rich lesson",
        "provenance": {"author": "Test", "method": "import", "rationale": "Synthetic test content"},
        "lessons": [{"id": "wave-lesson", "module": "waves", "title": "Waves", "minutes": 15,
                     "source_ids": ["source-1"], "activities": [templates[t] for t in ("media", "visualization", "discussion")]}],
    }
    tutor = Tutor()
    with TestClient(create_app(store, router=tutor, embedded_worker=False)) as client:
        yield client, tutor, body


def start(rich):
    client, _, body = rich
    response = client.put("/api/labs/waves", json=body)
    assert response.status_code == 200, response.text
    response = client.post("/api/labs/waves/activities", json={"module": "waves", "lesson_id": "wave-lesson", "idempotency_key": "visit"})
    assert response.status_code == 200, response.text
    return response.json()


def turn(client, visit, **kwargs):
    return client.post(f"/api/lab-activities/{visit['id']}/discussion", json={
        "activity_id": "discussion-1", "message": "Explain frequency", "expected_turn": 0, "idempotency_key": "turn-1", **kwargs,
    })


def test_rich_templates_discover_preview_publish_and_pin(rich, store):
    client, tutor, body = rich
    with store.tx() as c:
        before = store.revision(c)
    for mode in ("validate", "preview"):
        result = client.post(f"/api/labs/waves/{mode}", json=body)
        assert result.status_code == 200, result.text
    with store.tx() as c:
        assert store.revision(c) == before
        assert not store.list(c, "lab_activity")
    registry = client.get("/api/lab-activity-types").json()
    assert registry["version"] == "2.0"
    assert {"media", "visualization", "discussion"} <= {b["type"] for b in registry["types"]}
    visit = start(rich)
    revised = deepcopy(body)
    revised["expected_revision"] = 1
    revised["lessons"][0]["activities"][1]["javascript"] = "throw new Error('new version');"
    revised["lessons"][0]["activities"][2]["prompt"] = "Changed prompt"
    assert client.put("/api/labs/waves", json=revised).status_code == 200
    read = client.get(f"/api/lab-activities/{visit['id']}").json()
    assert read["lesson_snapshot"]["activities"][1]["javascript"] == body["lessons"][0]["activities"][1]["javascript"]
    assert not tutor.calls
    result = turn(client, visit)
    assert result.status_code == 200, result.text
    assert tutor.calls[0][2]["prompt"] == body["lessons"][0]["activities"][2]["prompt"]


@pytest.mark.parametrize("index,fields", [
    (0, {"url": "javascript:alert(1)"}), (0, {"url": "http://example.org/video.mp4"}),
    (0, {"url": "https://user:secret@example.org/v.mp4"}), (0, {"start_seconds": 10, "end_seconds": 5}),
    (0, {"provider": "youtube", "url": "https://evil.test/embed/abcdefghijk"}),
    (0, {"provider": "youtube", "url": "https://www.youtube-nocookie.com/embed/abcdefghijk?autoplay=1"}),
    (0, {"provider": "vimeo", "url": "https://player.vimeo.com/video/123", "end_seconds": 20}),
    (1, {"data": {"large": "x" * 100001}}), (1, {"height": 15000}),
    (1, {"permissions": ["allow-same-origin"]}), (2, {"max_turns": 1000}),
    (2, {"provider": "new-provider"}), (2, {"grading": True}),
])
def test_invalid_rich_config_is_rejected_atomically(rich, store, index, fields):
    client, _, body = rich
    body["lessons"][0]["activities"][index].update(fields)
    assert client.post("/api/labs/waves/validate", json=body).status_code == 422
    assert client.put("/api/labs/waves", json=body).status_code == 422
    with store.tx() as c:
        assert not store.list(c, "lab")


def test_media_and_visualization_record_exposure_not_output_or_grades(rich, store):
    client, _, _ = rich
    visit = start(rich)
    url = f"/api/lab-activities/{visit['id']}/events"
    media = {"action": "media", "idempotency_key": "play", "parameters": {"activity_id": "media-1"}}
    assert client.post(url, json=media).json()["reading_count"] == 1
    assert client.post(url, json=media).json()["reading_count"] == 1
    media["parameters"]["watched_seconds"] = 10000
    media["idempotency_key"] = "fake-watch"
    assert client.post(url, json=media).status_code == 400
    viz = {"action": "visualization", "idempotency_key": "plot", "parameters": {"activity_id": "visualization-1", "inputs": {"frequency": 3}}}
    result = client.post(url, json=viz)
    assert result.status_code == 200, result.text
    assert result.json()["visualization_inputs"]["visualization-1"] == {"frequency": 3}
    assert result.json()["experiment_count"] == 1
    for inputs in ({"frequency": 500}, {"frequency": True}, {"unknown": 2}):
        viz["parameters"]["inputs"] = inputs
        viz["idempotency_key"] = str(inputs)
        assert client.post(url, json=viz).status_code == 400
    with store.tx() as c:
        assert not store.list(c, "attempt") and not store.list(c, "learner")
        assert all(not e["payload"]["assessed"] for e in store.evidence(c, visit["id"]))


def test_tutor_grounding_idempotency_assistance_and_limits(rich, store):
    client, tutor, body = rich
    body["lessons"][0]["activities"][2]["max_turns"] = 1
    visit = start(rich)
    result = turn(client, visit)
    assert result.status_code == 200, result.text
    thread = result.json()["discussions"]["discussion-1"]
    assert thread["turns"][0]["provenance"]["prompt_version"] == "lab-discussion-v1"
    assert result.json()["help_count"] == 1 and result.json()["active_seconds"] == 0
    assert turn(client, visit).status_code == 200
    assert len(tutor.calls) == 1
    assert turn(client, visit, message="Different content").status_code == 409
    assert turn(client, visit, idempotency_key="new", expected_turn=1).status_code == 409
    role, system, context = tutor.calls[0]
    assert role == "tutor" and "untrusted reference" in system
    assert "FOREIGN PRIVATE" not in json.dumps(context)
    assert "javascript" not in json.dumps(context)
    assert context["sources"][0]["id"] == "fragment-1"
    with store.tx() as c:
        assert not store.list(c, "attempt") and not store.list(c, "learner")
        events = store.evidence(c, visit["id"])
        assert sum(e["event_type"] == "lab.activity.discussion" for e in events) == 1
        assert all(not e["payload"]["assessed"] for e in events)


@pytest.mark.parametrize("condition", ["paused", "simulation", "foreign_source", "wrong_block", "no_fragments"])
def test_tutor_scope_gates_run_before_provider(rich, store, condition):
    client, tutor, _ = rich
    visit = start(rich)
    kwargs = {}
    with store.tx() as c:
        if condition == "paused":
            activity = store.get(c, "lab_activity", visit["id"])
            store.put(c, "lab_activity", visit["id"], {**activity, "running": False})
        elif condition == "simulation":
            store.put(c, "session", "sealed", {"course_id": "course", "mode": "simulation", "status": "active", "snapshots": {"key": "SEALED ANSWER"}})
        elif condition == "foreign_source":
            source = store.get(c, "source", "source-1")
            store.put(c, "source", "source-1", {**source, "course_id": "other"})
        elif condition == "no_fragments":
            fragment = store.get(c, "fragment", "fragment-1")
            store.put(c, "fragment", "fragment-1", {**fragment, "source_version_id": "missing"})
        else:
            kwargs["activity_id"] = "media-1"
    assert turn(client, visit, **kwargs).status_code in {400, 409}
    assert not tutor.calls


@pytest.mark.parametrize("failure", ["provider", "citations", "grade"])
def test_tutor_failure_releases_pending_without_evidence(rich, store, failure):
    client, tutor, _ = rich
    visit = start(rich)
    def fail(context):
        if failure == "provider":
            raise ModelError("Model is not configured")
        if failure == "grade":
            return {"reply": "Well done", "citations": [], "grade": 100}, {}
        return {"reply": "An unsupported assertion", "citations": ["foreign-fragment"]}, {}
    tutor.handler = fail
    assert turn(client, visit).status_code in {502, 503}
    assert turn(client, visit).status_code == 409
    current = client.get(f"/api/lab-activities/{visit['id']}").json()
    assert current["discussions"]["discussion-1"] == {"turns": [], "pending": False}
    assert current["help_count"] == 0
    tutor.handler = None
    assert turn(client, visit, idempotency_key="retry").status_code == 200
    assert len(tutor.calls) == 2


def test_concurrent_request_and_pause_during_call_do_not_publish_reply(rich):
    client, tutor, _ = rich
    visit = start(rich)
    def during(context):
        assert turn(client, visit, idempotency_key="concurrent").status_code == 409
        assert client.post(f"/api/lab-activities/{visit['id']}/events", json={"action": "pause", "idempotency_key": "pause"}).status_code == 200
        return {"reply": "Do not release after pause", "citations": []}, {}
    tutor.handler = during
    assert turn(client, visit).status_code == 409
    result = client.get(f"/api/lab-activities/{visit['id']}").json()
    assert result["help_count"] == 0 and not result["discussions"]["discussion-1"]["turns"]


def test_tutor_route_preserves_token_and_origin_guard(rich, monkeypatch):
    client, tutor, _ = rich
    visit = start(rich)
    monkeypatch.setenv("GYM_ACCESS_TOKEN", "fixture-token")
    assert turn(client, visit).status_code == 401
    result = client.post(f"/api/lab-activities/{visit['id']}/discussion", headers={"Authorization": "Bearer fixture-token", "Origin": "https://foreign.test"}, json={})
    assert result.status_code == 403
    assert not tutor.calls
