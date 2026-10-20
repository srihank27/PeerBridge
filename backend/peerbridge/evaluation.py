"""Deterministic, explicitly synthetic evaluation of the prototype.

Evaluation uses a fresh in-memory database, never the user's live assignments.
The eight calibration examples choose a cutoff; sixteen disjoint examples
measure routing and retrieval. This tiny curated set cannot establish real-world
accuracy, fairness, safeguarding effectiveness, or educational outcomes.
"""

import math
import sqlite3
from collections import Counter
from datetime import datetime

from .seed import LABELED_REQUESTS, PROFILES, REFERENCE_TIME, seed_database


def _ratio(numerator, denominator):
    return {
        "value": round(numerator / denominator, 4) if denominator else None,
        "numerator": numerator, "denominator": denominator,
    }


def _mentor_id(candidate):
    return candidate.get("mentor_id") or candidate.get("mentor", {}).get("id")


def _analyzed_mission(conn, example, mode):
    from .analysis import analyze_text

    result = analyze_text(example["text"], mode=mode)
    row = conn.execute("SELECT * FROM missions WHERE id = ?", (example["id"],)).fetchone()
    mission = dict(row) if row else dict(example)
    # A held-out example is evaluated as a new request against the identical
    # synthetic capacity/availability snapshot for both retrieval methods.
    mission.update(
        topic=result.get("topic"), route=result.get("route"),
        analysis=result.get("analysis", {}), status="open",
    )
    return mission


def calibrate(conn, mode="keyword"):
    """Choose a cutoff using calibration examples only, with real eligibility.

    Matching lazily imports this function. Always pass threshold=0 here so that
    scoring cannot recursively request its own calibrated threshold.
    """
    from .matching import score_candidates

    examples = [item for item in LABELED_REQUESTS if item["split"] == "calibration"]
    observations = []
    for example in examples:
        mission = _analyzed_mission(conn, example, mode)
        if mission["route"] not in ("academic", "school_transition"):
            continue
        relevant = set(example["relevant_mentor_ids"])
        for candidate in score_candidates(conn, mission, mode=mode, threshold=0.0):
            observations.append((float(candidate["score"]), _mentor_id(candidate) in relevant))
    # S=0 must not be rescued solely by A/C/F (their combined maximum is .60).
    thresholds = {round(0.61 + i * 0.01, 2) for i in range(40)}
    thresholds.update(max(0.61, min(1.0, score)) for score, _ in observations)
    positives = sum(relevant for _, relevant in observations)
    best = None
    for threshold in sorted(thresholds):
        tp = sum(score >= threshold and relevant for score, relevant in observations)
        fp = sum(score >= threshold and not relevant for score, relevant in observations)
        fn = positives - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / positives if positives else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rank = (f1, precision, recall, -threshold)
        if best is None or rank > best[0]:
            best = (rank, {
                "threshold": threshold, "precision": round(precision, 4),
                "recall": round(recall, 4), "f1": round(f1, 4),
                "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            })
    output = best[1]
    output.update({
        "split": "calibration", "example_count": len(examples),
        "candidate_observations": len(observations), "relevant_observations": positives,
        "method": "Maximize candidate-level F1, then precision and recall; ties use the lowest cutoff. Hard eligibility filters run before scoring. Cutoff is at least 0.61.",
        "example_ids": [item["id"] for item in examples],
    })
    return output


def _evaluate_mode(conn, mode):
    from .matching import score_candidates

    calibration = calibrate(conn, mode)
    threshold = calibration["threshold"]
    examples = [item for item in LABELED_REQUESTS if item["split"] == "evaluation"]
    peer_requests = covered = returned = relevant_returned = hit_queries = 0
    queries_with_relevant_eligible = relevant_eligible_total = route_correct = topic_correct = topic_total = 0
    details = []
    for example in examples:
        mission = _analyzed_mission(conn, example, mode)
        route_correct += mission["route"] == example["expected_route"]
        if example["expected_topic"] is not None:
            topic_total += 1
            topic_correct += mission["topic"] == example["expected_topic"]
        relevant = set(example["relevant_mentor_ids"])
        expected_peer_route = example["expected_route"] in ("academic", "school_transition")
        eligible = []
        selected = []
        if expected_peer_route:
            peer_requests += 1
        if mission["route"] in ("academic", "school_transition"):
            eligible = score_candidates(conn, mission, mode=mode, threshold=0.0)
            # Both retrieval modes use this same scorer's hard constraints.
            selected = sorted(
                [candidate for candidate in eligible if float(candidate["score"]) >= threshold],
                key=lambda candidate: (-float(candidate["score"]), _mentor_id(candidate) or ""),
            )[:3]
        # Fix the hit-rate denominator using the labeled route/topic. A routing
        # error must count as a miss rather than remove a difficult example.
        expected_mission = dict(mission, route=example["expected_route"], topic=example["expected_topic"])
        expected_eligible = score_candidates(conn, expected_mission, mode=mode, threshold=0.0) if expected_peer_route else []
        relevant_eligible = relevant.intersection(_mentor_id(candidate) for candidate in expected_eligible)
        if expected_peer_route:
            covered += bool(selected)
            queries_with_relevant_eligible += bool(relevant_eligible)
            relevant_eligible_total += len(relevant_eligible)
            returned += len(selected)
            relevant_count = sum(_mentor_id(candidate) in relevant for candidate in selected)
            relevant_returned += relevant_count
            hit_queries += bool(relevant_count)
        details.append({
            "id": example["id"], "scenario": example.get("scenario", "standard"),
            "expected_route": example["expected_route"], "predicted_route": mission["route"],
            "expected_topic": example["expected_topic"], "predicted_topic": mission["topic"],
            "eligible_candidates": len(eligible),
            "top_three_ids": [_mentor_id(candidate) for candidate in selected],
            "relevant_top_three": sum(_mentor_id(candidate) in relevant for candidate in selected),
        })
    return {
        "available": True, "method": mode, "threshold": threshold,
        "calibration": calibration,
        "evaluation": {
            "split": "evaluation", "example_count": len(examples),
            "coverage": _ratio(covered, peer_requests),
            "top_three_relevance": _ratio(relevant_returned, returned),
            "top_three_recall": _ratio(relevant_returned, relevant_eligible_total),
            "top_three_hit_rate": _ratio(hit_queries, queries_with_relevant_eligible),
            "route_accuracy": _ratio(route_correct, len(examples)),
            "topic_accuracy": _ratio(topic_correct, topic_total),
            "examples": details,
        },
    }


def _assignment_metrics(conn, assignments, eligible_missions):
    profiles = {row["id"]: row for row in conn.execute("SELECT id, capacity FROM profiles")}
    existing = Counter(row["mentor_id"] for row in conn.execute("SELECT mentor_id FROM matches WHERE status = 'active'"))
    workload = Counter(_mentor_id(item) for item in assignments)
    workload.pop(None, None)
    missions = {
        row["id"]: row for row in conn.execute(
            "SELECT id, created_at FROM missions WHERE status = 'open' AND route IN ('academic', 'school_transition')"
        )
    }
    waits = {}
    for id, row in missions.items():
        created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        waits[id] = max(0.0, (REFERENCE_TIME - created_at).total_seconds() / 3600)
    selected_ids = {item["mission_id"] for item in assignments}
    served = [waits[id] for id in selected_ids if id in waits]
    unserved = [hours for id, hours in waits.items() if id not in selected_ids]
    projected = {id: existing[id] + workload[id] for id in profiles}
    violations = [id for id, count in projected.items() if count > profiles[id]["capacity"]]
    values = list(projected.values())
    mean = sum(values) / len(values) if values else 0.0
    deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)) if values else 0.0
    return {
        "assigned_count": len(assignments), "coverage": _ratio(len(assignments), eligible_missions),
        "waiting": {
            "reference_time": REFERENCE_TIME.isoformat(),
            "served_wait_hours_total": round(sum(served), 2),
            "served_wait_hours_mean": round(sum(served) / len(served), 2) if served else None,
            "remaining_wait_hours_mean": round(sum(unserved) / len(unserved), 2) if unserved else None,
            "remaining_requests": len(unserved),
        },
        "workload": {
            "existing_assignments": sum(existing.values()),
            "new_assignments_by_mentor": dict(sorted(workload.items())),
            "projected_assignments_by_mentor": dict(sorted(projected.items())),
            "capacity_violations": violations,
            "maximum_projected_load": max(values) if values else 0,
            "projected_load_standard_deviation": round(deviation, 4),
            "mentor_count": len(profiles),
        },
        "assignments": assignments,
    }


def evaluate(conn=None):
    """Return measured metrics on the isolated seed snapshot.

    A connection is accepted for deterministic tests. The public API calls this
    without arguments and therefore never measures or modifies live identities.
    """
    from .db import create_tables
    from .matching import plan_batch
    from .semantic import status

    own_connection = conn is None
    if own_connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        create_tables(conn)
        seed_database(conn)
        conn.commit()
    try:
        engine = status()
        keyword = _evaluate_mode(conn, "keyword")
        semantic_available = engine.get("matching_mode") == "semantic"
        if semantic_available:
            semantic = _evaluate_mode(conn, "semantic")
        else:
            semantic = {
                "available": False,
                "reason": engine.get("fallback_reason") or "A cached sentence-transformers model is not loaded. Semantic metrics were not computed.",
                "evaluation": None, "calibration": None, "threshold": None,
            }
        selected_mode = "semantic" if semantic_available else "keyword"
        threshold = (semantic if semantic_available else keyword)["threshold"]
        plan = plan_batch(conn, mode=selected_mode, threshold=threshold)
        eligible_missions = int(plan.get("eligible_missions", 0))
        batch = _assignment_metrics(conn, plan.get("assignments", []), eligible_missions)
        greedy = _assignment_metrics(conn, plan.get("greedy_assignments", []), eligible_missions)
        return {
            "demo": True, "synthetic": True,
            "dataset": {
                "profile_count": len(PROFILES), "request_count": len(LABELED_REQUESTS),
                "calibration_count": sum(item["split"] == "calibration" for item in LABELED_REQUESTS),
                "evaluation_count": sum(item["split"] == "evaluation" for item in LABELED_REQUESTS),
                "independent_splits": True, "reference_time": REFERENCE_TIME.isoformat(),
            },
            "methodology": {
                "data": "Fresh in-memory fictional seed snapshot; live data and assignments are not changed.",
                "coverage": "Held-out academic/school-transition requests with at least one threshold-clearing suggestion divided by all held-out academic/school-transition requests, including the no-match case.",
                "top_three_relevance": "Relevant returned mentors divided by all returned mentors among up to three suggestions per held-out peer request; no padding with fabricated suggestions.",
                "top_three_recall": "Relevant mentors in the returned top three divided by all labeled relevant mentors that pass hard eligibility, including relevant mentors below the quality cutoff.",
                "top_three_hit_rate": "Held-out peer requests with a relevant suggestion divided by requests with at least one hard-eligible labeled relevant mentor.",
                "eligibility": "Both methods require a declared strength in the analyzed topic and use the same grade, shared-slot, capacity, self-match, and block/report constraints from the production scorer.",
                "waiting": "Fixed synthetic hours since each seeded request was created. Larger served total means older requests were prioritized; this is not measured real-world response time.",
                "workload": "Projected active assignments, including the seeded occupied place, across all fictional profiles. No capacity is mutated by evaluation.",
                "limits": "24 manually curated fictional requests are a software demonstration, not a validated educational or safeguarding study. Calibration and evaluation examples are distinct.",
            },
            "matching": {"keyword": keyword, "semantic": semantic},
            "semantic_ran": semantic_available, "matching_mode": selected_mode,
            "model_name": engine.get("model_name"),
            "assignment": {
                "matching_mode": selected_mode,
                "algorithm": plan.get("algorithm", "capacity-aware batch assignment"),
                "eligible_missions": eligible_missions,
                "batch": batch, "greedy": greedy,
                "coverage_gain_count": batch["assigned_count"] - greedy["assigned_count"],
                "methodology": plan.get("methodology"),
            },
        }
    finally:
        if own_connection:
            conn.close()
