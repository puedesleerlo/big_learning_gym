"""The gym contract: propose, deliver, assess, report evidence."""

import random
from datetime import datetime, timezone

from sqlalchemy import insert

from .learning import recommend, update_learner
from .store import now, predictions, uid

PUBLIC_ITEM_FIELDS = {
    "id",
    "type",
    "stem",
    "options",
    "prompts",
    "terms",
    "points",
    "module",
    "vignette",
    "capabilities",
    "cognitive_operation",
    "rubric",
    "rubric_version",
}


def public_item(item):
    output = {k: v for k, v in item.items() if k in PUBLIC_ITEM_FIELDS}
    if "options" in output:
        output["options"] = [{k: o[k] for k in ("label", "text")} for o in output["options"]]
    if "prompts" in output:
        output["prompts"] = [{k: p[k] for k in ("id", "text")} for p in output["prompts"]]
    if output.get("vignette"):
        output["vignette"] = {
            k: v for k, v in output["vignette"].items() if k in {"id", "title", "text", "table"}
        }
    return output


def elapsed(start):
    return max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(start)).total_seconds())


def tick(session):
    if session.get("running"):
        delta = min(45, elapsed(session["last_tick"]))
        session["active_seconds"] += delta
        item = session.get("current_item")
        if item:
            session["item_seconds"][item] = session["item_seconds"].get(item, 0) + delta
    session["last_tick"] = now()


def create_session(store, spec):
    with store.tx() as c:
        store.get(c, "course", spec["course_id"])
        forms = store.list(c, "form")
        available = [
            i
            for i in store.list(c, "item")
            if i["course_id"] == spec["course_id"] and i["status"] == "active"
        ]
        if spec.get("blueprint_id"):
            blueprint = store.get(c, "blueprint", spec["blueprint_id"])
            if blueprint["course_id"] != spec["course_id"]:
                raise ValueError("Question set belongs to another course")
            if blueprint["mode"] == "simulation" and spec["mode"] != "simulation":
                raise ValueError("Simulation items require the sealed simulation workflow")
            if spec["mode"] == "simulation" and spec.get("form") != blueprint["id"]:
                raise ValueError("Simulation form must match the selected question set")
            available = [i for i in available if i.get("blueprint_id") == blueprint["id"]]
        attempts = store.list(c, "attempt")
        mode = spec["mode"]
        limit = None
        if mode == "simulation":
            form = next(
                (
                    f
                    for f in forms
                    if f["course_id"] == spec["course_id"]
                    and (f["id"] == spec.get("form") or f["label"] == spec.get("form"))
                ),
                None,
            )
            if not form:
                raise ValueError("Choose a complete simulation form")
            by_id = {i["id"]: i for i in available}
            if any(i not in by_id for i in form["item_ids"]):
                raise ValueError("This form contains a quarantined item")
            items = [by_id[i] for i in form["item_ids"]]
            limit = form["minutes"] * 60
        else:
            items = [
                i
                for i in available
                if (i["pool"] in {"practice", "transfer"} if mode == "practice" else i["pool"] == mode)
                and (spec["module"] == "all" or i["module"] == spec["module"])
            ]
            if not items:
                raise ValueError("No verified items for this mode yet. Create a set in Authoring.")

            # Weighted sampling without replacement: unseen and latest errors are favored.
            def weight(item):
                seen = [a for a in attempts if a["item_id"] == item["id"]]
                if not seen:
                    return 5.0
                last = seen[-1]
                ratio = (last.get("score") or 0) / item["points"]
                return (1.0 + 3 * (1 - ratio)) / (1 + len(seen) * 0.5)

            ranked = sorted(items, key=lambda i: random.random() ** (1 / weight(i)), reverse=True)
            items = ranked[: spec["count"]]
        ident = uid("session_")
        item_snapshots = {i["id"]: i for i in items}
        exposures = {
            i["id"]: sum(1 for a in attempts if a.get("family_id") == i.get("family_id")) for i in items
        }
        record = {
            **spec,
            "status": "active",
            "item_ids": [i["id"] for i in items],
            "snapshots": item_snapshots,
            "item_seconds": {},
            "assistance": {},
            "exposures": exposures,
            "started_at": now(),
            "last_tick": now(),
            "running": True,
            "active_seconds": 0.0,
            "current_item": items[0]["id"],
            "time_limit_seconds": limit,
            "selection_policy": "weakness-unseen-v1",
            "rationale": recommend(store, c, spec["course_id"]),
        }
        session = store.put(c, "session", ident, record)
        for item in items:
            states = [
                store.get(c, "learner", "learner:" + item["course_id"] + ":" + cap, False)
                for cap in item.get("capabilities", [])
            ]
            estimates = [
                s["dimensions"][item.get("cognitive_operation", "application")]["estimate"]
                for s in states
                if s and item.get("cognitive_operation", "application") in s["dimensions"]
            ]
            mean = sum(estimates) / len(estimates) if estimates else 0.5
            c.execute(
                insert(predictions).values(
                    id=uid("prediction_"),
                    target_id=ident + ":" + item["id"],
                    target_version=item["revision"],
                    quantity="expected_score_ratio",
                    distribution={"mean": mean, "calibrated": False},
                    input_state_revision=store.revision(c),
                    input_evidence_ids=[e for s in states if s for e in s["evidence_ids"]],
                    model_version="capability-beta-v1",
                    created_at=now(),
                    stale_reason=None,
                    dependencies=[
                        "learner:" + item["course_id"] + ":" + cap for cap in item.get("capabilities", [])
                    ],
                )
            )
        store.emit(
            c,
            "session.started",
            ident,
            {"mode": mode, "item_ids": record["item_ids"], "policy": "weakness-unseen-v1"},
        )
        return session_view(store, c, session)


def session_view(store, c, session):
    attempts = [a for a in store.list(c, "attempt") if a["session_id"] == session["id"]]
    result = {k: v for k, v in session.items() if k not in {"snapshots", "exposures", "assistance"}}
    result["items"] = [public_item(session["snapshots"][i]) for i in session["item_ids"]]
    result["remaining_seconds"] = (
        max(0, session["time_limit_seconds"] - elapsed(session["started_at"]))
        if session["time_limit_seconds"]
        else None
    )
    result["answers"] = {
        a["item_id"]: {
            "answer": a["answer"],
            "id": a["id"],
            "status": a["status"],
            **(
                {"score": a.get("score"), "feedback": a.get("feedback")}
                if session["mode"] != "simulation" or session["status"] == "finished"
                else {}
            ),
        }
        for a in attempts
    }
    if session["status"] == "finished":
        scored = [a for a in attempts if a.get("score") is not None]
        result["score"] = sum(a["score"] for a in scored)
        result["max_score"] = sum(i["points"] for i in session["snapshots"].values())
        result["pending_assessments"] = sum(a["status"] == "pending" for a in attempts)
        result["review"] = [
            {
                "item": public_item(session["snapshots"][i]),
                "feedback": feedback(session["snapshots"][i]),
                "attempt": next((a for a in attempts if a["item_id"] == i), None),
            }
            for i in session["item_ids"]
        ]
    return result


def feedback(item):
    return {
        k: item[k]
        for k in ["key", "explanation", "options", "prompts", "ref", "review", "verification"]
        if k in item
    }


def deterministic_score(item, answer):
    if item["type"] == "mcq":
        if answer not in [o["label"] for o in item["options"]]:
            raise ValueError("Select a valid option")
        return item["points"] if answer == item["key"] else 0
    if item["type"] == "matching":
        if not isinstance(answer, dict) or set(answer) != {p["id"] for p in item["prompts"]}:
            raise ValueError("Match every prompt")
        if not set(answer.values()) <= {t["id"] for t in item["terms"]}:
            raise ValueError("Choose valid matching terms")
        return (
            item["points"] * sum(answer[p["id"]] == p["key"] for p in item["prompts"]) / len(item["prompts"])
        )
    if not isinstance(answer, str) or len(answer.strip()) < 10:
        raise ValueError("Write an assessable answer of at least 10 characters")
    return None


def submit_answer(store, session_id, request):
    with store.tx() as c:
        s = store.get(c, "session", session_id)
        item_id = request["item_id"]
        if item_id not in s["item_ids"]:
            raise ValueError("Item does not belong to this session")
        prior = next(
            (
                a
                for a in store.list(c, "attempt")
                if a["session_id"] == session_id and a["item_id"] == item_id
            ),
            None,
        )
        if prior:
            if prior["idempotency_key"] == request["idempotency_key"]:
                return session_view(store, c, s)
            raise ValueError("This answer has already been submitted")
        if s["status"] != "active":
            raise ValueError("Session is already finished")
        if s["time_limit_seconds"] and elapsed(s["started_at"]) > s["time_limit_seconds"]:
            raise ValueError("Time is up. Finish the simulation to review your answers.")
        current = store.get(c, "item", item_id)
        # A retired item's already-open sessions retain their original snapshot;
        # quarantine is different: its scoring evidence has been declared invalid.
        if current["status"] not in {"active", "retired"}:
            raise ValueError("This item was quarantined; finish and start a new session")
        item = s["snapshots"][item_id]
        score = deterministic_score(item, request["answer"])
        tick(s)
        ident = uid("attempt_")
        attempt = {
            **request,
            "session_id": session_id,
            "course_id": s["course_id"],
            "mode": s["mode"],
            "item_revision": item["revision"],
            "family_id": item["family_id"],
            "item_type": item["type"],
            "active_seconds": round(s["item_seconds"].get(item_id, 0), 2),
            "wall_seconds": round(elapsed(s["started_at"]), 2),
            "assistance": s["assistance"].get(item_id, []),
            "previous_exposures": s["exposures"][item_id],
            "score": score,
            "status": "pending" if score is None else "assessed",
            "created_at": now(),
            "assessor_type": "llm" if score is None else "answer_key",
            "rubric_version": item.get("rubric_version", "v1"),
            "feedback": None if score is None else feedback(item),
        }
        event_id, _ = store.emit(
            c,
            "attempt.submitted",
            ident,
            {k: v for k, v in attempt.items() if k != "feedback"},
            key="answer:" + session_id + ":" + request["idempotency_key"],
        )
        attempt["event_id"] = event_id
        store.put(c, "attempt", ident, attempt)
        if score is not None and s["mode"] != "simulation":
            update_learner(store, c, attempt, item, event_id)
        else:
            store.enqueue(c, "assess", {"attempt_id": ident}, key="assess:" + ident, priority=0)
        store.put(c, "session", session_id, s)
        return session_view(store, c, store.get(c, "session", session_id))


def assistance(store, session_id, item_id, kind):
    if kind not in {"hint", "plain", "terms"}:
        raise ValueError("Unknown assistance type")
    with store.tx() as c:
        s = store.get(c, "session", session_id)
        if s["mode"] == "simulation":
            raise ValueError("Assistance is disabled in simulation")
        if s["status"] != "active" or item_id not in s["item_ids"]:
            raise ValueError("No active item")
        item = s["snapshots"][item_id]
        if kind == "terms":
            value = [
                t
                for t in store.list(c, "term")
                if t["course_id"] == s["course_id"]
                and (t["id"] in item.get("term_ids", []) or t.get("legacy_id") in item.get("gloss", []))
            ]
        else:
            value = item.get(kind, "No aid is available for this item")
        aids = s["assistance"].setdefault(item_id, [])
        if kind not in aids:
            aids.append(kind)
            store.put(c, "session", session_id, s)
            store.emit(c, "assistance.requested", session_id, {"item_id": item_id, "kind": kind})
        return {"kind": kind, "content": value}


def timer(store, session_id, action, item_id=None):
    with store.tx() as c:
        s = store.get(c, "session", session_id)
        if s["status"] != "active":
            return {"active_seconds": s["active_seconds"], "running": False}
        if item_id and item_id not in s["item_ids"]:
            raise ValueError("Unknown session item")
        tick(s)
        if action == "pause":
            s["running"] = False
        elif action == "resume":
            s["running"] = True
        if item_id:
            s["current_item"] = item_id
        store.put(c, "session", session_id, s)
        if action != "heartbeat":
            store.emit(
                c,
                "session." + action,
                session_id,
                {"active_seconds": s["active_seconds"], "item_id": item_id},
            )
        return {"active_seconds": s["active_seconds"], "running": s["running"]}


def finish(store, session_id, blocker=None):
    with store.tx() as c:
        s = store.get(c, "session", session_id)
        if s["status"] == "finished":
            return session_view(store, c, s)
        tick(s)
        s.update(status="finished", running=False, finished_at=now(), blocker=blocker)
        attempted = [a for a in store.list(c, "attempt") if a["session_id"] == session_id]
        if s["mode"] == "simulation":
            for attempt in attempted:
                update_learner(store, c, attempt, s["snapshots"][attempt["item_id"]], attempt["event_id"])
        s["completion"] = "complete" if len(attempted) == len(s["item_ids"]) else "unfinished"
        s["wall_seconds"] = elapsed(s["started_at"])
        s["interruption_seconds"] = max(0, s["wall_seconds"] - s["active_seconds"])
        store.put(c, "session", session_id, s)
        store.emit(
            c,
            "session.finished",
            session_id,
            {
                "active_seconds": s["active_seconds"],
                "wall_seconds": s["wall_seconds"],
                "interruption_seconds": s["interruption_seconds"],
                "completion": s["completion"],
                "blocker": blocker,
            },
        )
        return session_view(store, c, store.get(c, "session", session_id))
