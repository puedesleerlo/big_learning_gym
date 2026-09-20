import copy

import httpx
import pytest

from gym import authoring
from gym.agent_client import main

PROVENANCE = {"author": "Test author", "method": "agent", "rationale": "Grounded instructional example"}


@pytest.fixture
def authored(client):
    course = client.put(
        "/api/authoring/courses/course",
        json={
            "title": "Causal reasoning",
            "description": "Learn the foundations",
            "expected_revision": 1,
            "modules": [{"id": "basics", "title": "Foundations"}],
            "provenance": PROVENANCE,
        },
    )
    assert course.status_code == 200, course.text
    source = client.post(
        "/api/sources",
        data={"course_id": "course"},
        files={
            "file": (
                "foundation.md",
                b"# Interventions\nRandom assignment breaks treatment confounding in expectation.",
            )
        },
    ).json()
    result = client.post(
        f"/api/sources/{source['id']}/confirm", json={"expected_revision": source["revision"]}
    )
    assert result.status_code == 200
    fragment = client.get(f"/api/sources/{source['id']}/fragments").json()[0]
    return {"source": source, "fragment": fragment, "course": course.json()}


def question(authored):
    return {
        "course_id": "course",
        "module": "basics",
        "type": "mcq",
        "stem": "What does randomized treatment assignment change?",
        "key": "A",
        "options": [
            {
                "label": "A",
                "text": "Assignment mechanism",
                "why": "Randomization changes treatment assignment.",
            },
            {
                "label": "B",
                "text": "Every person's outcome",
                "why": "Not every individual necessarily benefits.",
            },
        ],
        "explanation": "Randomization changes assignment, not every individual treatment effect.",
        "hint": "Focus on the assignment mechanism.",
        "plain": "What changes when treatment is randomized?",
        "capabilities": ["randomization"],
        "cognitive_operation": "application",
        "source_fragment_ids": [authored["fragment"]["id"]],
        "provenance": PROVENANCE,
    }


def guide(authored):
    return {
        "expected_revision": 0,
        "course_id": "course",
        "code": "basics",
        "subtitle": "Interventions",
        "blocks": [
            {
                "id": "one",
                "h": "Assignment",
                "html": '<p onclick="bad()">Read <a href="javascript:bad()">this</a></p>',
            }
        ],
        "source_fragment_ids": [authored["fragment"]["id"]],
        "provenance": PROVENANCE,
    }


def term(authored):
    return {
        "expected_revision": 0,
        "course_id": "course",
        "module": "basics",
        "term": "Randomization",
        "def": "Assigning treatment through a random mechanism.",
        "distinguish": "Random sampling",
        "why": "Balances baseline causes in expectation.",
        "source_fragment_ids": [authored["fragment"]["id"]],
        "provenance": PROVENANCE,
    }


def test_course_graph_and_stale_revision(client, authored):
    payload = {k: authored["course"][k] for k in ["title", "description", "modules", "provenance"]}
    payload["expected_revision"] = 1
    assert client.put("/api/authoring/courses/course", json=payload).status_code == 409
    payload["expected_revision"] = authored["course"]["revision"]
    payload["modules"] = [{"id": "basics", "title": "Basics", "prerequisites": ["basics"]}]
    assert client.put("/api/authoring/courses/course", json=payload).status_code == 422
    assert client.get("/api/authoring/courses/course").json()["modules"][0]["title"] == "Foundations"


def test_material_writes_sanitize_and_validate_references(client, authored, store):
    response = client.put("/api/authoring/guides/intro", json=guide(authored))
    assert response.status_code == 200, response.text
    assert "onclick" not in response.json()["blocks"][0]["html"]
    assert "javascript:" not in response.json()["blocks"][0]["html"]
    updated = {**guide(authored), "expected_revision": 1, "subtitle": "Updated lesson"}
    assert client.put("/api/authoring/guides/intro", json=updated).status_code == 200
    assert client.put("/api/authoring/guides/intro", json=updated).status_code == 409
    assert client.put("/api/authoring/terms/random", json=term(authored)).status_code == 200
    library = client.get("/api/library/course").json()
    assert library["terms"][0]["def"].startswith("Assigning")
    assert library["guides"][0]["subtitle"] == "Updated lesson"
    bad = {**question(authored), "source_fragment_ids": ["missing"]}
    assert client.post("/api/authoring/items", json=bad).status_code == 400
    payload = {k: authored["course"][k] for k in ["title", "description", "provenance"]}
    payload.update(expected_revision=2, modules=[])
    assert client.put("/api/authoring/courses/course", json=payload).status_code == 400
    with store.tx() as c:
        assert store.list(c, "attempt") == []
        assert store.list(c, "learner") == []
        assert any(e["event_type"] == "authoring.guide.saved" for e in store.evidence(c))


def test_unconfirmed_and_cross_course_source_and_term_rejected(client, authored, store):
    source = client.post(
        "/api/sources",
        data={"course_id": "course"},
        files={"file": ("other.md", b"Unreviewed instructional text.")},
    ).json()
    fragment = client.get(f"/api/sources/{source['id']}/fragments").json()[0]
    data = {**question(authored), "source_fragment_ids": [fragment["id"]]}
    assert client.post("/api/authoring/items", json=data).status_code == 400
    with store.tx() as c:
        store.put(c, "fragment", "foreign", {**authored["fragment"], "course_id": "other"})
        store.put(c, "term", "foreign-term", {"course_id": "other"})
    data["source_fragment_ids"] = ["foreign"]
    assert client.post("/api/authoring/items", json=data).status_code == 400
    data = {**question(authored), "term_ids": ["foreign-term"]}
    assert client.post("/api/authoring/items", json=data).status_code == 400
    assert client.post("/api/authoring/items", json={**question(authored), "score": 5}).status_code == 422


def test_item_revision_preserves_active_session_and_historical_evidence(client, authored, store):
    old = client.put("/api/authoring/items/original", json=question(authored)).json()
    session = client.post(
        "/api/sessions", json={"course_id": "course", "module": "basics", "count": 1}
    ).json()
    revised = client.put(
        "/api/authoring/items/original",
        json={
            **question(authored),
            "expected_revision": old["revision"],
            "key": "B",
        },
    )
    assert revised.status_code == 200, revised.text
    new = revised.json()
    assert new["id"] != old["id"] and new["family_id"] == old["family_id"]
    answer = client.post(
        f"/api/sessions/{session['id']}/answers",
        json={
            "item_id": old["id"],
            "answer": "A",
            "idempotency_key": "old-answer",
        },
    )
    assert answer.status_code == 200, answer.text
    with store.tx() as c:
        historical = store.list(c, "attempt")[0]
        assert historical["score"] == old["points"]
        assert historical["item_id"] == old["id"]
        assert store.get(c, "item", old["id"])["status"] == "retired"
    next_session = client.post(
        "/api/sessions", json={"course_id": "course", "module": "basics", "count": 1}
    ).json()
    assert next_session["items"][0]["id"] == new["id"]
    retired = client.post(
        f"/api/authoring/items/{new['id']}/retire",
        json={"expected_revision": new["revision"], "provenance": PROVENANCE},
    )
    assert retired.status_code == 200
    assert client.post("/api/sessions", json={"course_id": "course", "count": 1}).status_code == 400


def test_atomic_import_idempotency_and_glossary_assistance(client, authored, store):
    bundle = {
        "idempotency_key": "bundle-first",
        "course_id": "course",
        "terms": [{"id": "random", **term(authored)}],
        "guides": [{"id": "intro", **guide(authored)}],
        "items": [{"id": "first", **question(authored), "term_ids": ["random"]}],
    }
    first = client.post("/api/authoring/import", json=bundle)
    assert first.status_code == 200, first.text
    repeated = client.post("/api/authoring/import", json=bundle).json()
    assert repeated["already_imported"] is True
    assert repeated["items"] == first.json()["items"]
    changed = copy.deepcopy(bundle)
    changed["guides"][0]["subtitle"] = "Changed"
    assert client.post("/api/authoring/import", json=changed).status_code == 409
    session = client.post("/api/sessions", json={"course_id": "course", "count": 1}).json()
    aid = client.post(f"/api/sessions/{session['id']}/aid", json={"item_id": "first", "kind": "terms"})
    assert aid.json()["content"][0]["id"] == "random"
    bad = {
        "idempotency_key": "bundle-rollback",
        "course_id": "course",
        "guides": [{"id": "rollback-guide", **guide(authored)}],
        "items": [{"id": "bad", **question(authored), "source_fragment_ids": ["missing"]}],
    }
    assert client.post("/api/authoring/import", json=bad).status_code == 400
    assert client.get("/api/authoring/guides/rollback-guide").status_code == 404
    with store.tx() as c:
        assert len(store.list(c, "authoring_import")) == 1


def test_pinned_rubric_version_remains_stable(client, authored, store):
    criteria = [{"name": "Reasoning", "weight": 1, "anchors": ["Missing mechanism", "Explains mechanism"]}]
    rubric = client.post(
        "/api/rubrics", json={"title": "Causal mechanism", "criteria": criteria, "course_id": "course"}
    ).json()
    item = question(authored)
    item.update(type="open", options=[], key="", rubric=criteria, rubric_version_id=rubric["version_id"])
    original = client.post("/api/authoring/items", json=item).json()
    new_criteria = [
        {"name": "Mechanism and limits", "weight": 1, "anchors": ["Missing limitations", "Explains limits"]}
    ]
    revised = client.put(
        f"/api/rubrics/{rubric['id']}",
        json={
            "expected_revision": rubric["revision"],
            "title": "Improved mechanism",
            "criteria": new_criteria,
            "course_id": "course",
        },
    ).json()
    assert revised["version_id"] != original["rubric_version_id"]
    bad = {**item, "rubric_version_id": revised["version_id"]}
    assert client.post("/api/authoring/items", json=bad).status_code == 400
    with store.tx() as c:
        assert store.get(c, "item", original["id"])["rubric"] == criteria


def test_discovery_auth_and_solution_redaction(client, authored, store, monkeypatch):
    item = client.put("/api/authoring/items/first", json=question(authored)).json()
    manifest = client.get("/api/agent/capabilities").json()
    assert any(o["path"] == "/api/assignments/{ident}/submit" for o in manifest["operations"])
    assert "ItemWrite" in client.get("/api/agent/schema").json()["components"]["schemas"]
    public = client.get("/api/authoring/courses/course/materials").json()["items"][0]
    assert "key" not in public and "why" not in public["options"][0]
    with store.tx() as c:
        store.put(
            c,
            "form",
            "testform",
            {"course_id": "course", "label": "test", "item_ids": [item["id"]], "minutes": 20},
        )
    session = client.post(
        "/api/sessions", json={"course_id": "course", "mode": "simulation", "form": "testform"}
    )
    assert session.status_code == 200
    assert client.get("/api/authoring/courses/course/materials?include_solutions=true").status_code == 409
    monkeypatch.setenv("GYM_ACCESS_TOKEN", "test-access-token")
    assert client.get("/api/agent/capabilities").status_code == 401
    assert (
        client.get(
            "/api/agent/capabilities", headers={"Authorization": "Bearer test-access-token"}
        ).status_code
        == 200
    )


def test_client_multipart_and_credential_redaction(tmp_path, monkeypatch, capsys):
    original_client = httpx.Client
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs)
    )
    monkeypatch.setenv("GYM_ACCESS_TOKEN", "secret-test-token")
    source = tmp_path / "file.md"
    source.write_text("Source text")
    assert main(["POST", "/api/sources", "--field", "course_id=course", "--file", "file=" + str(source)]) == 0
    assert captured[0].url.port == 8787
    assert captured[0].headers["authorization"] == "Bearer secret-test-token"
    assert b"Source text" in captured[0].content
    assert "secret-test-token" not in capsys.readouterr().out
    assert main(["GET", "https://foreign.invalid/api/overview"]) == 1


def test_direct_contract_rejects_imported_performance():
    with pytest.raises(ValueError):
        authoring.MaterialImport.model_validate(
            {"course_id": "course", "idempotency_key": "bad-import", "attempts": []}
        )
