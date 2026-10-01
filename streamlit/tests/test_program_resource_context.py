import unittest
from unittest.mock import patch

from helpers.program_resource_context import (
    apply_program_topic_form_defaults,
    build_program_topic_generation_context,
    build_program_topic_prompt_block,
    get_program_topic_recommendation_profile,
    infer_exam_prep_family,
    merge_program_topic_context_into_profile,
)


class ProgramResourceContextTests(unittest.TestCase):
    def test_infer_sat_exam_family_from_program_signals(self):
        family = infer_exam_prep_family(
            "english",
            program={
                "title": "SAT English Reading & Writing Prep",
                "program_overview": "Focused digital SAT preparation.",
            },
            topic={"title": "Craft and Structure"},
        )
        self.assertEqual(family, "sat_rw")

    def test_merge_program_topic_context_enriches_profile(self):
        context = build_program_topic_generation_context(
            {
                "title": "SAT English Reading & Writing Prep",
                "program_overview": "A focused SAT pathway.",
                "assessment_strategy": "Weekly SAT-style checks.",
                "resource_strategy": "Link every resource to the next exam skill.",
            },
            {
                "unit_number": 2,
                "title": "SAT Reading Question Types",
                "overview": "Domain practice",
            },
            {
                "topic_number": 1,
                "title": "Vocabulary in Context",
                "student_summary": "Use context clues to choose the best answer.",
                "learning_objectives": ["Use context clues", "Explain why distractors are wrong"],
                "success_criteria": ["Chooses the strongest text-based answer"],
                "suggested_worksheet_types": ["multiple_choice"],
                "suggested_exam_exercise_types": ["multiple_choice", "reading_comprehension"],
                "lesson_purpose": "practice_skill",
            },
            subject="english",
            learner_stage="upper_secondary",
            level_or_band="B2",
        )
        merged = merge_program_topic_context_into_profile({"summary": "Needs support with close reading."}, context)
        program = merged.get("program_context") or {}
        self.assertEqual(program.get("current_program_title"), "SAT English Reading & Writing Prep")
        self.assertEqual(program.get("current_topic_title"), "Vocabulary in Context")
        self.assertEqual(program.get("exam_family"), "sat_rw")
        self.assertIn("Vocabulary in Context", program.get("next_topics") or [])
        self.assertIn("multiple_choice", program.get("suggested_exam_types") or [])
        self.assertIn("Current program topic is Vocabulary in Context", merged.get("summary") or "")

    def test_prompt_block_adds_exam_prep_guidance(self):
        profile = {
            "program_context": {
                "current_program_title": "DELE B2 Prep",
                "current_unit_title": "Comprension lectora",
                "current_topic_title": "Registro y tono",
                "topic_summary": "Interpret register in authentic Spanish texts.",
                "topic_learning_objectives": ["Interpret communicative intent"],
                "suggested_exam_types": ["reading_comprehension"],
                "exam_family": "dele",
                "exam_display_name": "DELE",
                "exam_focus_areas": ["Communicative purpose", "Register control"],
            }
        }
        block = build_program_topic_prompt_block(profile, product="exam")
        self.assertIn("Program-linked resource brief:", block)
        self.assertIn("Registro y tono", block)
        self.assertIn("DELE", block)
        self.assertIn("Communicative purpose", block)
        self.assertIn("authentic", block.lower())

    def test_sat_reading_topic_recommends_reading_focused_formats(self):
        context = build_program_topic_generation_context(
            {"title": "SAT English Reading & Writing Prep"},
            {"title": "SAT Reading Foundations"},
            {
                "title": "Skimming & Scanning",
                "student_summary": "Read short SAT-style texts quickly to locate key ideas and evidence.",
                "learning_objectives": ["Skim short passages", "Scan for details"],
            },
            subject="english",
            learner_stage="upper_secondary",
            level_or_band="B2",
        )
        profile = get_program_topic_recommendation_profile(context)
        self.assertTrue(profile["worksheet_ranked"])
        self.assertIn("reading_comprehension", profile["worksheet_ranked"][:2])
        self.assertIn("multiple_choice", profile["exam_ranked"][:3])

    def test_general_grammar_topic_recommends_editing_formats(self):
        context = build_program_topic_generation_context(
            {"title": "B1 English Grammar Program"},
            {"title": "Present Simple Accuracy"},
            {
                "title": "Subject-verb agreement",
                "student_summary": "Correct common present simple agreement errors.",
                "learning_objectives": ["Notice agreement mistakes"],
                "success_criteria": ["Edits incorrect present simple sentences accurately"],
            },
            subject="english",
            learner_stage="lower_secondary",
            level_or_band="B1",
        )
        profile = get_program_topic_recommendation_profile(context)
        self.assertIn("error_correction", profile["worksheet_ranked"][:2])

    def test_prompt_block_warns_when_selected_format_is_less_typical(self):
        profile = {
            "program_context": {
                "current_program_title": "SAT English Reading & Writing Prep",
                "current_unit_title": "SAT Reading Foundations",
                "current_topic_title": "Skimming & Scanning",
                "topic_summary": "Read short texts quickly for gist and evidence.",
                "topic_learning_objectives": ["Skim", "Scan"],
                "exam_family": "sat_rw",
                "exam_display_name": "Digital SAT Reading and Writing",
                "exam_focus_areas": ["Information and Ideas"],
            }
        }
        block = build_program_topic_prompt_block(
            profile,
            product="worksheet",
            selected_formats=["word_search_vocab"],
        )
        self.assertIn("less typical", block.lower())
        self.assertIn("program goals", block.lower())

    def test_program_topic_defaults_preserve_manual_purpose_override_for_same_context(self):
        context = build_program_topic_generation_context(
            {"title": "SAT English Reading & Writing Prep"},
            {"title": "SAT Reading Foundations"},
            {
                "title": "Skimming & Scanning",
                "student_summary": "Read short texts quickly for gist and evidence.",
                "lesson_purpose": "practice_skill",
            },
            subject="english",
            learner_stage="upper_secondary",
            level_or_band="B2",
        )
        session_state = {}
        with patch("helpers.program_resource_context.st.session_state", session_state):
            apply_program_topic_form_defaults(
                context,
                stage_key="quick_plan_learner_stage",
                level_key="quick_plan_level",
                topic_key="quick_plan_topic",
                purpose_key="quick_plan_purpose",
            )
            self.assertEqual("practice_skill", session_state["quick_plan_purpose"])
            session_state["quick_plan_purpose"] = "review_topic"
            apply_program_topic_form_defaults(
                context,
                stage_key="quick_plan_learner_stage",
                level_key="quick_plan_level",
                topic_key="quick_plan_topic",
                purpose_key="quick_plan_purpose",
            )
            self.assertEqual("review_topic", session_state["quick_plan_purpose"])

    def test_program_topic_defaults_refresh_when_context_changes(self):
        first_context = build_program_topic_generation_context(
            {"title": "B1 English Grammar Program"},
            {"title": "Present Simple Accuracy"},
            {
                "title": "Subject-verb agreement",
                "student_summary": "Correct common present simple agreement errors.",
                "lesson_purpose": "review_topic",
            },
            subject="english",
            learner_stage="lower_secondary",
            level_or_band="B1",
        )
        second_context = build_program_topic_generation_context(
            {"title": "B1 English Grammar Program"},
            {"title": "Present Simple Accuracy"},
            {
                "title": "Error analysis",
                "student_summary": "Diagnose why agreement mistakes happen.",
                "lesson_purpose": "diagnose_difficulty",
            },
            subject="english",
            learner_stage="lower_secondary",
            level_or_band="B1",
        )
        session_state = {}
        with patch("helpers.program_resource_context.st.session_state", session_state):
            apply_program_topic_form_defaults(
                first_context,
                stage_key="quick_plan_learner_stage",
                level_key="quick_plan_level",
                topic_key="quick_plan_topic",
                purpose_key="quick_plan_purpose",
            )
            session_state["quick_plan_purpose"] = "practice_skill"
            apply_program_topic_form_defaults(
                second_context,
                stage_key="quick_plan_learner_stage",
                level_key="quick_plan_level",
                topic_key="quick_plan_topic",
                purpose_key="quick_plan_purpose",
            )
            self.assertEqual("diagnose_difficulty", session_state["quick_plan_purpose"])


if __name__ == "__main__":
    unittest.main()
