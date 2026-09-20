"""Point-in-time evaluation and guarded model promotion; never automatic causal attribution."""

import math
import statistics

from sqlalchemy import select

from .store import events, now, predictions, uid


def evaluate(store):
    with store.tx() as c:
        settings = store.get(c, "adaptation_settings", "default", False) or {"enabled": True}
        if not settings["enabled"]:
            return {"status": "disabled", "core_available": True}
        outcomes = [
            e for e in c.execute(select(events).where(events.c.event_type == "task.completed")).mappings()
        ]
        pairs = []
        for outcome in outcomes:
            actual = outcome["payload"].get("actual_active_minutes")
            if actual is None or actual <= 0:
                continue
            before = outcome["payload"]["before"]
            # Both timestamps enforce that no late-arriving outcome leaks into its own forecast.
            candidates = [
                p
                for p in c.execute(
                    select(predictions).where(
                        predictions.c.target_id == outcome["entity_id"],
                        predictions.c.target_version == before["scope_version"],
                        predictions.c.quantity == "remaining_effort",
                    )
                ).mappings()
                if p["created_at"] < outcome["occurred_at"] and p["created_at"] < outcome["received_at"]
            ]
            if not candidates:
                continue
            p = max(candidates, key=lambda x: x["created_at"])
            # Completion input is remaining active effort since this scope's forecast, not lifetime total.
            pairs.append(
                {
                    "prediction_id": p["id"],
                    "outcome_id": outcome["id"],
                    "task_id": outcome["entity_id"],
                    "predicted_at": p["created_at"],
                    "received_at": outcome["received_at"],
                    "actual": actual,
                    "p50": p["distribution"]["p50"],
                    "base_effort": p["distribution"]["p50"]
                    / (store.get(c, "model", p["model_version"], False) or {"multiplier": 1.0})["multiplier"],
                    "p80": p["distribution"]["p80"],
                    "category": before["category"],
                }
            )
        pairs.sort(key=lambda p: p["received_at"])

        def pinball(actual, pred, q):
            error = actual - pred
            return max(q * error, (q - 1) * error)

        result = {
            "created_at": now(),
            "pairs": pairs,
            "count": len(pairs),
            "baseline": "effort-prior-v1",
            "status": "insufficient_evidence",
            "decision": "Retain the active baseline",
            "causal_claim": "None. Prediction evaluation does not establish an intervention effect.",
            "promotion_requirements": "At least 12 matched outcomes, chronological holdout, >10% p50 error improvement, no p80 loss regression, explicit activation.",
        }
        performance = []
        for attempt in store.list(c, "attempt"):
            if (
                attempt.get("invalidated")
                or attempt.get("score") is None
                or attempt.get("assistance")
                or attempt.get("previous_exposures", 0)
            ):
                continue
            session = store.get(c, "session", attempt["session_id"])
            if session["status"] != "finished":
                continue
            pred = (
                c.execute(
                    select(predictions).where(
                        predictions.c.target_id == attempt["session_id"] + ":" + attempt["item_id"],
                        predictions.c.quantity == "expected_score_ratio",
                        predictions.c.created_at < attempt["created_at"],
                    )
                )
                .mappings()
                .first()
            )
            if pred:
                item = session["snapshots"][attempt["item_id"]]
                performance.append(
                    {
                        "prediction_id": pred["id"],
                        "attempt_id": attempt["id"],
                        "item_type": item["type"],
                        "predicted": pred["distribution"]["mean"],
                        "actual": attempt["score"] / item["points"],
                    }
                )
        result["independent_performance"] = {
            "count": len(performance),
            "pairs": performance,
            "mean_squared_score_error": statistics.mean(
                (p["predicted"] - p["actual"]) ** 2 for p in performance
            )
            if performance
            else None,
            "note": "A proper Brier score only for binary items; partial-credit rows use squared score error.",
        }
        if pairs:
            result["metrics"] = {
                "median_absolute_error": statistics.median(abs(p["actual"] - p["p50"]) for p in pairs),
                "p80_coverage": sum(p["actual"] <= p["p80"] for p in pairs) / len(pairs),
                "p80_pinball_loss": statistics.mean(pinball(p["actual"], p["p80"], 0.8) for p in pairs),
            }
        if len(pairs) >= 12:
            split = max(8, int(len(pairs) * 0.7))
            test = pairs[split:]
            # Every training outcome must have been available before any held-out forecast.
            cutoff = min(p["predicted_at"] for p in test)
            train = [p for p in pairs[:split] if p["received_at"] < cutoff]
            if len(train) < 8:
                result["decision"] = "Too few point-in-time training outcomes; retain baseline"
                ident = uid("evaluation_")
                store.put(c, "evaluation", ident, result)
                return {**result, "id": ident}
            factor = statistics.median(p["actual"] / p["base_effort"] for p in train)
            ratios = sorted(p["actual"] / p["base_effort"] for p in train)
            upper = ratios[min(len(ratios) - 1, math.ceil(len(ratios) * 0.8) - 1)]
            baseline = statistics.mean(abs(p["actual"] - p["p50"]) for p in test)
            candidate = statistics.mean(abs(p["actual"] - p["base_effort"] * factor) for p in test)
            old_tail = statistics.mean(pinball(p["actual"], p["p80"], 0.8) for p in test)
            new_tail = statistics.mean(pinball(p["actual"], p["base_effort"] * upper, 0.8) for p in test)
            passed = candidate < baseline * 0.9 and new_tail <= old_tail
            mid = uid("model_")
            store.put(
                c,
                "model",
                mid,
                {
                    "role": "effort",
                    "status": "shadow" if passed else "rejected",
                    "multiplier": factor,
                    "upper_multiplier": max(factor, upper),
                    "created_at": now(),
                    "promotion_eligible": passed,
                    "train_count": len(train),
                    "holdout_count": len(test),
                    "holdout_mae": candidate,
                    "baseline_mae": baseline,
                    "holdout_p80_loss": new_tail,
                    "input_prediction_ids": [p["prediction_id"] for p in pairs],
                },
            )
            result.update(
                status="candidate_in_shadow" if passed else "baseline_retained",
                candidate_id=mid,
                decision="Candidate passed a small temporal holdout; review before activation"
                if passed
                else "Candidate did not improve the baseline",
            )
        ident = uid("evaluation_")
        store.put(c, "evaluation", ident, result)
        return {**result, "id": ident}


def activate_model(store, ident):
    with store.tx() as c:
        model = store.get(c, "model", ident)
        if model["status"] not in {"shadow", "retired"} or not model.get("promotion_eligible"):
            raise ValueError("Only an evaluated candidate or previously active model can be activated")
        for current in store.list(c, "model"):
            if current["role"] == model["role"] and current["status"] == "active":
                store.put(c, "model", current["id"], {**current, "status": "retired"})
        result = store.put(c, "model", ident, {**model, "status": "active", "activated_at": now()})
        store.invalidate(c, "model:effort", "Model version changed")
        store.emit(c, "model.activated", ident, {"role": model["role"], "model_id": ident})
        return result


def record_intervention(store, data):
    alternatives = data.get("alternatives", [])
    if len(alternatives) < 2 or data.get("chosen") not in alternatives:
        raise ValueError("Record the eligible alternatives and chosen intervention")
    if data.get("randomized") and not 0 < data.get("assignment_probability", 0) <= 1:
        raise ValueError("Randomized decisions require actual assignment probability")
    with store.tx() as c:
        ident = uid("intervention_")
        result = store.put(
            c, "intervention", ident, {**data, "created_at": now(), "causal_effect": "not_established"}
        )
        store.emit(c, "intervention.assigned", ident, data)
        return result
