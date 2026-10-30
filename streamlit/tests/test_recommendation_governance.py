"""Synthetic checks for segment coverage, bias flags and human promotion gates."""

import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from helpers.recommendation_governance import evaluate_recommendation_evidence, heuristic_fallback_enabled, write_governance_artifact


def _judgments() -> list[dict]:
    rows = []
    for index in range(80):
        label = index % 2
        rows.append({
            "judgment_id": f"synthetic-{index}", "candidate_id": f"candidate-{index}", "labeler_id": f"reviewer-{index % 2}",
            "label_source": "independent_human", "candidate_source": "held_out" if index % 3 == 0 else "shown",
            "model_version": "synthetic-v1",
            "trained_until": "2026-01-01T00:00:00Z", "judged_at": "2026-02-01T00:00:00Z",
            "label": label, "score": 0.9 if label else 0.1, "baseline_score": 0.9 if label else 0.1,
            "kind": "exam" if index < 40 else "worksheet",
            "subject": "english" if index < 40 else "mathematics",
            "stage": "secondary" if index < 40 else "adult", "level": "a2" if index < 40 else "b1",
        })
    return rows


class RecommendationGovernanceTests(unittest.TestCase):
    def test_proxy_actions_and_duplicate_judgments_do_not_inflate_evidence(self):
        rows = _judgments()
        proxy = {**rows[0], "judgment_id": "proxy", "label_source": "opening"}
        repeated_candidate = {**rows[0], "judgment_id": "second-judgment"}
        result = evaluate_recommendation_evidence(rows + [rows[0], proxy, repeated_candidate], "teacher_resources")
        self.assertEqual(result["global"]["count"], 80)
        self.assertEqual(result["excluded_rows"], 3)
        self.assertTrue(result["eligible_for_human_approval"])
        self.assertEqual(result["action"], "hold")
        self.assertEqual(result["labeler_count"], 2)

    def test_small_segments_suppress_error_rates_and_block_promotion(self):
        rows = _judgments()[:10]
        result = evaluate_recommendation_evidence(rows, "teacher_resources")
        self.assertFalse(result["eligible_for_human_approval"])
        self.assertTrue(all(row.get("suppressed") for row in result["segments"]))
        self.assertNotIn("fp", result["segments"][0])

    def test_segment_error_gap_requires_bias_review(self):
        rows = _judgments()
        for item in rows[:40]:
            if item["label"] == 0 and int(item["judgment_id"].split("-")[-1]) < 20:
                item["score"] = 0.9
        result = evaluate_recommendation_evidence(rows, "teacher_resources")
        self.assertFalse(result["eligible_for_human_approval"])
        self.assertIn("segment_error_gap:kind:false_positive_rate", result["reasons"])

    def test_promotion_requires_matching_human_decision_and_retirement_is_explicit(self):
        rows = _judgments()
        baseline = evaluate_recommendation_evidence(rows, "teacher_resources")
        review = {
            "family": "teacher_resources", "policy_version": baseline["policy_version"],
            "model_version": baseline["model_version"],
            "evidence_sha256": baseline["evidence_sha256"], "reviewer": "synthetic-reviewer",
            "rationale": "Synthetic fixture demonstrates an independent review.",
            "reviewed_at": datetime.now(timezone.utc).isoformat(), "decision": "promote",
        }
        self.assertEqual(evaluate_recommendation_evidence(rows, "teacher_resources", review)["action"], "promote")
        self.assertEqual(evaluate_recommendation_evidence(rows, "teacher_resources", {**review, "evidence_sha256": "wrong"})["action"], "hold")
        self.assertEqual(evaluate_recommendation_evidence(rows, "teacher_resources", {**review, "model_version": "wrong"})["action"], "hold")
        self.assertEqual(evaluate_recommendation_evidence(rows, "teacher_resources", {**review, "reviewer": "reviewer-0"})["action"], "hold")
        self.assertEqual(evaluate_recommendation_evidence(rows, "teacher_resources", {**review, "decision": "retire"})["action"], "heuristic_fallback")

    def test_mixed_model_versions_cannot_be_promoted(self):
        rows = _judgments()
        rows[0]["model_version"] = "synthetic-v2"
        result = evaluate_recommendation_evidence(rows, "teacher_resources")
        self.assertIn("missing_or_mixed_model_version", result["reasons"])
        self.assertIsNone(result["model_version"])

    def test_temporal_evidence_and_baseline_regression_are_required(self):
        rows = _judgments()
        rows[0]["judged_at"] = "2025-01-01T00:00:00Z"
        self.assertEqual(evaluate_recommendation_evidence(rows, "teacher_resources")["excluded_rows"], 1)
        rows = _judgments()
        for item in rows[:40]:
            if item["label"] == 0:
                item["score"] = 0.9
        self.assertIn("regressed_vs_baseline:false_positive_rate", evaluate_recommendation_evidence(rows, "teacher_resources")["reasons"])

    def test_artifact_contains_aggregates_without_raw_judgments(self):
        rows = _judgments()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "judgments.json"
            source.write_text(json.dumps(rows), encoding="utf-8")
            path, result = write_governance_artifact(folder, "teacher_resources", evaluation_json=source)
            body = path.read_text(encoding="utf-8")
            self.assertEqual(result["global"]["count"], 80)
            self.assertNotIn("synthetic-0", body)
            self.assertNotIn("reviewer-0", body)

    def test_each_recommendation_family_has_an_independent_fallback_switch(self):
        with patch.dict("os.environ", {"CLASSIO_TEACHER_RECOMMENDATION_MODE": "heuristic", "CLASSIO_STUDENT_RECOMMENDATION_MODE": ""}):
            self.assertTrue(heuristic_fallback_enabled("teacher_resources"))
            self.assertFalse(heuristic_fallback_enabled("student_resources"))


if __name__ == "__main__":
    unittest.main()
