"""Validation at module boundaries; LLM content passes the same contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseInput(Strict):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=3000)


class SessionInput(Strict):
    course_id: str
    mode: Literal["practice", "simulation", "transfer"] = "practice"
    module: str = "all"
    count: int = Field(default=8, ge=1, le=40)
    form: str | None = None
    blueprint_id: str | None = None


class AnswerInput(Strict):
    item_id: str
    answer: str | dict[str, str]
    confidence: float | None = Field(default=None, ge=0, le=1)
    idempotency_key: str = Field(min_length=5, max_length=200)


class TimerInput(Strict):
    action: Literal["pause", "resume", "heartbeat"]
    item_id: str | None = None


class TaskInput(Strict):
    title: str = Field(min_length=2, max_length=200)
    course_id: str | None = None
    category: Literal["academic", "research", "capability", "exploration"] = "academic"
    deadline: str | None = None
    deadline_kind: Literal["hard", "soft"] = "hard"
    effort_minutes: int = Field(default=60, ge=5, le=10000)
    min_block: int = Field(default=20, ge=5, le=240)
    max_block: int = Field(default=60, ge=5, le=600)
    splittable: bool = True
    setup_minutes: int = Field(default=0, ge=0, le=60)
    definition_of_done: str = Field(min_length=5, max_length=3000)
    prerequisites: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    at_risk: bool = False
    goal_id: str | None = None

    @model_validator(mode="after")
    def blocks(self):
        if self.max_block < self.min_block:
            raise ValueError("Maximum block must be at least minimum block")
        return self


class GoalInput(Strict):
    title: str = Field(min_length=2, max_length=200)
    horizon: str
    target: str = Field(min_length=5)
    acceptance_criteria: list[str] = Field(min_length=1)
    evidence_requirements: list[str] = Field(default_factory=list)
    priority: Literal["academic", "research", "capability", "exploration"]
    capabilities: list[str] = Field(default_factory=list)


class GenerationInput(Strict):
    course_id: str
    topic: str = Field(min_length=2, max_length=300)
    source_ids: list[str] = Field(min_length=1)
    count: int = Field(default=4, ge=1, le=40)
    mode: Literal["practice", "transfer", "simulation"] = "practice"
    question_types: list[Literal["mcq", "matching", "open", "case", "counterfactual", "coding"]] = ["mcq"]
    type_counts: dict[str, int] | None = None
    shared_case_items: int = Field(default=0, ge=0, le=40)
    minutes: int = Field(default=20, ge=5, le=180)
    capabilities: list[str] = Field(default_factory=list)
    instructions: str = Field(default="", max_length=3000)
    profile_id: str | None = None
    profile_version_id: str | None = None
    rubric_id: str | None = None
    counterfactual_count: int = Field(default=0, ge=0, le=40)

    @model_validator(mode="after")
    def coverage(self):
        if self.counterfactual_count > self.count:
            raise ValueError("Counterfactual items cannot exceed total items")
        if self.shared_case_items > self.count:
            raise ValueError("Shared case items cannot exceed total items")
        if not self.question_types or len(set(self.question_types)) != len(self.question_types):
            raise ValueError("Choose unique question types")
        if len(self.question_types) > self.count:
            raise ValueError("Count must cover the requested question types")
        if self.type_counts and (
            set(self.type_counts) != set(self.question_types)
            or sum(self.type_counts.values()) != self.count
            or min(self.type_counts.values()) < 1
        ):
            raise ValueError("Type counts must cover each requested type and sum to the item count")
        return self


class Criterion(Strict):
    name: str
    weight: float = Field(gt=0, le=1)
    anchors: list[str] = Field(min_length=2)


class RubricInput(Strict):
    title: str = Field(min_length=2, max_length=200)
    criteria: list[Criterion] = Field(min_length=1)
    course_id: str | None = None
    source_id: str | None = None
    authority: Literal["instructor", "learner", "proposed"] = "learner"
    permitted_assistance: str = "Follow the course policy"
    capabilities: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def weights(self):
        if abs(sum(c.weight for c in self.criteria) - 1) > 0.001:
            raise ValueError("Rubric weights must sum to 1")
        if len({c.name for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criterion names must be unique")
        return self


class AssignmentInput(Strict):
    title: str = Field(min_length=2, max_length=200)
    course_id: str
    kind: Literal["homework", "practice_quiz", "worksheet", "lab", "essay", "coding", "project"] = "homework"
    prompt: str = Field(min_length=10, max_length=30000)
    source_ids: list[str] = Field(default_factory=list)
    rubric_id: str | None = None
    purpose: Literal["coursework", "self_study"] = "coursework"
    status: Literal["open", "completed"] = "open"
    follow_shared_rubric: bool = False
    deadline: str | None = None
    points: float = Field(default=100, gt=0, le=10000)
    individual: bool = True
    effort_minutes: int = Field(default=60, ge=5, le=10000)


class CourseworkOutcomeInput(Strict):
    idempotency_key: str = Field(min_length=5, max_length=200)
    score: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    feedback: str = Field(default="", max_length=50000)
    attribution: str = Field(min_length=3, max_length=500)
    source_url: str = Field(default="", max_length=2000)
    source_id: str | None = None
    artifact_version_id: str | None = None
    reclassify_artifact: bool = False
    occurred_at: str | None = None
    observed_at: str
    learner_comment: str = Field(default="", max_length=10000)
    limitations: str = Field(default="", max_length=5000)
    mark_completed: bool = False
    supersedes: str | None = None

    @model_validator(mode="after")
    def evidence(self):
        from datetime import datetime
        from urllib.parse import urlsplit

        if self.score is None and not self.feedback.strip():
            raise ValueError("Supply an observed grade or instructor feedback")
        for value in (self.observed_at, self.occurred_at):
            if value and datetime.fromisoformat(value).tzinfo is None:
                raise ValueError("Outcome timestamps need a timezone")
        if self.source_url:
            url = urlsplit(self.source_url)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("Source URL must be an HTTP(S) reference without credentials")
        if self.reclassify_artifact and not self.artifact_version_id:
            raise ValueError("Choose the artifact version to reclassify")
        return self


class ProfileInput(Strict):
    course_id: str
    source_ids: list[str] = Field(default_factory=list, max_length=20)
    assignment_ids: list[str] = Field(default_factory=list, max_length=10)
    target_assignment_id: str | None = None
    material_source_ids: list[str] = Field(default_factory=list, max_length=30)
    emergent_source_ids: list[str] = Field(default_factory=list, max_length=30)
    rubric_ids: list[str] = Field(default_factory=list, max_length=10)
    title: str = Field(default="", max_length=200)
    target: str = Field(default="", max_length=3000)
    profile: dict | None = None


class ProfileRerunInput(Strict):
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=5, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    target: str | None = Field(default=None, max_length=3000)
    target_assignment_id: str | None = None
    assignment_ids: list[str] | None = Field(default=None, max_length=10)
    source_ids: list[str] | None = Field(default=None, max_length=20)
    material_source_ids: list[str] | None = Field(default=None, max_length=30)
    emergent_source_ids: list[str] | None = Field(default=None, max_length=30)
    rubric_ids: list[str] | None = Field(default=None, max_length=10)


class GenerationRerunInput(Strict):
    idempotency_key: str = Field(min_length=5, max_length=200)
    profile_id: str | None = None
    profile_version_id: str | None = None
    source_ids: list[str] | None = None
    topic: str | None = Field(default=None, min_length=2, max_length=300)
    instructions: str | None = Field(default=None, max_length=3000)


class CounterfactualDerivation(Strict):
    changed_assumption: str = Field(min_length=10, max_length=2000)
    reasoning: str = Field(min_length=20, max_length=5000)
    uncertainty: str = Field(min_length=10, max_length=2000)
    source_fragment_ids: list[str] = Field(min_length=1, max_length=20)


class Option(Strict):
    label: str = Field(pattern="^[A-F]$")
    text: str = Field(min_length=1)
    why: str = Field(min_length=5)


class MatchingPrompt(Strict):
    id: str
    text: str
    key: str
    why: str


class MatchingTerm(Strict):
    id: str
    text: str


class GeneratedItem(Strict):
    type: Literal["mcq", "matching", "open", "case", "counterfactual", "coding"]
    stem: str = Field(min_length=20)
    options: list[Option] = Field(default_factory=list)
    key: str = ""
    prompts: list[MatchingPrompt] = Field(default_factory=list)
    terms: list[MatchingTerm] = Field(default_factory=list)
    explanation: str = Field(min_length=20)
    hint: str
    plain: str
    source_fragment_ids: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    cognitive_operation: Literal["recall", "application", "transfer", "counterfactual", "communication"]
    rubric: list[Criterion] = Field(default_factory=list)
    points: int = Field(default=5, ge=1, le=100)
    counterfactual_derivation: CounterfactualDerivation | None = None

    @model_validator(mode="after")
    def check_answer(self):
        if self.type == "mcq":
            labels = [x.label for x in self.options]
            if not 2 <= len(labels) <= 6 or len(set(labels)) != len(labels) or self.key not in labels:
                raise ValueError("MCQ requires 2–6 unique options and one valid answer")
        elif self.type == "matching":
            terms = {t.id for t in self.terms}
            if (
                len(self.prompts) < 2
                or len({p.id for p in self.prompts}) != len(self.prompts)
                or len(terms) != len(self.terms)
                or any(p.key not in terms for p in self.prompts)
            ):
                raise ValueError("Matching requires unique prompts and valid term keys")
        elif not self.rubric or abs(sum(c.weight for c in self.rubric) - 1) > 0.01:
            raise ValueError("Open items require a rubric with weights summing to one")
        return self


class CaseTable(Strict):
    caption: str
    columns: list[str] = Field(min_length=2)
    rows: list[list[str]] = Field(min_length=1)

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Case tables must be rectangular")
        return self


class SharedCase(Strict):
    title: str
    text: str = Field(min_length=100, max_length=12000)
    table: CaseTable | None = None
