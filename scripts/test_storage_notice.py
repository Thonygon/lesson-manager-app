import json
import tempfile
import unittest
from pathlib import Path

from build_storage_notice import SOURCE, build


class StorageNoticeTest(unittest.TestCase):
    def test_inventory_and_app_notice_stay_versioned(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        repo = SOURCE.parents[1]
        app = (repo / "expo/src/lib/privacy-notices.ts").read_text(encoding="utf-8")
        banner = (repo / "legal/storage-banner.js").read_text(encoding="utf-8")
        self.assertIn(f"STORAGE_NOTICE_VERSION = '{data['version']}'", app)
        self.assertIn(f"const version = '{data['version']}'", banner)
        names = " ".join(entry["name"] for entry in data["entries"])
        for key in ("__cf_bm", "classio.interfaceLanguage", "classio.storageNoticeSeen", "classio-explorer-practice", "masterClassioStorageNoticeSeen"):
            self.assertIn(key, names)
        self.assertNotIn("classio.language,", names)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build(output)
            for language in ("tr", "en", "es"):
                page = (output / language / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'<html lang="{language}">', page)
                self.assertIn(data["version"], page)
                self.assertIn("__cf_bm", page)
                self.assertIn("info@masterclassio.com", page)
                self.assertIn(f"/privacy/{language}/website/", page)
                self.assertEqual(page.count("<tr>"), len(data["entries"]) + 1)


if __name__ == "__main__":
    unittest.main()
