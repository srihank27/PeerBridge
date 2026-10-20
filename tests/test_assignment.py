"""Constructed counterexamples for assignment objectives and safety routing.

These fixtures are independent of the demonstration seed. They exercise the
real database, hard constraints, scorer, planner, and transactional acceptance.
"""

import json
import sqlite3
import unittest

from backend.peerbridge.analysis import analyze_text, normalized_text
from backend.peerbridge.db import create_tables
from backend.peerbridge.matching import accept_match, plan_batch, score_candidates


MON = "Mon 16:00"
TUE = "Tue 16:00"
EARLY = "2000-01-01T12:00:00+00:00"
LATER = "2000-01-02T12:00:00+00:00"
LATEST = "2000-01-03T12:00:00+00:00"


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        create_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def profile(self, identifier, *, strengths=None, capacity=1, slots=None, preferences=None, grade="high"):
        self.conn.execute(
            "INSERT INTO profiles(id,alias,avatar_id,grade_band,strengths,needs,available_slots,capacity,support_preferences,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (identifier, identifier, "bolt", grade, json.dumps(strengths or ["writing"]), "[]", json.dumps(slots or [MON]), capacity, json.dumps(preferences or ["step_by_step"]), EARLY),
        )
        return identifier

    def mission(self, identifier, requester, topic="algebra", created_at=EARLY):
        text = {"algebra": "Please help me with algebra equations.", "geometry": "Please help me with geometry triangles."}[topic]
        analyzed = analyze_text(text, mode="keyword")
        self.conn.execute(
            "INSERT INTO missions(id,requester_id,text,normalized_text,topic,route,status,analysis,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (identifier, requester, text, normalized_text(text), topic, "academic", "open", json.dumps(analyzed["analysis"]), created_at),
        )
        return identifier

    def plan(self, threshold=0.61):
        return plan_batch(self.conn, mode="keyword", threshold=threshold)

    @staticmethod
    def pairs(assignments):
        return {(item["mission_id"], item["mentor_id"]) for item in assignments}

    def test_maximum_cardinality_reroutes_an_adversarial_greedy_choice(self):
        self.profile("flexible", strengths=["algebra", "geometry"])
        self.profile("algebra-only", strengths=["algebra"], preferences=["practice"])
        self.profile("requester-algebra")
        self.profile("requester-geometry")
        self.mission("old-algebra", "requester-algebra", created_at=EARLY)
        self.mission("new-geometry", "requester-geometry", "geometry", LATER)

        result = self.plan()
        self.assertEqual(self.pairs(result["greedy_assignments"]), {("old-algebra", "flexible")})
        self.assertEqual(self.pairs(result["assignments"]), {("old-algebra", "algebra-only"), ("new-geometry", "flexible")})
        self.assertEqual(result["summary"], {"served": 2, "greedy_served": 1})
        self.assertAlmostEqual(sum(item["score"] for item in result["assignments"]), 1.8)

    def test_waiting_priority_serves_older_request_despite_lower_quality(self):
        self.profile("mentor", strengths=["algebra"])
        self.profile("older-requester", preferences=["practice"])
        self.profile("newer-requester")
        self.mission("older", "older-requester", created_at=EARLY)
        self.mission("newer", "newer-requester", created_at=LATER)

        result = self.plan()
        self.assertEqual(self.pairs(result["assignments"]), {("older", "mentor")})
        self.assertAlmostEqual(result["assignments"][0]["score"], 0.8)

    def test_quality_breaks_equal_cardinality_and_equal_waiting_ties(self):
        self.profile("mentor", strengths=["algebra"])
        self.profile("low-quality-requester", preferences=["practice"])
        self.profile("high-quality-requester")
        # The lower-quality request sorts first; quality must overcome that.
        self.mission("a-low-quality", "low-quality-requester", created_at=EARLY)
        self.mission("z-high-quality", "high-quality-requester", created_at=EARLY)

        result = self.plan()
        self.assertEqual(self.pairs(result["assignments"]), {("z-high-quality", "mentor")})
        self.assertAlmostEqual(result["assignments"][0]["score"], 1.0)

    def test_capacity_slots_match_sequential_acceptance_scores(self):
        self.profile("mentor", strengths=["algebra"], capacity=2)
        for index, created in enumerate((EARLY, LATER, LATEST)):
            requester = self.profile(f"requester-{index}")
            self.mission(f"mission-{index}", requester, created_at=created)

        result = self.plan()
        self.assertEqual(self.pairs(result["assignments"]), {("mission-0", "mentor"), ("mission-1", "mentor")})
        self.assertEqual([row["component_scores"]["F"] for row in result["assignments"]], [1.0, 0.5])
        self.assertEqual([row["score"] for row in result["assignments"]], [1.0, 0.925])
        self.conn.commit()
        self.conn.execute("BEGIN IMMEDIATE")
        for row in result["assignments"]:
            accepted = accept_match(self.conn, row["mission_id"], row["mentor_id"], mode="keyword", threshold=0.61)
            self.assertEqual(accepted["score"], row["score"])
            self.assertEqual(accepted["component_scores"], row["component_scores"])
        self.conn.commit()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM matches WHERE status='active'").fetchone()[0], 2)
        remaining = self.conn.execute("SELECT * FROM missions WHERE id='mission-2'").fetchone()
        self.assertEqual(score_candidates(self.conn, remaining, mode="keyword", threshold=0.61), [])

    def test_declining_f_prevents_assignment_below_quality_threshold(self):
        self.profile("mentor", strengths=["algebra"], capacity=3)
        for index, created in enumerate((EARLY, LATER, LATEST)):
            requester = self.profile(f"requester-{index}")
            self.mission(f"mission-{index}", requester, created_at=created)

        result = self.plan(threshold=0.96)
        self.assertEqual(self.pairs(result["assignments"]), {("mission-0", "mentor")})
        self.assertEqual(self.pairs(result["greedy_assignments"]), {("mission-0", "mentor")})
        self.conn.commit()
        self.conn.execute("BEGIN IMMEDIATE")
        accept_match(self.conn, "mission-0", "mentor", mode="keyword", threshold=0.96)
        self.conn.commit()
        remaining = self.conn.execute("SELECT * FROM missions WHERE id='mission-1'").fetchone()
        self.assertEqual(score_candidates(self.conn, remaining, mode="keyword", threshold=0.96), [])
        self.assertEqual(score_candidates(self.conn, remaining, mode="keyword", threshold=0.0)[0]["score"], 0.95)

    def test_blocked_no_slot_wrong_grade_unqualified_self_and_full_are_not_assigned(self):
        self.profile("requester", strengths=["algebra"])
        self.profile("blocked", strengths=["algebra"])
        self.profile("no-slot", strengths=["algebra"], slots=[TUE])
        self.profile("wrong-grade", strengths=["algebra"], grade="middle")
        self.profile("unqualified", strengths=["physics"])
        self.profile("full", strengths=["algebra"], capacity=0)
        self.mission("mission", "requester")
        self.conn.execute("INSERT INTO blocks(id,blocker_id,blocked_id,created_at) VALUES(?,?,?,?)", ("block", "requester", "blocked", EARLY))

        result = self.plan()
        self.assertEqual(result["assignments"], [])
        self.assertEqual(result["greedy_assignments"], [])
        self.assertEqual(result["eligible_missions"], 1)
        self.assertEqual(result["feasible_missions"], 0)

    def test_greedy_rechecks_ranking_after_capacity_changes(self):
        preferences = ["step_by_step", "practice"]
        self.profile("mentor-a", strengths=["algebra", "geometry"], capacity=2, preferences=preferences)
        self.profile("mentor-b", strengths=["algebra"], preferences=preferences + ["encouragement"])
        self.profile("requester-geometry", preferences=preferences)
        self.profile("requester-algebra", preferences=preferences)
        self.mission("old-geometry", "requester-geometry", "geometry", EARLY)
        self.mission("new-algebra", "requester-algebra", "algebra", LATER)

        result = self.plan()
        self.assertEqual(self.pairs(result["greedy_assignments"]), {("old-geometry", "mentor-a"), ("new-algebra", "mentor-b")})
        algebra = next(row for row in result["greedy_assignments"] if row["mission_id"] == "new-algebra")
        self.assertAlmostEqual(algebra["score"], 0.933333)

    def test_stale_academic_topic_is_reanalyzed_before_batch_preview(self):
        self.profile("mentor", strengths=["algebra"])
        self.profile("requester")
        self.mission("mission", "requester")
        # A request stored by a previous engine may no longer be recognized by
        # the currently running engine. Preview must agree with acceptance.
        text = "Can anyone help me?"
        self.conn.execute("UPDATE missions SET text=?, normalized_text=? WHERE id='mission'", (text, normalized_text(text)))
        result = self.plan()
        self.assertEqual(result["assignments"], [])
        self.assertEqual(result["greedy_assignments"], [])


class SafetyRoutingTests(unittest.TestCase):
    def test_private_routing_precedes_academic_keywords(self):
        for text in (
            "I am being bullied, but I mainly need algebra help.",
            "Someone is harassing me online and I want Python help.",
            "A classmate keeps hitting me. Can I get science help?",
            "I don't feel safe walking home.",
            "I do not feel safe at school, and I need algebra help.",
            "I don’t feel safe at school.",
            "I am not feeling safe near that classmate.",
        ):
            with self.subTest(text=text):
                result = analyze_text(text, mode="keyword")
                self.assertEqual(result["route"], "private_support")
                self.assertIsNone(result["topic"])

    def test_programming_use_of_kill_is_not_personal_safety_routing(self):
        result = analyze_text("I need to kill a running Python process.", mode="keyword")
        self.assertEqual(result["route"], "academic")
        self.assertEqual(result["topic"], "python")


if __name__ == "__main__":
    unittest.main()
