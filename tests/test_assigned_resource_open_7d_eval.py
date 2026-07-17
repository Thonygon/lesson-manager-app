import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from helpers import assigned_resource_open_7d_eval as eval7d


def _assignment(
    idx: int,
    *,
    assigned_at: str,
    opened_at: str = "",
    viewed_at: str = "",
    completed_at: str = "",
    teacher_id: str = "teacher-1",
    student_id: str = "student-1",
    assignment_type: str = "worksheet",
    source_record_id: str = "101",
    learning_program_assignment_id: int = 0,
) -> dict:
    return {
        "id": idx,
        "teacher_id": teacher_id,
        "student_id": student_id,
        "assignment_type": assignment_type,
        "source_type": "worksheet_builder",
        "source_record_id": source_record_id,
        "subject_key": "english",
        "subject_label": "English",
        "topic": f"topic-{idx}",
        "status": "assigned",
        "score_pct": None,
        "assigned_at": assigned_at,
        "opened_at": opened_at,
        "viewed_at": viewed_at,
        "submitted_at": "",
        "completed_at": completed_at,
        "created_at": assigned_at,
        "updated_at": assigned_at,
        "learning_program_assignment_id": learning_program_assignment_id,
        "learning_program_topic_id": 0,
        "recommendation_bucket": "",
        "recommendation_focus_kind": "",
        "resource_exposure_id": "",
    }


class AssignedResourceOpenWithin7DaysTests(unittest.TestCase):
    def test_target_includes_exact_seven_day_boundary(self):
        row = _assignment(
            1,
            assigned_at="2026-07-01T10:00:00+00:00",
            opened_at="2026-07-08T10:00:00+00:00",
        )
        outcome = eval7d.build_open_within_7d_label(row, extraction_time=eval7d._parse_dt("2026-07-16T00:00:00+00:00"))
        self.assertEqual(1, outcome.label)
        self.assertEqual("included", outcome.status)
        self.assertEqual("opened_at", outcome.qualifying_event)

    def test_target_right_censors_open_windows(self):
        row = _assignment(2, assigned_at="2026-07-14T10:00:00+00:00")
        outcome = eval7d.build_open_within_7d_label(row, extraction_time=eval7d._parse_dt("2026-07-16T09:59:00+00:00"))
        self.assertIsNone(outcome.label)
        self.assertEqual("right_censored", outcome.status)
        self.assertEqual("observation_window_open", outcome.exclusion_reason)

    def test_target_excludes_invalid_pre_assignment_open(self):
        row = _assignment(
            3,
            assigned_at="2026-07-10T10:00:00+00:00",
            opened_at="2026-07-09T10:00:00+00:00",
        )
        outcome = eval7d.build_open_within_7d_label(row, extraction_time=eval7d._parse_dt("2026-07-20T00:00:00+00:00"))
        self.assertIsNone(outcome.label)
        self.assertEqual("invalid", outcome.status)
        self.assertEqual("opened_at_before_assigned_at", outcome.exclusion_reason)

    def test_chronological_split_preserves_time_order(self):
        rows = []
        for idx in range(10):
            rows.append(
                {
                    "assignment_id": idx + 1,
                    "assigned_at": f"2026-07-{idx + 1:02d}T00:00:00+00:00",
                    "label_status": "included",
                    "opened_within_7d": idx % 2,
                }
            )
        df = pd.DataFrame(rows)
        split = eval7d.build_chronological_split(df)
        self.assertEqual(8, split["train_count"])
        self.assertEqual(2, split["holdout_count"])
        self.assertEqual("2026-07-09T00:00:00+00:00", split["cutoff_timestamp"])
        self.assertLess(
            max(split["development_df"]["assigned_at"]),
            min(split["holdout_df"]["assigned_at"]),
        )

    def test_dataset_history_features_use_only_past_mature_rows(self):
        snapshot = {
            "extracted_at": "2026-07-16T00:00:00+00:00",
            "assignments": [
                _assignment(
                    1,
                    assigned_at="2026-07-01T10:00:00+00:00",
                    opened_at="2026-07-03T10:00:00+00:00",
                    student_id="student-1",
                ),
                _assignment(
                    2,
                    assigned_at="2026-07-05T10:00:00+00:00",
                    student_id="student-1",
                ),
                _assignment(
                    3,
                    assigned_at="2026-07-08T10:00:00+00:00",
                    student_id="student-1",
                ),
            ],
            "practice_sessions": [
                {
                    "id": 11,
                    "user_id": "student-1",
                    "source_type": "worksheet",
                    "source_id": 101,
                    "subject": "english",
                    "topic": "topic-0",
                    "learner_stage": "middle_school",
                    "level": "B1",
                    "score_pct": 70,
                    "started_at": "2026-07-04T09:00:00+00:00",
                    "completed_at": "2026-07-04T09:10:00+00:00",
                    "created_at": "2026-07-04T09:00:00+00:00",
                }
            ],
            "resources": {
                "worksheet": {
                    "101": {
                        "id": 101,
                        "subject": "english",
                        "topic": "topic-1",
                        "learner_stage": "middle_school",
                        "level_or_band": "B1",
                        "worksheet_type": "worksheet",
                        "plan_language": "en",
                        "student_material_language": "en",
                        "created_at": "2026-06-01T00:00:00+00:00",
                        "status": "published",
                        "is_public": True,
                        "title": "Worksheet 101",
                    }
                },
                "exam": {},
                "video": {},
            },
        }
        df, _diag = eval7d.build_assignment_dataset(snapshot, extraction_time=eval7d._parse_dt("2026-07-16T00:00:00+00:00"))
        third = df.loc[df["assignment_id"] == 3].iloc[0]
        self.assertEqual(1.0, third["prior_student_mature_assignment_count"])
        self.assertEqual(1.0, third["prior_student_assignment_open_rate"])
        self.assertEqual(1.0, third["prior_student_practice_session_count"])
        self.assertEqual(70.0, third["prior_student_avg_practice_score"])

    def test_feature_selection_contains_no_forbidden_post_assignment_columns(self):
        feature_names = [name for name in eval7d.CATEGORICAL_FEATURES + eval7d.NUMERIC_FEATURES]
        self.assertEqual([], eval7d.validate_feature_eligibility(feature_names))

    def test_small_fold_builder_reports_failure_cleanly(self):
        df = pd.DataFrame(
            [
                {"assignment_id": 1, "assigned_at": "2026-07-01T00:00:00+00:00", "label_status": "included", "opened_within_7d": 1},
                {"assignment_id": 2, "assigned_at": "2026-07-02T00:00:00+00:00", "label_status": "included", "opened_within_7d": 1},
                {"assignment_id": 3, "assigned_at": "2026-07-03T00:00:00+00:00", "label_status": "included", "opened_within_7d": 0},
                {"assignment_id": 4, "assigned_at": "2026-07-04T00:00:00+00:00", "label_status": "included", "opened_within_7d": 0},
                {"assignment_id": 5, "assigned_at": "2026-07-05T00:00:00+00:00", "label_status": "included", "opened_within_7d": 1},
            ]
        )
        folds, reason = eval7d.build_time_series_folds(df)
        self.assertEqual([], folds)
        self.assertTrue(reason)

    def test_metric_calculation_detects_single_class_predictions(self):
        y_true = pd.Series([1, 0, 1, 0]).to_numpy()
        y_pred = pd.Series([0, 0, 0, 0]).to_numpy()
        y_prob = pd.Series([0.2, 0.2, 0.2, 0.2]).to_numpy()
        metrics = eval7d._metric_dict(y_true, y_pred, y_prob, y_prob)
        self.assertTrue(metrics["single_class_prediction"])
        self.assertEqual(0.0, metrics["recall"])
        self.assertEqual(1.0, metrics["specificity"])

    def test_selection_rule_can_return_no_credible_winner(self):
        rows = [
            {
                "model_name": "DummyClassifier",
                "model_kind": "baseline",
                "status": "success",
                "holdout_positive_rate": 0.5,
                "roc_auc": 0.52,
                "average_precision": 0.51,
            },
            {
                "model_name": "LogisticRegression",
                "model_kind": "supervised",
                "status": "success",
                "holdout_positive_rate": 0.5,
                "roc_auc": 0.525,
                "average_precision": 0.515,
                "single_class_prediction": False,
                "confidence_intervals": {"roc_auc": {"low": 0.40, "high": 0.64}},
            },
        ]
        self.assertEqual("no credible winner", eval7d.select_best_candidate(rows))

    def test_selection_rule_prefers_simpler_model_when_uncertainty_overlaps(self):
        rows = [
            {
                "model_name": "DummyClassifier",
                "model_kind": "baseline",
                "status": "success",
                "holdout_positive_rate": 0.5,
                "roc_auc": 0.50,
                "average_precision": 0.50,
            },
            {
                "model_name": "RandomForestClassifier",
                "model_kind": "supervised",
                "status": "success",
                "holdout_positive_rate": 0.5,
                "roc_auc": 0.74,
                "average_precision": 0.71,
                "single_class_prediction": False,
                "confidence_intervals": {"roc_auc": {"low": 0.63, "high": 0.81}},
            },
            {
                "model_name": "LogisticRegression",
                "model_kind": "supervised",
                "status": "success",
                "holdout_positive_rate": 0.5,
                "roc_auc": 0.73,
                "average_precision": 0.70,
                "single_class_prediction": False,
                "confidence_intervals": {"roc_auc": {"low": 0.61, "high": 0.80}},
            },
        ]
        self.assertEqual("LogisticRegression", eval7d.select_best_candidate(rows))

    def test_freeze_dataset_hashes_identifiers_and_is_deterministic(self):
        df = pd.DataFrame(
            [
                {
                    "assignment_id": 1,
                    "teacher_id": "teacher-1",
                    "student_id": "student-1",
                    "resource_key": "worksheet:100",
                    "source_record_id": "100",
                    "assigned_at": "2026-07-01T00:00:00+00:00",
                    "label_status": "included",
                    "opened_within_7d": 1,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            first_path, first_hash = eval7d.freeze_anonymized_dataset(df, run_id="run-1", output_dir=Path(tmpdir))
            second_path, second_hash = eval7d.freeze_anonymized_dataset(df, run_id="run-1", output_dir=Path(tmpdir))
            self.assertEqual(first_hash, second_hash)
            frozen = pd.read_csv(first_path)
            self.assertIn("teacher_hash", frozen.columns)
            self.assertIn("student_hash", frozen.columns)
            self.assertIn("resource_hash", frozen.columns)
            self.assertNotIn("teacher_id", frozen.columns)
            self.assertNotIn("student_id", frozen.columns)
            self.assertNotIn("source_record_id", frozen.columns)
            self.assertEqual(first_path.read_text(encoding="utf-8"), second_path.read_text(encoding="utf-8"))

    def test_evaluation_is_deterministic_without_sklearn(self):
        rows = []
        for idx in range(12):
            rows.append(
                {
                    "assignment_id": idx + 1,
                    "teacher_id": "teacher-1",
                    "student_id": f"student-{idx % 3}",
                    "resource_key": f"worksheet:{idx % 4}",
                    "assignment_type": "worksheet",
                    "source_type": "worksheet_builder",
                    "subject_key": "english",
                    "topic": f"topic-{idx % 4}",
                    "assigned_at": f"2026-06-{idx + 1:02d}T00:00:00+00:00",
                    "label_status": "included",
                    "opened_within_7d": 1 if idx % 2 == 0 else 0,
                    "assignment_weekday": "Monday",
                    "assignment_hour_bucket": "10:00",
                    "resource_topic": f"topic-{idx % 4}",
                    "resource_type": "worksheet",
                    "resource_learner_stage": "middle_school",
                    "resource_level": "B1",
                    "resource_language": "en",
                    "assignment_hour": 10.0,
                    "assignment_is_weekend": 0.0,
                    "is_program_assignment": 0.0,
                    "student_stage_known": 1.0,
                    "student_level_known": 1.0,
                    "resource_title_length": 12.0,
                    "resource_public_flag": 1.0,
                    "prior_student_mature_assignment_count": float(idx),
                    "prior_student_assignment_open_rate": 0.5,
                    "prior_student_completion_rate": 0.5,
                    "prior_student_practice_session_count": 2.0,
                    "prior_student_avg_practice_score": 70.0,
                    "prior_days_since_student_activity": 2.0,
                    "prior_teacher_mature_assignment_count": float(idx),
                    "prior_teacher_assignment_open_rate": 0.5,
                    "prior_resource_mature_assignment_count": 1.0,
                    "prior_resource_open_rate": 0.5,
                    "recommendation_bucket": "",
                    "recommendation_focus_kind": "",
                }
            )
        df = pd.DataFrame(rows)
        first = eval7d.evaluate_models(df)
        second = eval7d.evaluate_models(df)
        self.assertEqual(first["winner"], second["winner"])
        self.assertEqual(first["maturity_verdict"], second["maturity_verdict"])
        self.assertEqual(
            json.dumps(first["model_rows"], sort_keys=True, default=str),
            json.dumps(second["model_rows"], sort_keys=True, default=str),
        )


if __name__ == "__main__":
    unittest.main()
