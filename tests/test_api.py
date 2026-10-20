"""HTTP integration checks for fictional demo persistence and safety boundaries."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from backend.peerbridge.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PEERBRIDGE_DB", str(tmp_path / "peerbridge.sqlite3"))
    monkeypatch.setenv("PEERBRIDGE_MATCHING", "keyword")
    with TestClient(app) as test_client:
        yield test_client


def make_profile(client, alias="TestComet", **changes):
    body = {
        "alias": alias, "avatar_id": "comet", "grade_band": "high",
        "strengths": ["algebra"], "needs": ["writing"],
        "available_slots": ["Mon 16:00"], "capacity": 2,
        "support_preferences": ["encouragement"],
    }
    body.update(changes)
    response = client.post("/api/profiles", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def make_mission(client, requester_id, text="I need algebra help solving equations."):
    response = client.post("/api/missions", json={"requester_id": requester_id, "text": text})
    assert response.status_code == 201, response.text
    return response.json()


def accept(client, mission_id, mentor_id):
    return client.post("/api/matches", json={"mission_id": mission_id, "mentor_id": mentor_id})


def profile_body(profile):
    return {key: value for key, value in profile.items() if key not in {"id", "active_matches", "remaining_capacity"}}


def test_health_and_both_endpoint_prefixes(client):
    for prefix in ("", "/api"):
        health = client.get(prefix + "/health")
        assert health.status_code == 200
        assert health.json()["demo"] is True
        assert health.json()["matching_mode"] == "keyword"
        assert health.json()["fallback_reason"]
        assert len(client.get(prefix + "/profiles").json()) >= 12
    assert client.get("/profiles").json() == client.get("/api/profiles").json()


@pytest.mark.parametrize("text", [
    "I am being bullied and I do not feel safe at school.",
    "Someone threatened to hurt me; my email is secret@example.com.",
    "I want to hurt myself and need someone I trust.",
])
def test_sensitive_requests_stay_private_and_never_get_peers(client, text):
    mission = make_mission(client, "learner-aria", text)
    assert mission["route"] == "private_support"
    assert mission["status"] == "private"
    assert mission["id"] not in {m["id"] for m in client.get("/api/missions").json()}
    own = client.get("/api/profiles/learner-aria/missions").json()
    assert mission["id"] in {m["id"] for m in own}
    recommendation = client.post(f"/api/missions/{mission['id']}/recommendations").json()
    assert recommendation["candidates"] == []
    notice = recommendation["support_message"].lower()
    assert "no adult has been contacted" in notice
    assert "no live monitoring" in notice
    assert accept(client, mission["id"], "hero-quantumspark").status_code == 409
    assert client.patch(f"/api/missions/{mission['id']}", json={"status": "open"}).status_code == 409


def test_unknown_and_ambiguous_requests_require_clarification(client):
    for text in ("Can someone help me with a thing?", "I need algebra and writing help."):
        mission = make_mission(client, "learner-aria", text)
        assert mission["route"] == "clarify"
        assert mission["id"] not in {m["id"] for m in client.get("/api/missions").json()}
        assert client.post(f"/api/missions/{mission['id']}/recommendations").json()["candidates"] == []
        assert accept(client, mission["id"], "hero-quantumspark").status_code == 409


@pytest.mark.parametrize("contact", ["student@example.com", "+1 (916) 555-0123", "https://example.com/chat", "@mycontacthandle", "123 Example Street"])
def test_public_contact_details_are_rejected(client, contact):
    response = client.post("/api/missions", json={"requester_id": "learner-aria", "text": "I need algebra help; contact me at " + contact})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "contact_details"


def test_profile_creation_edit_and_case_insensitive_uniqueness(client):
    hero = make_profile(client, "StarlightUnit")
    assert hero["active_matches"] == 0 and hero["remaining_capacity"] == 2
    duplicate = client.post("/api/profiles", json={**profile_body(hero), "alias": "sTARLIGHTuNIT"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "alias_taken"
    updated = client.put(f"/api/profiles/{hero['id']}", json={**profile_body(hero), "capacity": 3, "needs": ["python"]})
    assert updated.status_code == 200
    assert client.get(f"/api/profiles/{hero['id']}").json()["remaining_capacity"] == 3


@pytest.mark.parametrize("change", [
    {"capacity": -1}, {"capacity": 6}, {"capacity": True}, {"strengths": ["magic"]},
    {"available_slots": ["Mon 16:00", "Mon 16:00"]}, {"avatar_id": "official-superhero"},
    {"alias": "hello@example.com"}, {"unknown_field": "ignored?"},
])
def test_profile_validation_returns_structured_errors(client, change):
    body = {"alias": "ValidationHero", "avatar_id": "bolt", "grade_band": "high", **change}
    response = client.post("/api/profiles", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]


def test_normalized_duplicate_missions_and_status_transitions(client):
    mission = make_mission(client, "learner-aria", "I need help with algebra.")
    duplicate = client.post("/api/missions", json={"requester_id": "learner-aria", "text": "  I NEED help with ALGEBRA!!!  "})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_mission"
    assert client.patch(f"/api/missions/{mission['id']}", json={"status": "completed"}).status_code == 200
    newer = make_mission(client, "learner-aria", "I need help with algebra.")
    assert client.patch(f"/api/missions/{mission['id']}", json={"status": "open"}).status_code == 409
    assert client.patch(f"/api/missions/{newer['id']}", json={"status": "cancelled"}).status_code == 200
    assert client.patch(f"/api/missions/{mission['id']}", json={"status": "open"}).status_code == 200
    assert client.patch(f"/api/missions/{mission['id']}", json={"status": "open"}).status_code == 409


def test_scores_explanations_and_resources_use_stored_profile_data(client):
    mentor = make_profile(client, "ExplainedMentor", capacity=1)
    requester = make_profile(client, "ExplainedRequester", strengths=["writing"], capacity=0)
    mission = make_mission(client, requester["id"])
    response = client.post(f"/api/missions/{mission['id']}/recommendations").json()
    candidate = next(c for c in response["candidates"] if c["mentor"]["id"] == mentor["id"])
    components = candidate["component_scores"]
    assert candidate["shared_slots"] == ["Mon 16:00"]
    assert all(0 <= score <= 1 for score in components.values())
    assert candidate["score"] == pytest.approx(.4 * components["S"] + .25 * components["A"] + .2 * components["C"] + .15 * components["F"], abs=1e-6)
    assert "Mon 16:00" in candidate["explanation"]
    assert "1 of 1" in candidate["explanation"]
    assert any("algebra" in resource["topics"] for resource in response["resources"])


@pytest.mark.parametrize("constraint", ["self", "wrong_grade", "no_slot", "full", "wrong_strength"])
def test_hard_constraints_cannot_be_bypassed_by_direct_accept(client, constraint):
    requester = make_profile(client, "ConstraintRequester")
    changes = {
        "wrong_grade": {"grade_band": "middle"}, "no_slot": {"available_slots": ["Sat 10:00"]},
        "full": {"capacity": 0}, "wrong_strength": {"strengths": ["writing"]},
    }
    mentor = requester if constraint == "self" else make_profile(client, "ConstraintMentor", **changes[constraint])
    mission = make_mission(client, requester["id"])
    candidates = client.post(f"/api/missions/{mission['id']}/recommendations").json()["candidates"]
    assert mentor["id"] not in {c["mentor"]["id"] for c in candidates}
    assert accept(client, mission["id"], mentor["id"]).status_code == 409


def test_capacity_is_reserved_on_accept_and_released_on_completion(client):
    mentor = make_profile(client, "OnePlaceMentor", capacity=1)
    requester = make_profile(client, "CapacityRequester", strengths=["writing"], capacity=0)
    first = make_mission(client, requester["id"], "I need algebra help with an equation.")
    second = make_mission(client, requester["id"], "I need algebra help learning variables.")
    assert accept(client, first["id"], mentor["id"]).status_code == 201
    assert accept(client, first["id"], "hero-quantumspark").status_code == 409
    assert accept(client, second["id"], mentor["id"]).status_code == 409
    active_profile = client.get(f"/api/profiles/{mentor['id']}").json()
    assert active_profile["active_matches"] == 1 and active_profile["remaining_capacity"] == 0
    assert client.put(f"/api/profiles/{mentor['id']}", json={**profile_body(mentor), "capacity": 0}).status_code == 409
    assert client.patch(f"/api/missions/{first['id']}", json={"status": "completed"}).status_code == 200
    assert client.post(f"/api/missions/{first['id']}/recommendations").json()["candidates"] == []
    assert client.get(f"/api/profiles/{mentor['id']}").json()["remaining_capacity"] == 1
    assert accept(client, second["id"], mentor["id"]).status_code == 201


def test_concurrent_acceptance_cannot_overbook_last_place(client):
    mentor = make_profile(client, "ConcurrentMentor", capacity=1)
    first = make_mission(client, "learner-aria", "Please help me understand algebra equations today.")
    requester = make_profile(client, "ConcurrentRequester", strengths=["writing"], capacity=0)
    second = make_mission(client, requester["id"], "Please explain algebra variables step by step.")
    barrier = Barrier(2)

    def claim(mission_id):
        barrier.wait(timeout=10)
        return accept(client, mission_id, mentor["id"]).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, [first["id"], second["id"]]))
    assert sorted(outcomes) == [201, 409]
    assert client.get(f"/api/profiles/{mentor['id']}").json()["active_matches"] == 1


def test_block_is_persistent_symmetric_and_closes_active_pair(client):
    mission = make_mission(client, "learner-aria", "Please explain algebra equations with letters.")
    accepted = accept(client, mission["id"], "hero-quantumspark")
    assert accepted.status_code == 201
    block = client.post("/api/blocks", json={"blocker_id": "hero-quantumspark", "blocked_id": "learner-aria"})
    assert block.status_code == 201
    assert len(client.get("/api/blocks?profile_id=learner-aria").json()) == 1
    assert accept(client, mission["id"], "hero-quantumspark").status_code == 409
    saved_match = next(m for m in client.get("/api/matches").json() if m["id"] == accepted.json()["id"])
    assert saved_match["status"] == "cancelled"
    assert mission["id"] in {m["id"] for m in client.get("/api/missions").json()}
    assert client.delete("/api/blocks/" + block.json()["id"]).status_code == 200
    assert accept(client, mission["id"], "hero-quantumspark").status_code == 201


@pytest.mark.parametrize("target_type", ["profile", "mission", "match"])
def test_reports_invalidate_eligibility_and_redact_review_queue(client, target_type):
    mission = make_mission(client, "learner-aria", "Please explain algebra equations privately in this demonstration.")
    confirmed = accept(client, mission["id"], "hero-quantumspark").json()
    target_id = {"profile": "hero-quantumspark", "mission": mission["id"], "match": confirmed["id"]}[target_type]
    reason = "Private quoted text with secret@example.com and a personal concern."
    response = client.post("/api/reports", json={"reporter_id": "learner-aria", "target_type": target_type, "target_id": target_id, "reason": reason})
    assert response.status_code == 201
    assert response.json()["review_status"] == "simulated_pending"
    assert accept(client, mission["id"], "hero-quantumspark").status_code == 409
    queue = client.get("/api/reports").json()
    assert len(queue) == 1
    assert reason not in str(queue) and mission["text"] not in str(queue)
    assert "secret@example.com" not in str(queue)
    assert "no live monitoring" in queue[0]["notice"].lower()


def test_batch_preview_is_read_only_and_acceptance_respects_capacity(client):
    before = client.get("/api/matches").json()
    before_profiles = client.get("/api/profiles").json()
    preview = client.post("/api/assignments/batch", json={"dry_run": True})
    assert preview.status_code == 200
    assert preview.json()["assignments"]
    assert client.get("/api/matches").json() == before
    assert client.get("/api/profiles").json() == before_profiles
    accepted = client.post("/api/assignments/batch", json={"dry_run": False})
    assert accepted.status_code == 200, accepted.text
    assert len(accepted.json()["matches"]) == len(accepted.json()["assignments"])
    assert all(p["active_matches"] <= p["capacity"] for p in client.get("/api/profiles").json())
    assert all(m["score"] >= accepted.json()["threshold"] for m in accepted.json()["matches"])


def test_resource_directory_and_no_invented_school_activity(client):
    directory = client.get("/api/resources").json()
    assert len(directory) >= 8
    assert all(r["url"].startswith("https://") and r["verified_at"] and r["access_notes"] for r in directory)
    algebra = client.get("/api/resources?topic=algebra").json()
    assert algebra and all("algebra" in r["topics"] for r in algebra)
    transition = client.post("/api/missions/eval-15/recommendations").json()
    assert transition["resources"] == []
    assert "trusted school adult" in transition["support_message"]
    assert client.get("/api/resources?topic=invented").status_code == 422


def test_reset_restores_seed_and_requires_explicit_confirmation(client):
    make_profile(client, "TemporaryHero")
    assert client.post("/api/demo/reset", json={"confirm": False}).status_code == 422
    assert client.post("/api/demo/reset", json={"confirm": 1}).status_code == 422
    assert client.post("/api/demo/reset", json={"confirm": True}).status_code == 200
    assert "TemporaryHero" not in {p["alias"] for p in client.get("/api/profiles").json()}
    assert len(client.get("/api/profiles").json()) == 14
    assert len(client.get("/api/matches").json()) == 1


def test_static_root_and_api_errors_are_not_confused(client):
    assert client.get("/").status_code == 200
    for path in ("/api/not-a-route", "/api/profiles/not-a-profile"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"]
    assert client.put("/api/health").status_code == 405
    assert client.put("/api/health").json()["error"]["message"]
    invalid_json = client.post("/api/missions", content="{", headers={"Content-Type": "application/json"})
    assert invalid_json.status_code == 422
    assert invalid_json.json()["error"]["code"] == "validation_error"
