"""Disposable browser-test app. Never connects to the user's database or model."""

import json
import os
import socket
import tempfile
from pathlib import Path

import uvicorn

from gym.api import create_app
from gym.lab_activity import LabWrite, publish_lab
from gym.lab_blocks import activity_types
from gym.store import Store


class FixtureTutor:
    def describe(self):
        return {"roles": {}, "providers": {}, "limits": {}}

    def complete(self, role, system, prompt):
        return {"reply": "Compare two cycles with three cycles over the same interval. What changed?", "citations": ["wave-fragment"]}, {
            "role": role, "provider": "fixture", "model": "fixture-tutor", "call_id": "fixture-call",
        }


if __name__ == "__main__":
    os.environ["GYM_ACCESS_TOKEN"] = ""
    os.environ["GYM_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    with tempfile.TemporaryDirectory(prefix="rich-lab-browser-") as directory:
        store = Store("sqlite:///" + str(Path(directory) / "test.db"), Path(directory))
        with store.tx() as c:
            store.put(c, "course", "waves", {"title": "Wave mechanics", "description": "Synthetic test course", "modules": [{"id": "frequency", "title": "Frequency"}]})
            store.put(c, "source", "wave-notes", {"course_id": "waves", "name": "Fixture notes", "role": "instruction", "reconstruction_status": "confirmed"})
            store.put(c, "fragment", "wave-fragment", {"source_version_id": "wave-notes", "anchor": "page:1", "text": "Frequency counts cycles per unit time."})
        templates = {x["type"]: x["template"] for x in activity_types()["types"]}
        media = {**templates["media"], "kind": "audio", "url": "https://media.example.test/lesson.wav", "title": "Listen to the explanation"}
        visualization = {**templates["visualization"], "title": "Wave playground"}
        discussion = {**templates["discussion"], "title": "Reason about waves"}
        publish_lab(store, "wave-lab", LabWrite.model_validate({
            "course_id": "waves", "expected_revision": 0, "title": "Explore waves", "description": "Watch, explore, discuss.",
            "provenance": {"author": "Browser fixture", "method": "import", "rationale": "Synthetic UI test"},
            "lessons": [{"id": "waves-lesson", "module": "frequency", "title": "Frequency and cycles", "minutes": 15,
                         "source_ids": ["wave-notes"], "activities": [media, visualization, discussion]}],
        }))
        app = create_app(store, FixtureTutor(), embedded_worker=False)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        print(json.dumps({"url": f"http://127.0.0.1:{sock.getsockname()[1]}"}), flush=True)
        uvicorn.Server(uvicorn.Config(app, log_level="error")).run(sockets=[sock])
