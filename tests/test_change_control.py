"""The guard must reject bypasses, not merely pass its own repository."""

from scripts.check_architecture import is_protected, review_errors, structural_errors


def note(**changes):
    return {
        "summary": "Preserve behavior while repairing the implementation",
        "type": "preserving",
        "paths": ["gym/planning.py"],
        "decisions": ["D-003"],
        "architecture": "unchanged",
        "algorithms": "unchanged",
        "rationale": "The algorithm and authority remain unchanged",
        "authorization": "Routine work within the accepted constraint",
        "validation": "Ran deadline and stale-plan rejection scenarios",
        "rollback": "Revert the implementation commit; no data migration",
        **changes,
    }


def test_protected_code_needs_a_new_path_specific_record():
    assert review_errors({"gym/planning.py": "M"}, {}, {"D-003"})
    assert review_errors(
        {"gym/planning.py": "M", "docs/changes/old.json": "M"}, {"docs/changes/old.json": note()}, {"D-003"}
    )
    assert not review_errors(
        {"gym/planning.py": "M", "docs/changes/fix.json": "A"}, {"docs/changes/fix.json": note()}, {"D-003"}
    )


def test_wildcards_and_unknown_decisions_cannot_waive_review():
    changes = {"gym/planning.py": "M", "docs/changes/fix.json": "A"}
    assert review_errors(changes, {"docs/changes/fix.json": note(paths=["gym/*"])}, {"D-003"})
    assert review_errors(changes, {"docs/changes/fix.json": note(decisions=["D-999"])}, {"D-003"})


def test_revision_requires_decision_and_claimed_document_updates():
    changes = {"gym/planning.py": "M", "docs/changes/fix.json": "A"}
    record = note(type="revision", architecture="updated", algorithms="updated")
    errors = review_errors(changes, {"docs/changes/fix.json": record}, {"D-003"})
    assert any("DECISIONS.md" in e for e in errors)
    assert any("ARCHITECTURE.md" in e for e in errors)
    assert any("ALGORITHMS.md" in e for e in errors)


def test_deleting_a_guard_or_a_test_is_also_a_protected_change():
    for path in [
        "AGENTS.md",
        ".github/workflows/ci.yml",
        ".github/CODEOWNERS",
        "scripts/check_architecture.py",
        "tests/test_sessions.py",
    ]:
        assert is_protected(path)
        assert review_errors({path: "D"}, {}, {"D-003"})


def test_invalid_records_fail_closed():
    assert review_errors(
        {"gym/planning.py": "M", "docs/changes/x.json": "A"}, {"docs/changes/x.json": []}, {"D-003"}
    )
    assert review_errors(
        {"gym/planning.py": "M", "docs/changes/x.json": "A"},
        {"docs/changes/x.json": note(paths=[123])},
        {"D-003"},
    )


def test_boundary_detector_rejects_provider_imports_and_foreign_schedule_writes(tmp_path):
    for name in ["AGENTS.md", "DECISIONS.md", "docs/ARCHITECTURE.md", "docs/ALGORITHMS.md"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Fixture reference")
    (tmp_path / "gym").mkdir()
    (tmp_path / "gym/planning.py").write_text("def helper():\n    from . import llm\n")
    (tmp_path / "gym/rogue.py").write_text("store.put(c, 'schedule', 'active', {})\n")
    errors = structural_errors(tmp_path)
    assert any("provider/transport" in e for e in errors)
    assert any("schedule writes" in e for e in errors)
