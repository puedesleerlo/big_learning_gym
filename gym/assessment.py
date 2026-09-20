"""Independent rubric judging; model output is attributed evidence, never an official grade."""

import json

from pydantic import BaseModel, Field

from .generation import SYSTEM
from .learning import update_learner
from .store import now, uid


class CriterionScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    evidence_quote: str
    explanation: str


class Judgment(BaseModel):
    criteria: list[CriterionScore]
    uncertainty: str = Field(min_length=5)
    feedback: str = Field(min_length=10)
    next_step: str = Field(min_length=10)


def judge(router, item, answer, role="assessor"):
    # No tutor conversation, predicted score, confidence or praise is passed to the assessor.
    result, provenance = router.complete(
        role,
        SYSTEM + " Assess the actual submitted reasoning, not writing length or fluency.",
        json.dumps(
            {
                "task": item["stem"],
                "rubric": item["rubric"],
                "reference": item.get("explanation", ""),
                "answer": answer,
                "schema": Judgment.model_json_schema(),
                "instruction": "Return a JSON judgment. "
                "Score every rubric criterion from 0 to 1. Evidence quotes must be exact passages from the answer; "
                "use an empty quote only when an expected feature is absent. State uncertainty. Do not call this an official grade.",
            }
        ),
    )
    judgment = Judgment.model_validate(result).model_dump()
    expected = {x["name"] for x in item["rubric"]}
    if {x["name"] for x in judgment["criteria"]} != expected or len(judgment["criteria"]) != len(expected):
        raise ValueError("Assessment did not cover each rubric criterion exactly once")
    for criterion in judgment["criteria"]:
        if criterion["evidence_quote"] not in answer:
            raise ValueError("Assessment contains a quote that is not in the attempt")
    scores = {x["name"]: x["score"] for x in judgment["criteria"]}
    total = sum(scores[x["name"]] * x["weight"] for x in item["rubric"]) * item.get("points", 100)
    return round(total, 2), {**judgment, "assessor": provenance, "kind": "provisional_model_judgment"}


def assess_attempt(store, router, attempt_id):
    with store.tx() as c:
        a = store.get(c, "attempt", attempt_id)
        if a["status"] != "pending":
            return
        session = store.get(c, "session", a["session_id"])
        item = session["snapshots"][a["item_id"]]
    score, judgment = judge(router, item, a["answer"])
    with store.tx() as c:
        a = store.get(c, "attempt", attempt_id)
        if a["status"] != "pending":
            return
        current = store.get(c, "item", a["item_id"])
        if current["status"] != "active":
            store.put(c, "attempt", attempt_id, {**a, "status": "invalidated", "invalidated": True})
            return
        a.update(score=score, feedback=judgment, status="assessed", assessed_at=now())
        event_id, _ = store.emit(
            c,
            "attempt.assessed",
            attempt_id,
            {"score": score, "judgment": judgment, "rubric_version": item["rubric_version"]},
            key="assessed:" + attempt_id,
            quality_flags=["provisional_model_judgment"],
        )
        store.put(c, "attempt", attempt_id, a)
        current_session = store.get(c, "session", a["session_id"])
        if current_session["mode"] != "simulation" or current_session["status"] == "finished":
            update_learner(store, c, a, item, event_id)


DEFAULT_RUBRIC = [
    {
        "name": "Claim and assumptions",
        "weight": 0.25,
        "anchors": ["Unclear claim or hidden assumptions", "Explicit, bounded claim with assumptions"],
    },
    {
        "name": "Evidence and method",
        "weight": 0.3,
        "anchors": [
            "No supporting evidence or invalid comparison",
            "Traceable evidence and justified method",
        ],
    },
    {
        "name": "Alternatives and objections",
        "weight": 0.25,
        "anchors": ["No alternative considered", "Strongest objection addressed with a discriminating test"],
    },
    {
        "name": "Conclusion and limits",
        "weight": 0.2,
        "anchors": ["Conclusion exceeds evidence", "Conclusion follows with limitations and a next test"],
    },
]


def save_artifact(store, data):
    with store.tx() as c:
        artifact_id = data.get("artifact_id") or uid("artifact_")
        old = store.get(c, "artifact", artifact_id, False)
        if old and old.get("classification") == "coursework_record":
            raise ValueError("This record was moved to coursework; update its attributed outcome there")
        for relation in data.get("relations", []):
            if relation.get("type") not in {
                "requires",
                "demonstrates",
                "supports",
                "contradicts",
                "derived_from",
                "evaluated_by",
            }:
                raise ValueError("Unknown provenance relation")
            if not relation.get("target_id"):
                raise ValueError("A provenance link needs a target")
        version = (old["version"] if old else 0) + 1
        version_id = artifact_id + f":v{version}"
        record = {
            "title": data["title"],
            "body": data["body"],
            "kind": data.get("kind", "argument"),
            "course_id": data.get("course_id"),
            "claim": data.get("claim", ""),
            "objection": data.get("objection", ""),
            "relations": data.get("relations", []),
            "ai_contribution": data.get("ai_contribution", "none"),
            "version": version,
            "artifact_id": artifact_id,
            "version_id": version_id,
            "created_at": now(),
            "rubric": data.get("rubric") or DEFAULT_RUBRIC,
            "rubric_version": "research-v1",
        }
        store.put(c, "artifact_version", version_id, record)
        store.put(c, "artifact", artifact_id, record, expected_revision=data.get("expected_revision"))
        store.emit(
            c,
            "artifact.saved",
            artifact_id,
            {"version_id": version_id, "version": version, "ai_contribution": record["ai_contribution"]},
        )
        return {**record, "id": artifact_id}


def critique_artifact(store, router, version_id):
    with store.tx() as c:
        artifact = store.get(c, "artifact_version", version_id)
        current = store.get(c, "artifact", artifact["artifact_id"])
        if current.get("classification") == "coursework_record":
            raise ValueError(
                "Instructor feedback belongs to coursework and cannot be critiqued as learner research"
            )
        previous = store.get(c, "artifact_review", "review:" + version_id, False)
        if previous:
            return previous
    item = {
        "stem": f"Defend the claim: {artifact['claim']}. Address the strongest objection: {artifact['objection']}",
        "rubric": artifact["rubric"],
        "points": 100,
    }
    score, feedback = judge(router, item, artifact["body"], "research_coach")
    with store.tx() as c:
        if store.get(c, "artifact", artifact["artifact_id"]).get("classification") == "coursework_record":
            raise ValueError("Artifact was moved to coursework during critique")
        review = store.put(
            c,
            "artifact_review",
            "review:" + version_id,
            {
                "version_id": version_id,
                "score": score,
                "feedback": feedback,
                "rubric_version": artifact["rubric_version"],
                "created_at": now(),
            },
        )
        store.emit(
            c,
            "artifact.reviewed",
            artifact["artifact_id"],
            {"review_id": review["id"], "version_id": version_id},
            quality_flags=["Does not count as independent capability or external validation"],
        )
        return review
