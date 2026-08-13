import unittest
from contextlib import nullcontext
from unittest.mock import patch

from helpers import material_recommendations


class MaterialRecommendationsInlineTests(unittest.TestCase):
    def test_inline_actions_render_inline_preview_without_global_assign_dialogs(self):
        match = {
            "kind": "worksheet",
            "source": "community",
            "recommendation_bucket": "very_close",
            "row": {
                "id": 7,
                "title": "Family Worksheet",
                "topic": "family",
                "subject": "English",
                "learner_stage": "teens",
                "level_or_band": "A1",
                "worksheet_type": "fill_in_blank",
            },
        }

        with (
            patch.object(material_recommendations, "find_similar_materials", return_value=[match]),
            patch.object(material_recommendations, "t", side_effect=lambda value: value),
            patch.object(material_recommendations.st, "markdown"),
            patch.object(material_recommendations.st, "warning"),
            patch.object(material_recommendations.st, "caption"),
            patch.object(material_recommendations.st, "button", return_value=False),
            patch.object(material_recommendations.st, "columns", side_effect=lambda spec, **kwargs: [nullcontext() for _ in range(len(spec))]),
            patch.object(material_recommendations, "_render_inline_material_recommendation") as render_inline,
            patch("helpers.teacher_student_integration.render_resource_bulk_assign_dialog") as render_dialog,
        ):
            matches = material_recommendations.render_generation_recommendations(
                {
                    "kind": "worksheet",
                    "subject": "English",
                    "learner_stage": "teens",
                    "level_or_band": "A1",
                    "topic": "family",
                },
                state_prefix="test_inline_recs",
                inline_actions=True,
            )

        self.assertEqual([match], matches)
        render_inline.assert_called_once_with("test_inline_recs")
        render_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
