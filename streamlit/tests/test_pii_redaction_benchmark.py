import unittest

from scripts.benchmark_pii_redaction import CASES, evaluate


class PiiRedactionBenchmarkTest(unittest.TestCase):
    def test_synthetic_multilingual_baseline(self):
        result = evaluate()
        self.assertEqual(sum(result["all"].values()), len(CASES))
        self.assertEqual(result["all"]["fn"], 0)
        self.assertEqual(result["all"]["fp"], 0)
        for locale in ("es", "en", "tr"):
            self.assertIn(f"locale:{locale}", result)


if __name__ == "__main__":
    unittest.main()
