import unittest
from unittest.mock import patch

from app_pages import home
from core.navigation import clear_smart_tool_result_state


class TeacherSmartToolDialogTests(unittest.TestCase):
    def setUp(self):
        self.original_state = dict(home.st.session_state)
        home.st.session_state.clear()

    def tearDown(self):
        home.st.session_state.clear()
        home.st.session_state.update(self.original_state)

    def test_work_smart_tool_renders_inside_large_dialog(self):
        home.st.session_state["_home_smart_tool_dialog"] = {
            "version": home._HOME_SMART_TOOL_DIALOG_VERSION,
            "flag": "open_quick_ws_expander",
        }
        dialog_calls = []

        def fake_dialog(title, *, width, on_dismiss):
            dialog_calls.append((title, width, on_dismiss))
            return lambda fn: fn

        with (
            patch.object(home.st, "dialog", side_effect=fake_dialog),
            patch.object(home, "render_quick_worksheet_maker_expander") as renderer,
            patch.object(home.st, "button", return_value=False),
        ):
            home._render_home_smart_tool_dialog()

        self.assertEqual(1, len(dialog_calls))
        self.assertEqual("large", dialog_calls[0][1])
        self.assertIs(home._clear_home_smart_tool_dialog, dialog_calls[0][2])
        renderer.assert_called_once_with()

    def test_invalid_dialog_state_is_cleared_without_rendering(self):
        home.st.session_state["_home_smart_tool_dialog"] = {
            "version": home._HOME_SMART_TOOL_DIALOG_VERSION,
            "flag": "unknown",
        }

        with patch.object(home.st, "dialog") as dialog:
            home._render_home_smart_tool_dialog()

        self.assertNotIn("_home_smart_tool_dialog", home.st.session_state)
        dialog.assert_not_called()

    def test_navigation_cleanup_dismisses_open_work_smart_dialog(self):
        home.st.session_state["_home_smart_tool_dialog"] = {
            "version": home._HOME_SMART_TOOL_DIALOG_VERSION,
            "flag": "open_quick_exam_expander",
        }

        clear_smart_tool_result_state(clear_selection=True)

        self.assertNotIn("_home_smart_tool_dialog", home.st.session_state)


if __name__ == "__main__":
    unittest.main()
