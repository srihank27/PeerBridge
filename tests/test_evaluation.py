"""Behavioral checks for the synthetic benchmark and its isolation boundaries."""

import copy
import sqlite3
import unittest
from unittest.mock import patch

from backend.peerbridge import analysis, evaluation, matching
from backend.peerbridge.db import create_tables
from backend.peerbridge.seed import LABELED_REQUESTS, PROFILES, seed_database


OFFLINE = {"matching_mode": "keyword", "model_name": None, "fallback_reason": "Test model is unavailable."}


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        create_tables(self.conn)
        seed_database(self.conn)
        self.conn.commit()
        self.offline = patch("backend.peerbridge.semantic.status", return_value=OFFLINE)
        self.offline.start()

    def tearDown(self):
        self.offline.stop()
        self.conn.close()

    def test_separate_splits_and_actual_denominators(self):
        result = evaluation.evaluate(self.conn)
        self.assertGreaterEqual(len(PROFILES), 12)
        self.assertTrue(20 <= len(LABELED_REQUESTS) <= 30)
        calibration_ids = {row["id"] for row in LABELED_REQUESTS if row["split"] == "calibration"}
        held_out_ids = {row["id"] for row in LABELED_REQUESTS if row["split"] == "evaluation"}
        self.assertFalse(calibration_ids & held_out_ids)
        keyword = result["matching"]["keyword"]
        measured = keyword["evaluation"]
        self.assertEqual(set(keyword["calibration"]["example_ids"]), calibration_ids)
        self.assertEqual({row["id"] for row in measured["examples"]}, held_out_ids)
        self.assertEqual(measured["coverage"]["denominator"], 13)
        self.assertEqual(measured["route_accuracy"]["denominator"], 16)
        self.assertEqual(measured["top_three_relevance"]["denominator"], sum(len(row["top_three_ids"]) for row in measured["examples"]))
        self.assertEqual(measured["top_three_relevance"]["numerator"], sum(row["relevant_top_three"] for row in measured["examples"]))

    def test_absent_model_never_gets_semantic_metrics(self):
        with patch.object(evaluation, "_evaluate_mode", wraps=evaluation._evaluate_mode) as measure:
            result = evaluation.evaluate(self.conn)
        self.assertFalse(result["semantic_ran"])
        self.assertFalse(result["matching"]["semantic"]["available"])
        self.assertIsNone(result["matching"]["semantic"]["evaluation"])
        self.assertIsNone(result["matching"]["semantic"]["threshold"])
        self.assertEqual([call.args[1] for call in measure.call_args_list], ["keyword"])

    def test_held_out_labels_cannot_change_calibration(self):
        baseline = evaluation.calibrate(self.conn, "keyword")
        changed = copy.deepcopy(LABELED_REQUESTS)
        for row in changed:
            if row["split"] == "evaluation":
                row["relevant_mentor_ids"] = ["invented-label"]
                row["expected_topic"] = "geometry"
        with patch.object(evaluation, "LABELED_REQUESTS", changed):
            recalibrated = evaluation.calibrate(self.conn, "keyword")
        self.assertEqual(baseline, recalibrated)

    def test_full_mentor_and_no_shared_qualified_slot_are_excluded(self):
        science = dict(self.conn.execute("SELECT * FROM missions WHERE id='eval-14'").fetchone())
        candidates = matching.score_candidates(self.conn, science, mode="keyword", threshold=0)
        self.assertNotIn("hero-shieldx", {row["mentor"]["id"] for row in candidates})
        no_match = dict(self.conn.execute("SELECT * FROM missions WHERE id='eval-13'").fetchone())
        cutoff = evaluation.calibrate(self.conn, "keyword")["threshold"]
        self.assertEqual(matching.score_candidates(self.conn, no_match, mode="keyword", threshold=cutoff), [])

    def test_routing_error_is_a_miss_without_shrinking_denominator(self):
        original = analysis.analyze_text
        affected_text = next(row["text"] for row in LABELED_REQUESTS if row["id"] == "eval-01")

        def with_one_miss(text, mode=None):
            if text == affected_text:
                return {"route": "clarify", "topic": None, "analysis": {}}
            return original(text, mode=mode)

        baseline = evaluation.evaluate(self.conn)["matching"]["keyword"]["evaluation"]
        with patch("backend.peerbridge.analysis.analyze_text", side_effect=with_one_miss):
            missed = evaluation.evaluate(self.conn)["matching"]["keyword"]["evaluation"]
        self.assertEqual(missed["top_three_hit_rate"]["denominator"], baseline["top_three_hit_rate"]["denominator"])
        self.assertEqual(missed["top_three_hit_rate"]["numerator"], baseline["top_three_hit_rate"]["numerator"] - 1)
        self.assertEqual(missed["coverage"]["denominator"], 13)
        self.assertEqual(missed["route_accuracy"]["numerator"], 15)

    def test_workloads_conserve_assignments_and_evaluation_has_no_writes(self):
        before = list(self.conn.iterdump())
        result = evaluation.evaluate(self.conn)
        self.assertEqual(before, list(self.conn.iterdump()))
        for name in ("batch", "greedy"):
            report = result["assignment"][name]
            workload = report["workload"]
            self.assertEqual(sum(workload["new_assignments_by_mentor"].values()), report["assigned_count"])
            self.assertEqual(sum(workload["projected_assignments_by_mentor"].values()), report["assigned_count"] + workload["existing_assignments"])
            self.assertEqual(workload["capacity_violations"], [])
            self.assertEqual(len({row["mission_id"] for row in report["assignments"]}), report["assigned_count"])
        self.assertGreaterEqual(result["assignment"]["batch"]["assigned_count"], result["assignment"]["greedy"]["assigned_count"])


if __name__ == "__main__":
    unittest.main()
