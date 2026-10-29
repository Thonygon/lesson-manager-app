import unittest
from unittest.mock import patch

from scripts import benchmark_pii_redaction
from scripts.benchmark_pii_redaction import CASES, evaluate


class PiiRedactionBenchmarkTest(unittest.TestCase):
    def test_synthetic_multilingual_baseline(self):
        result = evaluate()
        self.assertEqual(sum(result["all"].values()), len(CASES))
        self.assertEqual(result["all"]["fn"], 0)
        self.assertEqual(result["all"]["fp"], 0)
        for locale in ("es", "en", "tr"):
            self.assertIn(f"locale:{locale}", result)

    def test_partial_phone_mutation_does_not_count_as_redacted(self):
        with patch.object(benchmark_pii_redaction, "redact_direct_identifiers", side_effect=lambda value: value.replace("+", "")):
            self.assertGreater(evaluate()["entity:phone"]["fn"], 0)


if __name__ == "__main__":
    unittest.main()
