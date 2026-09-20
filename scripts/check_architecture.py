"""Check selected architectural boundaries and declared coverage of protected PR changes.

This does not authenticate approval or establish semantic equivalence. CODEOWNERS and
independent repository administration remain the review boundary.
"""

import argparse
import ast
import fnmatch
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = (
    "gym/*",
    "tests/*",
    "scripts/*",
    "config/*",
    "web/src/*",
    "web/tests/*",
    "web/package*",
    "web/pnpm-lock.yaml",
    "packages/*",
    "adaptations/*",
    "frontend-kit/*",
    "skills/build-gym-frontend/*",
    "web/vite.config.*",
    "pyproject.toml",
    "uv.lock",
    "Dockerfile",
    "compose.yaml",
    "AGENTS.md",
    "DECISIONS.md",
    ".cursor/*",
    ".github/*",
    ".gitignore",
    ".dockerignore",
    "docs/ARCHITECTURE.md",
    "docs/EXPERIENCES.md",
    "docs/ALGORITHMS.md",
    "docs/CHANGE_CONTROL.md",
    "docs/changes/*",
)
PURE_CORE = {"store", "learning", "planning", "adaptation", "sessions", "calendar"}
FORBIDDEN_CORE_IMPORTS = {
    "llm",
    "api",
    "agent_api",
    "mcp_server",
    "httpx",
    "requests",
    "openai",
    "anthropic",
    "litellm",
    "frontends",
    "frontend_kit",
    "frontend_fixture",
}
REQUIRED = ("AGENTS.md", "DECISIONS.md", "docs/ARCHITECTURE.md", "docs/ALGORITHMS.md")


def structural_errors(root):
    errors = []
    for name in REQUIRED:
        if not (root / name).is_file():
            errors.append(f"Missing required reference: {name}")
    for path in (root / "gym").glob("*.py"):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as error:
            errors.append(f"{path.name}: cannot inspect syntax at line {error.lineno}")
            continue
        for node in ast.walk(tree):
            imported = []
            if isinstance(node, ast.Import):
                imported = [part for alias in node.names for part in alias.name.split(".")]
            elif isinstance(node, ast.ImportFrom):
                imported = (node.module or "").split(".")
                if node.level and not node.module:
                    imported += [alias.name for alias in node.names]
            if path.stem in PURE_CORE and FORBIDDEN_CORE_IMPORTS.intersection(imported):
                errors.append(
                    f"{path.name}:{node.lineno}: deterministic core imports a provider/transport boundary (D-001/D-006)"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "put"
            ):
                # Store.put(connection, record_kind, id, data). This catches direct calls;
                # indirect SQL or aliases still require review, not claims of sandboxing.
                kind = node.args[1] if len(node.args) > 1 else None
                if (
                    isinstance(kind, ast.Constant)
                    and kind.value in {"schedule", "schedule_version"}
                    and path.stem != "planning"
                ):
                    errors.append(
                        f"{path.name}:{node.lineno}: active schedule writes belong to planning.py (D-003)"
                    )
    # The integration kit remains independent of any installed company design system.
    shared = root / "packages/gym-frontend/package.json"
    company_dependencies = set()
    for package in (root / "adaptations").glob("*/package.json"):
        company_dependencies.update(json.loads(package.read_text()).get("dependencies", {}))
    company_dependencies -= {"react", "react-dom", "@learning-gym/frontend"}
    if shared.exists():
        manifest = json.loads(shared.read_text())
        dependencies = set(manifest.get("dependencies", {})) | set(manifest.get("peerDependencies", {}))
        if dependencies & company_dependencies:
            errors.append("Shared frontend kit imports company dependencies (D-012)")
        for path in shared.parent.glob("*.*"):
            if path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
                for module in re.findall(r"(?:from|import)\s*['\"]([^'\"]+)", path.read_text()):
                    if any(module == dep or module.startswith(dep + "/") for dep in company_dependencies):
                        errors.append(f"{path.name}: company import belongs to its adaptation (D-012)")
    return errors


def is_protected(path):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in PROTECTED)


def review_errors(changes, records, known_decisions):
    """changes maps exact repo paths to A/M/D; records contains new note JSON only."""
    errors, covered = [], set()
    for path, record in records.items():
        if changes.get(path) != "A" or path == "docs/changes/TEMPLATE.json":
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}: change record must be an object")
            continue
        covered.add(path)
        for field in ("summary", "rationale", "validation", "rollback", "authorization"):
            value = record.get(field)
            if not isinstance(value, str) or len(value.strip()) < 12:
                errors.append(f"{path}: explain {field} in at least 12 characters")
        decisions = record.get("decisions")
        if (
            not isinstance(decisions, list)
            or not decisions
            or any(not isinstance(x, str) or x not in known_decisions for x in decisions)
        ):
            errors.append(f"{path}: reference existing D-NNN decision IDs")
        paths = record.get("paths")
        if (
            not isinstance(paths, list)
            or not paths
            or any(
                not isinstance(x, str)
                or x.startswith("/")
                or ".." in x.split("/")
                or any(t in x for t in "*?[")
                for x in paths
            )
        ):
            errors.append(f"{path}: list exact relative paths, without wildcard exemptions")
        else:
            covered.update(paths)
        if record.get("type") not in {"preserving", "revision"}:
            errors.append(f"{path}: type must be preserving or revision")
        if record.get("type") == "revision" and "DECISIONS.md" not in changes:
            errors.append(f"{path}: a revision needs a decision proposal/supersession in DECISIONS.md")
        for field, document in (
            ("architecture", "docs/ARCHITECTURE.md"),
            ("algorithms", "docs/ALGORITHMS.md"),
        ):
            if record.get(field) not in {"unchanged", "updated"}:
                errors.append(f"{path}: {field} must be unchanged or updated")
            elif record[field] == "updated" and document not in changes:
                errors.append(f"{path}: update the declared {document}")
    for path in changes:
        if is_protected(path) and path not in covered:
            errors.append(f"{path}: protected change lacks coverage in a NEW docs/changes/*.json record")
    return errors


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def changed_paths(base, head):
    # --no-renames makes both old and new identities reviewable instead of hiding a deletion.
    parts = git("diff", "--no-renames", "--name-status", "-z", f"{base}...{head}").decode().split("\0")
    return dict((parts[i + 1], parts[i]) for i in range(0, len(parts) - 1, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Base commit; compare committed merge-base...HEAD in CI")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    errors = structural_errors(ROOT)
    if args.base:
        try:
            changes = changed_paths(args.base, args.head)
            records = {}
            for path, status in changes.items():
                if (
                    status == "A"
                    and path.startswith("docs/changes/")
                    and path.endswith(".json")
                    and path != "docs/changes/TEMPLATE.json"
                ):
                    try:
                        records[path] = json.loads(git("show", f"{args.head}:{path}"))
                    except (json.JSONDecodeError, subprocess.CalledProcessError):
                        errors.append(f"{path}: cannot parse committed change record")
            decisions = git("show", f"{args.head}:DECISIONS.md").decode()
            errors.extend(review_errors(changes, records, set(re.findall(r"^## (D-\d{3})", decisions, re.M))))
        except subprocess.CalledProcessError:
            errors.append("Cannot inspect the requested commits; fetch the base branch/history")
    if errors:
        print("Architecture check failed:\n" + "\n".join("- " + error for error in errors))
        raise SystemExit(1)
    print(
        "Architecture boundaries passed."
        + (
            " Protected diff has declared change coverage."
            if args.base
            else " Diff coverage not checked; supply --base for a committed PR."
        )
    )


if __name__ == "__main__":
    main()
