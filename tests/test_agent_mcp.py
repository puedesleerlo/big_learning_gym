import json

import httpx
import pytest

pytest.importorskip("mcp")

from mcp.shared.memory import create_connected_server_and_client_session

from gym.api import create_app
from gym.mcp_server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def body(result):
    assert not result.isError, result.content
    return json.loads(result.content[0].text)["body"]


@pytest.mark.anyio
async def test_mcp_protocol_discovery_write_upload_and_read(store, tmp_path):
    api = create_app(store=store, embedded_worker=False)
    server = create_server(
        base_url="http://testserver",
        token="",
        transport=httpx.ASGITransport(app=api),
        upload_roots=[tmp_path],
    )
    source = tmp_path / "notes.md"
    source.write_text("# Causal notes\nInterventions change the treatment assignment mechanism.")
    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()
        assert {t.name for t in listed.tools} == {
            "gym_capabilities",
            "gym_schema",
            "gym_read",
            "gym_request",
            "gym_upload",
        }
        assert next(t for t in listed.tools if t.name == "gym_read").annotations.readOnlyHint
        manifest = body(await session.call_tool("gym_capabilities", {}))
        assert manifest["schema_url"] == "/api/agent/schema"
        schema = body(await session.call_tool("gym_schema", {"path": "/api/authoring/courses/{ident}"}))
        assert "CourseWrite" in schema["components"]["schemas"]
        created = body(
            await session.call_tool(
                "gym_request",
                {
                    "method": "PUT",
                    "path": "/api/authoring/courses/from-mcp",
                    "body": {
                        "expected_revision": 0,
                        "title": "MCP course",
                        "modules": [],
                        "provenance": {"author": "test", "rationale": "Protocol integration test"},
                    },
                },
            )
        )
        assert created["title"] == "MCP course"
        upload = body(
            await session.call_tool(
                "gym_upload",
                {
                    "path": "/api/sources",
                    "file_path": str(source),
                    "fields": {"course_id": "from-mcp", "role": "research"},
                },
            )
        )
        fragments = body(
            await session.call_tool("gym_read", {"path": f"/api/sources/{upload['id']}/fragments"})
        )
        assert "Interventions" in fragments[0]["text"]
        conflict = await session.call_tool(
            "gym_request",
            {
                "method": "PUT",
                "path": "/api/authoring/courses/from-mcp",
                "body": {
                    "expected_revision": 0,
                    "title": "Overwrite",
                    "modules": [],
                    "provenance": {"author": "test", "rationale": "Conflicting test update"},
                },
            },
        )
        assert conflict.isError and "409" in conflict.content[0].text
        forbidden = await session.call_tool("gym_read", {"path": "https://foreign.invalid/api/overview"})
        assert forbidden.isError
        traversal = await session.call_tool("gym_read", {"path": "/api/%2e%2e/secret"})
        assert traversal.isError
        outside = await session.call_tool(
            "gym_upload",
            {"path": "/api/sources", "file_path": "/etc/hosts", "fields": {"course_id": "from-mcp"}},
        )
        assert outside.isError
    with store.tx() as c:
        assert store.list(c, "attempt") == []
        assert store.list(c, "learner") == []


@pytest.mark.anyio
async def test_mcp_auth_and_error_redaction():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(401, text="Bad token: secret-test-token")

    server = create_server(
        base_url="http://localhost:8787", token="secret-test-token", transport=httpx.MockTransport(handler)
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("gym_capabilities", {})
        assert result.isError
        assert "secret-test-token" not in result.content[0].text
        assert "401" in result.content[0].text
    assert requests[0].headers["authorization"] == "Bearer secret-test-token"


@pytest.mark.anyio
async def test_mcp_targeted_profile_history_rerun_and_external_outcome(store):
    from gym.ingestion import ingest

    source = ingest(store, "course", "prior.md", b"Random assignment supports a comparison in expectation.")
    with store.tx() as c:
        store.put(c, "source", source["id"], {**source, "reconstruction_status": "confirmed"})
    server = create_server(
        base_url="http://testserver",
        token="",
        transport=httpx.ASGITransport(app=create_app(store, embedded_worker=False)),
    )
    async with create_connected_server_and_client_session(server) as session:

        async def write(path, payload):
            return body(
                await session.call_tool("gym_request", {"method": "POST", "path": path, "body": payload})
            )

        manifest = body(await session.call_tool("gym_capabilities", {}))
        assert "profile_rerun" in manifest["existing_workflows"]
        schema = body(await session.call_tool("gym_schema", {"path": "/api/profiles/{ident}/rerun"}))
        assert "ProfileRerunInput" in schema["components"]["schemas"]
        assignment = await write(
            "/api/assignments",
            {
                "course_id": "course",
                "title": "Future Quiz",
                "deadline": "2026-10-01T17:00:00-04:00",
                "effort_minutes": 60,
                "prompt": "Prepare to explain a randomized comparison.",
            },
        )
        profile = await write(
            "/api/profiles",
            {
                "course_id": "course",
                "target": "Prepare for the future quiz",
                "target_assignment_id": assignment["id"],
                "material_source_ids": [source["id"]],
            },
        )
        history = body(
            await session.call_tool("gym_read", {"path": f"/api/profiles/{profile['id']}/versions"})
        )
        assert history["versions"][0]["target_assignment_id"] == assignment["id"]
        rerun = await write(
            f"/api/profiles/{profile['id']}/rerun",
            {"expected_revision": profile["revision"], "idempotency_key": "mcp-rerun-test"},
        )
        assert rerun["run_version"] == 2
        outcome = await write(
            f"/api/assignments/{assignment['id']}/outcomes",
            {
                "idempotency_key": "mcp-outcome-test",
                "feedback": "An actual external instructor comment.",
                "attribution": "Synthetic instructor record",
                "observed_at": "2026-09-20T12:00:00-04:00",
            },
        )
        assert outcome["score"] is None and outcome["submission_id"] is None
        coursework = body(await session.call_tool("gym_read", {"path": "/api/coursework"}))
        assert coursework["submission"] == [] and len(coursework["coursework_outcome"]) == 1
