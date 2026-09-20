"""Frontend response documentation. These models do not filter or rewrite API output."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .lab_activity import LabLesson


class ReadModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class LabSummaryView(ReadModel):
    id: str
    course_id: str
    title: str
    description: str
    revision: int
    course_title: str
    lesson_count: int
    activity_count: int
    objectives: list[str]
    prerequisite_lab_ids: list[str]


class ActivitySummaryView(ReadModel):
    active_seconds: float
    study_visits: int
    finished_visits: int
    practice_linked_visits: int
    mastery_awarded: Literal[False]


class VisitView(ReadModel):
    id: str
    lab_id: str
    course_id: str
    lesson_id: str
    module: str
    lab_revision: int
    status: Literal["active", "finished"]
    running: bool
    active_seconds: float
    elapsed_seconds: float
    started_at: str
    last_tick: str
    session_id: str | None
    reading_count: int
    experiment_count: int
    help_count: int
    mastery_awarded: Literal[False]
    responses: dict[str, JsonValue]
    experiment_results: dict[str, JsonValue]
    lesson_snapshot: LabLesson | None = None
    discussions: dict[str, JsonValue] = Field(default_factory=dict)
    visualization_inputs: dict[str, dict[str, float]] = Field(default_factory=dict)


class LabView(ReadModel):
    id: str
    course_id: str
    title: str
    description: str
    revision: int
    course_title: str
    lessons: list[LabLesson]
    activities: list[VisitView]
    activity_summary: ActivitySummaryView


class PublicOption(BaseModel):
    label: str
    text: str


class PublicPrompt(BaseModel):
    id: str
    text: str


class PublicItemView(ReadModel):
    id: str
    type: Literal["mcq", "matching", "open", "case", "counterfactual", "coding"]
    stem: str
    points: float
    module: str
    options: list[PublicOption] = Field(default_factory=list)
    prompts: list[PublicPrompt] = Field(default_factory=list)
    terms: list[PublicPrompt] = Field(default_factory=list)
    rubric: list[dict[str, JsonValue]] = Field(default_factory=list)
    vignette: dict[str, JsonValue] | None = None


class AnswerView(ReadModel):
    answer: str | dict[str, str]
    id: str
    status: str
    score: float | None = None
    feedback: dict[str, JsonValue] | None = None


class SessionView(ReadModel):
    id: str
    course_id: str
    module: str
    mode: Literal["practice", "transfer", "simulation"]
    status: Literal["active", "finished"]
    running: bool
    active_seconds: float
    started_at: str
    current_item: str
    items: list[PublicItemView]
    answers: dict[str, AnswerView]
    remaining_seconds: float | None
    score: float | None = None
    max_score: float | None = None
    pending_assessments: int | None = None
    review: list[dict[str, JsonValue]] | None = None


class TimerView(BaseModel):
    running: bool
    active_seconds: float


class AidRequest(BaseModel):
    item_id: str
    kind: Literal["hint", "plain", "terms"]


class AidView(BaseModel):
    kind: str
    content: JsonValue


class FinishRequest(BaseModel):
    blocker: str | None = None


class APIErrorView(BaseModel):
    detail: str | list[dict[str, JsonValue]]


class SessionSummaryView(ReadModel):
    id: str
    course_id: str
    module: str
    mode: Literal["practice", "transfer", "simulation"]
    status: Literal["active", "finished"]
    started_at: str
    active_seconds: float


class OverviewView(ReadModel):
    courses: list[dict[str, JsonValue]]
    sessions: list[SessionSummaryView]


def document_frontend_contract(app):
    original = app.openapi

    def openapi():
        schema = original()
        schema["info"]["x-frontend-contract"] = "1.0"
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in (
            LabSummaryView,
            LabView,
            VisitView,
            SessionView,
            TimerView,
            AidRequest,
            AidView,
            FinishRequest,
            OverviewView,
            APIErrorView,
        ):
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs", {}))
            components[model.__name__] = definition

        responses = {
            ("/api/overview", "get"): "OverviewView",
            ("/api/labs", "get"): {"type": "array", "items": {"$ref": "#/components/schemas/LabSummaryView"}},
            ("/api/labs/{lab_id}", "get"): "LabView",
            ("/api/labs/{lab_id}/activities", "post"): "VisitView",
            ("/api/lab-activities/{ident}", "get"): "VisitView",
            ("/api/lab-activities/{ident}/events", "post"): "VisitView",
            ("/api/lab-activities/{ident}/discussion", "post"): "VisitView",
            ("/api/lab-activities/{ident}/link-session", "post"): "VisitView",
            ("/api/sessions", "post"): "SessionView",
            ("/api/sessions/{ident}", "get"): "SessionView",
            ("/api/sessions/{ident}/answers", "post"): "SessionView",
            ("/api/sessions/{ident}/finish", "post"): "SessionView",
            ("/api/sessions/{ident}/timer", "post"): "TimerView",
            ("/api/sessions/{ident}/aid", "post"): "AidView",
        }
        for (path, method), model in responses.items():
            shape = {"$ref": f"#/components/schemas/{model}"} if isinstance(model, str) else model
            schema["paths"][path][method]["responses"]["200"]["content"]["application/json"]["schema"] = shape
            for status, description in (
                (400, "Domain request rejected"),
                (401, "Workspace token required"),
                (403, "Origin or operation forbidden"),
                (404, "Content or session unavailable"),
                (409, "State conflict; reload before continuing"),
                (422, "Request validation failed"),
            ):
                schema["paths"][path][method]["responses"].setdefault(
                    str(status),
                    {
                        "description": description,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/APIErrorView"}}
                        },
                    },
                )
        for path, model in (
            ("/api/sessions/{ident}/aid", "AidRequest"),
            ("/api/sessions/{ident}/finish", "FinishRequest"),
        ):
            schema["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"] = {
                "$ref": f"#/components/schemas/{model}"
            }
        return schema

    app.openapi = openapi
