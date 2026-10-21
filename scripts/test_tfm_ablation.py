import unittest

from tfm_ablation import evaluate


class AblationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "code_version": "synthetic-test", "candidate_set_version": "synthetic-test",
            "contexts": [{"id": "synthetic-context", "candidates": [
                {"id": "r1", "eligible": True}, {"id": "r2", "eligible": True},
                {"id": "r3", "eligible": False},
            ], "scores": {"A": {"r1": 2, "r2": 1}, "B": {"r1": 1, "r2": 2}, "C": {"r1": 3, "r2": 1}}}],
        }

    def test_top_five_without_judgments_has_no_ndcg(self):
        result = evaluate(self.fixture)["contexts"][0]
        self.assertEqual(result["top5"]["A"], ["r1", "r2"])
        self.assertNotIn("ndcg_at_5", result)

    def test_candidate_mismatch_rejected(self):
        self.fixture["contexts"][0]["scores"]["B"].pop("r2")
        with self.assertRaisesRegex(ValueError, "same eligible candidates"):
            evaluate(self.fixture)

    def test_independent_judgments_required(self):
        self.fixture["contexts"][0]["judgments"] = {"r1": 3, "r2": 0}
        with self.assertRaisesRegex(ValueError, "independent human"):
            evaluate(self.fixture)
        self.fixture["contexts"][0]["judgment_source"] = "independent_human"
        self.assertEqual(evaluate(self.fixture)["contexts"][0]["ndcg_at_5"]["A"], 1)


if __name__ == "__main__":
    unittest.main()
