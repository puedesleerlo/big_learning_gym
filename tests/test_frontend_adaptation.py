import json

import pytest
from fastapi.testclient import TestClient

from gym.api import create_app
from gym.frontend_fixture import FixtureRouter, seed
from gym.frontend_kit import export_kit, install_frontend
from gym.frontends import check_frontend
from gym.store import Store
from gym.workspaces import Workspace, load_workspace


def package(path, ident="company"):
    path.mkdir()
    (path / "experience.json").write_text(
        json.dumps(
            {
                "id": ident,
                "version": "0.1.0",
                "contract_version": "1.0",
                "capabilities": ["labs", "practice"],
                "entry": "dist/index.html",
            }
        )
    )
    (path / "dist/assets").mkdir(parents=True)
    (path / "dist/index.html").write_text("<h1>Company frontend</h1>")
    (path / "dist/assets/app.js").write_text("export const company = true;")
    (path / "private.txt").write_text("DO NOT SERVE")
    return path


def test_workspace_paths_database_and_upload_roots_are_independent(tmp_path):
    stores = []
    try:
        for ident in ("alpha", "beta"):
            config = tmp_path / f"{ident}.json"
            config.write_text(
                json.dumps({"id": ident, "port": 8801 if ident == "alpha" else 8802, "data_dir": ident})
            )
            workspace = load_workspace(config)
            assert workspace.data_dir == tmp_path / ident
            assert workspace.database_url == "sqlite:///" + str(tmp_path / ident / "gym.db")
            store = workspace.store()
            stores.append(store)
            with store.tx() as c:
                assert not store.list(c, "course")
                store.put(c, "course", "same-id", {"title": ident})
                store.enqueue(c, "daily_check", {"workspace": ident}, key="same-job")
            (store.data_dir / "original.txt").write_text(ident)
            with TestClient(create_app(store, FixtureRouter(), False, workspace)) as client:
                assert client.get("/app-config.json").json()["workspace_id"] == ident
                assert client.get("/api/overview").json()["courses"][0]["title"] == ident
        for ident, store in zip(("alpha", "beta"), stores):
            assert (store.data_dir / "original.txt").read_text() == ident
    finally:
        for store in stores:
            store.engine.dispose()


def test_default_launch_preserves_existing_configuration(monkeypatch):
    monkeypatch.delenv("GYM_WORKSPACE", raising=False)
    workspace = load_workspace()
    assert workspace == Workspace()


@pytest.mark.parametrize(
    "fields",
    [
        {"id": "../escape"},
        {"id": "default"},
        {"port": True},
        {"port": 80},
        {"frontends": "not-a-list"},
        {"extra": "unknown"},
    ],
)
def test_invalid_workspace_configuration_is_rejected(tmp_path, fields):
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps({"id": "company", "data_dir": "data", **fields}))
    with pytest.raises(ValueError):
        load_workspace(path)


def test_frontend_mounts_and_public_metadata_do_not_expose_local_paths(store, tmp_path, monkeypatch):
    monkeypatch.setenv("GYM_ACCESS_TOKEN", "private-token")
    frontend = package(tmp_path / "frontend")
    workspace = Workspace("company", frontends=(frontend,))
    with TestClient(create_app(store, FixtureRouter(), False, workspace)) as client:
        metadata = client.get("/app-config.json")
        assert metadata.status_code == 200
        assert str(tmp_path) not in metadata.text and "private-token" not in metadata.text
        assert client.get("/experience/company/").text == "<h1>Company frontend</h1>"
        assert client.get("/experience/company/lesson/one").status_code == 200
        assert client.get("/experience/company/assets/app.js").status_code == 200
        assert client.get("/experience/company/assets/missing.js").status_code == 404
        assert client.get("/experience/company/%2e%2e%2fprivate.txt").status_code == 404
        assert client.get("/experience/unknown/").status_code == 404
        assert client.get("/api/labs").status_code == 401
        assert client.get("/api/labs", headers={"Authorization": "Bearer private-token"}).status_code == 200
        assert (
            client.post(
                "/api/sessions",
                json={},
                headers={"Authorization": "Bearer private-token", "Origin": "https://foreign.test"},
            ).status_code
            == 403
        )


def test_incompatible_or_unbuilt_frontends_are_not_installed(tmp_path):
    frontend = package(tmp_path / "frontend")
    manifest = json.loads((frontend / "experience.json").read_text())
    manifest["contract_version"] = "9.0"
    (frontend / "experience.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported"):
        check_frontend(frontend)


def test_install_updates_only_explicit_workspace_and_rejects_default(tmp_path):
    frontend = package(tmp_path / "frontend")
    with pytest.raises(ValueError, match="explicit"):
        install_frontend(frontend, None)
    config = tmp_path / "company.json"
    config.write_text(json.dumps({"id": "company", "data_dir": "local-data", "port": 8871}))
    install_frontend(frontend, config)
    install_frontend(frontend, config)
    assert load_workspace(config).frontends == (frontend,)
    assert load_workspace(config).port == 8871
    assert not (tmp_path / "local-data").exists()


def test_export_is_portable_synthetic_and_does_not_use_live_storage(tmp_path, monkeypatch):
    live = tmp_path / "live"
    monkeypatch.setenv("GYM_DATA_DIR", str(live))
    monkeypatch.setenv("GYM_DATABASE_URL", "sqlite:///" + str(live / "must-not-open.db"))
    bundle = tmp_path / "kit"
    export_kit(bundle)
    assert not live.exists()
    assert (bundle / "skill/SKILL.md").exists()
    assert (bundle / "contracts/activity-registry.json").exists()
    assert (bundle / "packages/gym-frontend/client.js").exists()
    package_json = json.loads((bundle / "starter/package.json").read_text())
    assert package_json["dependencies"]["@learning-gym/frontend"] == "file:../packages/gym-frontend"
    examples = json.loads((bundle / "contracts/examples.json").read_text())
    assert examples["lab"]["activities"] == []
    assert {item["type"] for item in examples["items"]} == {
        "mcq",
        "matching",
        "open",
        "case",
        "counterfactual",
        "coding",
    }
    assert all("key" not in item for item in examples["items"])
    with pytest.raises(ValueError, match="must not exist"):
        export_kit(bundle)


def test_fixture_refuses_existing_learner_workspace(store):
    with pytest.raises(ValueError, match="empty disposable"):
        seed(store)


def test_supported_api_journey_preserves_pinned_evidence_and_scoring(tmp_path, monkeypatch):
    monkeypatch.setenv("GYM_ACCESS_TOKEN", "")
    store = Store("sqlite:///" + str(tmp_path / "fixture.db"), tmp_path)
    try:
        seed(store)
        with TestClient(create_app(store, FixtureRouter(), False)) as client:
            before = client.get("/api/overview").json()
            assert before["attempts"] == 0
            assert not client.get("/api/labs/demo-lab").json()["activities"]
            visit = client.post(
                "/api/labs/demo-lab/activities",
                json={"lesson_id": "compare", "module": "reasoning", "idempotency_key": "visit-key"},
            ).json()
            event = {
                "action": "reading",
                "parameters": {"section": "lesson"},
                "idempotency_key": "reading-key",
            }
            for _ in range(2):
                assert (
                    client.post(f"/api/lab-activities/{visit['id']}/events", json=event).json()[
                        "reading_count"
                    ]
                    == 1
                )
            session = client.post(
                "/api/sessions",
                json={"course_id": "demo-course", "module": "reasoning", "mode": "practice", "count": 6},
            ).json()
            assert all("key" not in item for item in session["items"])
            assert (
                client.post(
                    f"/api/lab-activities/{visit['id']}/link-session", json={"session_id": session["id"]}
                ).status_code
                == 200
            )
            answer = {"item_id": "demo-practice-mcq", "answer": "A", "idempotency_key": "answer-key"}
            for _ in range(2):
                assert client.post(f"/api/sessions/{session['id']}/answers", json=answer).status_code == 200
            with store.tx() as c:
                attempts = store.list(c, "attempt")
                assert len(attempts) == 1 and attempts[0]["score"] == 5
                assert attempts[0]["assistance"] == ["lab_materials"]
                assert store.get(c, "lab_activity", visit["id"])["status"] == "finished"
    finally:
        store.engine.dispose()


def test_documented_response_models_match_live_journey(tmp_path, monkeypatch):
    from gym.frontend_contracts import AidView, LabSummaryView, LabView, SessionView, TimerView, VisitView

    monkeypatch.setenv("GYM_ACCESS_TOKEN", "")
    store = Store("sqlite:///" + str(tmp_path / "fixture.db"), tmp_path)
    try:
        seed(store)
        with TestClient(create_app(store, FixtureRouter(), False, Workspace())) as client:

            def response(method, path, model, body=None):
                result = client.request(method, path, json=body)
                assert result.status_code == 200, result.text
                model.model_validate(result.json())
                return result.json()

            for lab in client.get("/api/labs").json():
                LabSummaryView.model_validate(lab)
            lab = response("GET", "/api/labs/demo-lab", LabView)
            visit = response(
                "POST",
                "/api/labs/demo-lab/activities",
                VisitView,
                {"module": "reasoning", "lesson_id": "compare", "idempotency_key": "contract-visit"},
            )
            response("GET", "/api/labs/demo-lab", LabView)
            response(
                "POST",
                f"/api/lab-activities/{visit['id']}/events",
                VisitView,
                {"action": "reading", "idempotency_key": "contract-reading"},
            )
            session = response(
                "POST",
                "/api/sessions",
                SessionView,
                {"course_id": lab["course_id"], "module": "reasoning", "mode": "practice", "count": 6},
            )
            path = f"/api/sessions/{session['id']}"
            response(
                "POST",
                f"/api/lab-activities/{visit['id']}/link-session",
                VisitView,
                {"session_id": session["id"]},
            )
            response("POST", path + "/timer", TimerView, {"action": "pause"})
            response("POST", path + "/timer", TimerView, {"action": "resume"})
            response("POST", path + "/aid", AidView, {"item_id": "demo-practice-mcq", "kind": "hint"})
            response(
                "POST",
                path + "/answers",
                SessionView,
                {"item_id": "demo-practice-mcq", "answer": "A", "idempotency_key": "contract-answer"},
            )
            response(
                "POST",
                path + "/answers",
                SessionView,
                {
                    "item_id": "demo-practice-open",
                    "answer": "Hold the other inputs constant.",
                    "idempotency_key": "contract-open",
                },
            )
            response("POST", path + "/finish", SessionView, {})
            response("GET", path, SessionView)
            schema = client.get("/openapi.json").json()
            assert schema["info"]["x-frontend-contract"] == "1.0"
    finally:
        store.engine.dispose()


def test_dependency_checker_rejects_company_coupling(tmp_path):
    from scripts.check_architecture import REQUIRED, structural_errors

    for name in REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reference")
    shared = tmp_path / "packages/gym-frontend"
    shared.mkdir(parents=True)
    company = tmp_path / "adaptations/example"
    company.mkdir(parents=True)
    (company / "package.json").write_text(
        json.dumps({"dependencies": {"@example/design": "1.0", "react": "19"}})
    )
    (shared / "package.json").write_text(json.dumps({"peerDependencies": {"react": ">=18"}}))
    assert structural_errors(tmp_path) == []
    (shared / "hooks.js").write_text('import {Button} from "@example/design/button";')
    assert any("company import" in error for error in structural_errors(tmp_path))
    (shared / "hooks.js").unlink()
    (shared / "package.json").write_text(json.dumps({"dependencies": {"@example/design": "1.0"}}))
    assert any("company dependencies" in error for error in structural_errors(tmp_path))
