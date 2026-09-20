"""Disposable browser fixture. Does not load real learner data or call models."""

import argparse
import json
import os
import socket
import tempfile
from pathlib import Path

import uvicorn

from gym.api import create_app
from gym.frontend_fixture import FixtureRouter, seed
from gym.store import Store
from gym.workspaces import Workspace

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="browser-fixture")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    os.environ["GYM_ACCESS_TOKEN"] = args.token
    os.environ["GYM_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    with tempfile.TemporaryDirectory(prefix="gym-experience-browser-") as directory:
        store = Store("sqlite:///" + str(Path(directory) / "test.db"), Path(directory))
        seed(store)
        workspace = Workspace(
            args.id, frontends=(Path(__file__).resolve().parents[1] / "adaptations/makitra",)
        )
        app = create_app(store, FixtureRouter(), embedded_worker=False, workspace=workspace)

        @app.get("/__fixture/summary")
        def summary():
            with store.tx() as c:
                return {
                    "visits": store.list(c, "lab_activity"),
                    "attempts": store.list(c, "attempt"),
                    "sessions": [
                        {k: v for k, v in s.items() if k != "snapshots"} for s in store.list(c, "session")
                    ],
                    "learners": store.list(c, "learner"),
                }

        # Register this test-only probe before the application SPA fallback.
        app.router.routes.insert(0, app.router.routes.pop())
        sock = socket.socket()
        sock.bind(("127.0.0.1", args.port))
        print(json.dumps({"url": f"http://127.0.0.1:{sock.getsockname()[1]}"}), flush=True)
        uvicorn.Server(uvicorn.Config(app, log_level="error")).run(sockets=[sock])
