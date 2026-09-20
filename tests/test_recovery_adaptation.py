import zipfile
from pathlib import Path

import pytest
from sqlalchemy import insert

from gym import adaptation
from gym.backup import backup, restore
from gym.ingestion import correct_reconstruction, ingest
from gym.store import Store, events, predictions


def test_portable_backup_restores_originals_and_evidence(store, tmp_path):
    source = ingest(store, "course", "lesson.md", b"Original source with trustworthy evidence.")
    target = tmp_path / "workspace.zip"
    backup(store, target)
    restored = Store("sqlite:///" + str(tmp_path / "restored.db"), tmp_path / "restored")
    restore(restored, target)
    with restored.tx() as c:
        result = restored.get(c, "source", source["id"])
        assert Path(result["storage_path"]).read_bytes() == b"Original source with trustworthy evidence."
        assert restored.evidence(c, source["id"])
    with pytest.raises(ValueError, match="empty workspace"):
        restore(restored, target)
    with zipfile.ZipFile(target) as z:
        assert all("env" not in n for n in z.namelist())
        assert "MOONSHOT_API_KEY" not in z.read("workspace.json").decode()
    restored.engine.dispose()


def test_corrupt_backup_is_rejected_before_database_change(store, tmp_path):
    target = tmp_path / "valid.zip"
    backup(store, target)
    invalid = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(target) as original, zipfile.ZipFile(invalid, "w") as changed:
        for name in original.namelist():
            changed.writestr(name, b"{}" if name == "workspace.json" else original.read(name))
    with pytest.raises(ValueError, match="checksum"):
        restore(store, invalid)
    with store.tx() as c:
        assert store.get(c, "course", "course")["title"] == "Test gym"


def test_correction_retains_source_history_and_rejects_stale_edit(store):
    old = ingest(
        store, "course", "quiz.txt", b"Partially reconstructed original quiz prompt.", role="assessment"
    )
    changed = correct_reconstruction(
        store,
        old["id"],
        [{"anchor": "page 1", "text": "Corrected prompt and equation: x = 2."}],
        old["revision"],
    )
    with store.tx() as c:
        assert not store.get(c, "source", old["id"])["latest"]
        assert changed["reconstruction_status"] == "confirmed"
        assert changed["storage_path"] == old["storage_path"]
        assert len(store.list(c, "fragment")) == 2
    with pytest.raises(ValueError, match="changed"):
        correct_reconstruction(store, old["id"], [{"anchor": "page 1", "text": "stale"}], old["revision"])


def seed_forecasts(store, late=False):
    with store.tx() as c:
        for n in range(12):
            day = f"2026-08-{n + 1:02d}"
            c.execute(
                insert(predictions).values(
                    id=f"p{n}",
                    target_id=f"task{n}",
                    target_version=1,
                    quantity="remaining_effort",
                    distribution={"p50": 30, "p80": 42},
                    input_state_revision=1,
                    model_version="effort-prior-v1",
                    created_at=day + "T10:00:00+00:00",
                    dependencies=[],
                )
            )
            c.execute(
                insert(events).values(
                    id=f"e{n}",
                    idempotency_key=f"e{n}",
                    entity_id=f"task{n}",
                    event_type="task.completed",
                    occurred_at=day + "T11:00:00+00:00",
                    received_at=("2026-08-30" if late else day) + "T12:00:00+00:00",
                    payload={
                        "actual_active_minutes": 60,
                        "before": {"scope_version": 1, "category": "homework"},
                    },
                    quality_flags=[],
                )
            )


def test_point_in_time_candidate_activation_and_baseline_rollback(store):
    seed_forecasts(store)
    result = adaptation.evaluate(store)
    assert result["status"] == "candidate_in_shadow"
    active = adaptation.activate_model(store, result["candidate_id"])
    assert active["multiplier"] == 2
    assert adaptation.activate_model(store, "effort-prior-v1")["status"] == "active"


def test_late_outcomes_cannot_train_a_past_holdout(store):
    seed_forecasts(store, late=True)
    result = adaptation.evaluate(store)
    assert result["status"] == "insufficient_evidence"
    assert "candidate_id" not in result
