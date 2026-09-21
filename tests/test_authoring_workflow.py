"""Behavioral fixtures for goal-directed authoring and external coursework outcomes."""

import json

import pytest

from gym.assessment import critique_artifact, save_artifact
from gym.assignments import (
    confirm_profile,
    create_assignment,
    generate_profile,
    record_coursework_outcome,
    request_profile,
    rerun_profile,
    revise_assignment,
    save_draft,
    save_rubric,
    submit,
)
from gym.authoring import RevisionConflict
from gym.generation import generate, request_generation, rerun_generation
from gym.ingestion import ingest
from gym.sessions import create_session, public_item


def reviewed_source(
    store,
    text="Course premises: random assignment controls selection in expectation.",
    role="instruction",
    name="lecture.md",
):
    source = ingest(store, "course", name, text.encode(), role)
    with store.tx() as c:
        return store.put(c, "source", source["id"], {**source, "reconstruction_status": "confirmed"})


def practice_rubric():
    return {
        "title": "Proposed causal reasoning",
        "authority": "proposed",
        "course_id": "course",
        "criteria": [
            {
                "name": "Reasoning",
                "weight": 1,
                "anchors": ["Unsupported", "Justifies the changed assumption and uncertainty"],
            }
        ],
    }


def profile_body():
    return {
        "title": "Prepare for the future quiz",
        "assessment_kinds": ["practice_quiz"],
        "question_types": ["mcq", "open"],
        "structure": "Reason from assumptions",
        "scoring_rules": "Apply the explicit rubric",
        "reasoning_demands": ["Identify assumptions"],
        "difficulty_anchor": "Two inferential steps",
        "uncertainty": ["Future exam format not confirmed"],
        "supporting_fragment_ids": [],
        "content_scope": "Causal inference and changed assignment",
        "rubric_basis": "Proposed reasoning anchors derived from the available course concepts",
        "practice_rubric": practice_rubric(),
    }


def target_profile(store, material, **options):
    if "target_assignment_id" not in options:
        options["target_assignment_id"] = assignment(store)["id"]
    proposed = request_profile(
        store,
        "course",
        [],
        material_source_ids=[material["id"]],
        target="Prepare for future causal inference coursework",
        profile=profile_body(),
        **options,
    )
    return confirm_profile(
        store, proposed["id"], {"expected_revision": proposed["revision"], "profile": proposed["profile"]}
    )


def assignment(store, title="Actual coursework", **options):
    return create_assignment(
        store,
        {
            "deadline": "2026-10-01T17:00:00-04:00",
            "effort_minutes": 60,
            "course_id": "course",
            "title": title,
            "prompt": "State and defend the causal assumptions for this task.",
            **options,
        },
    )


def outcome(**options):
    return {
        "idempotency_key": "actual-feedback",
        "score": 17.25,
        "feedback": "TA: distinguish the two alternatives.",
        "attribution": "TA feedback transcribed from the course record",
        "observed_at": "2026-09-20T16:00:00-04:00",
        "source_url": "https://example.test/coursework/1",
        **options,
    }


def test_external_outcome_requires_no_local_work_and_closes_only_obligation(store):
    a = assignment(store, points=20)
    result = record_coursework_outcome(store, a["id"], outcome(mark_completed=True))
    assert result["score"] == 17.25 and result["submission_id"] is None and result["occurred_at"] is None
    assert record_coursework_outcome(store, a["id"], outcome(mark_completed=True)) == result
    with pytest.raises(RevisionConflict):
        record_coursework_outcome(store, a["id"], outcome(score=18))
    with store.tx() as c:
        for kind in ("submission", "assignment_draft", "attempt", "learner", "schedule"):
            assert store.list(c, kind) == []
        assert len(store.list(c, "coursework_outcome")) == 1
        assert store.get(c, "assignment", a["id"])["status"] == "completed"
        task = store.get(c, "task", a["task_id"])
        assert task["status"] == "complete" and task["progress"] == []


def test_feedback_only_and_attributed_artifact_reclassification_preserve_history(store):
    a = assignment(store, status="completed")
    artifact = save_artifact(
        store,
        {
            "course_id": "course",
            "title": "Misfiled TA feedback",
            "body": "An observed instructor comment, not learner work.",
        },
    )
    payload = outcome(score=None, artifact_version_id=artifact["version_id"], reclassify_artifact=True)
    recorded = record_coursework_outcome(store, a["id"], payload)
    assert recorded["original_record_snapshot"]["body"] == artifact["body"]
    with store.tx() as c:
        assert store.list(c, "task") == []
        assert store.get(c, "artifact", artifact["id"])["classification"] == "coursework_record"
        assert "classification" not in store.get(c, "artifact_version", artifact["version_id"])
    with pytest.raises(ValueError, match="cannot be critiqued"):
        critique_artifact(store, None, artifact["version_id"])
    correction = record_coursework_outcome(
        store, a["id"], outcome(idempotency_key="corrected-outcome", supersedes=recorded["id"])
    )
    assert correction["supersedes"] == recorded["id"]
    with pytest.raises(RevisionConflict):
        record_coursework_outcome(
            store, a["id"], outcome(idempotency_key="conflicting-correction", supersedes=recorded["id"])
        )


def test_missing_rubric_and_self_study_are_not_invented_obligations(store):
    a = assignment(store, purpose="self_study")
    assert a["rubric_version_id"] is None and not a.get("task_id")
    save_draft(store, a["id"], {"body": "A real draft without an explicit scoring rubric."})
    with pytest.raises(ValueError, match="explicit rubric"):
        submit(store, a["id"], {"idempotency_key": "do-not-submit"})
    actual = assignment(store)
    revised = revise_assignment(
        store, actual["id"], {"expected_revision": actual["revision"], "purpose": "self_study"}
    )
    assert revised["purpose"] == "self_study"
    with store.tx() as c:
        assert store.get(c, "task", actual["task_id"])["completion_kind"] == "self_study_reclassification"
        assert store.list(c, "submission") == []


def test_profile_goal_prior_emergent_evidence_and_no_outcomes_in_model_input(store):
    prior = reviewed_source(store)
    new = reviewed_source(
        store,
        text="The future quiz asks for changed assumptions and uncertainty.",
        role="assessment",
        name="clarification.md",
    )
    rubric = save_rubric(store, practice_rubric())
    earlier = assignment(store, title="Prior practice quiz", rubric_id=rubric["id"])
    future = assignment(store, title="Future quiz", rubric_id=rubric["id"])
    record_coursework_outcome(store, earlier["id"], outcome(feedback="PRIVATE_GRADE_FEEDBACK_SENTINEL"))
    save_draft(store, earlier["id"], {"body": "PRIVATE_LEARNER_ANSWER_SENTINEL"})
    p = request_profile(
        store,
        "course",
        [],
        assignment_ids=[earlier["id"]],
        target_assignment_id=future["id"],
        material_source_ids=[prior["id"]],
        target="Prepare for the future quiz",
    )

    assert not p["emergent_source_ids"]
    p = rerun_profile(
        store,
        p["id"],
        {
            "expected_revision": p["revision"],
            "idempotency_key": "new-clarification",
            "emergent_source_ids": [new["id"]],
        },
    )

    class Designer:
        def complete(self, role, system, prompt):
            assert "PRIVATE_" not in prompt
            data = json.loads(prompt)
            assert data["prior_coursework"][0]["id"] == earlier["id"]
            assert data["intended_coursework"]["id"] == future["id"]
            assert data["emergent_evidence"][0]["source_version_id"] == new["id"]
            return {"profile": profile_body()}, {"model": "fixture"}

    proposed = generate_profile(store, Designer(), p["id"], run_version=2)
    assert proposed["status"] == "needs_review"
    confirmed = confirm_profile(
        store, p["id"], {"expected_revision": proposed["revision"], "profile": proposed["profile"]}
    )
    assert confirmed["profile"]["practice_rubric"]["authority"] == "proposed"
    with store.tx() as c:
        assert len(store.list(c, "assessment_profile_version")) == 4


def test_profile_versions_reruns_and_blueprints_keep_frozen_evidence(store):
    source = reviewed_source(store)
    future = assignment(store, title="Future exam")
    p = target_profile(store, source, target_assignment_id=future["id"])
    bp = request_generation(
        store,
        {
            "course_id": "course",
            "source_ids": [source["id"]],
            "topic": "Causal inference",
            "profile_id": p["id"],
        },
    )
    newer = reviewed_source(
        store, text="Additional course context about transport to a new population.", name="new.md"
    )
    revise_assignment(
        store,
        future["id"],
        {
            "expected_revision": future["revision"],
            "prompt": "New task requirement: defend transport to a new population.",
        },
    )
    payload = {
        "expected_revision": p["revision"],
        "idempotency_key": "rerun-v2",
        "emergent_source_ids": [newer["id"]],
    }
    rerun = rerun_profile(store, p["id"], payload)
    assert rerun["run_version"] == 2 and rerun["status"] == "queued"
    assert rerun_profile(store, p["id"], payload)["id"] == p["id"]
    with pytest.raises(RevisionConflict):
        rerun_profile(store, p["id"], {**payload, "target": "A different goal"})
    assert generate_profile(store, None, p["id"], run_version=1)["run_version"] == 2
    with store.tx() as c:
        old = store.get(c, "assessment_profile_version", p["profile_version_id"])
        assert old["status"] == "confirmed" and old["emergent_source_ids"] == []
        assert "New task requirement" not in old["target_assignment_snapshot"]["prompt"]
        assert store.get(c, "blueprint", bp["id"])["profile_snapshot"] == bp["profile_snapshot"]
    # Explicit historical versions remain usable while the new proposal is being prepared.
    same_target = request_generation(
        store,
        {
            "course_id": "course",
            "source_ids": [source["id"]],
            "topic": "Causal inference",
            "profile_id": p["id"],
            "profile_version_id": p["profile_version_id"],
        },
    )
    assert same_target["profile_snapshot"]["run_version"] == 1


def test_profiles_reject_foreign_unconfirmed_and_outcome_sources(store):
    source = reviewed_source(store)
    feedback = reviewed_source(store, role="feedback", name="grade.md")
    p = target_profile(store, source)
    for new_ids in [[feedback["id"]], [source["id"]]]:
        with pytest.raises(ValueError):
            rerun_profile(
                store,
                p["id"],
                {
                    "expected_revision": p["revision"],
                    "idempotency_key": "invalid-source",
                    "emergent_source_ids": new_ids,
                },
            )
    with store.tx() as c:
        store.put(c, "course", "other", {"title": "Another course"})
    other = create_assignment(
        store,
        {
            "deadline": "2026-10-01T17:00:00-04:00",
            "effort_minutes": 60,
            "course_id": "other",
            "title": "Foreign target",
            "prompt": "A target in another course",
        },
    )
    with pytest.raises(ValueError, match="another course"):
        request_profile(
            store,
            "course",
            [],
            material_source_ids=[source["id"]],
            target_assignment_id=other["id"],
            target="Future quiz goal",
        )


class PracticeDesigner:
    def __init__(self, counterfactual_valid=True):
        self.counter = 0
        self.counterfactual_valid = counterfactual_valid

    def complete(self, role, system, prompt):
        data = json.loads(prompt)
        if role == "designer":
            items = []
            for index, kind in enumerate(data["blueprint"]["required_item_types_in_order"]):
                self.counter += 1
                cf = index in data["blueprint"]["counterfactual_item_indices_in_batch"]
                item = {
                    "type": kind,
                    "stem": f"New item {self.counter}: Under changed assignment, which conclusion is justified?",
                    "options": [
                        {"label": x, "text": "Option " + x, "why": "Because of the assignment assumption"}
                        for x in "ABCD"
                    ],
                    "key": "B",
                    "explanation": "Selection changes the applicability of the original identification argument.",
                    "hint": "Examine assignment",
                    "plain": "Which conclusion follows?",
                    "source_fragment_ids": [data["sources"][0]["id"]],
                    "capabilities": ["causal-reasoning"],
                    "cognitive_operation": "counterfactual" if cf else "application",
                    "points": 5,
                }
                if cf:
                    item["counterfactual_derivation"] = {
                        "changed_assumption": "Replace random assignment with participant selection.",
                        "reasoning": "Random assignment supported the original comparison; selection requires additional exchangeability assumptions.",
                        "uncertainty": "Selection mechanisms are unknown; additional evidence is required.",
                        "source_fragment_ids": item["source_fragment_ids"],
                    }
                items.append(item)
            return {"items": items}, {"model": "synthetic-designer"}
        return {
            "reviews": [
                {
                    "index": i,
                    "valid": True,
                    "solved_key": "B",
                    "rationale": "Independently solved under stated assumptions",
                    "issues": [],
                    "counterfactual_valid": self.counterfactual_valid,
                }
                for i, _ in enumerate(data["items"])
            ]
        }, {"model": "synthetic-verifier"}


def test_counterfactual_reasoning_is_verified_inside_practice_and_sealed_in_exam(store):
    source = reviewed_source(store)
    p = target_profile(store, source)
    bp = request_generation(
        store,
        {
            "course_id": "course",
            "source_ids": [source["id"]],
            "topic": "Causal inference",
            "profile_id": p["id"],
            "count": 2,
            "counterfactual_count": 1,
            "mode": "simulation",
        },
    )
    generated = generate(store, PracticeDesigner(), bp["id"])
    assert generated["status"] == "ready"
    with store.tx() as c:
        items = [store.get(c, "item", ident) for ident in generated["item_ids"]]
        assert items[1]["counterfactual_derivation"]
        assert "counterfactual_derivation" not in public_item(items[1])
        assert len(store.list(c, "form")) == 1
    with pytest.raises(ValueError, match="sealed"):
        create_session(
            store,
            {
                "course_id": "course",
                "mode": "practice",
                "module": "all",
                "count": 2,
                "blueprint_id": bp["id"],
            },
        )


def test_failed_counterfactual_derivation_quarantines_entire_mock_exam(store):
    source = reviewed_source(store)
    bp = request_generation(
        store,
        {
            "course_id": "course",
            "source_ids": [source["id"]],
            "topic": "Assumptions",
            "count": 2,
            "counterfactual_count": 1,
            "mode": "simulation",
        },
    )
    result = generate(store, PracticeDesigner(counterfactual_valid=False), bp["id"])
    assert result["status"] == "review_required" and result["quarantined_count"] == 1
    with store.tx() as c:
        assert store.list(c, "form") == []


def test_regeneration_keeps_old_items_and_idempotency_and_can_select_new_set(store):
    source = reviewed_source(store)
    p = target_profile(store, source)
    bp = request_generation(
        store,
        {
            "course_id": "course",
            "source_ids": [source["id"]],
            "topic": "Assumptions",
            "count": 2,
            "counterfactual_count": 1,
            "profile_id": p["id"],
        },
    )
    router = PracticeDesigner()
    first = generate(store, router, bp["id"])
    rerun = rerun_generation(store, bp["id"], {"idempotency_key": "regenerate-same-target"})
    assert rerun["parent_blueprint_id"] == bp["id"] and rerun["id"] != bp["id"]
    assert (
        rerun_generation(store, bp["id"], {"idempotency_key": "regenerate-same-target"})["id"] == rerun["id"]
    )
    with pytest.raises(RevisionConflict):
        rerun_generation(
            store, bp["id"], {"idempotency_key": "regenerate-same-target", "topic": "Another topic"}
        )
    second = generate(store, router, rerun["id"])
    session = create_session(
        store,
        {
            "course_id": "course",
            "module": "all",
            "mode": "practice",
            "count": 2,
            "blueprint_id": second["id"],
        },
    )
    assert set(session["item_ids"]) == set(second["item_ids"])
    with store.tx() as c:
        assert all(store.get(c, "item", ident)["status"] == "active" for ident in first["item_ids"])
        assert store.list(c, "attempt") == []


def test_rest_contract_exposes_goal_versions_rerun_and_outcome(client, store):
    schema = client.get("/api/agent/schema").json()
    for route in (
        "/api/profiles/{ident}/versions",
        "/api/profiles/{ident}/rerun",
        "/api/generations/{ident}/rerun",
        "/api/assignments/{ident}/outcomes",
    ):
        assert route in schema["paths"]
    source = reviewed_source(store)
    response = client.post(
        "/api/profiles",
        json={
            "course_id": "course",
            "material_source_ids": [source["id"]],
            "target": "Prepare for future quiz",
            "target_assignment_id": assignment(store)["id"],
            "profile": profile_body(),
        },
    )
    assert response.status_code == 200, response.text
    profile = response.json()
    history = client.get(f"/api/profiles/{profile['id']}/versions").json()
    assert len(history["versions"]) == 1
    assert (
        client.put(
            f"/api/profiles/{profile['id']}", json={"expected_revision": 999, "profile": profile_body()}
        ).status_code
        == 409
    )


def test_profile_requires_real_dated_coursework_and_new_evidence_only_on_rerun(client, store):
    source = reviewed_source(store)
    spec = {
        "course_id": "course",
        "material_source_ids": [source["id"]],
        "target": "Prepare for the actual quiz",
    }
    assert client.post("/api/profiles", json=spec).status_code == 422
    task = assignment(store)
    spec["target_assignment_id"] = task["id"]
    assert (
        client.post("/api/profiles", json={**spec, "emergent_source_ids": [source["id"]]}).status_code == 422
    )
    optional = assignment(store, purpose="self_study", deadline=None)
    response = client.post("/api/profiles", json={**spec, "target_assignment_id": optional["id"]})
    assert response.status_code == 400 and "actual coursework" in response.text
    with store.tx() as c:
        store.put(c, "assignment", task["id"], {**task, "deadline": None})
    response = client.post("/api/profiles", json=spec)
    assert response.status_code == 400 and "deadline" in response.text
    with store.tx() as c:
        assert not store.list(c, "assessment_profile")
        store.put(c, "assignment", task["id"], task)
    response = client.post("/api/profiles", json=spec)
    assert response.status_code == 200
    p = response.json()
    assert p["contract_version"] == "targeted-profile-v2"
    assert p["target_assignment_snapshot"]["id"] == task["id"]
    assert p["emergent_source_ids"] == []
    with store.tx() as c:
        store.put(c, "assignment", task["id"], {**task, "deadline": "invalid"})
    response = client.post(
        f"/api/profiles/{p['id']}/rerun",
        json={"expected_revision": p["revision"], "idempotency_key": "invalid-deadline"},
    )
    assert response.status_code == 400 and "deadline" in response.text
    assert len(client.get(f"/api/profiles/{p['id']}/versions").json()["versions"]) == 1


def test_existing_v1_profile_keeps_generation_scope_but_rerun_requires_target(store):
    material = reviewed_source(store)
    other = reviewed_source(
        store, name="unselected.md", text="Unselected concepts must remain outside this profile."
    )
    p = target_profile(store, material)
    with store.tx() as c:
        legacy = store.put(
            c,
            "assessment_profile",
            p["id"],
            {**p, "contract_version": "targeted-profile-v1", "target_assignment_id": None},
        )
    # Historical profiles continue to enforce the same material scope.
    spec = {
        "course_id": "course",
        "profile_id": p["id"],
        "topic": "Causal reasoning",
        "source_ids": [material["id"]],
    }
    assert request_generation(store, spec)["profile_snapshot"]["contract_version"] == "targeted-profile-v1"
    with pytest.raises(ValueError, match="material scope"):
        request_generation(store, {**spec, "source_ids": [other["id"]]})
    payload = {"expected_revision": legacy["revision"], "idempotency_key": "upgrade-legacy"}
    with pytest.raises(ValueError):
        rerun_profile(store, p["id"], payload)
    upgraded = rerun_profile(store, p["id"], {**payload, "target_assignment_id": assignment(store)["id"]})
    assert upgraded["contract_version"] == "targeted-profile-v2"
