"""Explainable scoring, hard eligibility constraints, and capacity-aware assignment."""

from collections import deque
from datetime import datetime, timezone
from functools import lru_cache
import json
import sqlite3
import uuid

from . import semantic
from .analysis import analyze_text
from .db import decode, match_dict, profile_dict, resource_dict, utcnow


class MatchConflict(ValueError):
    pass


def is_reported(conn, target_type, target_id):
    return conn.execute("SELECT 1 FROM reports WHERE target_type=? AND target_id=? LIMIT 1", (target_type, target_id)).fetchone() is not None


def publishable(conn, mission):
    m = dict(mission)
    return (m["route"] in ("academic", "school_transition") and m["status"] in ("open", "matched")
            and not is_reported(conn, "mission", m["id"])
            and not is_reported(conn, "profile", m["requester_id"]))


def eligibility(conn, mission, mentor):
    """Return (eligible, reason). Used identically by both matching modes."""
    m, p = dict(mission), dict(mentor)
    if not publishable(conn, m) or m["status"] != "open":
        return False, "The mission is not open for peer matching."
    if analyze_text(m["text"], "keyword")["route"] == "private_support":
        return False, "Safety routing keeps this request private."
    requester = conn.execute("SELECT * FROM profiles WHERE id=?", (m["requester_id"],)).fetchone()
    if requester is None or p["id"] == m["requester_id"]:
        return False, "A hero cannot mentor their own request."
    if not m.get("topic") or m["topic"] not in decode(p["strengths"], []):
        return False, "The mentor has not declared a strength in this topic."
    if p["grade_band"] != requester["grade_band"]:
        return False, "Grade bands do not match."
    if is_reported(conn, "profile", p["id"]):
        return False, "This profile has a pending simulated report."
    if conn.execute("SELECT 1 FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)", (m["requester_id"], p["id"], p["id"], m["requester_id"])).fetchone():
        return False, "This pairing has been blocked."
    if conn.execute("SELECT 1 FROM reports r JOIN matches x ON r.target_type='match' AND r.target_id=x.id WHERE (x.requester_id=? AND x.mentor_id=?) OR (x.requester_id=? AND x.mentor_id=?)", (m["requester_id"], p["id"], p["id"], m["requester_id"])).fetchone():
        return False, "A match for this pair has a pending simulated report."
    if not (set(decode(p["available_slots"], [])) & set(decode(requester["available_slots"], []))):
        return False, "No shared availability."
    active = conn.execute("SELECT COUNT(*) FROM matches WHERE mentor_id=? AND status='active'", (p["id"],)).fetchone()[0]
    if p["capacity"] <= active:
        return False, "This mentor has no remaining capacity."
    return True, "All hard eligibility constraints pass."


def score_candidates(conn, mission, mode="keyword", threshold=0.0):
    m = dict(mission)
    requester_row = conn.execute("SELECT * FROM profiles WHERE id=?", (m["requester_id"],)).fetchone()
    if not requester_row or not m.get("topic"):
        return []
    requester = profile_dict(conn, requester_row)
    result = []
    actual_mode = semantic.effective_mode(mode)
    for row in conn.execute("SELECT * FROM profiles ORDER BY alias COLLATE NOCASE"):
        if not eligibility(conn, m, row)[0]:
            continue
        mentor = profile_dict(conn, row)
        shared = sorted(set(requester["available_slots"]) & set(mentor["available_slots"]))
        requester_preferences, mentor_preferences = set(requester["support_preferences"]), set(mentor["support_preferences"])
        preference_union = requester_preferences | mentor_preferences
        components = {
            "S": semantic.similarity(m["text"], mentor["strengths"], actual_mode, topic=m["topic"]),
            "A": len(shared) / max(1, len(requester["available_slots"])),
            "C": len(requester_preferences & mentor_preferences) / len(preference_union) if preference_union else 0.5,
            "F": mentor["remaining_capacity"] / mentor["capacity"],
        }
        score = sum(components[key] * weight for key, weight in (("S", .40), ("A", .25), ("C", .20), ("F", .15)))
        if score + 1e-9 < threshold:
            continue
        strengths = m["topic"].replace("_", " ") if m["topic"] in mentor["strengths"] else ", ".join(s.replace("_", " ") for s in mentor["strengths"])
        explanation = (f"Declared strengths: {strengths}. Shared availability: {', '.join(shared)}. "
                       f"Support preference overlap: {len(requester_preferences & mentor_preferences)}/{len(preference_union) or 0}; "
                       f"mentor has {mentor['remaining_capacity']} of {mentor['capacity']} places free. "
                       f"S uses {'cached sentence embeddings' if actual_mode == 'semantic' else 'explicit topic keywords'}; "
                       "H = 0.40S + 0.25A + 0.20C + 0.15F. Giving and receiving are independent.")
        result.append({"mentor": mentor, "score": round(score, 6), "component_scores": {k: round(v, 6) for k, v in components.items()}, "explanation": explanation, "shared_slots": shared})
    return sorted(result, key=lambda c: (-c["score"], c["mentor"]["alias"].casefold()))


def determine_threshold(conn, mode="keyword"):
    # Calibration is always isolated from changing demo assignments, reports,
    # or blocks. Evaluation records are never used to choose this threshold.
    return _calibrated_threshold(semantic.effective_mode(mode))


@lru_cache(maxsize=2)
def _calibrated_threshold(mode):
    from .evaluation import calibrate
    from .db import create_tables
    from .seed import seed_database
    with sqlite3.connect(":memory:") as calibration_conn:
        calibration_conn.row_factory = sqlite3.Row
        create_tables(calibration_conn)
        seed_database(calibration_conn)
        result = calibrate(calibration_conn, mode)
    value = result["threshold"] if isinstance(result, dict) else result
    return min(1.0, max(0.61, float(value)))


def recommend(conn, mission, mode=None, threshold=None, exclude_reported=True):
    m = dict(mission)
    status = semantic.status()
    actual_mode = semantic.effective_mode(mode)
    selected_threshold = determine_threshold(conn, actual_mode) if threshold is None else threshold
    current_analysis = analyze_text(m["text"], actual_mode)
    # Reanalyze seed labels with the actual running engine. Existing private or
    # unclear requests require resubmission before they may enter peer matching.
    if m["route"] not in ("private_support", "clarify"):
        m.update(topic=current_analysis["topic"], route=current_analysis["route"])
    analysis = current_analysis["analysis"]
    resource_rows = [resource_dict(row) for row in conn.execute("SELECT * FROM resources ORDER BY title")]
    resources = [r for r in resource_rows if m.get("topic") and m["topic"] in r["topics"]]
    support_message = None
    if m["route"] == "private_support":
        resources = [r for r in resource_rows if "private_support" in r["topics"]]
        support_message = "This request stays off the mission board and has no peer recommendations. Please reach a trusted adult, such as a parent, caregiver, teacher, or counselor. If you are in immediate danger, seek emergency help. This is a fictional local demo: no adult has been contacted and there is no live monitoring. Automated routing is not a guarantee of safety."
    elif m["route"] == "clarify":
        support_message = "Please name one subject and describe the help you need. No peer matching has been attempted. This local demo has no live monitoring and no adult has been contacted."
    elif m["route"] == "school_transition" and not resources:
        support_message = "Ask a trusted school adult about verified welcome activities. No school club or ambassador program is assumed. This local demo has no live monitoring and no adult has been contacted."
    candidates = score_candidates(conn, m, actual_mode, selected_threshold)
    return {"route": m["route"], "topic": m["topic"], "analysis": analysis, "matching_mode": actual_mode,
            "fallback_reason": status["fallback_reason"] if actual_mode != "semantic" else None,
            "threshold": selected_threshold, "candidates": candidates, "resources": resources, "support_message": support_message}


def accept_match(conn, mission_id, mentor_id, mode=None, threshold=None):
    """Caller holds BEGIN IMMEDIATE, including score/capacity revalidation."""
    row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
    if row is None:
        raise MatchConflict("The mission does not exist.")
    if row["status"] != "open":
        raise MatchConflict("This mission is no longer open. Refresh the mission board.")
    actual_mode = semantic.effective_mode(mode)
    analyzed = analyze_text(row["text"], actual_mode)
    if row["route"] not in ("academic", "school_transition") or analyzed["route"] not in ("academic", "school_transition"):
        raise MatchConflict("This request is private or needs clarification and cannot enter peer matching.")
    mission = dict(row, topic=analyzed["topic"], route=analyzed["route"])
    selected_threshold = determine_threshold(conn, actual_mode) if threshold is None else threshold
    candidate = next((c for c in score_candidates(conn, mission, actual_mode, selected_threshold) if c["mentor"]["id"] == mentor_id), None)
    if candidate is None:
        raise MatchConflict("This pairing no longer passes availability, grade, blocking, report, capacity, and quality checks. Refresh the recommendations.")
    identifier = f"match-{uuid.uuid4().hex}"
    conn.execute("INSERT INTO matches(id,mission_id,mentor_id,requester_id,topic,component_scores,score,explanation,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (identifier, mission_id, mentor_id, row["requester_id"], mission["topic"], json.dumps(candidate["component_scores"]), candidate["score"], candidate["explanation"], "active", utcnow()))
    conn.execute("UPDATE missions SET status='matched',topic=?,route=?,analysis=? WHERE id=?", (mission["topic"], mission["route"], json.dumps(analyzed["analysis"]), mission_id))
    return match_dict(conn, conn.execute("SELECT * FROM matches WHERE id=?", (identifier,)).fetchone())


def _waiting_seconds(created_at):
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
    except (ValueError, TypeError):
        return 0


def plan_batch(conn, mode=None, threshold=None):
    actual_mode = semantic.effective_mode(mode)
    threshold = determine_threshold(conn, actual_mode) if threshold is None else threshold
    missions = []
    for row in conn.execute("SELECT * FROM missions WHERE status='open' ORDER BY created_at,id"):
        if not publishable(conn, row):
            continue
        analyzed = analyze_text(row["text"], actual_mode)
        if analyzed["route"] in ("academic", "school_transition"):
            missions.append(dict(row, topic=analyzed["topic"], route=analyzed["route"]))
    possibilities = {m["id"]: score_candidates(conn, m, actual_mode, threshold) for m in missions}
    mentors = {c["mentor"]["id"]: c["mentor"] for candidates in possibilities.values() for c in candidates}
    source, sink = "source", "sink"
    graph = {}

    def edge(a, b, capacity, cost):
        graph.setdefault(a, [])
        graph.setdefault(b, [])
        forward = [b, len(graph[b]), capacity, cost]
        reverse = [a, len(graph[a]), 0, -cost]
        graph[a].append(forward)
        graph[b].append(reverse)
        return forward

    selected_edges = []
    priority_scale = (len(missions) + 1) * 10001
    for m in missions:
        mission_node = f"mission:{m['id']}"
        edge(source, mission_node, 1, 0)
        waiting = _waiting_seconds(m["created_at"])
        for candidate in possibilities[m["id"]]:
            mentor_id = candidate["mentor"]["id"]
            for slot in range(candidate["mentor"]["remaining_capacity"]):
                # Later capacity slots have a lower F component. An edge must
                # still clear the threshold at the time it will be accepted.
                adjusted = dict(candidate)
                adjusted["component_scores"] = dict(candidate["component_scores"])
                adjusted["component_scores"]["F"] = round((candidate["mentor"]["remaining_capacity"] - slot) / candidate["mentor"]["capacity"], 6)
                adjusted["score"] = round(candidate["score"] - .15 * slot / candidate["mentor"]["capacity"], 6)
                if slot:
                    adjusted["explanation"] += f" In this batch preview, {slot} earlier assignment(s) use this mentor's capacity first; F is projected at acceptance."
                if adjusted["score"] + 1e-9 < threshold:
                    continue
                cost = -(waiting * priority_scale + int(adjusted["score"] * 10000))
                e = edge(mission_node, f"mentor:{mentor_id}:{slot}", 1, cost)
                selected_edges.append((m, adjusted, e, slot))
    for mentor_id, p in mentors.items():
        for slot in range(p["remaining_capacity"]):
            edge(f"mentor:{mentor_id}:{slot}", sink, 1, 0)
    # Successive shortest augmenting paths. Continue to maximum flow even if
    # rerouting uses positive residual costs; cardinality precedes all costs.
    while source in graph and sink in graph:
        distances, parent = {source: 0}, {}
        queue, queued = deque([source]), {source}
        while queue:
            node = queue.popleft()
            queued.remove(node)
            for index, item in enumerate(graph[node]):
                target, _, capacity, cost = item
                distance = distances[node] + cost
                if capacity > 0 and distance < distances.get(target, float("inf")):
                    distances[target] = distance
                    parent[target] = (node, index)
                    if target not in queued:
                        queue.append(target)
                        queued.add(target)
        if sink not in parent:
            break
        node = sink
        while node != source:
            previous, index = parent[node]
            item = graph[previous][index]
            item[2] -= 1
            graph[node][item[1]][2] += 1
            node = previous

    def assignment(mission, candidate):
        return {"mission_id": mission["id"], "requester_id": mission["requester_id"], "mentor_id": candidate["mentor"]["id"], "mentor_alias": candidate["mentor"]["alias"], "score": candidate["score"], "component_scores": candidate["component_scores"], "explanation": candidate["explanation"], "shared_slots": candidate["shared_slots"]}

    assignments = [assignment(m, c) for m, c, e, slot in sorted(selected_edges, key=lambda item: (item[1]["mentor"]["id"], item[3])) if e[2] == 0]
    capacity_left = {i: p["remaining_capacity"] for i, p in mentors.items()}
    greedy = []
    for m in missions:
        current_candidates = []
        for c in possibilities[m["id"]]:
            mentor_id = c["mentor"]["id"]
            used = c["mentor"]["remaining_capacity"] - capacity_left[mentor_id]
            adjusted_score = round(c["score"] - .15 * used / c["mentor"]["capacity"], 6)
            if capacity_left[mentor_id] > 0 and adjusted_score + 1e-9 >= threshold:
                adjusted = dict(c)
                adjusted["score"] = adjusted_score
                adjusted["component_scores"] = dict(c["component_scores"])
                adjusted["component_scores"]["F"] = round(capacity_left[mentor_id] / c["mentor"]["capacity"], 6)
                if used:
                    adjusted["explanation"] += f" In the greedy simulation, {used} earlier assignment(s) use this mentor's capacity first; F is projected at acceptance."
                current_candidates.append(adjusted)
        if current_candidates:
            selected = min(current_candidates, key=lambda c: (-c["score"], c["mentor"]["alias"].casefold()))
            capacity_left[selected["mentor"]["id"]] -= 1
            greedy.append(assignment(m, selected))
    return {"assignments": assignments, "greedy_assignments": greedy, "algorithm": "capacity-aware minimum-cost maximum-flow", "matching_mode": actual_mode, "threshold": threshold, "eligible_missions": len(missions), "feasible_missions": sum(bool(v) for v in possibilities.values()), "methodology": "Maximum number of publishable open missions served; then total waiting time of served missions; then total quality. Capacity slots include the decline in F, and each slot clears the calibrated threshold. Greedy processes oldest missions first and takes the highest available recommendation. Coverage denominator includes publishable missions with no eligible mentor.", "summary": {"served": len(assignments), "greedy_served": len(greedy)}}
