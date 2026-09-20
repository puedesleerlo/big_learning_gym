"""Behavioral contracts for D-003/D-004/D-006, not implementation snapshots."""

from datetime import datetime, timedelta, timezone

import pytest

from gym.contracts import TaskInput
from gym.learning import update_learner
from gym.planning import create_task, propose_schedule
from scripts.check_architecture import ROOT, structural_errors


def test_core_respects_provider_and_schedule_boundaries():
    assert structural_errors(ROOT) == []


@pytest.mark.parametrize(
    "assistance,exposures,assessor,weight",
    [
        ([], 0, "deterministic", 1),
        (["hint"], 0, "deterministic", 0.25),
        ([], 1, "deterministic", 0.25),
        ([], 0, "llm", 0.5),
        (["hint"], 1, "llm", 0.03125),
    ],
)
def test_learning_evidence_weight_is_an_explicit_contract(
    store, item, assistance, exposures, assessor, weight
):
    attempt = {
        "score": 4,
        "assistance": assistance,
        "previous_exposures": exposures,
        "assessor_type": assessor,
        "mode": "practice",
    }
    with store.tx() as c:
        update_learner(store, c, attempt, item, "observation")
        dimension = store.list(c, "learner")[0]["dimensions"]["application"]
        assert dimension["alpha"] == pytest.approx(1 + 0.8 * weight)
        assert dimension["beta"] == pytest.approx(1 + 0.2 * weight)
        update_learner(store, c, attempt, item, "observation")
        assert store.list(c, "learner")[0]["dimensions"]["application"] == dimension


def test_exploration_budget_includes_setup_and_does_not_book_a_plan(store):
    day = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    create_task(
        store,
        TaskInput.model_validate(
            {
                "title": "Explore a new method",
                "definition_of_done": "Produce a worked comparison",
                "category": "exploration",
                "effort_minutes": 120,
                "min_block": 5,
                "max_block": 20,
                "setup_minutes": 5,
            }
        ).model_dump(),
    )
    proposal = propose_schedule(
        store,
        {
            "start_date": day,
            "days": 1,
            "timezone": "UTC",
            "weekdays": list(range(7)),
            "day_start": "09:00",
            "day_end": "17:00",
            "daily_minutes": 200,
            "slack": 0,
        },
    )
    assert proposal["blocks"]
    allocated = sum(b["work_minutes"] + b["setup_minutes"] for b in proposal["blocks"])
    assert 0 < allocated <= 20  # 10% of the 200-minute usable horizon, setup included.
    assert not proposal["feasible"]  # Residual scope remains explicit.
    with store.tx() as c:
        assert store.get(c, "schedule", "active", False) is None
