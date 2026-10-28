import unittest

from helpers.ai_prompt_privacy import minimize_student_profile_for_ai, redact_direct_identifiers
from helpers.student_personalization import build_student_profile_prompt_block


class AiPromptPrivacyTests(unittest.TestCase):
    def test_provider_boundary_redacts_recognizable_identifiers(self):
        prompt = 'Fractions for student_name: "Ada Example", email ada@example.test, phone +90 555 111 2233, address: 17 Sample Street.'
        safe = redact_direct_identifiers(prompt)
        self.assertIn('Fractions', safe)
        for private in ('Ada Example', 'ada@example.test', '+90 555 111 2233', '17 Sample Street'):
            self.assertNotIn(private, safe)

    def test_national_and_bank_identifiers_are_removed_without_erasing_math(self):
        safe = redact_direct_identifiers('TCKN: 10000000146; DNI: 12345678Z; Passport: ABCDEF; IBAN TR33 0006 1005 1978 6457 8413 26.')
        for private in ('10000000146', '12345678Z', 'ABCDEF', 'TR33 0006'):
            self.assertNotIn(private, safe)
        self.assertIn('[identity number removed]', redact_direct_identifiers('10000000146'))
        self.assertEqual(redact_direct_identifiers('Exercise: 12345678901 + 2'), 'Exercise: 12345678901 + 2')
        self.assertEqual(
            redact_direct_identifiers('Lesson topic: passport vocabulary and travel'),
            'Lesson topic: passport vocabulary and travel',
        )
        self.assertEqual(
            redact_direct_identifiers('Explain DNI vocabulary in Spanish'),
            'Explain DNI vocabulary in Spanish',
        )

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
        self.assertNotIn("learner_id", safe)
        self.assertEqual(safe["learner_stage"], "lower_secondary")
        self.assertEqual(safe["recent_average_score_pct"], 62.5)
        self.assertNotIn("Private Student", str(safe))
        self.assertNotIn("private@example.test", str(safe))
        self.assertNotIn(profile["student_user_id"], str(safe))
        self.assertNotIn("Learner numeric reference", build_student_profile_prompt_block(safe, product="lesson_plan"))
        self.assertEqual(safe, minimize_student_profile_for_ai(profile))

    def test_rejects_unstructured_values_in_signal_fields(self):
        safe = minimize_student_profile_for_ai({"learner_stage": "A2 for Private Student", "native_language": "x@y.test"})
        self.assertEqual(safe, {})

    def test_keeps_bounded_pedagogical_signals_in_final_prompt(self):
        profile = {
            "student_user_id": "55bbd13d-1eb5-4cdc-81ec-06b27e23c45c",
            "student_name": "Private Student",
            "weak_topics": ["Fractions", "Private Student needs ratios", "https://example.test"],
            "strong_topics": ["Percentages"],
            "weak_formats": ["short_answer"],
            "program_context": {
                "current_program_title": "Algebra foundations",
                "next_topics": ["Linear equations", "Private Student's address"],
                "suggested_worksheet_types": ["matching"],
            },
        }
        safe = minimize_student_profile_for_ai(profile)
        self.assertEqual(safe, minimize_student_profile_for_ai(safe))
        self.assertEqual(safe["weak_topics"], ["Fractions"])
        self.assertEqual(safe["program_context"]["next_topics"], ["Linear equations"])
        prompt = build_student_profile_prompt_block(safe, product="lesson_plan")
        for signal in ("Fractions", "Percentages", "short answer", "Algebra foundations", "Linear equations"):
            self.assertIn(signal, prompt)
        self.assertNotIn("Private Student", prompt)
        self.assertNotIn("example.test", prompt)


if __name__ == "__main__":
    unittest.main()
