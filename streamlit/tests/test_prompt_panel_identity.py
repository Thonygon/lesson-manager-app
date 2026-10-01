import logging
import unittest
from unittest.mock import patch

from helpers.generation_guidance import build_expert_panel_prompt_blurb
from helpers.learning_programs import (
    _build_program_skeleton_prompts,
    _program_language_quality_issues,
    _sync_saved_learning_program_from_builder,
)
from helpers.lesson_planner import _build_ai_prompts as _build_lesson_plan_prompts
from helpers.quick_exam_builder import _build_exam_prompts
from helpers.worksheet_builder import _build_worksheet_prompts


for logger_name in (
    "streamlit",
    "streamlit.runtime",
    "streamlit.runtime.caching.cache_data_api",
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.runtime.state.session_state_proxy",
):
    logging.getLogger(logger_name).setLevel(logging.ERROR)


class PromptPanelIdentityTests(unittest.TestCase):
    def test_shared_panel_blurb_mentions_specialist_team(self):
        blurb = build_expert_panel_prompt_blurb("worksheet")
        self.assertIn("expert generation panel", blurb)
        self.assertIn("PhD-level professionals", blurb)
        self.assertIn("subject-specific pedagogy", blurb)

    def test_worksheet_prompt_uses_panel_identity(self):
        system_prompt, _user_prompt = _build_worksheet_prompts(
            {
                "subject": "english",
                "topic": "Daily routines",
                "learner_stage": "lower_secondary",
                "level_or_band": "A1",
                "worksheet_type": "reading_comprehension",
                "plan_language": "en",
                "student_material_language": "en",
            }
        )
        self.assertIn("expert generation panel", system_prompt)

    def test_exam_prompt_uses_panel_identity(self):
        system_prompt, _user_prompt = _build_exam_prompts(
            {
                "subject": "science",
                "subject_group": "science",
                "topic": "Plants",
                "exam_title": "Plants Quiz",
                "learner_stage": "upper_primary",
                "level_or_band": "beginner_band",
                "exam_length": "short",
                "exercise_types": ["multiple_choice", "short_answer", "classification"],
                "instructions": "Answer all questions.",
                "plan_language": "en",
                "student_material_language": "en",
            }
        )
        self.assertIn("expert generation panel", system_prompt)

    def test_lesson_plan_prompt_uses_panel_identity(self):
        system_prompt, _user_prompt = _build_lesson_plan_prompts(
            {
                "subject": "mathematics",
                "topic": "Fractions",
                "learner_stage": "upper_primary",
                "level_or_band": "intermediate_band",
                "lesson_purpose": "introduce_concept",
                "plan_language": "en",
                "student_material_language": "en",
                "required_sections": ["title", "objective", "core_material"],
                "core_material_required_keys": ["worked_example"],
            }
        )
        self.assertIn("expert generation panel", system_prompt)

    def test_learning_program_prompt_uses_panel_identity(self):
        system_prompt, _user_prompt = _build_program_skeleton_prompts(
            {
                "subject": "history",
                "subject_display": "History",
                "subject_family": "general",
                "learner_stage": "upper_secondary",
                "level_or_band": "advanced_band",
                "program_language": "en",
                "requested_units": 8,
                "requested_lessons_per_unit": 4,
                "subject_progression_profile": {
                    "focus_strands": ["analysis", "critique", "transfer"],
                    "sequence_expectations": ["Start with secure understanding.", "Move into interpretation.", "Finish with synthesis."],
                },
            }
        )
        self.assertIn("expert generation panel", system_prompt)

    def test_learning_program_prompt_explicitly_states_requested_languages(self):
        _system_prompt, user_prompt = _build_program_skeleton_prompts(
            {
                "subject": "spanish",
                "subject_display": "Español",
                "subject_family": "language",
                "learner_stage": "upper_secondary",
                "level_or_band": "B2",
                "program_language": "es",
                "student_material_language": "es",
                "requested_units": 9,
                "requested_lessons_per_unit": 3,
                "subject_progression_profile": {
                    "focus_strands": ["comprensión", "producción"],
                    "sequence_expectations": ["Empieza con comprensión.", "Avanza hacia producción."],
                },
            }
        )
        self.assertIn('program_language is "es" (Spanish)', user_prompt)
        self.assertIn('student_material_language is "es" (Spanish)', user_prompt)
        self.assertIn("do not default to English", user_prompt)

    def test_learning_program_language_quality_flags_obvious_english_when_spanish_requested(self):
        issues = _program_language_quality_issues(
            {
                "title": "DELE B2 Exam Preparation Program",
                "program_overview": "This program prepares upper secondary learners for the DELE B2 exam by developing reading, writing, listening, and speaking skills through authentic tasks and exam-style practice.",
                "teacher_rationale": "The curriculum is sequenced to move from diagnostic to integrated performance, ensuring that each skill is explicitly taught, practiced, and then combined in realistic exam tasks.",
                "student_summary": "Build confidence for the exam with clear goals.",
                "units": [],
            },
            program_language="es",
            student_material_language="es",
        )
        self.assertTrue(issues)
        self.assertIn("teacher-facing program fields are not in requested es", issues[0])

    def test_learning_program_sync_preserves_student_material_language(self):
        with patch("helpers.learning_programs.update_learning_program", return_value=(True, "ok")) as update_mock:
            ok, msg = _sync_saved_learning_program_from_builder(
                saved_program_id=42,
                result={"title": "Programa DELE", "units": []},
                meta={
                    "subject": "spanish",
                    "learner_stage": "upper_secondary",
                    "level_or_band": "B2",
                    "visibility": "private",
                    "custom_subject_name": "",
                    "program_language": "es",
                    "student_material_language": "es",
                    "student_native_language": "en",
                    "builder_config": {"program_track": "exam_prep", "exam_prep_target": "dele"},
                    "parent_program_id": None,
                    "sequence_group_id": "dele-upper-secondary",
                    "sequence_order": 1,
                    "prerequisite_summary": "",
                },
                subject="spanish",
                learner_stage="upper_secondary",
                level_or_band="B2",
                custom_subject_name="",
                visibility="private",
                mode_used="ai",
            )
        self.assertTrue(ok)
        self.assertEqual("ok", msg)
        self.assertEqual("es", update_mock.call_args.kwargs["program_language"])
        self.assertEqual("es", update_mock.call_args.kwargs["student_material_language"])


if __name__ == "__main__":
    unittest.main()
