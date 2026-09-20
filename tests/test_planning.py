from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from gym.calendar import export_schedule, import_ics, upsert_event
from gym.contracts import TaskInput
from gym.planning import accept_schedule, create_task, pin_block, propose_schedule, revise_task, timestamp
from gym.store import predictions


def settings():
    day = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    return {
        "start_date": day,
        "days": 1,
        "timezone": "UTC",
        "weekdays": list(range(7)),
        "day_start": "09:00",
        "day_end": "17:00",
        "daily_minutes": 240,
        "slack": 0.2,
    }


def task(store, **overrides):
    return create_task(
        store,
        TaskInput.model_validate(
            {
                "title": "Prepare assessment",
                "definition_of_done": "Complete and check the work",
                "effort_minutes": 60,
                **overrides,
            }
        ).model_dump(),
    )


def test_non_overlap_dependencies_slack_and_commitments(store):
    a = task(store)
    b = task(store, title="Second stage", prerequisites=[a["id"]], category="research")
    opts = settings()
    day = opts["start_date"]
    upsert_event(
        store, {"title": "Meeting", "start": day + "T09:00:00+00:00", "end": day + "T10:00:00+00:00"}
    )
    plan = propose_schedule(store, opts)
    blocks = plan["blocks"]
    assert plan["feasible"]
    assert all(timestamp(x["start"]) >= timestamp(day + "T10:00:00+00:00") for x in blocks)
    for x, y in zip(blocks, blocks[1:]):
        assert timestamp(x["end"]) <= timestamp(y["start"])
    assert sum((timestamp(x["end"]) - timestamp(x["start"])).total_seconds() / 60 for x in blocks) <= 192
    assert max(timestamp(x["end"]) for x in blocks if x["task_id"] == a["id"]) <= min(
        timestamp(x["start"]) for x in blocks if x["task_id"] == b["id"]
    )


def test_infeasible_does_not_extend_workload(store):
    task(store, effort_minutes=600)
    plan = propose_schedule(store, {**settings(), "daily_minutes": 60})
    assert not plan["feasible"] and plan["conflicts"]
    assert sum(b["work_minutes"] for b in plan["blocks"]) <= 45
    with pytest.raises(ValueError, match="conflicts"):
        accept_schedule(store, plan["id"])


def test_stale_proposal_rejected(store):
    task(store)
    plan = propose_schedule(store, settings())
    upsert_event(
        store,
        {
            "title": "New meeting",
            "start": settings()["start_date"] + "T12:00:00Z",
            "end": settings()["start_date"] + "T13:00:00Z",
        },
    )
    with pytest.raises(ValueError, match="stale"):
        accept_schedule(store, plan["id"])


def test_deadline_change_preserves_estimate_but_scope_invalidates(store):
    t = task(store)
    with store.tx() as c:
        original = c.execute(select(predictions)).mappings().one()["id"]
    revise_task(store, t["id"], {"deadline": settings()["start_date"] + "T17:00:00Z"})
    with store.tx() as c:
        assert (
            c.execute(select(predictions).where(predictions.c.id == original))
            .mappings()
            .one()["stale_reason"]
            is None
        )
    revise_task(store, t["id"], {"effort_minutes": 90})
    with store.tx() as c:
        assert (
            c.execute(select(predictions).where(predictions.c.id == original))
            .mappings()
            .one()["stale_reason"]
        )


def test_pins_survive_repair_and_export_import_does_not_duplicate(store):
    task(store)
    plan = propose_schedule(store, settings())
    accept_schedule(store, plan["id"])
    pin = plan["blocks"][0]
    pin_block(store, pin["id"], True)
    repaired = propose_schedule(store, settings())
    assert any(b["id"] == pin["id"] and b["start"] == pin["start"] for b in repaired["blocks"])
    result = import_ics(store, export_schedule(store))
    assert result["count"] == 0


def test_ics_revision_cancellation_and_date_only(store):
    def ics(seq, status="CONFIRMED", start="20300101"):
        return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:sample\r\nSEQUENCE:{seq}\r\nSUMMARY:All day\r\nDTSTART;VALUE=DATE:{start}\r\nDTEND;VALUE=DATE:20300104\r\nSTATUS:{status}\r\nEND:VEVENT\r\nEND:VCALENDAR".encode()

    import_ics(store, ics(1))
    import_ics(store, ics(1))
    import_ics(store, ics(2, start="20300102"))
    import_ics(store, ics(1))
    with store.tx() as c:
        values = store.list(c, "calendar")
        assert len(values) == 1
        assert values[0]["start"] == "2030-01-02" and values[0]["all_day"]
    import_ics(store, ics(3, "CANCELLED"))
    with store.tx() as c:
        assert store.list(c, "calendar")[0]["cancelled"]
