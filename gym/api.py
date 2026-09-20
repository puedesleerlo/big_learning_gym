"""Single-user HTTP boundary. No answer keys in active-session responses."""

import hmac
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, update
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import (
    adaptation,
    assessment,
    assignments,
    calendar,
    generation,
    ingestion,
    learning,
    planning,
    sessions,
)
from .contracts import (
    AnswerInput,
    CourseInput,
    CourseworkOutcomeInput,
    GenerationInput,
    GenerationRerunInput,
    GoalInput,
    ProfileInput,
    ProfileRerunInput,
    SessionInput,
    TaskInput,
    TimerInput,
)
from .llm import Router
from .store import decisions, jobs, llm_calls, now, predictions, uid
from .worker import Worker


def create_app(store=None, router=None, embedded_worker=None, workspace=None):
    load_dotenv()
    from .workspaces import load_workspace

    workspace = workspace or load_workspace()
    store = store or workspace.store()
    router = router or Router(store)
    if embedded_worker is None:
        embedded_worker = os.getenv("GYM_EMBEDDED_WORKER", "1") == "1"
    stop = threading.Event()

    def work():
        worker = Worker(store, router)
        ticks = 0
        while not stop.is_set():
            try:
                if ticks % 30 == 0:
                    worker.maintenance()
                if not worker.run_one():
                    stop.wait(1)
                    ticks += 1
            except Exception:
                # Health endpoint exposes failed jobs; the supervisor stays available.
                stop.wait(2)

    @asynccontextmanager
    async def lifespan(app):
        thread = threading.Thread(target=work, daemon=True) if embedded_worker else None
        if thread:
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=2)

    app = FastAPI(title="Big Learning Gym", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.router = router
    app.state.workspace = workspace
    allowed = os.getenv("GYM_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            token = os.getenv("GYM_ACCESS_TOKEN", "")
            if token and not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
                return JSONResponse({"detail": "Enter the server access token"}, status_code=401)
            origin = request.headers.get("origin")
            if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
                if urlparse(origin).netloc != request.headers.get("host"):
                    return JSONResponse({"detail": "Cross-origin changes are not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response

    @app.exception_handler(ValueError)
    async def validation_error(_, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/api/overview")
    def overview():
        with store.tx() as c:
            courses = store.list(c, "course")
            items = store.list(c, "item")
            all_sessions = store.list(c, "session")
            attempts = store.list(c, "attempt")
            finished = {
                s["id"] for s in all_sessions if s["status"] == "finished" or s["mode"] != "simulation"
            }
            for course in courses:
                own = [i for i in items if i["course_id"] == course["id"] and i["status"] == "active"]
                course["counts"] = {
                    mode: sum(i["pool"] == mode for i in own)
                    for mode in ["practice", "simulation", "transfer"]
                }
                course["modules"] = course.get("modules") or [
                    {"id": m, "title": m} for m in sorted({i["module"] for i in own})
                ]
                course["forms"] = [f for f in store.list(c, "form") if f["course_id"] == course["id"]]
                course["new_attempts"] = sum(a["course_id"] == course["id"] for a in attempts)
            return {
                "courses": courses,
                "recommendation": learning.recommend(store, c),
                "revision": store.revision(c),
                "sessions": [
                    {
                        k: v
                        for k, v in s.items()
                        if k
                        in {
                            "id",
                            "course_id",
                            "mode",
                            "status",
                            "started_at",
                            "completion",
                            "active_seconds",
                            "module",
                        }
                    }
                    for s in all_sessions
                ][-30:],
                "attempts": len([a for a in attempts if a["session_id"] in finished]),
                "goals": store.list(c, "goal"),
                "learner_states": store.list(c, "learner"),
                "tasks": store.list(c, "task"),
            }

    @app.post("/api/courses")
    def create_course(data: CourseInput):
        with store.tx() as c:
            ident = uid("course_")
            result = store.put(c, "course", ident, {**data.model_dump(), "modules": [], "created_at": now()})
            store.emit(c, "course.created", ident, data.model_dump())
            return result

    @app.get("/api/library/{course_id}")
    def library(course_id: str):
        with store.tx() as c:
            store.get(c, "course", course_id)
            return {
                "guides": [g for g in store.list(c, "guide") if g["course_id"] == course_id],
                "terms": [g for g in store.list(c, "term") if g["course_id"] == course_id],
            }

    @app.post("/api/sessions")
    def start_session(data: SessionInput):
        return sessions.create_session(store, data.model_dump())

    @app.get("/api/sessions/{ident}")
    def session(ident: str):
        with store.tx() as c:
            return sessions.session_view(store, c, store.get(c, "session", ident))

    @app.post("/api/sessions/{ident}/answers")
    def answer(ident: str, data: AnswerInput):
        return sessions.submit_answer(store, ident, data.model_dump())

    @app.post("/api/sessions/{ident}/timer")
    def timer(ident: str, data: TimerInput):
        return sessions.timer(store, ident, data.action, data.item_id)

    @app.post("/api/sessions/{ident}/aid")
    def aid(ident: str, data: dict):
        return sessions.assistance(store, ident, data["item_id"], data["kind"])

    @app.post("/api/sessions/{ident}/finish")
    def finish(ident: str, data: dict):
        return sessions.finish(store, ident, data.get("blocker"))

    @app.get("/api/sources")
    def sources(course_id: str | None = None):
        with store.tx() as c:
            return [
                {k: v for k, v in s.items() if k != "storage_path"}
                for s in store.list(c, "source")
                if not course_id or s["course_id"] == course_id
            ]

    @app.post("/api/sources")
    async def upload(
        course_id: str = Form(...), role: str = Form("instruction"), file: UploadFile = File(...)
    ):
        raw = await file.read(ingestion.MAX_BYTES + 1)
        result = ingestion.ingest(store, course_id, file.filename or "source.txt", raw, role)
        return {k: v for k, v in result.items() if k != "storage_path"}

    @app.get("/api/sources/{ident}/fragments")
    def fragments(ident: str):
        with store.tx() as c:
            return [f for f in store.list(c, "fragment") if f["source_version_id"] == ident]

    @app.post("/api/sources/{ident}/confirm")
    def confirm_source(ident: str, data: dict):
        with store.tx() as c:
            source = store.get(c, "source", ident)
            if data.get("expected_revision") != source["revision"]:
                raise ValueError("Source changed; review its latest version")
            result = store.put(
                c, "source", ident, {**source, "reconstruction_status": "confirmed", "confirmed_at": now()}
            )
            store.emit(c, "source.confirmed", ident, {"source_version_id": ident})
            return {k: v for k, v in result.items() if k != "storage_path"}

    @app.post("/api/sources/{ident}/correction")
    def correct_source(ident: str, data: dict):
        result = ingestion.correct_reconstruction(store, ident, data["fragments"], data["expected_revision"])
        return {k: v for k, v in result.items() if k != "storage_path"}

    @app.post("/api/sources/{ident}/rubric")
    def extract_rubric(ident: str):
        with store.tx() as c:
            source = store.get(c, "source", ident)
            if source.get("role") != "rubric" or source.get("reconstruction_status") != "confirmed":
                raise ValueError("Review a rubric source before extraction")
            return {"job_id": store.enqueue(c, "extract_rubric", {"source_id": ident}, priority=5)}

    @app.get("/api/coursework")
    def coursework():
        with store.tx() as c:
            return {
                kind: store.list(c, kind)
                for kind in [
                    "rubric",
                    "rubric_version",
                    "assignment",
                    "assignment_draft",
                    "submission",
                    "submission_assessment",
                    "official_grade",
                    "coursework_outcome",
                    "assessment_profile",
                ]
            }

    @app.post("/api/rubrics")
    def create_rubric(data: dict):
        return assignments.save_rubric(store, data)

    @app.put("/api/rubrics/{ident}")
    def edit_rubric(ident: str, data: dict):
        return assignments.save_rubric(store, data, ident)

    @app.post("/api/assignments")
    def create_assignment(data: dict):
        return assignments.create_assignment(store, data)

    @app.put("/api/assignments/{ident}")
    def revise_assignment(ident: str, data: dict):
        return assignments.revise_assignment(store, ident, data)

    @app.post("/api/assignments/{ident}/outcomes")
    def record_coursework_outcome(ident: str, data: CourseworkOutcomeInput):
        return assignments.record_coursework_outcome(store, ident, data.model_dump())

    @app.post("/api/assignments/{ident}/draft")
    def save_draft(ident: str, data: dict):
        return assignments.save_draft(store, ident, data)

    @app.post("/api/assignments/{ident}/submit")
    def submission(ident: str, data: dict):
        return assignments.submit(store, ident, data)

    @app.post("/api/submissions/{ident}/assess")
    def assess_submission(ident: str):
        with store.tx() as c:
            store.get(c, "submission", ident)
            return {"job_id": store.enqueue(c, "assess_submission", {"submission_id": ident}, priority=0)}

    @app.post("/api/submissions/{ident}/grade")
    def record_grade(ident: str, data: dict):
        return assignments.official_grade(store, ident, data)

    @app.post("/api/profiles")
    def profile(data: ProfileInput):
        return assignments.request_profile(store, **data.model_dump())

    @app.put("/api/profiles/{ident}")
    def edit_profile(ident: str, data: dict):
        return assignments.confirm_profile(store, ident, data)

    @app.get("/api/profiles/{ident}/versions")
    def profile_versions(ident: str):
        with store.tx() as c:
            current = store.get(c, "assessment_profile", ident)
            versions = [
                v for v in store.list(c, "assessment_profile_version") if v.get("profile_id") == ident
            ]
            return {"current": current, "versions": versions}

    @app.post("/api/profiles/{ident}/rerun")
    def rerun_profile(ident: str, data: ProfileRerunInput):
        return assignments.rerun_profile(store, ident, data.model_dump(exclude_unset=True))

    @app.post("/api/sources/{ident}/interpret")
    def interpret(ident: str):
        with store.tx() as c:
            source = store.get(c, "source", ident)
            return {"job_id": store.enqueue(c, "interpret", {"source_id": source["id"]}, priority=10)}

    @app.get("/api/interpretations")
    def interpretations():
        with store.tx() as c:
            return store.list(c, "interpretation")

    @app.post("/api/generations")
    def create_generation(data: GenerationInput):
        return generation.request_generation(store, data.model_dump())

    @app.get("/api/generations")
    def generations():
        with store.tx() as c:
            return store.list(c, "blueprint")

    @app.post("/api/generations/{ident}/rerun")
    def rerun_generation(ident: str, data: GenerationRerunInput):
        return generation.rerun_generation(store, ident, data.model_dump(exclude_unset=True))

    @app.get("/api/progress")
    def progress():
        from .lab_activity import activity_view

        with store.tx() as c:
            closed = {
                s["id"]
                for s in store.list(c, "session")
                if s["status"] == "finished" or s["mode"] != "simulation"
            }
            attempts = [a for a in store.list(c, "attempt") if a["session_id"] in closed]
            return {
                "learner_states": store.list(c, "learner"),
                "attempts": attempts,
                "execution": learning.execution_summary(store, c),
                "evaluations": store.list(c, "evaluation"),
                "interventions": store.list(c, "intervention"),
                "lab_activities": [
                    activity_view(store, c, activity, include_snapshot=False)
                    for activity in store.list(c, "lab_activity")
                ],
                "adaptation": store.get(c, "adaptation_settings", "default", False) or {"enabled": True},
            }

    @app.get("/api/evidence")
    def evidence():
        with store.tx() as c:
            active = {
                s["id"]
                for s in store.list(c, "session")
                if s["status"] == "active" and s["mode"] == "simulation"
            }
            hidden = {a["id"] for a in store.list(c, "attempt") if a["session_id"] in active}
            return [e for e in store.evidence(c, limit=200) if e["entity_id"] not in hidden]

    @app.post("/api/items/{ident}/report")
    def quarantine(ident: str, data: dict):
        reason = data.get("reason", "")
        if len(reason.strip()) < 5:
            raise ValueError("Explain what is wrong with the item")
        with store.tx() as c:
            item = store.get(c, "item", ident)
            store.put(c, "item", ident, {**item, "status": "quarantined", "quarantine_reason": reason})
            affected = []
            for a in store.list(c, "attempt"):
                if a["item_id"] == ident:
                    store.put(c, "attempt", a["id"], {**a, "invalidated": True})
                    affected.append(a["id"])
            # Rebuild affected capability estimates from valid observations, preserving historical evidence.
            for state in store.list(c, "learner"):
                if state["course_id"] == item["course_id"] and state["capability"] in item.get(
                    "capabilities", []
                ):
                    store.put(
                        c,
                        "learner",
                        state["id"],
                        {
                            **state,
                            "dimensions": {},
                            "evidence_ids": [],
                            "assisted_attempts": 0,
                            "independent_attempts": 0,
                            "unseen_checks": 0,
                            "hypotheses": ["Estimate rebuilt after item quarantine"],
                        },
                    )
            for a in store.list(c, "attempt"):
                other = store.get(c, "item", a["item_id"])
                session = store.get(c, "session", a["session_id"])
                if session["mode"] == "simulation" and session["status"] != "finished":
                    continue
                if (
                    other["course_id"] == item["course_id"]
                    and not a.get("invalidated")
                    and set(other.get("capabilities", [])) & set(item.get("capabilities", []))
                ):
                    learning.update_learner(store, c, a, other, a["event_id"])
            store.emit(c, "item.quarantined", ident, {"reason": reason, "invalidated_attempts": affected})
            return {"status": "quarantined", "affected_attempts": len(affected)}

    @app.get("/api/planning")
    def planning_state():
        with store.tx() as c:
            return {
                "tasks": store.list(c, "task"),
                "goals": store.list(c, "goal"),
                "calendar": store.list(c, "calendar"),
                "calendar_conflicts": store.list(c, "calendar_conflict"),
                "schedule": store.get(c, "schedule", "active", False),
                "predictions": [dict(x) for x in c.execute(select(predictions)).mappings()],
                "proposals": [
                    dict(x)
                    for x in c.execute(
                        select(decisions)
                        .where(decisions.c.decision_type == "schedule")
                        .order_by(decisions.c.created_at.desc())
                        .limit(10)
                    ).mappings()
                ],
            }

    @app.post("/api/goals")
    def goal(data: GoalInput):
        with store.tx() as c:
            ident = uid("goal_")
            result = store.put(
                c, "goal", ident, {**data.model_dump(), "approved_at": now(), "owner": "learner"}
            )
            store.emit(c, "goal.approved", ident, data.model_dump())
            return result

    @app.post("/api/tasks")
    def task(data: TaskInput):
        return planning.create_task(store, data.model_dump())

    @app.patch("/api/tasks/{ident}")
    def revise_task(ident: str, data: dict):
        return planning.revise_task(store, ident, data)

    @app.post("/api/calendar")
    def calendar_event(data: dict):
        return calendar.upsert_event(store, data)

    @app.post("/api/calendar/import")
    async def calendar_import(source: str = Form("ics:calendar"), file: UploadFile = File(...)):
        return calendar.import_ics(store, await file.read(5 * 1024 * 1024 + 1), source)

    @app.post("/api/schedules")
    def schedule(data: dict):
        return planning.propose_schedule(store, data)

    @app.post("/api/schedules/{ident}/accept")
    def accept(ident: str):
        return planning.accept_schedule(store, ident)

    @app.post("/api/blocks/{ident}/pin")
    def pin(ident: str, data: dict):
        return planning.pin_block(store, ident, data["pinned"])

    @app.get("/api/schedule.ics")
    def calendar_export():
        return Response(
            calendar.export_schedule(store),
            media_type="text/calendar",
            headers={"Content-Disposition": "attachment; filename=learning-plan.ics"},
        )

    @app.get("/api/artifacts")
    def artifacts():
        with store.tx() as c:
            return {
                "artifacts": store.list(c, "artifact"),
                "reviews": store.list(c, "artifact_review"),
                "versions": store.list(c, "artifact_version"),
            }

    @app.post("/api/artifacts")
    def save_artifact(data: dict):
        if not data.get("title") or len(data.get("body", "")) < 10:
            raise ValueError("An artifact needs a title and substantive content")
        if len(data["body"]) > 100000:
            raise ValueError("Artifact exceeds the text limit")
        return assessment.save_artifact(store, data)

    @app.post("/api/artifacts/{version_id}/critique")
    def critique(version_id: str):
        with store.tx() as c:
            store.get(c, "artifact_version", version_id)
            return {"job_id": store.enqueue(c, "critique", {"version_id": version_id}, priority=5)}

    @app.post("/api/adaptation/evaluate")
    def evaluate():
        return adaptation.evaluate(store)

    @app.post("/api/adaptation/settings")
    def adaptation_settings(data: dict):
        if not isinstance(data.get("enabled"), bool):
            raise ValueError("enabled must be a boolean")
        with store.tx() as c:
            result = store.put(c, "adaptation_settings", "default", {"enabled": data["enabled"]})
            store.emit(c, "adaptation.overridden", "default", data)
            return result

    @app.post("/api/models/{ident}/activate")
    def activate(ident: str):
        return adaptation.activate_model(store, ident)

    @app.post("/api/interventions")
    def intervention(data: dict):
        return adaptation.record_intervention(store, data)

    @app.get("/api/health")
    def health():
        with store.tx() as c:
            queue = [
                dict(x)
                for x in c.execute(select(jobs).order_by(jobs.c.created_at.desc()).limit(100)).mappings()
            ]
            return {
                "database": "connected",
                "dialect": store.engine.dialect.name,
                "revision": store.revision(c),
                "jobs": queue,
                "job_health": store.list(c, "job_health"),
                "connectors": store.list(c, "connector"),
                "stale_estimates": len(
                    list(c.execute(select(predictions.c.id).where(predictions.c.stale_reason.is_not(None))))
                ),
                "models": router.describe(),
                "model_versions": store.list(c, "model"),
                "calls": [
                    dict(x)
                    for x in c.execute(
                        select(llm_calls).order_by(llm_calls.c.created_at.desc()).limit(30)
                    ).mappings()
                ],
            }

    @app.post("/api/jobs/{ident}/retry")
    def retry_job(ident: str):
        import time

        with store.tx() as c:
            job = c.execute(select(jobs).where(jobs.c.id == ident)).mappings().first()
            if not job or job["status"] != "failed":
                raise ValueError("Only failed jobs can be retried")
            c.execute(
                update(jobs)
                .where(jobs.c.id == ident)
                .values(status="queued", attempts=0, run_at=time.time(), last_error=None)
            )
            return {"status": "queued"}

    from .agent_api import register_agent_api
    from .lab_activity import register_lab_api
    from .lab_tutor import register_lab_tutor_api

    register_lab_api(app, store)
    register_lab_tutor_api(app, store, router)
    register_agent_api(app, store)

    from .frontends import register_frontends

    register_frontends(app, workspace)

    from .frontend_contracts import document_frontend_contract

    document_frontend_contract(app)

    dist = Path(__file__).resolve().parent.parent / "web/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(dist / "index.html")

    return app
