import unittest

from helpers.ai_prompt_privacy import minimize_student_profile_for_ai


class AiPromptPrivacyTests(unittest.TestCase):
    def test_student_identity_and_free_text_are_removed(self):
        profile = {
            "student_user_id": "55bbd13d-1eb5-4cdc-81ec-06b27e23c45c",
            "student_name": "Private Student",
            "email": "private@example.test",
            "summary": "Private Student lives at a private address",
            "weak_topics": ["Private Student needs fractions"],
            "program_context": {"current_program_title": "Private Student's course"},
            "learner_stage": "lower_secondary",
            "level_or_band": "A2",
            "recent_average_score_pct": 62.5,
        }
        safe = minimize_student_profile_for_ai(profile)
        self.assertIsInstance(safe["learner_id"], int)
        self.assertEqual(safe["learner_stage"], "lower_secondary")
        self.assertEqual(safe["recent_average_score_pct"], 62.5)
        self.assertNotIn("Private Student", str(safe))
        self.assertNotIn("private@example.test", str(safe))
        self.assertNotIn(profile["student_user_id"], str(safe))
        self.assertEqual(safe, minimize_student_profile_for_ai(profile))

    def test_rejects_unstructured_values_in_signal_fields(self):
        safe = minimize_student_profile_for_ai({"learner_stage": "A2 for Private Student", "native_language": "x@y.test"})
        self.assertEqual(safe, {})


if __name__ == "__main__":
    unittest.main()
