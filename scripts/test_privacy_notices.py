import json
import tempfile
import unittest
from pathlib import Path

from build_privacy_notices import AUDIENCES, LANGUAGES, SOURCE, build


class PrivacyNoticesTest(unittest.TestCase):
    def test_all_audiences_and_languages_have_public_pages(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        expo_version = (SOURCE.parents[1] / "expo/src/lib/privacy-notices.ts").read_text(encoding="utf-8")
        self.assertIn(f"PRIVACY_NOTICE_VERSION = '{source['version']}'", expo_version)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build(output)
            self.assertTrue((output / "index.html").exists())
            self.assertTrue((output / "privacy.css").exists())
            for language in LANGUAGES:
                for audience in AUDIENCES:
                    page = (output / language / audience / "index.html").read_text(encoding="utf-8")
                    self.assertIn(f'<html lang="{language}">', page)
                    self.assertIn(source["version"], page)
                    self.assertIn('mailto:info@masterclassio.com', page)
                    self.assertIn(f'https://masterclassio.com/privacy/{language}/{audience}/', page)
                    for related in AUDIENCES:
                        self.assertIn(f'/privacy/{language}/{related}/', page)


if __name__ == "__main__":
    unittest.main()
