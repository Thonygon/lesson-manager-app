import json
import html
import re
import tempfile
import unittest
from pathlib import Path

from build_legal_agreements import LANGUAGES, SLUGS, SOURCE, build, document_hash


class LegalAgreementsTest(unittest.TestCase):
    def test_public_pages_and_expo_manifest_match(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build(root, root / "expo.ts")
            self.assertEqual(len(manifest["documents"]), len(SLUGS) * len(LANGUAGES))
            for entry in manifest["documents"]:
                slug, language = entry["slug"], entry["language"]
                page = (root / slug / language / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'<html lang="{language}">', page)
                self.assertIn(html.escape(source["documents"][slug][language]["lead"], quote=True), page)
                self.assertIn(entry["sha256"], page)
                self.assertEqual(entry["sha256"], document_hash(source["documents"][slug][language]))
                self.assertIn(f'/{slug}/en/', page)
                self.assertIn(f'/{slug}/es/', page)
                self.assertIn(f'/{slug}/tr/', page)
            app_copy = (SOURCE.parents[1] / "expo/src/lib/legal-publication.generated.ts").read_text(encoding="utf-8")
            self.assertEqual((root / "expo.ts").read_text(encoding="utf-8"), app_copy)
            self.assertIn(source["documents"]["terms"]["en"]["lead"], (root / "terms" / "index.html").read_text(encoding="utf-8"))

    def test_acceptance_registry_matches_published_text(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        sql = (SOURCE.parents[1] / "streamlit/migrations/versioned_legal_acceptance.sql").read_text(encoding="utf-8")
        registered = set(re.findall(r"\('([^']+)','([^']+)','([^']+)','([0-9a-f]{64})','[0-9-]+'\)", sql))
        expected = {
            (slug, language, source["version"], document_hash(source["documents"][slug][language]))
            for slug in SLUGS for language in LANGUAGES
        }
        self.assertEqual(registered, expected)


if __name__ == "__main__":
    unittest.main()
