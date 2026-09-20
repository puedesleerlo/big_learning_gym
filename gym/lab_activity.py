"""Guided study content and observed activity, separate from assessed attempts.

The server measures time; a missing heartbeat never earns more than 45 seconds.
Reading and toy experiments record preparation, not mastery or task completion.
Only a not-yet-answered practice session may be linked, so preparation can be
disclosed before its attempts enter the existing learner-evidence pipeline.
"""

import json
import math
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, HttpUrl, JsonValue, model_validator

from .authoring import Provenance
from .contracts import Strict
from .lab_blocks import ActivityBlock, activity_types
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
    module: str | None = Field(default=None, min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    stage: str = Field(default="", max_length=100)
    minutes: int = Field(ge=1, le=10000)
    prerequisites: list[str] = Field(default_factory=list, max_length=100)
    question: str = Field(default="", max_length=5000)
    objectives: list[str] = Field(default_factory=list, max_length=30)
    intuition: list[str] = Field(default_factory=list, max_length=30)
    worked_example: WorkedExample | None = None
    takeaways: list[str] = Field(default_factory=list, max_length=30)
    pitfall: str = Field(default="", max_length=5000)
    experiment: Literal["", "intervention", "simpson", "collider", "discovery"] = ""
    experiment_task: str = Field(default="", max_length=6000)
    reflection: str = Field(default="", max_length=6000)
    source_ids: list[str] = Field(min_length=1, max_length=100)
    paper_bridge: PaperBridge | None = None
    activities: list[ActivityBlock] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def activity_ids(self):
        self.module = self.module or self.id
        if len({block.id for block in self.activities}) != len(self.activities):
            raise ValueError("Activity IDs must be unique within each lesson")
        if not (self.activities or self.intuition or self.worked_example or self.experiment or self.experiment_task):
            raise ValueError("A lesson needs activities or a legacy teaching presentation")
        if sum(block.type == "assessment" for block in self.activities) > 1:
            raise ValueError("A lesson supports one linked assessment per study visit")
        return self


class LabWrite(Strict):
    course_id: str | None = Field(default=None, min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(max_length=6000)
    lessons: list[LabLesson] = Field(min_length=1, max_length=100)
    sources: list[LabSource] = Field(default_factory=list, max_length=100)
    objectives: list[str] = Field(default_factory=list, max_length=30)
    prerequisite_lab_ids: list[str] = Field(default_factory=list, max_length=100)
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
            if lesson.paper_bridge and lesson.paper_bridge.source_id not in sources:
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
    lesson_id: str | None = Field(default=None, min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=200)


class ActivityEvent(Strict):
    action: Literal["heartbeat", "pause", "resume", "reading", "help", "experiment", "response", "media", "visualization", "finish"]
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
        "lab_id": activity.get("lab_id", activity["course_id"]),
        "lesson_id": activity.get("lesson_id", activity["module"]),
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


def _validate_lab(store, c, ident, model):
    if len(ident) > 200 or not ident or any(char in ident for char in "/\\?#"):
        raise HTTPException(400, detail="Use a stable lab ID without URL delimiters")
    old = store.get(c, "lab", ident, False)
    course_id = model.course_id or (old["course_id"] if old else ident)
    if old and old["course_id"] != course_id:
        raise HTTPException(409, detail="A lab cannot change its owning course")
    if model.expected_revision != (old["revision"] if old else 0):
        raise HTTPException(409, detail="Lab changed; read the current revision before publishing")
    course = _required(store, c, "course", course_id)
    modules = {m["id"] for m in course.get("modules", [])}
    warnings = []
    items = store.list(c, "item")
    for lesson in model.lessons:
        if lesson.module not in modules:
            raise HTTPException(400, detail="Every lab lesson must reference a module of its course")
        for source_id in lesson.source_ids:
            source = _required(store, c, "source", source_id)
            if source.get("course_id") != course_id:
                raise HTTPException(400, detail="Lesson sources must belong to this course")
            if source.get("reconstruction_status") != "confirmed":
                raise HTTPException(400, detail="Confirm source reconstruction before publishing a lab")
            if source.get("role") not in {"instruction", "research"}:
                raise HTTPException(400, detail="Lab sources must be instruction or research material")
        for block in lesson.activities:
            if block.type == "coursework":
                assignment = _required(store, c, "assignment", block.assignment_id)
                if assignment.get("course_id") != course_id:
                    raise HTTPException(400, detail="Coursework must belong to the lab's course")
                rubric = _required(store, c, "rubric_version", assignment.get("rubric_version_id"))
                if rubric.get("course_id") and rubric["course_id"] != course_id:
                    raise HTTPException(400, detail="Coursework rubric must belong to the lab's course")
            elif block.type == "assessment":
                available = sum(i.get("course_id") == course_id and i.get("module") == lesson.module
                                and i.get("pool") == block.mode and i.get("status") == "active" for i in items)
                if available < block.count:
                    warnings.append(f"{lesson.title}: {available} active {block.mode} items for a requested {block.count}; author more questions before practice.")
    if len(set(model.prerequisite_lab_ids)) != len(model.prerequisite_lab_ids):
        raise HTTPException(400, detail="Lab prerequisites must be unique")
    visited, visiting = set(), {ident}

    def visit(other_id):
        if other_id in visiting:
            raise HTTPException(400, detail="Lab prerequisites cannot contain a cycle")
        if other_id in visited:
            return
        other = _required(store, c, "lab", other_id)
        if other["course_id"] != course_id:
            raise HTTPException(400, detail="Lab prerequisites must belong to this course")
        visiting.add(other_id)
        for prerequisite in other.get("prerequisite_lab_ids", []):
            visit(prerequisite)
        visiting.remove(other_id)
        visited.add(other_id)

    for other_id in model.prerequisite_lab_ids:
        visit(other_id)
    data = model.model_dump(mode="json", exclude={"expected_revision"})
    data["course_id"] = course_id
    return data, course, warnings


def preview_lab(store, ident, model):
    with store.tx() as c:
        data, course, warnings = _validate_lab(store, c, ident, model)
        return {"valid": True, "warnings": warnings, "lab": {
            **data, "id": ident, "course_title": course["title"], "revision": model.expected_revision,
            "preview": True, "activities": [], "activity_summary": _activity_summary([]),
        }}


def publish_lab(store, ident, model):
    with store.tx() as c:
        data, course, _ = _validate_lab(store, c, ident, model)
        data["published_at"] = now()
        lab = store.put(c, "lab", ident, data)
        version_id = f"lab:{ident}:{lab['revision']}"
        store.put(c, "lab_version", version_id, {**data, "lab_revision": lab["revision"]})
        if not course.get("has_lab"):
            store.put(c, "course", course["id"], {**course, "has_lab": True})
        store.emit(c, "lab.published", ident, {
            "course_id": course["id"], "lab_id": ident,
            "lab_revision": lab["revision"], "lab_version_id": version_id,
            "module_ids": sorted({lesson.module for lesson in model.lessons}), "provenance": data["provenance"],
        })
        return lab


def _practice_outcome(store, c, activity):
    session_id = activity.get("session_id")
    if not session_id:
        return None
    session = _required(store, c, "session", session_id)
    attempts = [a for a in store.list(c, "attempt") if a.get("session_id") == session_id]
    scored = [a for a in attempts if a.get("score") is not None and not a.get("invalidated")]
    invalidated_items = {a["item_id"] for a in attempts if a.get("invalidated")}
    snapshots = session.get("snapshots", {})
    max_score = sum(item.get("points", 0) for ident, item in snapshots.items() if ident not in invalidated_items)
    # No answers, explanations, keys, or item snapshots enter this projection.
    return {
        "session_id": session_id, "status": session["status"], "mode": session["mode"],
        "completion": session.get("completion", "in_progress"),
        "attempt_count": len(attempts), "assessed_count": len(scored),
        "pending_count": sum(a.get("status") == "pending" and not a.get("invalidated") for a in attempts),
        "invalidated_count": sum(bool(a.get("invalidated")) for a in attempts),
        "score": sum(a["score"] for a in scored), "max_score": max_score,
        "active_seconds": session.get("active_seconds", 0),
        "assisted_attempt_count": sum(bool(a.get("assistance")) for a in attempts),
        "previously_exposed_attempt_count": sum(bool(a.get("previous_exposures")) for a in attempts),
        "provisional": any(a.get("assessor_type") == "llm" for a in scored),
        "attempts": [{
            key: a.get(key) for key in (
                "id", "item_id", "status", "score", "active_seconds", "created_at",
                "assistance", "previous_exposures", "assessor_type", "event_id", "invalidated",
            )
        } for a in attempts],
        "interpretation": "Observed practice outcomes after guided preparation; no causal attribution or mastery guarantee.",
    }


def activity_view(store, c, activity, include_snapshot=True):
    result = {k: v for k, v in activity.items() if k != "start_idempotency_key"}
    result.setdefault("lab_id", activity["course_id"])
    result.setdefault("lesson_id", activity["module"])
    result.setdefault("responses", {})
    result.setdefault("experiment_results", {})
    if include_snapshot:
        result["discussions"] = {t["block_id"]: {"turns": t["turns"], "pending": bool(t.get("pending"))
                                                and now() < t.get("pending_expires_at", "9999")}
                                 for t in store.list(c, "lab_discussion") if t["activity_id"] == activity["id"]}
    if include_snapshot or not result.get("lab_title") or not result.get("lesson_title"):
        version = _required(store, c, "lab_version", activity["lab_version_id"])
        lesson = next((lesson for lesson in version["lessons"] if lesson["id"] == result["lesson_id"]), None)
        result["lab_title"] = version["title"]
        result["lesson_title"] = (lesson or {}).get("title", result["lesson_id"])
        if include_snapshot:
            result["lesson_snapshot"] = lesson
            result["source_catalog_snapshot"] = version.get("sources", [])
    end = activity.get("finished_at") or now()
    result["active_seconds"] = round(activity["active_seconds"], 2)
    result["elapsed_seconds"] = round(_seconds(activity["started_at"], end), 2)
    result["interruption_seconds"] = round(max(0, result["elapsed_seconds"] - result["active_seconds"]), 2)
    result["practice_outcome"] = _practice_outcome(store, c, activity)
    result["study_finished"] = activity["status"] == "finished"
    result["mastery_awarded"] = False
    return result


def _activity_summary(activities):
    return {
        "active_seconds": round(sum(a["active_seconds"] for a in activities), 2),
        "study_visits": len(activities), "finished_visits": sum(a["study_finished"] for a in activities),
        "practice_linked_visits": sum(bool(a.get("session_id")) for a in activities),
        "mastery_awarded": False,
    }


def list_labs(store, course_id=None):
    with store.tx() as c:
        courses = {course["id"]: course for course in store.list(c, "course")}
        return [{
            **{k: lab.get(k) for k in ("id", "course_id", "title", "description", "revision")},
            "course_title": courses.get(lab["course_id"], {}).get("title", lab["course_id"]),
            "lesson_count": len(lab["lessons"]),
            "activity_count": sum(len(lesson.get("activities", [])) for lesson in lab["lessons"]),
            "objectives": lab.get("objectives", []), "prerequisite_lab_ids": lab.get("prerequisite_lab_ids", []),
        } for lab in store.list(c, "lab") if course_id is None or lab["course_id"] == course_id]


def get_lab(store, ident):
    with store.tx() as c:
        lab = _required(store, c, "lab", ident)
        course = _required(store, c, "course", lab["course_id"])
        activities = [activity_view(store, c, activity, include_snapshot=False) for activity in store.list(c, "lab_activity")
                      if activity.get("lab_id", activity["course_id"]) == ident]
        return {**lab, "course_title": course["title"], "activities": activities,
                "activity_summary": _activity_summary(activities)}


def start_activity(store, ident, model):
    with store.tx() as c:
        payload = model.model_dump(exclude_none=True)
        receipt_id, previous = _receipt(store, c, "start:" + ident, model.idempotency_key, payload)
        if previous:
            return activity_view(store, c, _required(store, c, "lab_activity", previous["activity_id"]))
        lab = _required(store, c, "lab", ident)
        lessons = [entry for entry in lab["lessons"]
                   if (entry.get("module") or entry["id"]) == model.module
                   and (model.lesson_id is None or entry["id"] == model.lesson_id)]
        if len(lessons) != 1:
            raise HTTPException(400, detail="Specify a lesson_id and its module published in this lab")
        lesson = lessons[0]
        timestamp = now()
        _pause_others(store, c, timestamp)
        activity = store.put(c, "lab_activity", uid("lab_activity_"), {
            "course_id": lab["course_id"], "module": model.module, "lab_revision": lab["revision"],
            "lab_id": ident, "lesson_id": lesson["id"], "lab_title": lab["title"], "lesson_title": lesson["title"],
            "lab_version_id": f"lab:{ident}:{lab['revision']}", "source_ids": lesson["source_ids"],
            "experiment": lesson.get("experiment", ""), "status": "active", "running": True,
            "active_seconds": 0.0, "started_at": timestamp, "last_tick": timestamp,
            "reading_count": 0, "experiment_count": 0, "help_count": 0,
            "reflection": "", "session_id": None, "responses": {}, "experiment_results": {},
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


def _block_event(store, c, activity, model):
    """Check against the version actually studied, never a later publication."""
    parameters = dict(model.parameters)
    block_id = parameters.get("activity_id")
    if not block_id:
        if model.action in {"response", "media", "visualization"}:
            raise HTTPException(400, detail="This event must name its activity_id")
        if model.action == "experiment" and not activity.get("experiment"):
            raise HTTPException(400, detail="Name a parameter experiment activity_id published in this lesson")
        return parameters
    version = _required(store, c, "lab_version", activity["lab_version_id"])
    lesson = next((entry for entry in version["lessons"]
                   if entry["id"] == activity.get("lesson_id", activity["module"])), None)
    block = next((entry for entry in (lesson or {}).get("activities", []) if entry["id"] == block_id), None)
    if block is None:
        raise HTTPException(400, detail="Activity is not part of this visit's published lesson")
    if model.action == "response":
        if block["type"] not in {"prediction", "reflection"}:
            raise HTTPException(400, detail="Only prediction or reflection activities accept a response")
        value = parameters.get("value")
        if not isinstance(value, str) or len(value) > 12000 or not value.strip():
            raise HTTPException(400, detail="A response must contain between 1 and 12000 characters")
        activity.setdefault("responses", {})[block_id] = {"value": value, "recorded_at": now()}
    elif model.action == "experiment":
        if block["type"] != "parameter_experiment":
            raise HTTPException(400, detail="This activity is not a parameter experiment")
        values = parameters.get("inputs")
        if not isinstance(values, dict) or set(values) != {p["key"] for p in block["inputs"]}:
            raise HTTPException(400, detail="Provide exactly the experiment's published parameter keys")
        for param in block["inputs"]:
            value = values[param["key"]]
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    or not param["min"] <= value <= param["max"]):
                raise HTTPException(400, detail=f"Parameter {param['key']} is outside its published bounds")
        output = block.get("offset", 0) + sum(p.get("coefficient", 1) * values[p["key"]] for p in block["inputs"])
        parameters = {"activity_id": block_id, "inputs": values, "output": output}
        activity.setdefault("experiment_results", {})[block_id] = {"inputs": values, "output": output}
    elif model.action == "media":
        if block["type"] != "media" or set(parameters) != {"activity_id"}:
            raise HTTPException(400, detail="Media exposure names a media block, never playback duration or completion")
        activity["reading_count"] += 1
    elif model.action == "visualization":
        if block["type"] != "visualization" or set(parameters) != {"activity_id", "inputs"}:
            raise HTTPException(400, detail="Visualization exposure accepts only its published controls")
        values = parameters["inputs"]
        if not isinstance(values, dict) or set(values) != {p["key"] for p in block["parameters"]}:
            raise HTTPException(400, detail="Provide exactly the visualization's parameter keys")
        for param in block["parameters"]:
            value = values[param["key"]]
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    or not param["min"] <= value <= param["max"]):
                raise HTTPException(400, detail="Visualization input is outside its published bounds")
        activity["experiment_count"] += 1
        activity.setdefault("visualization_inputs", {})[block_id] = values
    elif model.action == "reading" and block["type"] not in {"reading", "worked_example"}:
        raise HTTPException(400, detail="Reading events require a reading or worked example activity")
    return parameters


def record_event(store, ident, model):
    with store.tx() as c:
        activity = _required(store, c, "lab_activity", ident)
        payload = model.model_dump(mode="json")
        receipt_id, previous = _receipt(store, c, "event:" + ident, model.idempotency_key, payload)
        if previous:
            return activity_view(store, c, activity)
        if activity["status"] != "active":
            raise HTTPException(409, detail="Study visit is already finished")
        parameters = _block_event(store, c, activity, model)
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
        _emit(store, c, activity, model.action, parameters=parameters, reflection=model.reflection)
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
    @app.get("/api/lab-activity-types", tags=["labs"])
    def types():
        """Discover supported declarative activities, contracts and starter templates."""
        return activity_types()

    @app.get("/api/labs", tags=["labs"])
    def catalog(course_id: str | None = None):
        return list_labs(store, course_id)

    @app.post("/api/labs/{lab_id}/validate", tags=["labs"])
    @app.post("/api/labs/{lab_id}/preview", tags=["labs"])
    def preview(lab_id: str, body: LabWrite):
        """Validate and render a proposed definition without writes, timers or learning evidence."""
        return preview_lab(store, lab_id, body)

    @app.put("/api/labs/{lab_id}", tags=["labs"])
    def publish(lab_id: str, body: LabWrite):
        """Publish versioned study presentation. Assessment keys are forbidden."""
        return publish_lab(store, lab_id, body)

    @app.get("/api/labs/{lab_id}", tags=["labs"])
    def read_lab(lab_id: str):
        return get_lab(store, lab_id)

    @app.post("/api/labs/{lab_id}/activities", tags=["labs"])
    def start(lab_id: str, body: ActivityStart):
        return start_activity(store, lab_id, body)

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
