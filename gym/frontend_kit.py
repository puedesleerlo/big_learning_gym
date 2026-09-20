"""Export agent context from synthetic state, and install trusted static builds."""

import json
import shutil
import tempfile
from pathlib import Path

from .frontends import CONTRACT_VERSION, check_frontend
from .workspaces import ROOT, Workspace, load_workspace


def install_frontend(directory, workspace_path):
    if not workspace_path:
        raise ValueError("Install into an explicit local workspace: --workspace path/to/company.json")
    source = Path(directory).expanduser().resolve()
    manifest = check_frontend(source)
    workspace = load_workspace(workspace_path)
    entries = [p for p in workspace.frontends if check_frontend(p)["id"] != manifest["id"]]
    entries.append(source)
    config_path = Path(workspace_path).expanduser().resolve()
    config = json.loads(config_path.read_text())
    config["frontends"] = [str(p) for p in entries]
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return f"Installed {manifest['id']} {manifest['version']}. Restart this workspace and open /experience/{manifest['id']}/"


def export_kit(directory):
    from .api import create_app
    from .frontend_fixture import FixtureRouter, journey_examples, seed
    from .store import Store

    target = Path(directory).expanduser().resolve()
    if target.exists():
        raise ValueError("Export destination must not exist; choose a fresh directory")
    target.mkdir(parents=True)
    try:
        shutil.copytree(
            ROOT / "packages/gym-frontend",
            target / "packages/gym-frontend",
            ignore=shutil.ignore_patterns("node_modules"),
        )
        shutil.copytree(
            ROOT / "frontend-kit/starter",
            target / "starter",
            ignore=shutil.ignore_patterns("node_modules", "dist"),
        )
        # Keep the package portable when the starter's relative location changes.
        package = target / "starter/package.json"
        data = json.loads(package.read_text())
        data["dependencies"]["@learning-gym/frontend"] = "file:../packages/gym-frontend"
        package.write_text(json.dumps(data, indent=2) + "\n")
        lock = target / "starter/pnpm-lock.yaml"
        lock.write_text(lock.read_text().replace("../../packages/gym-frontend", "../packages/gym-frontend"))
        shutil.copytree(ROOT / "skills/build-gym-frontend", target / "skill")
        shutil.copy2(ROOT / "frontend-kit/START_HERE.md", target / "START_HERE.md")
        shutil.copy2(ROOT / "frontend-kit/check.mjs", target / "check.mjs")
        contracts = target / "contracts"
        contracts.mkdir()
        with tempfile.TemporaryDirectory(prefix="gym-frontend-export-") as temp:
            store = Store("sqlite:///" + str(Path(temp) / "fixture.db"), Path(temp))
            try:
                fixture = seed(store)
                app = create_app(store, FixtureRouter(), embedded_worker=False, workspace=Workspace())
                (contracts / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
                (contracts / "activity-registry.json").write_text(
                    json.dumps(fixture["registry"], indent=2) + "\n"
                )
                (contracts / "examples.json").write_text(json.dumps(fixture, indent=2) + "\n")
                (contracts / "journey-examples.json").write_text(
                    json.dumps(journey_examples(store), indent=2) + "\n"
                )
            finally:
                store.engine.dispose()
        (target / "bundle.json").write_text(
            json.dumps(
                {"contract_version": CONTRACT_VERSION, "data": "synthetic only", "entry": "START_HERE.md"},
                indent=2,
            )
            + "\n"
        )
    except Exception:
        shutil.rmtree(target)
        raise
    return str(target)
