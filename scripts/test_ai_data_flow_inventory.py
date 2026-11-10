import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_ai_data_flow_inventory as inventory


class AiDataFlowInventoryTest(unittest.TestCase):
    def test_new_sdk_helper_requires_inventory_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "streamlit/helpers/new_provider.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("client.models.generate_content(model='new', contents=[prompt])")
            with patch.object(inventory, "ROOT", root):
                self.assertIn("Uninventoried AI boundary: streamlit/helpers/new_provider.py", inventory.check())

    def test_inventoried_route_requires_runtime_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "expo/src/app/api/generate+api.ts"
            route.parent.mkdir(parents=True)
            route.write_text("requestAiProvider(provider, prompt)")
            manifest = root / "inventory.json"
            manifest.write_text(json.dumps({"approved_hosts": ["test"], "flows": [{
                "id": "text", "source": str(route.relative_to(root)),
                "boundary": str(route.relative_to(root)), "purpose": "test",
                "data_categories": ["pedagogy"], "destinations": ["test"],
                "live_check": "pending", "approval_surface": "expo_text",
                "approval_version": "EXPO_TEXT_PROMPT_VERSION",
            }]}))
            with patch.object(inventory, "ROOT", root), patch.object(inventory, "INVENTORY", manifest):
                self.assertTrue(any("missing runtime approval" in error for error in inventory.check()))

            route.write_text("requestAiProvider(provider, prompt); approvedAiProviders(expo_text, EXPO_TEXT_PROMPT_VERSION);")
            with patch.object(inventory, "ROOT", root), patch.object(inventory, "INVENTORY", manifest):
                self.assertTrue(any("provider call precedes runtime approval" in error for error in inventory.check()))

    def test_sdk_call_requires_earlier_approval_in_same_function(self):
        source = """
def guarded():
    require_ai_runtime_approval('streamlit_text', 'gemini', 'm', 'v')
    return client.models.generate_content(model='m', contents='safe')

def bypass():
    return client.models.generate_content(model='m', contents='unsafe')

def late_guard():
    response = client.responses.stream(model='m', input='unsafe')
    require_ai_runtime_approval('streamlit_text', 'openai', 'm', 'v')
    return response
"""
        self.assertEqual(inventory._python_unguarded_sdk_calls(source), [7, 10])


if __name__ == "__main__":
    unittest.main()
