"""Local effort estimates and the single deterministic scheduling authority."""

import math
from datetime import datetime, timedelta, timezone
from datetime import time as dtime
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, update

from .store import decisions, now, predictions, uid


def timestamp(value, tz="America/New_York", date_end=False):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if len(value) == 10 and date_end:
        parsed += timedelta(days=1)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(tz))
    return parsed.astimezone(timezone.utc)


def create_task(store, data):
    if data.get("deadline"):
        timestamp(data["deadline"])
    with store.tx() as c:
        for dep in data.get("prerequisites", []):
            store.get(c, "task", dep)
        if data.get("course_id"):
            store.get(c, "course", data["course_id"])
        if data.get("goal_id"):
            store.get(c, "goal", data["goal_id"])
        ident = uid("task_")
        task = store.put(
            c,
            "task",
            ident,
            {**data, "scope_version": 1, "status": "open", "created_at": now(), "progress": []},
        )
        store.emit(c, "task.created", ident, {"scope_version": 1})
        estimate(store, c, task)
        return task


def estimate(store, c, task):
    current = (
        c.execute(
            select(predictions)
            .where(
                predictions.c.target_id == task["id"],
                predictions.c.stale_reason.is_(None),
                predictions.c.quantity == "remaining_effort",
            )
            .order_by(predictions.c.created_at.desc())
        )
        .mappings()
        .first()
    )
    if current:
        return dict(current)
    models = [m for m in store.list(c, "model") if m["role"] == "effort" and m["status"] == "active"]
    model = models[-1] if models else {"id": "effort-prior-v1", "multiplier": 1.0, "upper_multiplier": 1.4}
    base = task["effort_minutes"]
    p50 = max(5, round(base * model["multiplier"]))
    p80 = max(p50, math.ceil(base * model.get("upper_multiplier", 1.4)))
    ident = uid("prediction_")
    result = dict(
        id=ident,
        target_id=task["id"],
        target_version=task["scope_version"],
        quantity="remaining_effort",
        distribution={
            "p50": p50,
            "p80": p80,
            "unit": "active_minutes",
            "calibrated": False,
            "basis": "User remaining-scope estimate and task-type prior; uncertainty is not a guarantee",
        },
        input_state_revision=store.revision(c),
        input_evidence_ids=[e["id"] for e in store.evidence(c, task["id"], 20)],
        model_version=model["id"],
        created_at=now(),
        dependencies=["task:" + task["id"], "model:effort"],
        stale_reason=None,
    )
    c.execute(insert(predictions).values(**result))
    return result


def revise_task(store, ident, changes):
    permitted = {
        "deadline",
        "effort_minutes",
        "blocked_reason",
        "status",
        "at_risk",
        "definition_of_done",
        "active_minutes",
        "note",
        "expected_revision",
    }
    if set(changes) - permitted:
        raise ValueError("Unsupported task change")
    with store.tx() as c:
        task = store.get(c, "task", ident)
        if changes.get("expected_revision") not in {None, task["revision"]}:
            raise ValueError("Task changed; reload first")
        before = task.copy()
        if "deadline" in changes and changes["deadline"]:
            timestamp(changes["deadline"])
        if "effort_minutes" in changes and not 5 <= changes["effort_minutes"] <= 10000:
            raise ValueError("Invalid remaining effort")
        if changes.get("status") not in {None, "open", "complete"}:
            raise ValueError("Invalid status")
        if changes.get("active_minutes", 0) < 0:
            raise ValueError("Active minutes must be nonnegative")
        scope = any(
            k in changes and changes[k] != task.get(k)
            for k in ["effort_minutes", "definition_of_done", "blocked_reason"]
        )
        task.update(
            {k: v for k, v in changes.items() if k not in {"active_minutes", "note", "expected_revision"}}
        )
        if scope:
            task["scope_version"] += 1
            store.invalidate(c, "task:" + ident, "Scope or remaining work changed")
        if changes.get("active_minutes") is not None:
            task["progress"] = [
                *task["progress"],
                {
                    "active_minutes": changes["active_minutes"],
                    "note": changes.get("note", ""),
                    "scope_version": before["scope_version"],
                    "occurred_at": now(),
                    "complete": task["status"] == "complete",
                },
            ]
        result = store.put(c, "task", ident, task)
        kind = (
            "task.scope_changed"
            if scope
            else "task.completed"
            if task["status"] == "complete"
            else "task.deadline_changed"
        )
        store.emit(
            c,
            kind,
            ident,
            {"before": before, "after": task, "actual_active_minutes": changes.get("active_minutes")},
        )
        if scope and task["status"] != "complete":
            estimate(store, c, result)
        return result


def propose_schedule(store, settings):
    tz = settings.get("timezone", "America/New_York")
    zone = ZoneInfo(tz)
    days = int(settings.get("days", 7))
    ceiling = int(settings.get("daily_minutes", 120))
    slack = float(settings.get("slack", 0.2))
    start_date = settings.get("start_date", datetime.now(zone).date().isoformat())
    if not 1 <= days <= 30 or not 15 <= ceiling <= 720 or not 0 <= slack <= 0.5:
        raise ValueError("Invalid planning horizon or workload limit")
    weekdays = settings.get("weekdays", [0, 1, 2, 3, 4])
    begin = dtime.fromisoformat(settings.get("day_start", "09:00"))
    end = dtime.fromisoformat(settings.get("day_end", "18:00"))
    if begin >= end:
        raise ValueError("Availability must end after it starts")
    with store.tx() as c:
        tasks = [t for t in store.list(c, "task") if t["status"] != "complete"]
        all_tasks = {t["id"]: t for t in store.list(c, "task")}
        estimates = {t["id"]: estimate(store, c, t) for t in tasks}
        input_revision = store.revision(c)
        events = [
            e for e in store.list(c, "calendar") if not e.get("cancelled") and e["kind"] == "commitment"
        ]
        previous = store.get(c, "schedule", "active", False)
        pins = [
            b
            for b in (previous or {}).get("blocks", [])
            if b.get("pinned") and timestamp(b["end"]) > datetime.now(timezone.utc)
        ]
        occupied = []
        conflicts = []
        slots = []
        usage = {}
        blocks = []
        for e in events:
            occupied.append((timestamp(e["start"], tz), timestamp(e["end"], tz), e["id"]))
        start = datetime.fromisoformat(start_date).date()
        for d in range(days):
            day = start + timedelta(days=d)
            if day.weekday() not in weekdays:
                continue
            a = datetime.combine(day, begin, zone).astimezone(timezone.utc)
            b = datetime.combine(day, end, zone).astimezone(timezone.utc)
            cursor = a
            while cursor + timedelta(minutes=5) <= b:
                stop = cursor + timedelta(minutes=5)
                if cursor >= datetime.now(timezone.utc) and not any(
                    cursor < y and stop > x for x, y, _ in occupied
                ):
                    slots.append((cursor, stop, day.isoformat()))
                cursor = stop
        free = {a: (b, day) for a, b, day in slots}
        budgets = {day: math.floor(ceiling * (1 - slack) / 5) * 5 for _, _, day in slots}
        task_end = {
            i: datetime.min.replace(tzinfo=timezone.utc)
            for i, t in all_tasks.items()
            if t["status"] == "complete"
        }
        allocated = {}
        failed = set()
        for pin in pins:
            a = timestamp(pin["start"])
            b = timestamp(pin["end"])
            day = a.astimezone(zone).date().isoformat()
            invalid = any(a < y and b > x for x, y, _ in occupied) or any(
                a < timestamp(x["end"]) and b > timestamp(x["start"]) for x in blocks
            )
            task = all_tasks.get(pin["task_id"])
            if not task or task["status"] == "complete":
                continue
            if task.get("deadline") and b > timestamp(task["deadline"], tz):
                invalid = True
            for step in range(int((b - a).total_seconds() / 300)):
                if a + timedelta(minutes=step * 5) not in free:
                    invalid = True
            if invalid:
                conflicts.append(
                    {
                        "task_id": pin["task_id"],
                        "title": pin["title"],
                        "reason": "Pinned block conflicts with current constraints; resolve it before accepting a repair",
                    }
                )
                failed.add(pin["task_id"])
                continue
            blocks.append(pin)
            duration = (b - a).total_seconds() / 60
            usage[day] = usage.get(day, 0) + duration
            allocated[pin["task_id"]] = allocated.get(pin["task_id"], 0) + pin.get("work_minutes", duration)
            for slot in list(free):
                if a <= slot < b:
                    del free[slot]

        def order(t):
            priority = (
                0
                if t["category"] == "academic" and t.get("at_risk")
                else {"research": 1, "academic": 2, "capability": 3, "exploration": 4}[t["category"]]
            )
            return (priority, t.get("deadline") or "9999", t["created_at"])

        exploration_limit = math.floor(sum(budgets.values()) * 0.1 / 5) * 5
        exploration_used = sum(
            b["work_minutes"] + b.get("setup_minutes", 0) for b in blocks if b["category"] == "exploration"
        )
        pending = sorted(tasks, key=order)
        while pending:
            ready = next(
                (
                    t
                    for t in pending
                    if all(d in task_end or d in failed or d not in all_tasks for d in t["prerequisites"])
                ),
                None,
            )
            if ready is None:
                for t in pending:
                    conflicts.append(
                        {
                            "task_id": t["id"],
                            "title": t["title"],
                            "reason": "Dependency cycle or missing predecessor",
                        }
                    )
                break
            t = ready
            pending.remove(t)
            ident = t["id"]
            reason = t.get("blocked_reason") or (
                "Prerequisite is not schedulable"
                if any(d in failed or d not in all_tasks for d in t["prerequisites"])
                else None
            )
            if ident in failed:
                continue
            if reason:
                failed.add(ident)
                conflicts.append({"task_id": ident, "title": t["title"], "reason": reason})
                continue
            earliest = max(
                [task_end[d] for d in t["prerequisites"]] or [datetime.min.replace(tzinfo=timezone.utc)]
            )
            cutoff = (
                timestamp(t["deadline"], tz)
                if t.get("deadline") and t["deadline_kind"] == "hard"
                else datetime.max.replace(tzinfo=timezone.utc)
            )
            work = math.ceil(estimates[ident]["distribution"]["p80"] / 5) * 5 - allocated.get(ident, 0)
            minimum = math.ceil(t["min_block"] / 5) * 5
            if work > 0:
                work = max(minimum, work)
            setup = math.ceil(t.get("setup_minutes", 0) / 5) * 5
            required = max(0, work)
            own = []
            exploration_cap = max(0, exploration_limit - exploration_used)
            if t["category"] == "exploration":
                work = min(work, exploration_cap)
            while work > 0:
                picked = None
                for a in sorted(free):
                    if a < earliest:
                        continue
                    _, day = free[a]
                    capacity = budgets[day] - usage.get(day, 0)
                    max_duration = (
                        min(t["max_block"] + setup, work + setup, capacity)
                        if t["splittable"]
                        else work + setup
                    )
                    if t["category"] == "exploration":
                        max_duration = min(max_duration, exploration_limit - exploration_used)
                    if max_duration > capacity:
                        continue
                    duration = 0
                    while duration + 5 <= max_duration:
                        slot = a + timedelta(minutes=duration)
                        if slot not in free or free[slot][1] != day or free[slot][0] > cutoff:
                            break
                        duration += 5
                    if t["splittable"] and 0 < work - (duration - setup) < minimum:
                        duration -= minimum - (work - (duration - setup))
                    min_work = minimum
                    if duration >= min_work + setup and (t["splittable"] or duration >= work + setup):
                        picked = (a, day, duration)
                        break
                if not picked:
                    break
                a, day, duration = picked
                b = a + timedelta(minutes=duration)
                own.append(
                    {
                        "id": uid("block_"),
                        "task_id": ident,
                        "title": t["title"],
                        "category": t["category"],
                        "start": a.isoformat(),
                        "end": b.isoformat(),
                        "work_minutes": duration - setup,
                        "setup_minutes": setup,
                        "pinned": False,
                    }
                )
                for step in range(duration // 5):
                    free.pop(a + timedelta(minutes=step * 5))
                usage[day] = usage.get(day, 0) + duration
                if t["category"] == "exploration":
                    exploration_used += duration
                work -= duration - setup
                earliest = b
            blocks.extend(own)
            if work > 0 or required > exploration_cap and t["category"] == "exploration":
                failed.add(ident)
                conflicts.append(
                    {
                        "task_id": ident,
                        "title": t["title"],
                        "reason": "Remaining effort does not fit available blocks under the current policy",
                        "unscheduled_minutes": max(
                            work, required - exploration_cap if t["category"] == "exploration" else 0
                        ),
                        "options": ["Reduce scope", "Change the deadline", "Revise availability"],
                    }
                )
            else:
                own_ends = [timestamp(b["end"]) for b in blocks if b["task_id"] == ident]
                task_end[ident] = max(own_ends or [earliest])
        for day, total in usage.items():
            if total > budgets.get(day, 0):
                conflicts.append(
                    {
                        "title": "Pinned workload",
                        "reason": f"Pinned blocks exceed the workload limit on {day}",
                    }
                )
        # Pins are user decisions, but cannot silently override changed prerequisite feasibility.
        for t in tasks:
            own = [b for b in blocks if b["task_id"] == t["id"]]
            if own:
                first = min(timestamp(b["start"]) for b in own)
                if any(
                    dep in failed or dep not in task_end or task_end[dep] > first
                    for dep in t["prerequisites"]
                ):
                    conflicts.append(
                        {
                            "task_id": t["id"],
                            "title": t["title"],
                            "reason": "A pinned or planned block starts before its prerequisite can finish",
                        }
                    )
        proposal = {
            "blocks": sorted(blocks, key=lambda b: b["start"]),
            "conflicts": conflicts,
            "settings": settings,
            "policy": "hierarchical-greedy-v1",
            "feasible": not conflicts,
            "scope": "Current tasks and supplied availability",
            "date_only_policy": "Date-only deadlines are preserved; preparation is allocated before that date until a time is confirmed.",
        }
        ident = uid("decision_")
        c.execute(
            insert(decisions).values(
                id=ident,
                decision_type="schedule",
                input_state_revision=input_revision,
                prediction_ids=[p["id"] for p in estimates.values()],
                proposed_action=proposal,
                alternatives=["Keep the accepted plan", "Reduce scope", "Adjust availability"],
                rationale="Protect endangered academic work, advance research, strengthen capabilities, cap exploration at 10%, preserve slack.",
                policy_version="hierarchical-greedy-v1",
                approval_status="proposed",
                execution_status="not_executed",
                created_at=now(),
            )
        )
        store.put(c, "planner_settings", "default", settings)
        return {"id": ident, "input_state_revision": input_revision, **proposal}


def accept_schedule(store, decision_id):
    with store.tx() as c:
        row = c.execute(select(decisions).where(decisions.c.id == decision_id)).mappings().first()
        if not row or row["decision_type"] != "schedule":
            raise ValueError("Schedule proposal not found")
        if row["approval_status"] == "accepted":
            return store.get(c, "schedule", "active")
        if row["input_state_revision"] != store.revision(c):
            raise ValueError("The plan is stale because inputs changed. Generate a fresh proposal.")
        if not row["proposed_action"]["feasible"]:
            raise ValueError("Resolve scheduling conflicts before accepting this plan")
        for pid in row["prediction_ids"]:
            p = c.execute(select(predictions).where(predictions.c.id == pid)).mappings().one()
            if p["stale_reason"]:
                raise ValueError("The plan uses a stale estimate. Replan first.")
        schedule = store.put(
            c,
            "schedule",
            "active",
            {**row["proposed_action"], "decision_id": decision_id, "accepted_at": now()},
        )
        store.put(c, "schedule_version", decision_id, schedule)
        c.execute(
            update(decisions)
            .where(decisions.c.id == decision_id)
            .values(approval_status="accepted", execution_status="applied_locally")
        )
        store.emit(
            c, "schedule.accepted", decision_id, {"decision_id": decision_id}, key="accept:" + decision_id
        )
        return schedule


def pin_block(store, block_id, pinned):
    with store.tx() as c:
        plan = store.get(c, "schedule", "active")
        block = next((b for b in plan["blocks"] if b["id"] == block_id), None)
        if not block:
            raise ValueError("Block not found")
        block["pinned"] = bool(pinned)
        store.put(c, "schedule", "active", plan)
        store.emit(c, "schedule.override", block_id, {"pinned": bool(pinned)})
        return plan
