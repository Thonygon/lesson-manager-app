import unittest
from unittest.mock import patch

from helpers import goal_explorer


class ExplorerSmartToolDialogTests(unittest.TestCase):
    def test_each_explorer_smart_tool_renders_inside_large_dialog(self):
        renderer_names = {
            "planner": "_render_explore_lesson_planner",
            "worksheet": "_render_explore_worksheet_maker",
            "exam": "_render_explore_exam_builder",
            "program": "_render_explore_program_maker",
        }

        for tool_key, renderer_name in renderer_names.items():
            with self.subTest(tool_key=tool_key):
                calls = []

                def fake_dialog(title, *, width):
                    calls.append((title, width))
                    return lambda fn: fn

                with (
                    patch.object(goal_explorer.st, "dialog", side_effect=fake_dialog),
                    patch.object(goal_explorer, renderer_name) as renderer,
                ):
                    goal_explorer._render_explore_ai_tool_dialog(tool_key, "Tool title")

                self.assertEqual([("Tool title", "large")], calls)
                renderer.assert_called_once_with()

    def test_unknown_explorer_smart_tool_does_not_open_dialog(self):
        with patch.object(goal_explorer.st, "dialog") as dialog:
            goal_explorer._render_explore_ai_tool_dialog("unknown", "Unknown")

        dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
