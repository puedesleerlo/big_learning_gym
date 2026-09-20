"""Trusted frontend installation and static serving; never learner content execution."""

import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .workspaces import NAME

CONTRACT_VERSION = "1.0"
CAPABILITIES = {"labs", "practice", "transfer"}


def check_frontend(directory, require_build=True):
    root = Path(directory).expanduser().resolve()
    manifest = json.loads((root / "experience.json").read_text())
    if not isinstance(manifest, dict):
        raise ValueError("experience.json must be an object")
    if not isinstance(manifest.get("id"), str) or not NAME.fullmatch(manifest["id"]):
        raise ValueError("Frontend id must be a lowercase name, starting with a letter")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"Frontend requires unsupported contract {manifest.get('contract_version')}")
    if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
        raise ValueError("Frontend version is required")
    capabilities = manifest.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(c, str) or c not in CAPABILITIES for c in capabilities)
    ):
        raise ValueError("Declare supported capabilities: labs, practice, transfer")
    if manifest.get("entry") != "dist/index.html":
        raise ValueError("Frontend entry must be dist/index.html")
    if require_build and not (root / "dist/index.html").is_file():
        raise ValueError("Build the frontend before installing it")
    return manifest


def register_frontends(app, workspace):
    installed = {}
    for directory in workspace.frontends:
        manifest = check_frontend(directory)
        if manifest["id"] in installed:
            raise ValueError(f"Duplicate frontend id: {manifest['id']}")
        installed[manifest["id"]] = (directory, manifest)

    @app.get("/app-config.json", include_in_schema=False)
    def bootstrap():
        # Public boot metadata intentionally contains no paths, content, or credentials.
        return {
            "workspace_id": workspace.id,
            "contract_version": CONTRACT_VERSION,
            "api_base": "/api",
            "experiences": [
                {"id": ident, "version": m["version"], "capabilities": m["capabilities"]}
                for ident, (_, m) in installed.items()
            ],
        }

    @app.get("/experience/{ident}", include_in_schema=False)
    def experience_redirect(ident: str):
        if ident not in installed:
            raise HTTPException(404, "Frontend is not installed in this workspace")
        return RedirectResponse(f"/experience/{ident}/")

    @app.get("/experience/{ident}/{path:path}", include_in_schema=False)
    def experience(ident: str, path: str):
        if ident not in installed:
            raise HTTPException(404, "Frontend is not installed in this workspace")
        directory, _ = installed[ident]
        dist = (directory / "dist").resolve()
        target = (dist / (path or "index.html")).resolve()
        if not target.is_relative_to(dist):
            raise HTTPException(404)
        if not target.is_file():
            # Missing assets must not become a successful HTML response.
            if Path(path).suffix or path.startswith("assets/"):
                raise HTTPException(404)
            target = dist / "index.html"
        return FileResponse(target)
