import logging
import unittest

from helpers.answer_key_utils import split_answer_key_items
from helpers.generation_guidance import build_generation_profile_guidance
from helpers.learning_programs import get_subject_progression_profile
from helpers.lesson_planner import (
    ACADEMIC_BANDS,
    LANGUAGE_LEVELS,
    LESSON_PURPOSES,
    QUICK_SUBJECTS,
    _lesson_plan_quality_issues,
    build_quick_lesson_plan,
    normalize_planner_output,
)
from helpers.practice_engine import _check_answer
from helpers.quick_exam_builder import normalize_exam_output
from helpers.worksheet_builder import _prune_error_correction_items


for logger_name in (
    "streamlit",
    "streamlit.runtime",
    "streamlit.runtime.caching.cache_data_api",
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.runtime.state.session_state_proxy",
):
    logging.getLogger(logger_name).setLevel(logging.ERROR)


class LowerSecondaryQualityTests(unittest.TestCase):
    def test_lower_secondary_profiles_use_explicit_stage_level_markers(self):
        expected_markers = {
            ("english", "A1"): "high-frequency adolescent vocabulary",
            ("english", "B2"): "extended interpretation",
            ("english", "C1"): "critical reading",
            ("english", "C2"): "near-native comprehension",
            ("spanish", "A1"): "high-frequency adolescent vocabulary",
            ("spanish", "B2"): "extended interpretation",
            ("mathematics", "beginner_band"): "number fluency repair",
            ("science", "beginner_band"): "foundational scientific vocabulary",
            ("science", "advanced_band"): "scientific models",
            ("music", "beginner_band"): "pulse and rhythm security",
            ("music", "advanced_band"): "theory depth",
            ("study_skills", "beginner_band"): "task initiation",
            ("study_skills", "advanced_band"): "independent planning",
            ("history", "beginner_band"): "foundational knowledge",
        }

        for (subject, level_or_band), marker in expected_markers.items():
            with self.subTest(subject=subject, level_or_band=level_or_band):
                profile = get_subject_progression_profile(subject, "lower_secondary", level_or_band)
                focus_strands = profile.get("focus_strands") or []
                joined = " | ".join(focus_strands)
                self.assertIn(marker, joined)

                if subject == "spanish":
                    priorities = profile.get("global_priorities") or []
                    self.assertTrue(priorities)
                    self.assertIn("Treat Spanish as a full communicative curriculum", priorities[0])

    def test_lower_secondary_guidance_covers_all_supported_subjects_and_levels(self):
        supported_subjects = [subject for subject in QUICK_SUBJECTS if subject != "other"]
        supported_subjects.append("history")

        for subject in supported_subjects:
            levels = LANGUAGE_LEVELS if subject in {"english", "spanish"} else ACADEMIC_BANDS
            for product in ("worksheet", "exam", "lesson_plan"):
                for level_or_band in levels:
                    with self.subTest(subject=subject, product=product, level_or_band=level_or_band):
                        guidance = build_generation_profile_guidance(
                            subject,
                            "lower_secondary",
                            level_or_band,
                            product=product,
                        )
                        self.assertIn("ages 12 to 14", guidance)
                        self.assertIn("Prioritize these focus strands:", guidance)
                        self.assertGreaterEqual(len([line for line in guidance.splitlines() if line.strip()]), 6)

    def test_lower_secondary_quick_lesson_templates_pass_quality_checks(self):
        supported_subjects = [subject for subject in QUICK_SUBJECTS if subject != "other"]
        supported_subjects.append("history")

        for subject in supported_subjects:
            levels = LANGUAGE_LEVELS if subject in {"english", "spanish"} else ACADEMIC_BANDS
            for level_or_band in levels:
                for lesson_purpose in LESSON_PURPOSES:
                    with self.subTest(subject=subject, level_or_band=level_or_band, lesson_purpose=lesson_purpose):
                        plan = normalize_planner_output(
                            build_quick_lesson_plan(
                                subject=subject,
                                learner_stage="lower_secondary",
                                level_or_band=level_or_band,
                                lesson_purpose=lesson_purpose,
                                topic="Lower secondary audit topic",
                            )
                        )
                        issues = _lesson_plan_quality_issues(
                            plan,
                            subject=subject,
                            learner_stage="lower_secondary",
                            level_or_band=level_or_band,
                            lesson_purpose=lesson_purpose,
                        )
                        self.assertEqual([], issues)

    def test_serialized_answer_keys_and_spanish_open_answers_are_accepted(self):
        raw_answer_key = (
            "['1. María y Juan van a la escuela.;', "
            "'2. María come pan.;', "
            "'3. Juan bebe agua.;', "
            "'4. Hoy es un día especial.']"
        )
        answers = split_answer_key_items(raw_answer_key, expected_count=4)

        self.assertEqual(
            [
                "María y Juan van a la escuela.",
                "María come pan.",
                "Juan bebe agua.",
                "Hoy es un día especial.",
            ],
            answers,
        )
        self.assertTrue(_check_answer("reading_comprehension", "Maria come pan", answers[1]))
        self.assertTrue(_check_answer("reading_comprehension", "Juan bebe agua", answers[2]))

    def test_error_correction_cleanup_removes_already_correct_items(self):
        worksheet = {
            "worksheet_type": "error_correction",
            "questions": [
                "Yo hablo español",
                "Ella comió manzanas",
                "Ellos vive en Madrid",
                "Usted nadas en la piscina",
            ],
            "answer_key": "\n".join([
                "Yo hablo español",
                "Ella come manzanas",
                "Ellos viven en Madrid",
                "Usted nada en la piscina",
            ]),
        }

        pruned = _prune_error_correction_items(worksheet)

        self.assertEqual(
            [
                "Ella comió manzanas",
                "Ellos vive en Madrid",
                "Usted nadas en la piscina",
            ],
            pruned["questions"],
        )
        self.assertEqual(
            [
                "Ella come manzanas",
                "Ellos viven en Madrid",
                "Usted nada en la piscina",
            ],
            split_answer_key_items(pruned["answer_key"]),
        )

    def test_exam_normalization_prunes_invalid_error_correction_rows(self):
        raw = {
            "subject": "spanish",
            "plan_language": "es",
            "student_material_language": "es",
            "title": "Corrección de errores",
            "instructions": "Corrige las oraciones.",
            "sections": [
                {
                    "type": "error_correction",
                    "title": "Parte 1",
                    "instructions": "Corrige cada oración.",
                    "questions": [
                        "Yo hablo español",
                        "Ella comió manzanas",
                        "Ellos vive en Madrid",
                        "Usted nadas en la piscina",
                    ],
                    "answers": [
                        "Yo hablo español",
                        "Ella come manzanas",
                        "Ellos viven en Madrid",
                        "Usted nada en la piscina",
                    ],
                }
            ],
        }

        exam_data, answer_key = normalize_exam_output(raw)

        self.assertEqual(3, len(exam_data["sections"][0]["questions"]))
        self.assertEqual(
            [
                "Ella come manzanas",
                "Ellos viven en Madrid",
                "Usted nada en la piscina",
            ],
            answer_key["sections"][0]["answers"],
        )


if __name__ == "__main__":
    unittest.main()
