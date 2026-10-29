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


if __name__ == "__main__":
    unittest.main()
