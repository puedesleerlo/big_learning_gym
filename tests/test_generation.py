import json

import pytest

from gym.generation import generate, request_generation
from gym.ingestion import ingest, parse_file


class FakeRouter:
    def __init__(self, wrong_key=False):
        self.calls = []
        self.wrong_key = wrong_key
        self.counter = 0

    def complete(self, role, system, prompt, json_output=True):
        data = json.loads(prompt)
        self.calls.append((role, data))
        if role == "designer":
            items = []
            for kind in data["blueprint"]["required_item_types_in_order"]:
                self.counter += 1
                items.append(
                    {
                        "type": kind,
                        "stem": f"Scenario {self.counter}: Which conclusion is warranted under random assignment?",
                        "options": [
                            {"label": x, "text": "Answer " + x, "why": "Rationale " + x} for x in "ABCD"
                        ]
                        if kind == "mcq"
                        else [],
                        "key": "B" if kind == "mcq" else "",
                        "explanation": "Random assignment changes the identification assumptions.",
                        "hint": "Examine assignment",
                        "plain": "What can you conclude?",
                        "source_fragment_ids": [data["sources"][0]["id"]],
                        "capabilities": ["causal-reasoning"],
                        "cognitive_operation": "application",
                        "rubric": []
                        if kind == "mcq"
                        else [{"name": "Reasoning", "weight": 1, "anchors": ["Unsupported", "Justified"]}],
                        "points": 5,
                    }
                )
            return {"items": items}, {"model": "test", "call_id": "fake"}
        return {
            "reviews": [
                {
                    "index": i,
                    "valid": True,
                    "solved_key": "A" if self.wrong_key else x["key"],
                    "rationale": "Independently checked",
                    "issues": [],
                }
                for i, x in enumerate(data["items"])
            ]
        }, {"model": "test", "call_id": "fake"}


def source(store, role="instruction"):
    return ingest(
        store,
        "course",
        "lesson.md",
        b"# Random assignment\nRandom assignment addresses treatment selection in expectation.",
        role,
    )


def test_generation_batches_and_enforces_type_coverage(store):
    s = source(store)
    r = FakeRouter()
    bp = request_generation(
        store,
        {
            "course_id": "course",
            "topic": "Causal inference",
            "source_ids": [s["id"]],
            "count": 6,
            "question_types": ["mcq", "open"],
            "type_counts": {"mcq": 4, "open": 2},
        },
    )
    result = generate(store, r, bp["id"])
    assert result["status"] == "ready" and len(result["item_ids"]) == 6
    assert [x[0] for x in r.calls] == ["designer", "designer", "verifier", "verifier"]
    # A retry after publication performs no paid calls or item duplication.
    generate(store, r, bp["id"])
    assert len(r.calls) == 4


def test_verifier_key_disagreement_quarantines(store):
    s = source(store)
    r = FakeRouter(wrong_key=True)
    bp = request_generation(
        store, {"course_id": "course", "topic": "Causal inference", "source_ids": [s["id"]], "count": 1}
    )
    result = generate(store, r, bp["id"])
    assert result["quarantined_count"] == 1
    with store.tx() as c:
        assert store.list(c, "item")[0]["status"] == "quarantined"


def test_raw_assessment_content_is_not_used_to_generate_practice(store):
    s = source(store, "assessment")
    with pytest.raises(ValueError, match="assessment material"):
        request_generation(store, {"course_id": "course", "topic": "Reasoning", "source_ids": [s["id"]]})


def test_source_versions_deduplicate_and_keep_originals(store):
    a = source(store)
    b = source(store)
    assert a["id"] == b["id"]
    newer = ingest(
        store, "course", "lesson.md", b"# Revised lecture\nA corrected assumption is now explicit."
    )
    assert newer["version"] == 2
    with store.tx() as c:
        assert not store.get(c, "source", a["id"])["latest"]
        assert store.get(c, "source", newer["id"])["latest"]


def test_native_notebook_boundaries_and_outputs():
    raw = json.dumps(
        {"cells": [{"cell_type": "code", "source": ["2+2"], "outputs": [{"data": {"text/plain": ["4"]}}]}]}
    ).encode()
    fragments, _ = parse_file("lab.ipynb", raw)
    assert fragments[0]["anchor"] == "cell:1" and "4" in fragments[0]["text"]


def test_shared_case_remains_identical_across_generation_batches(store):
    class CaseRouter(FakeRouter):
        def complete(self, role, system, prompt, json_output=True):
            if "Create one original shared case" in prompt:
                return {
                    "vignette": {
                        "title": "One fixed scenario",
                        "text": "A fictional tutoring program randomly assigns learners to a new service. All outcomes are observed, but applicability outside the sampled population requires additional assumptions.",
                        "table": {
                            "caption": "Recorded scores",
                            "columns": ["Group", "Mean"],
                            "rows": [["Treatment", "75"], ["Control", "70"]],
                        },
                    }
                }, {"model": "fixture"}
            return super().complete(role, system, prompt, json_output)

    s = source(store)
    bp = request_generation(
        store,
        {
            "course_id": "course",
            "topic": "Causal reasoning",
            "source_ids": [s["id"]],
            "count": 6,
            "mode": "simulation",
            "shared_case_items": 3,
        },
    )
    result = generate(store, CaseRouter(), bp["id"])
    with store.tx() as c:
        items = [store.get(c, "item", i) for i in result["item_ids"]]
        assert all("vignette" not in i for i in items[:3])
        assert items[3]["vignette"] == items[5]["vignette"]
        assert len(store.list(c, "form")) == 1
