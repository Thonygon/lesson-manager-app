import unittest

from helpers.learning_programs import (
    _build_program_generation_payload,
    _infer_exam_prep_target,
)


class LearningProgramExamPrepBuilderTests(unittest.TestCase):
    def test_explicit_exam_prep_payload_is_marked_exam_aware(self):
        payload = _build_program_generation_payload(
            subject="english",
            learner_stage="upper_secondary",
            level_or_band="B2",
            units=8,
            lessons_per_unit=4,
            program_track="exam_prep",
            exam_prep_target="sat_rw",
        )
        self.assertEqual(payload.get("program_track"), "exam_prep")
        self.assertEqual(payload.get("exam_prep_target"), "sat_rw")
        self.assertIn("Digital SAT Reading and Writing", payload.get("exam_prep_target_label", ""))
        self.assertTrue(any("Digital SAT" in line for line in payload.get("program_track_guidance", [])))

    def test_existing_sat_program_can_infer_exam_target_without_builder_config(self):
        target = _infer_exam_prep_target(
            subject="english",
            program={
                "title": "SAT English Reading & Writing Prep",
                "program_overview": "A focused Digital SAT pathway.",
            },
            builder_config={},
        )
        self.assertEqual(target, "sat_rw")


if __name__ == "__main__":
    unittest.main()
