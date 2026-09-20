"""Guided study content and observed activity, separate from assessed attempts.

The server measures time; a missing heartbeat never earns more than 45 seconds.
Reading and toy experiments record preparation, not mastery or task completion.
Only a not-yet-answered practice session may be linked, so preparation can be
disclosed before its attempts enter the existing learner-evidence pipeline.
"""

import json
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, HttpUrl, JsonValue, model_validator

from .authoring import Provenance
from .contracts import Strict
from .store import digest, now, uid

HEARTBEAT_CAP_SECONDS = 45.0


class LabSource(Strict):
    id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    kind: str = Field(default="reference", max_length=100)
    year: int | None = Field(default=None, ge=1000, le=3000)
    authors: str = Field(default="", max_length=3000)
    summary: str = Field(default="", max_length=6000)
    status: str = Field(default="", max_length=1000)


class WorkedExample(Strict):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=15000)


class PaperBridge(Strict):
    source_id: str
    why_it_matters: str = Field(max_length=6000)
    read_first: str = Field(max_length=6000)
    claim: str = Field(max_length=6000)
    assumptions: list[str] = Field(max_length=30)
    limits: list[str] = Field(max_length=30)
    exercise: str = Field(max_length=6000)


class LabLesson(Strict):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    stage: str = Field(max_length=100)
    minutes: int = Field(ge=1, le=10000)
    prerequisites: list[str] = Field(default_factory=list, max_length=100)
    question: str = Field(min_length=1, max_length=5000)
    objectives: list[str] = Field(min_length=1, max_length=30)
    intuition: list[str] = Field(min_length=1, max_length=30)
    worked_example: WorkedExample
    takeaways: list[str] = Field(min_length=1, max_length=30)
    pitfall: str = Field(max_length=5000)
    experiment: Literal["", "intervention", "simpson", "collider", "discovery"] = ""
    experiment_task: str = Field(default="", max_length=6000)
    reflection: str = Field(default="", max_length=6000)
    source_ids: list[str] = Field(min_length=1, max_length=100)
    paper_bridge: PaperBridge


class LabWrite(Strict):
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(max_length=6000)
    lessons: list[LabLesson] = Field(min_length=1, max_length=100)
    sources: list[LabSource] = Field(min_length=1, max_length=100)
    provenance: Provenance

    @model_validator(mode="after")
    def references(self):
        lessons = {lesson.id: lesson for lesson in self.lessons}
        sources = {source.id for source in self.sources}
        if len(lessons) != len(self.lessons) or len(sources) != len(self.sources):
            raise ValueError("Lesson and catalog source IDs must be unique")
        visiting, visited = set(), set()

        def visit(ident):
            if ident not in lessons:
                raise ValueError("A prerequisite must refer to a published lab lesson")
            if ident in visiting:
                raise ValueError("Lab prerequisites cannot contain a cycle")
            if ident in visited:
                return
            visiting.add(ident)
            lesson = lessons[ident]
            if len(set(lesson.source_ids)) != len(lesson.source_ids):
                raise ValueError("Lesson source references must be unique")
            if lesson.paper_bridge.source_id not in sources:
                raise ValueError("Paper bridge must refer to a catalog source")
            for prerequisite in lesson.prerequisites:
                visit(prerequisite)
            visiting.remove(ident)
            visited.add(ident)

        for ident in lessons:
            visit(ident)
        return self


class ActivityStart(Strict):
    module: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=200)


class ActivityEvent(Strict):
    action: Literal["heartbeat", "pause", "resume", "reading", "help", "experiment", "finish"]
    idempotency_key: str = Field(min_length=1, max_length=200)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    reflection: str | None = Field(default=None, max_length=12000)
    session_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def bounded_parameters(self):
        if len(json.dumps(self.parameters, allow_nan=False)) > 16000:
            raise ValueError("Experiment parameters must be at most 16000 characters")
        if self.session_id and self.action != "finish":
            raise ValueError("A session can only be linked on finish or through link-session")
        return self


class SessionLink(Strict):
    session_id: str = Field(min_length=1, max_length=200)


def _required(store, c, kind, ident):
    value = store.get(c, kind, ident, False)
    if value is None:
        raise HTTPException(404, detail=f"{kind} not found")
    return value


def _seconds(start, end):
    return max(0.0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())


def _tick(activity, timestamp):
    if activity["status"] == "active" and activity["running"]:
        activity["active_seconds"] += min(HEARTBEAT_CAP_SECONDS, _seconds(activity["last_tick"], timestamp))
    activity["last_tick"] = timestamp


def _emit(store, c, activity, action, *, parameters=None, reflection=None):
    store.emit(c, "lab.activity." + action, activity["id"], {
        "course_id": activity["course_id"], "module": activity["module"],
        "lab_revision": activity["lab_revision"], "source_ids": activity["source_ids"],
        "active_seconds": round(activity["active_seconds"], 2),
        "elapsed_seconds": round(_seconds(activity["started_at"], activity["last_tick"]), 2),
        "running": activity["running"], "session_id": activity.get("session_id"),
        "reading_count": activity["reading_count"], "experiment_count": activity["experiment_count"],
        "help_count": activity["help_count"], "parameters": parameters or {},
        "reflection": reflection, "evidence_kind": "guided_preparation",
        "assessed": False, "task_completion": False,
    }, source_id=activity["lab_version_id"], source_revision=str(activity["lab_revision"]))


def _pause_others(store, c, timestamp, except_id=None):
    # One learner has one foreground lab timer, including across courses/tabs.
    for other in store.list(c, "lab_activity"):
        if other["id"] != except_id and other["status"] == "active" and other["running"]:
            _tick(other, timestamp)
            other["running"] = False
            store.put(c, "lab_activity", other["id"], other)
            _emit(store, c, other, "pause", parameters={"reason": "another_lab_started"})


def _receipt(store, c, scope, key, payload):
    ident = "lab-receipt:" + digest([scope, key])
    old = store.get(c, "lab_receipt", ident, False)
    if old and old["payload_hash"] != digest(payload):
        raise HTTPException(409, detail="Idempotency key already used for different content")
    return ident, old


def publish_lab(store, course_id, model):
    with store.tx() as c:
        course = _required(store, c, "course", course_id)
        modules = {m["id"] for m in course.get("modules", [])}
        for lesson in model.lessons:
            if lesson.id not in modules:
                raise HTTPException(400, detail="Every lab lesson must be a module of its course")
            for source_id in lesson.source_ids:
                source = _required(store, c, "source", source_id)
                if source.get("course_id") != course_id:
                    raise HTTPException(400, detail="Lesson sources must belong to this course")
                if source.get("reconstruction_status") != "confirmed":
                    raise HTTPException(400, detail="Confirm source reconstruction before publishing a lab")
                if source.get("role") not in {"instruction", "research"}:
                    raise HTTPException(400, detail="Lab sources must be instruction or research material")
        old = store.get(c, "lab", course_id, False)
        if model.expected_revision != (old["revision"] if old else 0):
            raise HTTPException(409, detail="Lab changed; read the current revision before publishing")
        data = model.model_dump(mode="json", exclude={"expected_revision"})
        data.update(course_id=course_id, published_at=now())
        lab = store.put(c, "lab", course_id, data)
        version_id = f"lab:{course_id}:{lab['revision']}"
        store.put(c, "lab_version", version_id, {**data, "lab_revision": lab["revision"]})
        if not course.get("has_lab"):
            store.put(c, "course", course_id, {**course, "has_lab": True})
        store.emit(c, "lab.published", course_id, {
            "lab_revision": lab["revision"], "lab_version_id": version_id,
            "module_ids": [lesson.id for lesson in model.lessons], "provenance": data["provenance"],
        })
        return lab


def _practice_outcome(store, c, activity):
    session_id = activity.get("session_id")
    if not session_id:
        return None
    session = _required(store, c, "session", session_id)
    attempts = [a for a in store.list(c, "attempt") if a.get("session_id") == session_id]
    scored = [a for a in attempts if a.get("score") is not None]
    snapshots = session.get("snapshots", {})
    max_score = sum(item.get("points", 0) for item in snapshots.values())
    # No answers, explanations, keys, or item snapshots enter this projection.
    return {
        "session_id": session_id, "status": session["status"], "mode": session["mode"],
        "completion": session.get("completion", "in_progress"),
        "attempt_count": len(attempts), "assessed_count": len(scored),
        "pending_count": sum(a.get("status") == "pending" for a in attempts),
        "score": sum(a["score"] for a in scored), "max_score": max_score,
        "active_seconds": session.get("active_seconds", 0),
        "assisted_attempt_count": sum(bool(a.get("assistance")) for a in attempts),
        "previously_exposed_attempt_count": sum(bool(a.get("previous_exposures")) for a in attempts),
        "provisional": any(a.get("assessor_type") == "llm" for a in attempts),
        "attempts": [{
            key: a.get(key) for key in (
                "id", "item_id", "status", "score", "active_seconds", "created_at",
                "assistance", "previous_exposures", "assessor_type", "event_id",
            )
        } for a in attempts],
        "interpretation": "Observed practice outcomes after guided preparation; no causal attribution or mastery guarantee.",
    }


def activity_view(store, c, activity):
    result = {k: v for k, v in activity.items() if k != "start_idempotency_key"}
    end = activity.get("finished_at") or now()
    result["active_seconds"] = round(activity["active_seconds"], 2)
    result["elapsed_seconds"] = round(_seconds(activity["started_at"], end), 2)
    result["interruption_seconds"] = round(max(0, result["elapsed_seconds"] - result["active_seconds"]), 2)
    result["practice_outcome"] = _practice_outcome(store, c, activity)
    result["study_finished"] = activity["status"] == "finished"
    result["mastery_awarded"] = False
    return result


def get_lab(store, course_id):
    with store.tx() as c:
        lab = _required(store, c, "lab", course_id)
        activities = [activity_view(store, c, activity) for activity in store.list(c, "lab_activity")
                      if activity["course_id"] == course_id]
        return {**lab, "activities": activities, "activity_summary": {
            "active_seconds": round(sum(a["active_seconds"] for a in activities), 2),
            "study_visits": len(activities), "finished_visits": sum(a["study_finished"] for a in activities),
            "practice_linked_visits": sum(bool(a.get("session_id")) for a in activities),
            "mastery_awarded": False,
        }}


def start_activity(store, course_id, model):
    with store.tx() as c:
        payload = model.model_dump()
        receipt_id, previous = _receipt(store, c, "start:" + course_id, model.idempotency_key, payload)
        if previous:
            return activity_view(store, c, _required(store, c, "lab_activity", previous["activity_id"]))
        lab = _required(store, c, "lab", course_id)
        lesson = next((entry for entry in lab["lessons"] if entry["id"] == model.module), None)
        if lesson is None:
            raise HTTPException(400, detail="Module is not published in this lab")
        timestamp = now()
        _pause_others(store, c, timestamp)
        activity = store.put(c, "lab_activity", uid("lab_activity_"), {
            "course_id": course_id, "module": model.module, "lab_revision": lab["revision"],
            "lab_version_id": f"lab:{course_id}:{lab['revision']}", "source_ids": lesson["source_ids"],
            "experiment": lesson["experiment"], "status": "active", "running": True,
            "active_seconds": 0.0, "started_at": timestamp, "last_tick": timestamp,
            "reading_count": 0, "experiment_count": 0, "help_count": 0,
            "reflection": "", "session_id": None,
        })
        _emit(store, c, activity, "started")
        store.put(c, "lab_receipt", receipt_id, {"payload_hash": digest(payload), "activity_id": activity["id"]})
        return activity_view(store, c, activity)


def _link(store, c, activity, session_id, timestamp):
    if activity.get("session_id"):
        if activity["session_id"] != session_id:
            raise HTTPException(409, detail="This visit already links a different practice session")
        return
    session = _required(store, c, "session", session_id)
    if session.get("course_id") != activity["course_id"] or session.get("module") != activity["module"]:
        raise HTTPException(400, detail="Practice session must belong to the same course and module")
    if session.get("mode") not in {"practice", "transfer"} or session.get("status") != "active":
        raise HTTPException(400, detail="Link an active practice or transfer session before answering")
    if datetime.fromisoformat(session["started_at"]) < datetime.fromisoformat(activity["started_at"]):
        raise HTTPException(400, detail="Practice session must start after this study visit began")
    if any(a.get("session_id") == session_id for a in store.list(c, "attempt")):
        raise HTTPException(409, detail="Link practice before answering so preparation is recorded honestly")
    if any(a.get("session_id") == session_id and a["id"] != activity["id"]
           for a in store.list(c, "lab_activity")):
        raise HTTPException(409, detail="Practice session is already linked to another study visit")
    exposed = any(activity[k] for k in ("reading_count", "experiment_count", "help_count"))
    if exposed:
        session["guided_activity_id"] = activity["id"]
        assistance = session.setdefault("assistance", {})
        for item_id in session["item_ids"]:
            aids = assistance.setdefault(item_id, [])
            if "lab_materials" not in aids:
                aids.append("lab_materials")
        store.put(c, "session", session_id, session)
        store.emit(c, "assistance.requested", session_id, {
            "kind": "lab_materials", "item_ids": session["item_ids"],
            "lab_activity_id": activity["id"], "module": activity["module"],
            "source_ids": activity["source_ids"],
        })
    if activity["status"] == "active":
        _tick(activity, timestamp)
        activity.update(status="finished", running=False, finished_at=timestamp)
        _emit(store, c, activity, "finish", parameters={"reason": "practice_started"})
    activity["session_id"] = session_id
    _emit(store, c, activity, "session_linked")


def record_event(store, ident, model):
    with store.tx() as c:
        activity = _required(store, c, "lab_activity", ident)
        payload = model.model_dump(mode="json")
        receipt_id, previous = _receipt(store, c, "event:" + ident, model.idempotency_key, payload)
        if previous:
            return activity_view(store, c, activity)
        if activity["status"] != "active":
            raise HTTPException(409, detail="Study visit is already finished")
        if model.action == "experiment" and not activity["experiment"]:
            raise HTTPException(400, detail="This lesson does not publish a toy experiment")
        timestamp = now()
        _tick(activity, timestamp)
        if model.action == "pause":
            activity["running"] = False
        elif model.action == "resume":
            _pause_others(store, c, timestamp, except_id=ident)
            activity["running"] = True
        elif model.action in {"reading", "help", "experiment"}:
            activity[model.action + "_count"] += 1
        elif model.action == "finish":
            activity.update(status="finished", running=False, finished_at=timestamp)
        if model.reflection is not None:
            activity["reflection"] = model.reflection
        if model.session_id:
            _link(store, c, activity, model.session_id, timestamp)
        _emit(store, c, activity, model.action, parameters=model.parameters, reflection=model.reflection)
        activity = store.put(c, "lab_activity", ident, activity)
        store.put(c, "lab_receipt", receipt_id, {"payload_hash": digest(payload), "activity_id": ident})
        return activity_view(store, c, activity)


def link_session(store, ident, model):
    with store.tx() as c:
        activity = _required(store, c, "lab_activity", ident)
        already_linked = activity.get("session_id") == model.session_id
        _link(store, c, activity, model.session_id, now())
        if not already_linked:
            activity = store.put(c, "lab_activity", ident, activity)
        return activity_view(store, c, activity)


def register_lab_api(app, store):
    @app.put("/api/labs/{course_id}", tags=["labs"])
    def publish(course_id: str, body: LabWrite):
        """Publish versioned study presentation. Assessment keys are forbidden."""
        return publish_lab(store, course_id, body)

    @app.get("/api/labs/{course_id}", tags=["labs"])
    def read_lab(course_id: str):
        return get_lab(store, course_id)

    @app.post("/api/labs/{course_id}/activities", tags=["labs"])
    def start(course_id: str, body: ActivityStart):
        return start_activity(store, course_id, body)

    @app.post("/api/lab-activities/{ident}/events", tags=["labs"])
    def event(ident: str, body: ActivityEvent):
        return record_event(store, ident, body)

    @app.post("/api/lab-activities/{ident}/link-session", tags=["labs"])
    def link(ident: str, body: SessionLink):
        return link_session(store, ident, body)

    @app.get("/api/lab-activities/{ident}", tags=["labs"])
    def read_activity(ident: str):
        with store.tx() as c:
            return activity_view(store, c, _required(store, c, "lab_activity", ident))
