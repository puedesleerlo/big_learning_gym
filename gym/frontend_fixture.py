"""Synthetic material for disposable frontend previews and tests only."""

from copy import deepcopy

from .lab_activity import LabWrite, get_lab, list_labs, publish_lab
from .lab_blocks import activity_types
from .sessions import public_item


class FixtureRouter:
    def describe(self):
        return {"roles": {}, "providers": {}, "limits": {}}

    def complete(self, role, system, prompt):
        return {
            "reply": "Which comparison keeps the other conditions unchanged?",
            "citations": ["demo-fragment"],
        }, {
            "role": role,
            "provider": "synthetic",
            "model": "fixture-tutor",
            "call_id": "fixture-call",
        }


def seed(store):
    """Caller must supply an empty, disposable store. Never seed a learner workspace."""
    with store.tx() as c:
        if store.list(c, "course"):
            raise ValueError("Frontend fixtures require an empty disposable workspace")
        store.put(
            c,
            "course",
            "demo-course",
            {
                "title": "The practice kitchen",
                "description": "Synthetic learning material",
                "modules": [{"id": "reasoning", "title": "Reason with evidence"}],
            },
        )
        store.put(
            c,
            "source",
            "demo-source",
            {
                "course_id": "demo-course",
                "name": "Synthetic practice notes",
                "role": "instruction",
                "reconstruction_status": "confirmed",
            },
        )
        store.put(
            c,
            "fragment",
            "demo-fragment",
            {
                "source_version_id": "demo-source",
                "anchor": "section:1",
                "text": "Changing one input while holding the others constant makes a comparison easier to interpret.",
            },
        )
        rubric = {
            "course_id": "demo-course",
            "title": "Reasoning rubric",
            "criteria": [
                {"name": "Reasoning", "weight": 1, "anchors": ["Unsupported", "Explained using evidence"]}
            ],
        }
        store.put(c, "rubric_version", "demo-rubric-v1", rubric)
        store.put(
            c,
            "assignment",
            "demo-assignment",
            {
                "course_id": "demo-course",
                "title": "Explain your comparison",
                "kind": "essay",
                "prompt": "Explain why a controlled comparison is useful.",
                "points": 5,
                "rubric_version_id": "demo-rubric-v1",
            },
        )
        items = []
        for pool in ("practice", "transfer"):
            for kind in ("mcq", "matching", "open", "case", "counterfactual", "coding"):
                item = {
                    "course_id": "demo-course",
                    "module": "reasoning",
                    "type": kind,
                    "pool": pool,
                    "status": "active",
                    "stem": "Which comparison changes only one input?"
                    if kind == "mcq"
                    else f"Explain a controlled comparison ({kind}).",
                    "points": 5,
                    "options": [
                        {"label": "A", "text": "Change one input", "why": "Other inputs remain fixed."},
                        {"label": "B", "text": "Change every input", "why": "The comparison mixes changes."},
                    ],
                    "key": "A",
                    "prompts": [
                        {"id": "p1", "text": "Held constant", "key": "t1", "why": "A control."},
                        {"id": "p2", "text": "Changed", "key": "t2", "why": "The input of interest."},
                    ],
                    "terms": [{"id": "t1", "text": "Control"}, {"id": "t2", "text": "Input"}],
                    "explanation": "Hold other conditions constant to interpret a single changed input.",
                    "hint": "Count how many inputs change.",
                    "plain": "What stays the same?",
                    "family_id": f"demo-{pool}-{kind}",
                    "capabilities": ["reasoning"],
                    "cognitive_operation": "application",
                    "rubric_version": "demo-rubric-v1",
                    "rubric": rubric["criteria"],
                }
                if kind == "case":
                    item["vignette"] = {
                        "id": "synthetic-comparison",
                        "title": "Two small trials",
                        "text": "Two groups compare a controlled change. Keep the remaining inputs constant and explain which observation would support the proposed comparison.",
                        "table": {
                            "caption": "Synthetic observations",
                            "columns": ["Trial", "Input", "Outcome"],
                            "rows": [["First", "2", "4"], ["Second", "3", "6"]],
                        },
                    }
                items.append(store.put(c, "item", f"demo-{pool}-{kind}", item))
    templates = {x["type"]: deepcopy(x["template"]) for x in activity_types()["types"]}
    templates["reading"].update(
        title="Make a useful comparison",
        body="Change one input. Hold the rest steady. Write down what you expect before observing the result.\n\nThis is synthetic practice material for exploring a learning experience.",
    )
    templates["coursework"]["assignment_id"] = "demo-assignment"
    templates["assessment"].update(count=6, title="Put it into practice")
    templates["media"].update(
        kind="audio",
        provider="native",
        url="https://media.example.test/lesson.wav",
        transcript="A controlled comparison holds other inputs steady.",
    )
    lessons = []
    for index, (ident, title, types) in enumerate(
        [
            (
                "compare",
                "One change at a time",
                [
                    "reading",
                    "prediction",
                    "worked_example",
                    "parameter_experiment",
                    "reflection",
                    "assessment",
                ],
            ),
            (
                "explore",
                "Look, listen, and discuss",
                ["media", "visualization", "discussion", "coursework", "assessment"],
            ),
        ]
    ):
        activities = [deepcopy(templates[t]) for t in types]
        for block in activities:
            block["id"] = f"{ident}-{block['type']}"
            if block["type"] == "assessment" and index:
                block["mode"] = "transfer"
        lessons.append(
            {
                "id": ident,
                "module": "reasoning",
                "title": title,
                "minutes": 12 + index * 3,
                "objectives": ["Explain what changed and what stayed constant"],
                "source_ids": ["demo-source"],
                "activities": activities,
            }
        )
    publish_lab(
        store,
        "demo-lab",
        LabWrite.model_validate(
            {
                "course_id": "demo-course",
                "expected_revision": 0,
                "title": "Small experiments, better questions",
                "description": "A place to slow down, try an idea, and make your reasoning visible.",
                "objectives": ["Practice a controlled comparison"],
                "provenance": {
                    "author": "Gym frontend fixture",
                    "method": "import",
                    "rationale": "Synthetic material for isolated compatibility tests",
                },
                "lessons": lessons,
            }
        ),
    )
    return {
        "labs": list_labs(store),
        "lab": get_lab(store, "demo-lab"),
        "items": [public_item(i) for i in items if i["pool"] == "practice"],
        "registry": activity_types(),
    }


def journey_examples(store):
    """Actual responses from the synthetic store, separate from the no-history demo."""
    from . import sessions
    from .lab_activity import (
        ActivityEvent,
        ActivityStart,
        SessionLink,
        link_session,
        record_event,
        start_activity,
    )

    visit = start_activity(
        store,
        "demo-lab",
        ActivityStart(module="reasoning", lesson_id="compare", idempotency_key="synthetic-start"),
    )
    reading = record_event(
        store, visit["id"], ActivityEvent(action="reading", idempotency_key="synthetic-reading")
    )
    session = sessions.create_session(
        store, {"course_id": "demo-course", "module": "reasoning", "mode": "practice", "count": 6}
    )
    linked = link_session(store, visit["id"], SessionLink(session_id=session["id"]))
    paused = sessions.timer(store, session["id"], "pause")
    sessions.timer(store, session["id"], "resume")
    aid = sessions.assistance(store, session["id"], "demo-practice-mcq", "hint")
    answered = sessions.submit_answer(
        store,
        session["id"],
        {
            "item_id": "demo-practice-mcq",
            "answer": "A",
            "confidence": None,
            "idempotency_key": "synthetic-answer",
        },
    )
    finished = sessions.finish(store, session["id"])
    return {
        "data": "Synthetic examples only; not learner history",
        "visit_started": visit,
        "reading_recorded": reading,
        "session_created": session,
        "visit_linked": linked,
        "session_paused": paused,
        "assistance": aid,
        "answer_saved": answered,
        "session_finished": finished,
    }
