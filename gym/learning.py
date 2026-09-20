"""Evidence-backed learner state and transparent activity selection, independent of LLMs."""

import math
from datetime import datetime, timedelta, timezone

from .store import now

DIMENSIONS = ["recall", "application", "transfer", "counterfactual", "communication"]


def update_learner(store, c, attempt, item, event_id):
    if attempt.get("score") is None or attempt.get("invalidated"):
        return
    ratio = attempt["score"] / item["points"]
    independent = not attempt.get("assistance") and not attempt.get("self_reported_ai", False)
    novel = attempt.get("previous_exposures", 0) == 0
    for capability in item.get("capabilities", [item["module"]]):
        ident = "learner:" + item["course_id"] + ":" + capability
        old = store.get(c, "learner", ident, False) or {
            "capability": capability,
            "course_id": item["course_id"],
            "dimensions": {},
            "evidence_ids": [],
            "assisted_attempts": 0,
            "independent_attempts": 0,
            "unseen_checks": 0,
            "hypotheses": [],
            "model_version": "capability-beta-v1",
        }
        if event_id in old["evidence_ids"]:
            continue
        dim = item.get("cognitive_operation", "application")
        dimension = old["dimensions"].get(
            dim, {"alpha": 1.0, "beta": 1.0, "observations": 0, "independent_unseen": 0}
        )
        # Weak, transparent evidence weighting; no claim to a calibrated mastery probability.
        weight = (1.0 if independent else 0.25) * (1.0 if novel else 0.25)
        if attempt.get("assessor_type") == "llm":
            weight *= 0.5
        dimension = {
            **dimension,
            "alpha": dimension["alpha"] + ratio * weight,
            "beta": dimension["beta"] + (1 - ratio) * weight,
            "observations": dimension["observations"] + 1,
            "independent_unseen": dimension["independent_unseen"] + int(independent and novel),
        }
        a, b = dimension["alpha"], dimension["beta"]
        mean = a / (a + b)
        sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
        dimension.update(
            estimate=round(mean, 3),
            interval=[round(max(0, mean - 1.96 * sd), 3), round(min(1, mean + 1.96 * sd), 3)],
        )
        old["dimensions"] = {**old["dimensions"], dim: dimension}
        old["evidence_ids"] = [*old["evidence_ids"], event_id]
        old["assisted_attempts"] += int(not independent)
        old["independent_attempts"] += int(independent)
        old["unseen_checks"] += int(independent and novel and attempt["mode"] in {"simulation", "transfer"})
        old["last_observed_at"] = now()
        old["next_check_at"] = (
            datetime.now(timezone.utc) + timedelta(days=3 if ratio >= 0.8 and independent else 1)
        ).isoformat()
        old["hypotheses"] = (
            ["Supported performance needs an unseen, unaided check"]
            if not independent
            else [f"Revisit {dim}: the latest attempt did not meet the 80% practice criterion"]
            if ratio < 0.8
            else ["Check delayed retention in a different item family"]
        )
        store.put(c, "learner", ident, old)
        store.invalidate(c, ident, "New assessment evidence")


def recommend(store, c, course_id=None):
    # Official outcomes take precedence over provisional model feedback. Scope advice to
    # the actual assignment; a holistic grade never becomes general subject mastery.
    latest_submissions = {
        s["assignment_id"]: s
        for s in store.list(c, "submission")
        if not course_id or s["course_id"] == course_id
    }
    grades = {g["submission_id"]: g for g in store.list(c, "official_grade")}
    reviews = {r["submission_id"]: r for r in store.list(c, "submission_assessment")}
    for submission in reversed(list(latest_submissions.values())):
        outcome = grades.get(submission["id"]) or reviews.get(submission["id"])
        if outcome and outcome["score"] < outcome["max_score"] * 0.8:
            assignment = store.get(c, "assignment", submission["assignment_id"])
            official = submission["id"] in grades
            return {
                "title": "Revisit " + assignment["title"],
                "course_id": submission["course_id"],
                "assignment_id": assignment["id"],
                "mode": "coursework",
                "module": "all",
                "rationale": ("Instructor feedback" if official else "Provisional rubric feedback")
                + " identifies unfinished criteria. Inspect the feedback and revise the work before using its score as evidence of capability.",
                "evidence_ids": [outcome["id"]],
                "expected_output": "A revised submission addressing the weakest rubric criteria",
                "minutes": [15, 30],
                "alternatives": [
                    "Check the original instructions",
                    "Discuss the rubric with your instructor",
                ],
            }
    sealed = {
        s["id"] for s in store.list(c, "session") if s["mode"] == "simulation" and s["status"] == "active"
    }
    attempts = [
        a for a in store.list(c, "attempt") if not a.get("invalidated") and a["session_id"] not in sealed
    ]
    items = {
        i["id"]: i
        for i in store.list(c, "item")
        if i["status"] == "active" and (not course_id or i["course_id"] == course_id)
    }
    latest = {a.get("family_id", a["item_id"]): a for a in attempts}
    mistakes = [
        a
        for a in latest.values()
        if a["item_id"] in items
        and a.get("score") is not None
        and a["score"] < items[a["item_id"]]["points"] * 0.8
    ]
    if mistakes:
        target = max(mistakes, key=lambda a: a["created_at"])
        item = items[target["item_id"]]
        return {
            "title": f"Rebuild your reasoning in {item['module']}",
            "course_id": item["course_id"],
            "module": item["module"],
            "mode": "practice",
            "rationale": "Your most recent error is the evidence for this choice. Practice a different question, then take an unaided check.",
            "evidence_ids": [target.get("event_id")],
            "expected_output": "An answer and a defensible explanation",
            "minutes": [10, 20],
            "alternatives": ["Review the source guide", "Take an unseen simulation"],
        }
    due = [
        s
        for s in store.list(c, "learner")
        if s.get("next_check_at", "z") <= now() and (not course_id or s["course_id"] == course_id)
    ]
    if due:
        s = due[0]
        return {
            "title": "Test what stayed with you",
            "course_id": s["course_id"],
            "module": "all",
            "mode": "transfer",
            "rationale": "A delayed check is due. An unfamiliar case tests whether learning transfers beyond the original question.",
            "evidence_ids": s["evidence_ids"][-3:],
            "expected_output": "An unaided answer to an unfamiliar case",
            "minutes": [10, 20],
            "alternatives": ["Take a practice set", "Defer the check"],
        }
    courses = store.list(c, "course")
    course = next((x for x in courses if x["id"] == course_id), courses[0] if courses else None)
    return {
        "title": "Find your starting point" if not attempts else "Build on an unseen question",
        "course_id": course["id"] if course else None,
        "module": "all",
        "mode": "practice",
        "rationale": "There is not enough independent evidence yet. A short practice set will reveal which capabilities need attention.",
        "evidence_ids": [],
        "expected_output": "A short diagnostic with confidence and assistance recorded",
        "minutes": [10, 20],
        "alternatives": ["Create a gym from your materials", "Review a study guide"],
    }


def execution_summary(store, c):
    groups = {}
    for a in store.list(c, "attempt"):
        kind = a.get("item_type", "unknown")
        g = groups.setdefault(kind, {"count": 0, "active_seconds": 0, "assisted": 0})
        g["count"] += 1
        g["active_seconds"] += a.get("active_seconds", 0)
        g["assisted"] += bool(a.get("assistance"))
    return [
        {"type": k, **v, "mean_active_seconds": round(v["active_seconds"] / v["count"])}
        for k, v in groups.items()
    ]
