"""Bounded live-provider integration, using synthetic teaching material in an isolated DB.

Run explicitly; the unit test suite never makes paid calls. Saves only a redacted report.
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

from gym.assignments import (
    assess_submission,
    create_assignment,
    extract_rubric,
    generate_profile,
    request_profile,
    save_draft,
    save_rubric,
    submit,
)
from gym.generation import generate, request_generation
from gym.ingestion import ingest
from gym.llm import Router
from gym.store import Store, now

load_dotenv()
report = {"started_at": now(), "model": "kimi-k3", "checks": []}


def check(name, fn):
    start = time.monotonic()
    value = fn()
    report["checks"].append({"name": name, "passed": True, "seconds": round(time.monotonic() - start, 2)})
    print(name, "passed", flush=True)
    Path("data/live-validation.json").write_text(json.dumps(report, indent=2))
    return value


with tempfile.TemporaryDirectory(prefix="gym-live-") as folder:
    store = Store("sqlite:///" + folder + "/test.db", folder)
    router = Router(store)
    with store.tx() as c:
        store.put(
            c,
            "course",
            "methods",
            {"title": "Validation methods", "description": "Synthetic integration fixture"},
        )
    source = ingest(
        store,
        "methods",
        "lecture.md",
        b"""# Comparing group averages
The sample mean is the sum of observed values divided by the number of observations.
An unadjusted treatment-control mean difference is an association in observational data.
A variable influencing both treatment choice and outcome can confound that difference.
Random assignment makes treatment independent of pre-treatment characteristics in expectation;
it does not guarantee identical covariate balance in every finite sample.
A causal interpretation also requires a well-defined treatment, no relevant interference,
and appropriate handling of missing outcomes. State those assumptions instead of claiming certainty.
In a randomized experiment with complete outcome observation, the difference in sample means
estimates the average treatment effect under the design assumptions. Do not automatically
generalize an estimate from one population to a different population.
Report what was measured, compare alternatives, state limitations, and name a useful next check.
""",
    )
    exam = ingest(
        store,
        "methods",
        "official-practice.md",
        b"""# Instructor-released practice worksheet
Two short-answer questions, 10 points each, allow 15 minutes. No outside facts are required.
Question 1: Group A receives tutoring and averages 75; group B chooses not to receive tutoring
and averages 70. Explain why the difference need not identify the tutoring effect.
Question 2: Describe what random assignment changes and one assumption it does not remove.
Rubric for each: correct conclusion 4 points; justified reasoning 4 points; limitation 2 points.
Responses should use 80-150 words. No answer key is supplied. AI practice use is allowed.
""",
        role="assessment",
    )
    with store.tx() as c:
        store.put(c, "source", exam["id"], {**exam, "reconstruction_status": "confirmed"})
    profile = request_profile(store, "methods", [exam["id"]])
    profile = check("assessment profile", lambda: generate_profile(store, router, profile["id"]))
    with store.tx() as c:
        store.put(c, "assessment_profile", profile["id"], {**profile, "status": "confirmed"})
    spec = {
        "course_id": "methods",
        "topic": "Assumptions behind a difference in means",
        "source_ids": [source["id"]],
        "count": 3,
        "shared_case_items": 2,
        "mode": "practice",
        "question_types": ["mcq", "matching", "open"],
        "profile_id": profile["id"],
        "instructions": "Use the profile's reasoning demands; this diagnostic deliberately uses one MCQ, one matching item and one open response.",
    }
    bp = request_generation(store, spec)
    result = check(
        "grounded generation and independent verification", lambda: generate(store, router, bp["id"])
    )
    if result["quarantined_count"]:
        raise RuntimeError(
            "Live generation required quarantine; inspect the workflow before claiming success"
        )
    rubric_source = ingest(
        store,
        "methods",
        "official-rubric.txt",
        b"Instructor rubric: Conclusion 40 percent, from incorrect claim to correct bounded claim. Reasoning 40 percent, from no explanation to sound causal reasoning. Limitations 20 percent, from missing to explicit relevant assumption. Hints may be used during practice.",
        role="rubric",
    )
    with store.tx() as c:
        store.put(c, "source", rubric_source["id"], {**rubric_source, "reconstruction_status": "confirmed"})
    check("editable rubric extraction", lambda: extract_rubric(store, router, rubric_source["id"]))
    rubric = save_rubric(
        store,
        {
            "title": "Reasoning rubric",
            "authority": "instructor",
            "criteria": [
                {
                    "name": "Conclusion",
                    "weight": 0.4,
                    "anchors": ["Incorrect causal conclusion", "Correct bounded conclusion"],
                },
                {
                    "name": "Reasoning",
                    "weight": 0.4,
                    "anchors": ["No explanation", "Explains confounding and assignment"],
                },
                {
                    "name": "Limitations",
                    "weight": 0.2,
                    "anchors": ["No caveat", "Names a valid assumption or limitation"],
                },
            ],
        },
    )
    a = create_assignment(
        store,
        {
            "course_id": "methods",
            "title": "Interpret a comparison",
            "prompt": "Explain whether a nonrandom tutoring comparison identifies a causal effect.",
            "rubric_id": rubric["id"],
        },
    )
    save_draft(
        store,
        a["id"],
        {
            "body": "The five-point difference is an association, not sufficient evidence of a causal effect. Students selecting tutoring could differ in prior ability or motivation, which also influence outcomes. Random assignment would address treatment selection in expectation, but would not guarantee exact finite-sample balance. I would inspect missing outcomes and interference before making a bounded causal claim.",
            "event": "save",
        },
    )
    submission = submit(
        store, a["id"], {"idempotency_key": "live-submission-v1", "ai_contribution": "substantive"}
    )
    judgment = check(
        "rubric assessment with attributable evidence",
        lambda: assess_submission(store, router, submission["id"]),
    )
    report["generated_types"] = ["mcq", "matching", "open"]
    report["verified_items"] = len(result["item_ids"])
    report["shared_case_items"] = 2
    report["assessment_score"] = judgment["score"]
    report["finished_at"] = now()
    report["synthetic_data_only"] = True
    report["credentials_persisted_in_report"] = False
    Path("data/live-validation.json").write_text(json.dumps(report, indent=2))
    print("Live integration completed; redacted report: data/live-validation.json", flush=True)
