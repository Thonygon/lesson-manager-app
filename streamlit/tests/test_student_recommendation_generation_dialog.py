import unittest
from unittest.mock import patch

from app_pages import app_page_students as students_page


class StudentRecommendationGenerationDialogTests(unittest.TestCase):
    def setUp(self):
        self.original_state = dict(students_page.st.session_state)
        students_page.st.session_state.clear()

    def tearDown(self):
        students_page.st.session_state.clear()
        students_page.st.session_state.update(self.original_state)

    def test_each_recommendation_generator_renders_in_a_large_dialog(self):
        renderer_names = {
            "lesson_plan": "render_quick_lesson_planner_expander",
            "worksheet": "render_quick_worksheet_maker_expander",
            "exam": "render_quick_exam_builder_expander",
        }

        for tool_kind, renderer_name in renderer_names.items():
            with self.subTest(tool_kind=tool_kind):
                students_page.st.session_state.clear()
                students_page.st.session_state["_student_recommendation_generation_dialog"] = {
                    "version": students_page._STUDENT_GENERATION_DIALOG_VERSION,
                    "tool_kind": tool_kind,
                }
                dialog_calls = []

                def fake_dialog(title, *, width, on_dismiss):
                    dialog_calls.append((title, width, on_dismiss))
                    return lambda fn: fn

                with (
                    patch.object(students_page.st, "dialog", side_effect=fake_dialog),
                    patch.object(students_page, renderer_name) as renderer,
                    patch.object(students_page.st, "button", return_value=False),
                ):
                    students_page._render_student_generation_dialog()

                self.assertEqual(1, len(dialog_calls))
                self.assertEqual("large", dialog_calls[0][1])
                self.assertIs(students_page._clear_student_generation_dialog, dialog_calls[0][2])
                renderer.assert_called_once_with(embedded=True)

    def test_recommendation_prefill_opens_dialog_without_leaving_students_page(self):
        students_page.st.session_state["page"] = "students"
        recommendation = {
            "subject_key": "english",
            "learner_stage": "lower_secondary",
            "level_or_band": "A2",
            "title": "Past tense review",
            "student_label": "Ada Student",
            "student_id": "student-1",
        }

        with (
            patch.object(students_page, "clear_smart_tool_result_state") as clear_results,
            patch.object(students_page, "set_active_recommendation_context"),
            patch.object(students_page, "record_recommendation_event"),
            patch.object(students_page, "get_current_user_id", return_value="teacher-1"),
            patch.object(students_page.st, "rerun") as rerun,
        ):
            students_page._prefill_smart_tool_from_recommendation(recommendation, "worksheet")

        clear_results.assert_called_once_with()
        self.assertEqual("students", students_page.st.session_state["page"])
        self.assertEqual("Past tense review", students_page.st.session_state["ws_topic"])
        self.assertEqual(
            {
                "version": students_page._STUDENT_GENERATION_DIALOG_VERSION,
                "tool_kind": "worksheet",
            },
            students_page.st.session_state["_student_recommendation_generation_dialog"],
        )
        rerun.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
