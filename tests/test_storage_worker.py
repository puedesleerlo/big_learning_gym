import time

from sqlalchemy import select, update

from gym.store import events, jobs
from gym.worker import Worker


def test_duplicate_event_is_noop(store):
    with store.tx() as c:
        first = store.emit(c, "calendar.changed", "event", {}, key="same-event")
        revision = store.revision(c)
        second = store.emit(c, "calendar.changed", "event", {}, key="same-event")
        assert first[0] == second[0] and not second[1]
        assert store.revision(c) == revision
        assert len(list(c.execute(select(events)))) == 1
        assert len(list(c.execute(select(jobs)))) == 1


def test_state_and_outbox_roll_back_together(store):
    try:
        with store.tx() as c:
            store.put(c, "task", "task", {"title": "Should not persist"})
            store.emit(c, "task.created", "task", {})
            raise RuntimeError("Simulated failure")
    except RuntimeError:
        pass
    with store.tx() as c:
        assert store.get(c, "task", "task", False) is None
        assert not list(c.execute(select(events)))
        assert not list(c.execute(select(jobs)))


def test_interrupted_worker_reclaims_lease(store):
    with store.tx() as c:
        jid = store.enqueue(c, "daily_check", {}, key="recover")
    worker = Worker(store)
    claimed = worker.claim()
    assert claimed["id"] == jid
    with store.tx() as c:
        c.execute(update(jobs).where(jobs.c.id == jid).values(lease_until=time.time() - 1))
    assert worker.run_one()
    with store.tx() as c:
        result = c.execute(select(jobs).where(jobs.c.id == jid)).mappings().one()
        assert result["status"] == "succeeded" and result["attempts"] == 2


def test_failed_job_is_visible_and_bounded(store):
    with store.tx() as c:
        jid = store.enqueue(c, "unknown", {}, key="bad")
    worker = Worker(store)
    for _ in range(3):
        worker.run_one()
        with store.tx() as c:
            c.execute(update(jobs).where(jobs.c.id == jid).values(run_at=0))
    with store.tx() as c:
        result = c.execute(select(jobs).where(jobs.c.id == jid)).mappings().one()
        assert result["status"] == "failed" and result["last_error"]
