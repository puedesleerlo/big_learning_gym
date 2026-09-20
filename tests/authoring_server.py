"""Synthetic browser fixture for authoring; no real learner data or model calls."""

import json
import os
import socket
import tempfile
from pathlib import Path

import uvicorn
from test_authoring_workflow import PracticeDesigner, profile_body

from gym.api import create_app
from gym.assignments import create_assignment
from gym.ingestion import ingest
from gym.store import Store


class FixtureAuthor(PracticeDesigner):
    def describe(self):
        return {"roles": {}, "providers": {}, "limits": {}}

    def complete(self, role, system, prompt):
        data = json.loads(prompt)
        if "assessment_examples" in data:
            body = profile_body()
            body["title"] = data.get("title") or "Future quiz profile"
            body["content_scope"] = data["target"]
            return {"profile": body}, {"model": "synthetic-profile"}
        return super().complete(role, system, prompt)


if __name__ == "__main__":
    os.environ["GYM_ACCESS_TOKEN"] = ""
    os.environ["GYM_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    with tempfile.TemporaryDirectory(prefix="gym-authoring-browser-") as directory:
        store = Store("sqlite:///" + str(Path(directory) / "test.db"), Path(directory))
        with store.tx() as c:
            store.put(
                c,
                "course",
                "course",
                {"title": "Synthetic statistics gym", "description": "Authoring fixture", "modules": []},
            )
        for name, text in [
            ("Prior lecture.md", "Random assignment controls selection in expectation."),
            ("New clarification.md", "Changed assumptions require examining exchangeability and transport."),
        ]:
            source = ingest(store, "course", name, text.encode())
            with store.tx() as c:
                store.put(c, "source", source["id"], {**source, "reconstruction_status": "confirmed"})
        create_assignment(
            store,
            {
                "title": "Future Quiz 2",
                "course_id": "course",
                "prompt": "Defend an inference and its uncertainty under changed assumptions.",
            },
        )
        create_assignment(
            store,
            {
                "title": "Prior Quiz 1",
                "course_id": "course",
                "prompt": "Explain the original assignment comparison and selection assumptions.",
                "status": "completed",
            },
        )
        app = create_app(store, FixtureAuthor(), embedded_worker=True)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        print(json.dumps({"url": f"http://127.0.0.1:{sock.getsockname()[1]}"}), flush=True)
        uvicorn.Server(uvicorn.Config(app, log_level="error")).run(sockets=[sock])
