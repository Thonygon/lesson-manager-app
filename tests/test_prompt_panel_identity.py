import logging
import unittest

from helpers.generation_guidance import build_expert_panel_prompt_blurb
from helpers.learning_programs import _build_program_skeleton_prompts
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


if __name__ == "__main__":
    unittest.main()
