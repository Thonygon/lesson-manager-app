import ast
import unittest
from pathlib import Path

from translations_en import EN
from translations_es import ES
from translations_tr import TR


class AdminConsoleHardeningTests(unittest.TestCase):
    def test_admin_page_has_no_duplicate_function_names(self):
        source = Path("app_pages/admin.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        seen: dict[str, int] = {}
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                seen[node.name] = seen.get(node.name, 0) + 1
        duplicates = {name: count for name, count in seen.items() if count > 1}
        self.assertEqual({}, duplicates)

    def test_admin_translation_hardening_keys_exist_in_all_languages(self):
        required = [
            "admin_create_account_confirm",
            "admin_create_account_confirm_error",
            "admin_subscription_assign_confirm",
            "admin_subscription_assign_confirm_error",
            "admin_subscription_action_confirm",
            "admin_subscription_action_confirm_error",
            "admin_plan_save_confirm",
            "admin_plan_save_confirm_error",
            "admin_model_reports_status_caption",
            "admin_eic_role_visibility_note",
            "admin_eic_experiment_type_label",
            "admin_eic_experiment_table_type",
            "admin_pagination_previous",
            "admin_pagination_next",
            "admin_pagination_status",
        ]
        for key in required:
            self.assertIn(key, EN)
            self.assertIn(key, ES)
            self.assertIn(key, TR)


if __name__ == "__main__":
    unittest.main()
