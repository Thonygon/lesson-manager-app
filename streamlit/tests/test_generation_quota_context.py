import unittest
from unittest.mock import patch

from helpers import lesson_planner as planner
from helpers import quick_exam_builder as exams
from helpers import worksheet_builder as worksheets


class GenerationQuotaContextTests(unittest.TestCase):
    def test_anonymous_provider_attempts_do_not_reserve_an_account_quota(self):
        provider_calls = (
            (planner._generate_with_openrouter, "OPENROUTER_API_KEY"),
            (planner._generate_with_gemini, "GEMINI_API_KEY"),
            (planner._generate_with_openai, "OPENAI_API_KEY"),
        )
        for helper, key in provider_calls:
            with self.subTest(provider=key), \
                patch.object(planner.st, "secrets", {key: "test-key"}), \
                patch.object(planner, "OpenAI"), \
                patch("google.genai.Client"), \
                patch.object(planner, "get_ai_model_for_provider", return_value="test-model"), \
                patch("helpers.ai_runtime_approval.require_ai_runtime_approval"), \
                patch.object(planner, "run_recorded_provider_attempt", return_value="generated"), \
                patch("services.permissions_service.reserve_ai_tool", return_value=False) as reserve:
                self.assertEqual(helper("system", "user", reserve_account_quota=False), "generated")
                reserve.assert_not_called()

    def test_normal_provider_attempts_still_require_reservation(self):
        with patch.object(planner.st, "secrets", {"OPENROUTER_API_KEY": "test-key"}), \
            patch("helpers.ai_runtime_approval.require_ai_runtime_approval"), \
            patch("services.permissions_service.reserve_ai_tool", return_value=False) as reserve:
            with self.assertRaisesRegex(RuntimeError, "AI generation limit reached"):
                planner._generate_with_openrouter("system", "user")
            reserve.assert_called_once_with()

    def test_all_document_generators_forward_the_quota_context(self):
        cases = (
            (planner, "generate_ai_lesson_plan", "_build_ai_prompts", "_generate_with_openrouter", dict(
                subject="math", learner_stage="lower_secondary", level_or_band="A2",
                lesson_purpose="practice", topic="Fractions", plan_language="en",
                student_material_language="en")),
            (worksheets, "generate_ai_worksheet", "_build_worksheet_prompts", "_generate_with_openrouter", dict(
                subject="math", learner_stage="lower_secondary", level_or_band="A2",
                worksheet_type="short_answer", topic="Fractions", plan_language="en",
                student_material_language="en")),
            (exams, "generate_ai_exam", "_build_exam_prompts", "_generate_with_openrouter", dict(
                subject="math", learner_stage="lower_secondary", level_or_band="A2",
                topic="Fractions", exam_title="Test", exam_length="short",
                exercise_types=["short_answer"], instructions="", plan_language="en",
                student_material_language="en")),
        )
        for module, generator_name, prompt_name, provider_name, kwargs in cases:
            with self.subTest(generator=generator_name), \
                patch.object(module, prompt_name, return_value=("system", "user")), \
                patch.object(planner, "get_ai_provider_order", return_value=["openrouter"]), \
                patch.object(planner, provider_name, side_effect=RuntimeError("provider stopped")) as provider:
                with self.assertRaises(RuntimeError):
                    getattr(module, generator_name)(**kwargs, reserve_account_quota=False)
                provider.assert_called_once_with("system", "user", reserve_account_quota=False)


if __name__ == "__main__":
    unittest.main()
