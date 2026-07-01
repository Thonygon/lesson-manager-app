import logging
import unittest

from helpers.generation_guidance import build_generation_profile_guidance
from helpers.learning_programs import get_subject_progression_profile
from helpers.lesson_planner import (
    ACADEMIC_BANDS,
    LANGUAGE_LEVELS,
    LEARNER_STAGES,
    LESSON_PURPOSES,
    QUICK_SUBJECTS,
    _lesson_plan_quality_issues,
    build_quick_lesson_plan,
    normalize_planner_output,
)


for logger_name in (
    "streamlit",
    "streamlit.runtime",
    "streamlit.runtime.caching.cache_data_api",
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.runtime.state.session_state_proxy",
):
    logging.getLogger(logger_name).setLevel(logging.ERROR)


def _subjects() -> list[str]:
    return [subject for subject in QUICK_SUBJECTS if subject != "other"] + ["history"]


def _levels_for_subject(subject: str) -> list[str]:
    return LANGUAGE_LEVELS if subject in {"english", "spanish"} else ACADEMIC_BANDS


class GenerationQualityMatrixTests(unittest.TestCase):
    def test_progression_profiles_are_populated_across_all_stages(self):
        for subject in _subjects():
            for learner_stage in LEARNER_STAGES:
                for level_or_band in _levels_for_subject(subject):
                    with self.subTest(subject=subject, learner_stage=learner_stage, level_or_band=level_or_band):
                        profile = get_subject_progression_profile(subject, learner_stage, level_or_band)
                        self.assertTrue(profile.get("focus_strands"))
                        self.assertTrue(profile.get("sequence_expectations"))

    def test_generation_guidance_is_populated_across_all_products(self):
        for subject in _subjects():
            for learner_stage in LEARNER_STAGES:
                for level_or_band in _levels_for_subject(subject):
                    for product in ("worksheet", "exam", "lesson_plan"):
                        with self.subTest(
                            subject=subject,
                            learner_stage=learner_stage,
                            level_or_band=level_or_band,
                            product=product,
                        ):
                            guidance = build_generation_profile_guidance(
                                subject,
                                learner_stage,
                                level_or_band,
                                product=product,
                            )
                            lines = [line for line in guidance.splitlines() if line.strip()]
                            self.assertGreaterEqual(len(lines), 6)
                            self.assertTrue(
                                "Learners are typically around ages" in guidance
                                or "Learners are adults." in guidance
                            )
                            self.assertIn("Prioritize these focus strands:", guidance)

    def test_quick_lesson_templates_pass_quality_checks_across_all_stages(self):
        for subject in _subjects():
            for learner_stage in LEARNER_STAGES:
                for level_or_band in _levels_for_subject(subject):
                    for lesson_purpose in LESSON_PURPOSES:
                        with self.subTest(
                            subject=subject,
                            learner_stage=learner_stage,
                            level_or_band=level_or_band,
                            lesson_purpose=lesson_purpose,
                        ):
                            plan = normalize_planner_output(
                                build_quick_lesson_plan(
                                    subject=subject,
                                    learner_stage=learner_stage,
                                    level_or_band=level_or_band,
                                    lesson_purpose=lesson_purpose,
                                    topic="Generation quality audit topic",
                                )
                            )
                            issues = _lesson_plan_quality_issues(
                                plan,
                                subject=subject,
                                learner_stage=learner_stage,
                                level_or_band=level_or_band,
                                lesson_purpose=lesson_purpose,
                            )
                            self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
