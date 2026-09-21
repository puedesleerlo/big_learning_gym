import json
from pathlib import Path

from scripts.install_causality import install


def test_causality_import_is_repeatable_and_uses_existing_workflows(client, store):
    bundle = json.loads((Path(__file__).parents[1] / "content/causality/lab.json").read_text())
    first = install(client, bundle)
    assert first["practice_items"] == 36
    assert first["guides"] == 13
    assert first["assignments"] == 4
    second = install(client, bundle)
    assert second["already_imported"] is True
    assert second["rubric_id"] == first["rubric_id"]
    ident = first["course_id"]
    library = client.get(f"/api/library/{ident}").json()
    assert len(library["guides"]) == 13
    assert len(library["terms"]) == first["terms"]
    assert all(len(g["blocks"]) >= 2 for g in library["guides"])
    course = client.get(f"/api/authoring/courses/{ident}").json()
    assert len(course["modules"]) == 12
    sources = client.get("/api/sources", params={"course_id": ident}).json()
    assert len(sources) == 13
    assert all(s["reconstruction_status"] == "confirmed" for s in sources)
    coursework = client.get("/api/coursework").json()
    own_tasks = [a for a in coursework["assignment"] if a["course_id"] == ident]
    assert len(own_tasks) == 4
    assert all(a["purpose"] == "self_study" and not a.get("task_id") for a in own_tasks)
    assert all(a["rubric_id"] == first["rubric_id"] for a in own_tasks)
    with store.tx() as c:
        assert store.get(c, "course", "course")["title"] == "Test gym"
        for kind in ["attempt", "session", "learner", "submission", "official_grade"]:
            assert store.list(c, kind) == []

    response = client.post("/api/sessions", json={"course_id": ident, "module": "C01", "count": 3})
    assert response.status_code == 200
    session = response.json()
    assert len(session["items"]) == 3
    assert all("key" not in item for item in session["items"])
    with store.tx() as c:
        question = next(
            i for i in store.list(c, "item") if i["id"] in session["item_ids"] and i["type"] == "mcq"
        )
    checked = client.post(
        f"/api/sessions/{session['id']}/answers",
        json={
            "item_id": question["id"],
            "answer": question["key"],
            "idempotency_key": "test-causality-answer",
        },
    )
    assert checked.status_code == 200
    assert checked.json()["answers"][question["id"]]["score"] == question["points"]
