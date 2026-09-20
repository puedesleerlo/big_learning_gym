import json

import httpx
import pytest
from sqlalchemy import select

from gym.adaptation import activate_model, evaluate
from gym.llm import ModelError, Router
from gym.store import llm_calls


def test_provider_is_routed_and_credentials_not_persisted(store, monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-secret-value")
    path = tmp_path / "models.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "custom": {
                        "adapter": "openai_chat",
                        "base_url": "https://example.test/v1",
                        "api_key_env": "TEST_PROVIDER_KEY",
                        "token_parameter": "max_tokens",
                    }
                },
                "roles": {"tutor": {"provider": "custom", "model": "arbitrary-model", "max_tokens": 20}},
                "limits": {
                    "timeout_seconds": 2,
                    "max_calls_per_day": 1,
                    "max_input_characters": 1000,
                    "max_retries": 0,
                },
            }
        )
    )
    seen = []

    def responder(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer":4}'}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 5},
            },
        )

    router = Router(store, path, httpx.MockTransport(responder))
    result, trace = router.complete("tutor", "Return JSON", "What is 2+2?")
    assert result["answer"] == 4 and trace["provider"] == "custom"
    assert seen[0].headers["Authorization"] == "Bearer test-secret-value"
    with store.tx() as c:
        logs = [dict(x) for x in c.execute(select(llm_calls)).mappings()]
        assert "test-secret-value" not in json.dumps(logs)
    with pytest.raises(ModelError, match="limit"):
        router.complete("tutor", "JSON", "again")


def test_anthropic_adapter(store, monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_KEY", "secret")
    config = {
        "providers": {
            "a": {"adapter": "anthropic", "base_url": "https://example.test/v1", "api_key_env": "TEST_KEY"}
        },
        "roles": {"assessor": {"provider": "a", "model": "claude-test", "max_tokens": 500}},
        "limits": {
            "timeout_seconds": 2,
            "max_calls_per_day": 5,
            "max_input_characters": 1000,
            "max_retries": 0,
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))

    def responder(request):
        assert request.url.path == "/v1/messages" and request.headers["x-api-key"] == "secret"
        assert json.loads(request.content)["system"] == "Return JSON"
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": '{"ok":true}'}], "stop_reason": "end_turn"}
        )

    assert Router(store, path, httpx.MockTransport(responder)).complete("assessor", "Return JSON", "Judge")[
        0
    ]["ok"]


def test_adaptation_disabled_does_not_disable_practice(store, client, item):
    assert client.post("/api/adaptation/settings", json={"enabled": False}).status_code == 200
    assert evaluate(store)["status"] == "disabled"
    assert client.post("/api/sessions", json={"course_id": "course", "count": 1}).status_code == 200


def test_insufficient_outcomes_retain_baseline_and_regression_rejected(store):
    assert evaluate(store)["decision"] == "Retain the active baseline"
    with store.tx() as c:
        store.put(c, "model", "bad", {"role": "effort", "status": "rejected", "promotion_eligible": False})
    with pytest.raises(ValueError):
        activate_model(store, "bad")


def test_access_token_and_same_origin_guards(store, monkeypatch):
    from fastapi.testclient import TestClient

    from gym.api import create_app

    monkeypatch.setenv("GYM_ACCESS_TOKEN", "test-access")
    with TestClient(create_app(store, embedded_worker=False)) as client:
        assert client.get("/api/overview").status_code == 401
        assert client.get("/api/overview", headers={"Authorization": "Bearer test-access"}).status_code == 200
        assert (
            client.post(
                "/api/courses",
                json={"title": "Injected"},
                headers={"Authorization": "Bearer test-access", "Origin": "https://foreign.test"},
            ).status_code
            == 403
        )
