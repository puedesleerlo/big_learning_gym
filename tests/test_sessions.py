from datetime import datetime, timedelta, timezone

from gym import sessions


def start(store, mode="practice", form=None):
    return sessions.create_session(
        store, {"course_id": "course", "mode": mode, "count": 1, "module": "all", "form": form}
    )


def test_answer_keys_are_sealed_and_assistance_is_recorded(store, client, item):
    s = start(store)
    q = s["items"][0]
    assert "key" not in q and "hint" not in q
    assert all(set(o) == {"label", "text"} for o in q["options"])
    sessions.assistance(store, s["id"], "item", "hint")
    response = client.post(
        f"/api/sessions/{s['id']}/answers",
        json={"item_id": "item", "answer": "B", "confidence": 0.75, "idempotency_key": "answer-1"},
    )
    assert response.status_code == 200
    assert response.json()["answers"]["item"]["score"] == 5
    with store.tx() as c:
        state = store.list(c, "learner")[0]
        assert state["assisted_attempts"] == 1 and state["independent_attempts"] == 0
        assert store.list(c, "attempt")[0]["confidence"] == 0.75


def test_duplicate_answer_has_one_effect(store, client, item):
    s = start(store)
    payload = {"item_id": "item", "answer": "B", "idempotency_key": "retry-key"}
    for _ in range(2):
        assert client.post(f"/api/sessions/{s['id']}/answers", json=payload).status_code == 200
    with store.tx() as c:
        assert len(store.list(c, "attempt")) == 1
        assert store.list(c, "learner")[0]["independent_attempts"] == 1


def test_simulation_delays_feedback_and_learner_updates(store, client, item):
    with store.tx() as c:
        store.put(c, "item", "item", {**item, "pool": "simulation"})
        store.put(
            c, "form", "form", {"course_id": "course", "label": "A", "item_ids": ["item"], "minutes": 10}
        )
    s = start(store, "simulation", "form")
    assert (
        client.post(f"/api/sessions/{s['id']}/aid", json={"item_id": "item", "kind": "hint"}).status_code
        == 400
    )
    result = client.post(
        f"/api/sessions/{s['id']}/answers",
        json={"item_id": "item", "answer": "B", "idempotency_key": "exam-key"},
    ).json()
    assert "score" not in result["answers"]["item"]
    assert client.get("/api/progress").json()["learner_states"] == []
    assert client.get("/api/progress").json()["attempts"] == []
    assert not any(e["event_type"] == "attempt.submitted" for e in client.get("/api/evidence").json())
    result = client.post(f"/api/sessions/{s['id']}/finish", json={}).json()
    assert result["score"] == 5
    assert client.get("/api/progress").json()["learner_states"][0]["unseen_checks"] == 1


def test_timer_caps_missing_heartbeats_and_marks_unfinished(store, item):
    s = start(store)
    with store.tx() as c:
        record = store.get(c, "session", s["id"])
        store.put(
            c,
            "session",
            s["id"],
            {**record, "last_tick": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()},
        )
    result = sessions.finish(store, s["id"], "Interrupted")
    assert result["active_seconds"] <= 45
    assert result["completion"] == "unfinished"


def test_matching_partial_credit():
    item = {
        "type": "matching",
        "points": 10,
        "prompts": [{"id": "p1", "key": "t1"}, {"id": "p2", "key": "t2"}],
        "terms": [{"id": "t1"}, {"id": "t2"}],
    }
    assert sessions.deterministic_score(item, {"p1": "t1", "p2": "t1"}) == 5


def test_quarantine_flags_attempts_and_removes_their_estimate(store, client, item):
    s = start(store)
    sessions.submit_answer(
        store, s["id"], {"item_id": "item", "answer": "B", "confidence": None, "idempotency_key": "answer-1"}
    )
    assert (
        client.post("/api/items/item/report", json={"reason": "Answer key is incorrect"}).status_code == 200
    )
    data = client.get("/api/progress").json()
    assert data["attempts"][0]["invalidated"]
    assert data["learner_states"][0]["dimensions"] == {}


def test_same_capability_name_is_scoped_to_each_course(store, item):
    with store.tx() as c:
        store.put(c, "course", "other-course", {"title": "Another discipline"})
        store.put(c, "item", "other-item", {**item, "course_id": "other-course", "family_id": "other-family"})
    for course_id, item_id in [("course", "item"), ("other-course", "other-item")]:
        s = sessions.create_session(
            store, {"course_id": course_id, "mode": "practice", "count": 1, "module": "all"}
        )
        sessions.submit_answer(
            store,
            s["id"],
            {"item_id": item_id, "answer": "B", "confidence": None, "idempotency_key": course_id},
        )
    with store.tx() as c:
        states = store.list(c, "learner")
        assert {s["course_id"] for s in states} == {"course", "other-course"}
        assert all(s["independent_attempts"] == 1 for s in states)
