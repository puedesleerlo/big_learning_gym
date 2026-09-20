"""A calendar replica with identity, revisions and cancellations. No implicit external writes."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from .planning import timestamp
from .store import digest, now, uid


def upsert_event(store, data, source="manual"):
    if data.get("kind", "commitment") not in {"commitment", "deadline"}:
        raise ValueError("Invalid temporal object")
    if not data.get("title"):
        raise ValueError("Event title is required")
    tz = data.get("timezone", "America/New_York")
    if not data.get("cancelled"):
        if data.get("kind", "commitment") == "commitment":
            if (
                not data.get("start")
                or not data.get("end")
                or timestamp(data["end"], tz) <= timestamp(data["start"], tz)
            ):
                raise ValueError("Commitments require a valid start and end")
        elif not data.get("due"):
            raise ValueError("Deadline requires a due date")
    provider_id = data.get("provider_id") or uid("manual_")
    ident = "cal_" + digest([source, provider_id, data.get("recurrence_id", "")])[:24]
    data = {
        **data,
        "kind": data.get("kind", "commitment"),
        "provider_id": provider_id,
        "source": source,
        "source_authority": data.get(
            "source_authority", "user_confirmed" if source == "manual" else "calendar_source"
        ),
        "timezone": tz,
        "cancelled": bool(data.get("cancelled")),
        "source_revision": str(data.get("source_revision", digest(data))),
    }
    with store.tx() as c:
        old = store.get(c, "calendar", ident, False)
        if old and old["source_revision"] == data["source_revision"]:
            return old
        if old and data.get("sequence", 0) < old.get("sequence", 0):
            return old
        # Imported app-owned allocations acknowledge our own export, never become new obligations.
        if data.get("app_owned"):
            return {"id": ident, "acknowledged": True}
        result = store.put(c, "calendar", ident, {**data, "received_at": now()})
        store.emit(
            c,
            "calendar.changed",
            ident,
            {"before": old, "after": data},
            key="calendar:" + ident + ":" + data["source_revision"],
            source_id=source,
            source_revision=data["source_revision"],
        )
        if data.get("task_id") and data["kind"] == "deadline" and not data["cancelled"]:
            task = store.get(c, "task", data["task_id"])
            # Source authority conflicts require explicit user resolution, not last-write-wins.
            if task.get("deadline_authority") not in {None, source} and task.get("deadline") != data["due"]:
                store.put(
                    c,
                    "calendar_conflict",
                    ident,
                    {
                        "task_id": task["id"],
                        "event_id": ident,
                        "current": task["deadline"],
                        "proposed": data["due"],
                        "status": "unresolved",
                    },
                )
            else:
                store.put(
                    c, "task", task["id"], {**task, "deadline": data["due"], "deadline_authority": source}
                )
        return result


def import_ics(store, raw, source="ics:calendar", timezone_name="America/New_York"):
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("Calendar import limited to 5 MB")
    cal = Calendar.from_ical(raw)
    results = []
    warnings = []
    components = [x for x in cal.walk() if x.name in {"VEVENT", "VTODO"}]
    overrides = {
        (str(x.get("UID")), str(x.get("RECURRENCE-ID"))) for x in components if x.get("RECURRENCE-ID")
    }
    zone = ZoneInfo(timezone_name)

    def encode(value):
        return value.isoformat()

    for event in components:
        provider_id = str(event.get("UID") or "")
        if not provider_id:
            warnings.append("Skipped event without UID")
            continue
        if event.get("X-GYM-OWNED"):
            continue
        cancelled = str(event.get("STATUS", "")) == "CANCELLED"
        due = event.decoded("DUE", None)
        start = event.decoded("DTSTART", None)
        end = event.decoded("DTEND", None)
        deadline = event.name == "VTODO" or str(event.get("X-GYM-KIND", "")) == "deadline"
        value = due or start
        if not value and not cancelled:
            warnings.append(f"No temporal value for {provider_id}")
            continue
        if cancelled and not value:
            with store.tx() as c:
                old = [
                    e
                    for e in store.list(c, "calendar")
                    if e["provider_id"] == provider_id and e["source"] == source
                ]
            for item in old:
                results.append(
                    upsert_event(
                        store,
                        {
                            **item,
                            "cancelled": True,
                            "source_revision": digest(event.to_ical()),
                            "sequence": int(event.get("SEQUENCE", 0)),
                        },
                        source,
                    )
                )
            continue
        if not deadline and end is None:
            duration = event.decoded("DURATION", None)
            end = start + (
                duration or (timedelta(days=1) if not isinstance(start, datetime) else timedelta(0))
            )
            if end == start:
                warnings.append(f"No duration for {provider_id}; confirm its end time")
                continue
        instances = [value]
        if event.get("RRULE"):
            from dateutil.rrule import rrulestr

            dtstart = (
                value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time(), zone)
            )
            if dtstart.tzinfo is None:
                dtstart = dtstart.replace(tzinfo=zone)
            rule = rrulestr(event["RRULE"].to_ical().decode(), dtstart=dtstart)
            lower = datetime.now(zone) - timedelta(days=7)
            upper = datetime.now(zone) + timedelta(days=90)
            instances = list(rule.between(lower, upper, inc=True))
            if len(instances) > 2000:
                raise ValueError("Recurrence expands to too many instances")
            if not isinstance(value, datetime):
                instances = [x.date() for x in instances]
        excluded = set()
        exdates = event.get("EXDATE", [])
        for field in exdates if isinstance(exdates, list) else [exdates]:
            excluded.update(x.dt for x in field.dts)
        for instance in instances:
            if instance in excluded:
                continue
            recurrence = event.decoded("RECURRENCE-ID", None)
            recurrence_id = encode(recurrence or instance) if event.get("RRULE") or recurrence else ""
            if event.get("RRULE") and any(u == provider_id and encode(instance) in r for u, r in overrides):
                continue
            data = {
                "provider_id": provider_id,
                "recurrence_id": recurrence_id,
                "title": str(event.get("SUMMARY", "Untitled")),
                "kind": "deadline" if deadline else "commitment",
                "cancelled": cancelled,
                "timezone": timezone_name,
                "sequence": int(event.get("SEQUENCE", 0)),
                "source_revision": digest([event.to_ical().decode(), recurrence_id]),
                "all_day": not isinstance(instance, datetime),
                "task_id": str(event.get("X-GYM-TASK-ID") or "") or None,
            }
            if deadline:
                data["due"] = encode(instance)
            else:
                data.update(start=encode(instance), end=encode(instance + (end - start)))
            results.append(upsert_event(store, data, source))
    with store.tx() as c:
        store.put(
            c,
            "connector",
            source,
            {
                "source": source,
                "last_success_at": now(),
                "mode": "manual_ics_import",
                "warnings": warnings,
                "recurrence_horizon_days": 90,
                "count": len(results),
            },
        )
    return {"count": len(results), "warnings": warnings, "source": source}


def export_schedule(store):
    with store.tx() as c:
        schedule = store.get(c, "schedule", "active")
    calendar = Calendar()
    calendar.add("prodid", "-//Big Learning Gym//EN")
    calendar.add("version", "2.0")
    for b in schedule["blocks"]:
        e = Event()
        e.add("uid", b["id"] + "@big-learning-gym")
        e.add("summary", b["title"])
        e.add("dtstart", timestamp(b["start"]))
        e.add("dtend", timestamp(b["end"]))
        e.add("dtstamp", datetime.now(timezone.utc))
        e.add("X-GYM-OWNED", "true")
        e.add("description", "Approved learning block. Task: " + b["task_id"])
        calendar.add_component(e)
    return calendar.to_ical()
