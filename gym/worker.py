"""Database-backed jobs with leases, retries, debounce and catch-up on resume."""

import argparse
import threading
import time

from sqlalchemy import or_, select, update

from .store import events, jobs, now, uid


class Worker:
    def __init__(self, store, router=None):
        from .llm import Router

        self.store = store
        self.router = router or Router(store)

    def claim(self):
        with self.store.tx() as c:
            q = (
                select(jobs)
                .where(
                    or_(
                        (jobs.c.status == "queued") & (jobs.c.run_at <= time.time()),
                        (jobs.c.status == "running") & (jobs.c.lease_until < time.time()),
                    )
                )
                .order_by(jobs.c.priority, jobs.c.run_at)
                .limit(1)
            )
            if self.store.engine.dialect.name == "postgresql":
                q = q.with_for_update(skip_locked=True)
            row = c.execute(q).mappings().first()
            if not row:
                return None
            row = dict(row)
            if row["attempts"] >= row["max_attempts"]:
                c.execute(
                    update(jobs)
                    .where(jobs.c.id == row["id"])
                    .values(status="failed", last_error="Retry budget exhausted after interruption")
                )
                return None
            token = uid("lease_")
            c.execute(
                update(jobs)
                .where(jobs.c.id == row["id"])
                .values(
                    status="running",
                    attempts=row["attempts"] + 1,
                    lease_until=time.time() + 900,
                    lease_token=token,
                )
            )
            return {**row, "attempts": row["attempts"] + 1, "lease_token": token}

    def run_one(self):
        job = self.claim()
        if not job:
            return False
        stopped = threading.Event()

        def renew():
            while not stopped.wait(30):
                with self.store.tx() as c:
                    c.execute(
                        update(jobs)
                        .where(
                            jobs.c.id == job["id"],
                            jobs.c.lease_token == job["lease_token"],
                            jobs.c.status == "running",
                        )
                        .values(lease_until=time.time() + 900)
                    )

        renewal = threading.Thread(target=renew, daemon=True)
        renewal.start()
        try:
            self.dispatch(job["kind"], job["payload"])
        except Exception as error:
            # Error messages are safe module errors; provider bodies and prompts never enter the queue.
            safe = (
                str(error)
                if isinstance(error, ValueError)
                else f"{type(error).__name__}: check server logs or retry after repair"
            )
            with self.store.tx() as c:
                status = "failed" if job["attempts"] >= job["max_attempts"] else "queued"
                c.execute(
                    update(jobs)
                    .where(jobs.c.id == job["id"], jobs.c.lease_token == job["lease_token"])
                    .values(
                        status=status,
                        last_error=safe[:600],
                        run_at=time.time() + min(300, 2 ** job["attempts"] * 5),
                        lease_until=0,
                    )
                )
                if job["kind"] == "generate":
                    bp = self.store.get(c, "blueprint", job["payload"]["blueprint_id"])
                    self.store.put(
                        c,
                        "blueprint",
                        bp["id"],
                        {**bp, "status": "failed" if status == "failed" else "retrying", "error": safe[:600]},
                    )
        else:
            with self.store.tx() as c:
                c.execute(
                    update(jobs)
                    .where(jobs.c.id == job["id"], jobs.c.lease_token == job["lease_token"])
                    .values(status="succeeded", finished_at=now(), lease_until=0, last_error=None)
                )
                self.store.put(
                    c, "job_health", job["kind"], {"last_success_at": now(), "last_job_id": job["id"]}
                )
        finally:
            stopped.set()
            renewal.join(timeout=2)
        return True

    def dispatch(self, kind, payload):
        if kind == "operational":
            return self.operational(payload["event_id"])
        if kind == "generate":
            from .generation import generate

            return generate(self.store, self.router, payload["blueprint_id"])
        if kind == "assess":
            from .assessment import assess_attempt

            return assess_attempt(self.store, self.router, payload["attempt_id"])
        if kind == "profile":
            from .assignments import generate_profile

            return generate_profile(self.store, self.router, payload["profile_id"])
        if kind == "assess_submission":
            from .assignments import assess_submission

            return assess_submission(self.store, self.router, payload["submission_id"])
        if kind == "extract_rubric":
            from .assignments import extract_rubric

            return extract_rubric(self.store, self.router, payload["source_id"])
        if kind == "critique":
            from .assessment import critique_artifact

            return critique_artifact(self.store, self.router, payload["version_id"])
        if kind == "interpret":
            from .generation import interpret_source

            return interpret_source(self.store, self.router, payload["source_id"])
        if kind == "evaluate":
            from .adaptation import evaluate

            return evaluate(self.store)
        if kind in {"repair_schedule", "daily_check"}:
            from .planning import propose_schedule

            with self.store.tx() as c:
                settings = self.store.get(c, "planner_settings", "default", False)
            if settings:
                settings = {k: v for k, v in settings.items() if k not in {"id", "revision"}}
                if kind == "daily_check":
                    settings.pop("start_date", None)
                return propose_schedule(self.store, settings)
            return
        raise ValueError("Unknown job type: " + kind)

    def operational(self, event_id):
        with self.store.tx() as c:
            event = c.execute(select(events).where(events.c.id == event_id)).mappings().one()
            kind = event["event_type"]
            if kind == "source.ingested":
                for old in event["payload"].get("previous_version_ids", []):
                    self.store.invalidate(c, "source:" + old, "Source version changed")
            if kind in {
                "calendar.changed",
                "task.created",
                "task.scope_changed",
                "task.deadline_changed",
                "task.completed",
                "schedule.override",
                "model.activated",
            }:
                # Events in the same short window share one repair, preserving atomic outbox semantics.
                self.store.enqueue(
                    c, "repair_schedule", {}, key=f"repair:{int(time.time() // 30)}", priority=30, delay=30
                )
            if kind == "model.activated":
                from .planning import estimate

                for task in self.store.list(c, "task"):
                    if task["status"] != "complete":
                        estimate(self.store, c, task)

    def maintenance(self):
        from datetime import datetime, timezone

        date = datetime.now(timezone.utc)
        with self.store.tx() as c:
            self.store.enqueue(c, "daily_check", {}, key="daily:" + date.date().isoformat(), priority=50)
            # No labels means no expensive training or LLM work. Evaluation is deterministic.
            self.store.enqueue(
                c,
                "evaluate",
                {},
                key=f"weekly:{date.isocalendar().year}:{date.isocalendar().week}",
                priority=60,
            )
            self.store.put(c, "job_health", "worker", {"heartbeat_at": now()})


def main():
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    from .workspaces import load_workspace

    worker = Worker(load_workspace().store())
    last = 0
    while True:
        if time.time() - last > 30:
            worker.maintenance()
            last = time.time()
        ran = worker.run_one()
        if args.once:
            break
        if not ran:
            time.sleep(1)


if __name__ == "__main__":
    main()
