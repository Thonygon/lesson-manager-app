import unittest

from helpers.student_recommendation_ml import summarize_student_recommendation_samples


def _sample(idx: int, score: float, label: int) -> dict:
    return {
        "kind": "worksheet" if idx % 2 == 0 else "exam",
        "subject": "english",
        "topic": f"topic_{idx}",
        "timestamp": f"2026-01-{idx + 1:02d}T00:00:00+00:00",
        "target": score,
        "label": label,
        "source": "test",
        "features": {
            "kind_worksheet": 1.0 if idx % 2 == 0 else 0.0,
            "kind_exam": 0.0 if idx % 2 == 0 else 1.0,
            "subject_in_program": 1.0,
            "level_fit": 0.9 if label else 0.3,
            "topic_in_program": 0.8 if label else 0.2,
            "explicit_topic_match": 0.9 if label else 0.1,
            "topic_match_ambiguity": 0.0 if label else 0.2,
        },
    }


class StudentRecommendationMLTests(unittest.TestCase):
    def test_summary_returns_metrics_and_counts(self):
        samples = [
            _sample(0, 0.92, 1),
            _sample(1, 0.88, 1),
            _sample(2, 0.77, 1),
            _sample(3, 0.28, 0),
            _sample(4, 0.33, 0),
            _sample(5, 0.25, 0),
            _sample(6, 0.81, 1),
            _sample(7, 0.22, 0),
        ]
        summary = summarize_student_recommendation_samples(samples)
        self.assertEqual(8, summary["sample_count"])
        self.assertGreaterEqual(summary["train_count"], 4)
        self.assertGreaterEqual(summary["test_count"], 1)
        self.assertIn("worksheet", summary["counts_by_kind"])
        self.assertIn("metrics", summary)
        self.assertGreaterEqual(summary["metrics"]["roc_auc"], 0.5)
        self.assertGreaterEqual(summary["blend_weight"], 0.35)


if __name__ == "__main__":
    unittest.main()
