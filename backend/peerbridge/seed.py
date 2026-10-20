"""Fictional, reproducible data for the local PeerBridge demonstration.

Nothing here describes an actual student, school, club, or referral service.
The labeled corpus is intentionally small and is not a production benchmark.
"""

import json
import re
from datetime import datetime, timedelta, timezone


SLOTS = ["Mon 16:00", "Tue 16:00", "Wed 16:00", "Thu 16:00", "Fri 16:00", "Sat 10:00"]
REFERENCE_TIME = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def _profile(id, alias, avatar, grade, strengths, needs, slots, capacity=2, preferences=None):
    return {
        "id": id, "alias": alias, "avatar_id": avatar, "grade_band": grade,
        "strengths": strengths, "needs": needs, "available_slots": slots,
        "capacity": capacity,
        "support_preferences": preferences or ["step_by_step", "encouragement"],
    }


PROFILES = [
    _profile("hero-quantumspark", "QuantumSpark", "bolt", "high", ["algebra", "physics", "robotics"], ["writing", "presentations"], SLOTS[:2]),
    _profile("hero-novamind", "NovaMind", "orbit", "high", ["writing", "presentations", "study_skills"], ["python", "science"], [SLOTS[0], SLOTS[2]]),
    _profile("hero-shieldx", "ShieldX", "shield", "middle", ["science", "study_skills", "school_transition"], ["algebra"], [SLOTS[1], SLOTS[3]], capacity=1),
    _profile("hero-flashforge", "FlashForge", "comet", "high", ["python", "robotics"], ["writing", "algebra"], [SLOTS[0], SLOTS[3]]),
    _profile("hero-orbit", "OrbitAce", "orbit", "high", ["geometry", "algebra"], ["presentations"], [SLOTS[2], SLOTS[4]], preferences=["practice", "step_by_step"]),
    _profile("hero-echo", "EchoVerse", "comet", "middle", ["writing", "presentations"], ["geometry"], [SLOTS[1], SLOTS[4]]),
    _profile("hero-sage", "SageCircuit", "bolt", "middle", ["science", "algebra"], ["writing"], [SLOTS[1], SLOTS[3]]),
    _profile("hero-lumen", "LumenWave", "orbit", "high", ["physics", "science"], ["study_skills"], [SLOTS[2], SLOTS[5]], capacity=1),
    _profile("hero-atlas", "AtlasGuide", "shield", "middle", ["school_transition", "study_skills"], ["algebra"], [SLOTS[1], SLOTS[3]]),
    _profile("hero-pixel", "PixelPilot", "comet", "high", ["python", "writing"], ["physics"], [SLOTS[0], SLOTS[4]], capacity=1),
    _profile("hero-harbor", "HarborLight", "shield", "high", ["school_transition", "study_skills"], ["geometry"], [SLOTS[2], SLOTS[5]]),
    _profile("learner-aria", "AuroraQuest", "orbit", "high", ["science"], ["algebra", "geometry", "python", "writing", "presentations", "physics", "robotics"], SLOTS),
    _profile("learner-mira", "MoonTrail", "comet", "middle", ["geometry"], ["algebra", "science", "writing", "school_transition", "study_skills"], [SLOTS[1], SLOTS[3], SLOTS[4]]),
    _profile("learner-owen", "SaturdayStar", "bolt", "high", ["presentations"], ["python"], [SLOTS[5]], capacity=1, preferences=["practice"]),
]


def _request(id, requester, text, topic, route, relevant, split="evaluation", seed_status="open", **extra):
    return {
        "id": id, "requester_id": requester, "text": text,
        "expected_topic": topic, "expected_route": route,
        "relevant_mentor_ids": relevant, "split": split,
        "seed_status": seed_status, **extra,
    }


LABELED_REQUESTS = [
    _request("cal-01", "learner-aria", "Can someone walk me through algebra equations step by step?", "algebra", "academic", ["hero-quantumspark", "hero-orbit"], "calibration", "completed"),
    _request("cal-02", "learner-aria", "I need practice with geometry and triangle angles.", "geometry", "academic", ["hero-orbit"], "calibration", "completed"),
    _request("cal-03", "learner-aria", "I want to learn Python loops and variables.", "python", "academic", ["hero-flashforge", "hero-pixel"], "calibration", "completed"),
    _request("cal-04", "learner-aria", "Please help with writing a clear essay introduction.", "writing", "academic", ["hero-novamind", "hero-pixel"], "calibration", "completed"),
    _request("cal-05", "learner-aria", "I would like to practice a class presentation and public speaking.", "presentations", "academic", ["hero-novamind", "learner-owen"], "calibration", "completed"),
    _request("cal-06", "learner-mira", "Can someone explain my science experiment and the scientific method?", "science", "academic", ["hero-sage"], "calibration", "completed"),
    _request("cal-07", "learner-aria", "I need help with a thing, but I am not sure what.", None, "clarify", [], "calibration"),
    _request("cal-08", "learner-mira", "Someone threatened to hurt me at school. I need a trusted adult.", None, "private_support", [], "calibration", "private"),
    _request("eval-01", "learner-aria", "I am stuck solving algebra equations with x on both sides.", "algebra", "academic", ["hero-quantumspark", "hero-orbit"]),
    _request("eval-02", "learner-aria", "I need geometry practice finding the area of triangles.", "geometry", "academic", ["hero-orbit"]),
    _request("eval-03", "learner-aria", "My Python for loop repeats the wrong number of times.", "python", "academic", ["hero-flashforge", "hero-pixel"]),
    _request("eval-04", "learner-aria", "Could a robotics partner explain how a robot sensor works?", "robotics", "academic", ["hero-quantumspark", "hero-flashforge"]),
    _request("eval-05", "learner-mira", "I want help writing an essay with a stronger conclusion.", "writing", "academic", ["hero-echo"]),
    _request("eval-06", "learner-aria", "Can I rehearse my presentation and get public speaking practice?", "presentations", "academic", ["hero-novamind", "learner-owen"]),
    _request("eval-07", "learner-mira", "I need science help planning a fair experiment.", "science", "academic", ["hero-sage"], seed_status="matched", scenario="full_mentor_existing_assignment"),
    _request("eval-08", "learner-aria", "I need help with physics forces, motion, and Newton's laws.", "physics", "academic", ["hero-quantumspark", "hero-lumen"]),
    _request("eval-09", "learner-mira", "I need study skills for planning homework and revision.", "study_skills", "academic", ["hero-atlas"]),
    _request("eval-10", "learner-aria", "I am new at school and need help with the school transition and finding classrooms.", "school_transition", "school_transition", ["hero-harbor"]),
    _request("eval-11", "learner-aria", "Can anyone help me?", None, "clarify", [], scenario="ambiguous"),
    _request("eval-12", "learner-mira", "I am being bullied and do not feel safe at school.", None, "private_support", [], seed_status="private", scenario="sensitive"),
    _request("eval-13", "learner-owen", "I need Python practice with functions on Saturday.", "python", "academic", [], scenario="no_shared_slot"),
    _request("eval-14", "learner-mira", "Could someone explain the science behind a plant growing experiment?", "science", "academic", ["hero-sage"], scenario="full_mentor_excluded"),
    _request("eval-15", "learner-mira", "I am new at school. I want school transition help understanding the timetable.", "school_transition", "school_transition", ["hero-atlas"], scenario="trusted_adult_resource_fallback"),
    _request("eval-16", "learner-aria", "Can someone teach watercolor painting?", None, "clarify", [], scenario="unsupported_topic"),
]


# Public URLs were checked on 2026-10-19 for existence and topical relevance.
# This is not a comprehensive content, age-suitability, or safety review.
# These are public publishers, not endorsements or school-specific referrals.
RESOURCES = [
    {"id": "resource-algebra", "title": "Khan Academy: Algebra", "url": "https://www.khanacademy.org/math/algebra", "topics": ["algebra"], "access_notes": "Free lessons and practice. Some progress features require a free account.", "verified_at": None},
    {"id": "resource-geometry", "title": "Khan Academy: Geometry", "url": "https://www.khanacademy.org/math/geometry", "topics": ["geometry"], "access_notes": "Free lessons and practice. Some progress features require a free account.", "verified_at": None},
    {"id": "resource-python", "title": "Python: Official Tutorial", "url": "https://docs.python.org/3/tutorial/", "topics": ["python"], "access_notes": "Free official text tutorial. Assumes some basic programming familiarity; a peer can help beginners.", "verified_at": None},
    {"id": "resource-writing", "title": "Purdue OWL: General Writing", "url": "https://owl.purdue.edu/owl/general_writing/index.html", "topics": ["writing"], "access_notes": "Free writing guidance without an account. Choose the section relevant to the assignment.", "verified_at": None},
    {"id": "resource-physics", "title": "OpenStax: Physics", "url": "https://openstax.org/details/books/physics", "topics": ["physics"], "access_notes": "Free web textbook and downloadable PDF. Some optional partner services may charge.", "verified_at": None},
    {"id": "resource-science", "title": "OpenStax: Biology 2e", "url": "https://openstax.org/details/books/biology-2e", "topics": ["science"], "access_notes": "Free web textbook and PDF; college-level material may need a peer or teacher's guidance.", "verified_at": None},
    {"id": "resource-presentations", "title": "Toastmasters: Public Speaking Tips", "url": "https://www.toastmasters.org/resources/public-speaking-tips", "topics": ["presentations"], "access_notes": "The linked speaking tips are free. Club membership and other services may have fees.", "verified_at": None},
    {"id": "resource-study", "title": "Cornell Learning Strategies Center: How to Study", "url": "https://lsc.cornell.edu/how-to-study/", "topics": ["study_skills"], "access_notes": "Free public study guides. Cornell-specific appointments and courses may be restricted.", "verified_at": None},
    {"id": "resource-robotics", "title": "Arduino: Learn", "url": "https://docs.arduino.cc/learn/", "topics": ["robotics"], "access_notes": "Free electronics and programming guides. Hands-on activities may need separately purchased hardware.", "verified_at": None},
]

for _resource in RESOURCES:
    _resource["verified_at"] = "2026-10-19"


def seed_database(conn):
    """Populate an empty schema; transaction ownership stays with the caller."""
    from .analysis import analyze_text

    for profile in PROFILES:
        conn.execute(
            "INSERT INTO profiles (id, alias, avatar_id, grade_band, strengths, needs, available_slots, capacity, support_preferences, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (profile["id"], profile["alias"], profile["avatar_id"], profile["grade_band"], json.dumps(profile["strengths"]), json.dumps(profile["needs"]), json.dumps(profile["available_slots"]), profile["capacity"], json.dumps(profile["support_preferences"]), REFERENCE_TIME.isoformat()),
        )
    for index, item in enumerate(LABELED_REQUESTS):
        created_at = (REFERENCE_TIME - timedelta(hours=72 - index * 2)).isoformat()
        # Persist the actual rules' analysis, independently of expected labels.
        # Explicit keyword mode keeps initialization offline and inexpensive.
        result = analyze_text(item["text"], mode="keyword")
        conn.execute(
            "INSERT INTO missions (id, requester_id, text, normalized_text, topic, route, status, analysis, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item["id"], item["requester_id"], item["text"], " ".join(re.findall(r"\w+", item["text"].casefold())), result["topic"], result["route"], item["seed_status"], json.dumps(result["analysis"]), created_at),
        )
    conn.execute(
        "INSERT INTO matches (id, mission_id, mentor_id, requester_id, topic, component_scores, score, explanation, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("match-seeded-shieldx", "eval-07", "hero-shieldx", "learner-mira", "science", json.dumps({"S": 1.0, "A": 0.666667, "C": 1.0, "F": 1.0}), 0.916667, "Curated existing fictional assignment: science strength, two of three requester slots shared, matching support preferences, and one free place when accepted. H = 0.40S + 0.25A + 0.20C + 0.15F. This fills ShieldX's one place; new recommendations exclude this mentor until completion.", "active", (REFERENCE_TIME - timedelta(hours=36)).isoformat()),
    )
    for resource in RESOURCES:
        conn.execute(
            "INSERT INTO resources (id, title, url, topics, access_notes, verified_at) VALUES (?, ?, ?, ?, ?, ?)",
            (resource["id"], resource["title"], resource["url"], json.dumps(resource["topics"]), resource["access_notes"], resource["verified_at"]),
        )
