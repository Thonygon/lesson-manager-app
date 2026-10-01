import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from helpers import assigned_resource_open_7d_eval as eval7d
from helpers import assigned_resource_open_7d_review as review7d


class AssignedResourceOpenReviewTests(unittest.TestCase):
    def test_viewed_at_behaviour_marks_positive(self):
        row = {
            "assigned_at": "2026-07-01T10:00:00+00:00",
            "opened_at": "",
            "viewed_at": "2026-07-02T10:00:00+00:00",
        }
        outcome = eval7d.build_open_within_7d_label(row, extraction_time=eval7d._parse_dt("2026-07-10T00:00:00+00:00"))
        self.assertEqual(1, outcome.label)
        self.assertEqual("viewed_at", outcome.qualifying_event)

    def test_fully_missing_feature_is_dropped_from_training_frame(self):
        frame = pd.DataFrame(
            {
                "assignment_type": ["worksheet", "exam"],
                "prior_resource_open_rate": [float("nan"), float("nan")],
                "prior_student_assignment_open_rate": [0.5, 0.4],
            }
        )
        active, dropped = eval7d.active_features_for_training_frame(
            frame,
            ["assignment_type", "prior_resource_open_rate", "prior_student_assignment_open_rate"],
        )
        self.assertEqual(["assignment_type", "prior_student_assignment_open_rate"], active)
        self.assertEqual("fully_missing_in_training_frame", dropped["prior_resource_open_rate"])

    def test_metric_intervals_are_generated(self):
        y_true = pd.Series([1, 0, 1, 0, 1, 0, 1, 0, 1, 0]).to_numpy()
        y_pred = pd.Series([1, 0, 1, 0, 1, 0, 0, 0, 1, 1]).to_numpy()
        y_prob = pd.Series([0.8, 0.2, 0.7, 0.1, 0.6, 0.2, 0.4, 0.3, 0.9, 0.6]).to_numpy()
        intervals = eval7d._bootstrap_metric_intervals(y_true, y_pred, y_prob, y_prob, seed=7)
        self.assertIn("roc_auc", intervals)
        self.assertIsNotNone(intervals["roc_auc"])

    def test_selection_rule_can_identify_no_robust_winner(self):
        model_rows = [
            {"model_name": "DummyClassifier", "model_kind": "baseline", "status": "success", "holdout_positive_rate": 0.48, "roc_auc": 0.5, "average_precision": 0.71},
            {"model_name": "LogisticRegressionReduced", "model_kind": "supervised", "status": "success", "holdout_positive_rate": 0.48, "roc_auc": 0.68, "average_precision": 0.64, "single_class_prediction": False, "confidence_intervals": {"roc_auc": {"low": 0.41, "high": 0.89}}},
            {"model_name": "SVC", "model_kind": "supervised", "status": "success", "holdout_positive_rate": 0.48, "roc_auc": 0.63, "average_precision": 0.74, "single_class_prediction": False, "confidence_intervals": {"roc_auc": {"low": 0.41, "high": 0.86}}},
        ]
        self.assertEqual("LogisticRegressionReduced", eval7d.select_best_candidate(model_rows))
        self.assertTrue(
            review7d._substantial_overlap(
                model_rows[1]["confidence_intervals"],
                model_rows[2]["confidence_intervals"],
                "roc_auc",
            )
        )

    def test_review_outputs_keep_run_id_consistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dataset = pd.DataFrame(
                [
                    {
                        "assignment_id": idx + 1,
                        "teacher_id": "teacher-1",
                        "student_id": f"student-{idx%2}",
                        "resource_key": f"worksheet:{idx%3}",
                        "assignment_type": "worksheet",
                        "source_type": "worksheet_builder",
                        "subject_key": "english",
                        "topic": f"topic-{idx%3}",
                        "assigned_at": f"2026-06-{idx+1:02d}T00:00:00+00:00",
                        "opened_at": "2026-06-02T00:00:00+00:00" if idx % 2 == 0 else "",
                        "viewed_at": "",
                        "completed_at": "",
                        "submitted_at": "",
                        "observation_window_closed_at": f"2026-06-{idx+8:02d}T00:00:00+00:00",
                        "label_status": "included",
                        "label_exclusion_reason": "",
                        "qualifying_event": "opened_at" if idx % 2 == 0 else "",
                        "qualifying_open_at": "2026-06-02T00:00:00+00:00" if idx % 2 == 0 else "",
                        "opened_within_7d": 1 if idx % 2 == 0 else 0,
                        "assignment_weekday": "Monday",
                        "assignment_hour_bucket": "10:00",
                        "resource_topic": f"topic-{idx%3}",
                        "resource_type": "worksheet",
                        "resource_learner_stage": "middle_school",
                        "resource_level": "B1",
                        "resource_language": "en",
                        "recommendation_bucket": "",
                        "recommendation_focus_kind": "",
                        "assignment_hour": 10.0,
                        "assignment_is_weekend": 0.0,
                        "is_program_assignment": 0.0,
                        "student_stage_known": 1.0,
                        "student_level_known": 1.0,
                        "resource_title_length": 12.0,
                        "resource_public_flag": 1.0,
                        "prior_student_mature_assignment_count": float(idx),
                        "prior_student_assignment_open_rate": 0.5 if idx > 0 else float("nan"),
                        "prior_student_completion_rate": 0.5 if idx > 0 else float("nan"),
                        "prior_student_practice_session_count": 1.0,
                        "prior_student_avg_practice_score": 70.0,
                        "prior_days_since_student_activity": 1.0,
                        "prior_teacher_mature_assignment_count": float(idx),
                        "prior_teacher_assignment_open_rate": 0.5 if idx > 0 else float("nan"),
                        "prior_resource_mature_assignment_count": 1.0,
                        "prior_resource_open_rate": float("nan"),
                    }
                    for idx in range(12)
                ]
            )
            dataset_path, fingerprint = eval7d.freeze_anonymized_dataset(dataset, run_id="reviewrun1", output_dir=base)
            summary = {
                "run_id": "reviewrun1",
                "feature_schema_version": "assigned_resource_open_7d.v1",
                "extracted_at": "2026-07-16T08:40:55+00:00",
                "data_fingerprint": fingerprint,
                "frozen_dataset_path": str(dataset_path),
                "source_row_count": 12,
                "included_row_count": 12,
                "excluded_row_count": 0,
                "positive_count": 6,
                "negative_count": 6,
                "teacher_count": 1,
                "student_count": 2,
                "resource_count": 3,
                "date_range": {"assigned_at_min": "2026-06-01T00:00:00+00:00", "assigned_at_max": "2026-06-12T00:00:00+00:00"},
            }
            (base / "assigned_resource_open_7d_dataset_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            evaluation = eval7d.evaluate_models(dataset)
            run_summary = {
                "run_id": "reviewrun1",
                "feature_schema_version": "assigned_resource_open_7d.v1",
                "generated_at": "2026-07-16T08:40:55+00:00",
                "dataset": summary,
                "evaluation": {key: value for key, value in evaluation.items() if key not in {"feature_audit", "predictions", "model_rows", "feature_importance_rows", "dropped_run_features"}},
            }
            (base / "assigned_resource_open_7d_run_summary.json").write_text(json.dumps(run_summary), encoding="utf-8")
            comparison_rows = []
            for row in evaluation["model_rows"]:
                flat = dict(row)
                flat["confidence_intervals"] = json.dumps(row.get("confidence_intervals") or {})
                flat["confusion_matrix"] = json.dumps(row.get("confusion_matrix"))
                comparison_rows.append(flat)
            pd.DataFrame(comparison_rows).to_csv(base / "assigned_resource_open_7d_model_comparison.csv", index=False)
            pd.DataFrame(evaluation["predictions"]).to_csv(base / "assigned_resource_open_7d_holdout_predictions.csv", index=False)
            pd.DataFrame(eval7d.build_feature_audit(dataset, evaluation["feature_names"])).to_csv(base / "assigned_resource_open_7d_feature_audit.csv", index=False)
            (base / "assigned_resource_open_7d_technical_report.md").write_text("old", encoding="utf-8")
            (base / "assigned_resource_open_7d_findings_interpretation_report.md").write_text("old", encoding="utf-8")

            result = review7d.review_assigned_resource_open_7d(base)
            revised = json.loads((base / "assigned_resource_open_7d_run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual("reviewrun1", result["run_id"])
            self.assertEqual("VALIDATED_NO_ROBUST_WINNER", result["final_verdict"])
            self.assertEqual("reviewrun1", revised["run_id"])
            self.assertEqual("reviewrun1", revised["dataset"]["run_id"])
            self.assertTrue((base / "assigned_resource_open_7d_label_reconciliation.csv").exists())
            self.assertTrue((base / "assigned_resource_open_7d_integrity_review.md").exists())


if __name__ == "__main__":
    unittest.main()
