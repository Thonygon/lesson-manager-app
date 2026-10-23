import unittest
from datetime import datetime, timezone

from scripts.evaluate_quality_feedback import build_report


class QualityFeedbackEvaluationTests(unittest.TestCase):
    def test_keeps_student_fit_separate_from_topic_confusion(self):
        since = datetime(2026, 10, 23, tzinfo=timezone.utc)
        timestamp = "2026-10-23T12:00:00Z"
        snapshot = {
            "classio_generation_intent_feedback": [
                {"feature_name": "generate_plan", "feedback_surface": "generation_preview", "satisfied": True, "answered_at": timestamp},
                {"feature_name": "generate_plan", "feedback_surface": "resource_page", "satisfied": False, "reason": "level", "answered_at": timestamp},
            ],
            "classio_teacher_relevance_feedback": [
                {"exposure_id": "wrong", "reason": "wrong_topic", "active": True, "resource_is_public": True, "topic_id": 3, "updated_at": timestamp},
                {"exposure_id": "fit", "reason": "student_unfit", "active": True, "resource_is_public": True, "topic_id": 3, "updated_at": timestamp},
            ],
            "classio_teacher_relevance_feedback_events": [{"action": "undone", "created_at": timestamp}],
            "resource_exposures": [
                {"exposure_id": "wrong", "exposure_type": "teacher_resource_recommendation", "shown_at": timestamp},
                {"exposure_id": "fit", "exposure_type": "teacher_resource_recommendation", "shown_at": timestamp},
                {"exposure_id": "assigned", "exposure_type": "teacher_resource_recommendation", "shown_at": timestamp},
            ],
            "resource_exposure_events": [{"exposure_id": "assigned", "event_type": "assigned", "event_at": timestamp}],
        }
        report = build_report(snapshot, since)
        self.assertEqual(report["generation_intent"]["by_surface"], {"generation_preview": 1, "resource_page": 1})
        self.assertEqual(report["teacher_relevance"]["active_student_unfit"], 1)
        self.assertEqual(report["observed_confusion"]["true_positive"], 1)
        self.assertEqual(report["observed_confusion"]["false_positive"], 1)
        self.assertIsNone(report["observed_confusion"]["false_negative"])


if __name__ == "__main__":
    unittest.main()
