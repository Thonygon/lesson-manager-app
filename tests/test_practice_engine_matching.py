import unittest

from helpers.practice_engine import (
    exam_to_exercises,
    normalize_exercise_data_for_web,
    worksheet_to_exercises,
)
from helpers.quick_exam_builder import repair_exam_answer_key


class PracticeEngineMatchingTests(unittest.TestCase):
    def setUp(self):
        self.questions = [
            {"left": "Refrigerator", "right": "For watching movies"},
            {"left": "Bed", "right": "For brushing teeth"},
            {"left": "Television", "right": "For keeping food cold"},
            {"left": "Toothbrush", "right": "For sleeping"},
        ]

    def test_exam_matching_letters_resolve_against_column_b(self):
        payload = exam_to_exercises(
            {
                "title": "Home vocabulary",
                "sections": [
                    {
                        "type": "matching",
                        "title": "Match",
                        "questions": self.questions,
                    }
                ],
            },
            {
                "sections": [
                    {"title": "Match", "answers": ["C", "D", "A", "B"]}
                ]
            },
        )

        self.assertEqual(
            [
                "For keeping food cold",
                "For sleeping",
                "For watching movies",
                "For brushing teeth",
            ],
            payload["exercises"][0]["answers"],
        )

    def test_exam_repair_canonicalizes_matching_markers(self):
        _exam, answer_key = repair_exam_answer_key(
            {"sections": [{"type": "matching", "questions": self.questions}]},
            {"sections": [{"answers": ["C", "D", "A", "B"]}]},
        )

        self.assertEqual(
            [
                "For keeping food cold",
                "For sleeping",
                "For watching movies",
                "For brushing teeth",
            ],
            answer_key["sections"][0]["answers"],
        )

    def test_exam_repair_canonicalizes_legacy_dict_markers(self):
        _exam, answer_key = repair_exam_answer_key(
            {"sections": [{"type": "matching", "questions": self.questions}]},
            {
                "sections": [
                    {
                        "answers": [
                            {"1. Refrigerator": "C"},
                            {"2. Bed": "D"},
                            {"3. Television": "A"},
                            {"4. Toothbrush": "B"},
                        ]
                    }
                ]
            },
        )

        self.assertEqual(
            [
                "For keeping food cold",
                "For sleeping",
                "For watching movies",
                "For brushing teeth",
            ],
            answer_key["sections"][0]["answers"],
        )

    def test_legacy_numeric_matching_keys_are_supported(self):
        payload = normalize_exercise_data_for_web(
            {
                "exercises": [
                    {
                        "type": "matching",
                        "questions": self.questions,
                        "answers": ["3", "4", "1", "2"],
                    }
                ]
            }
        )

        self.assertEqual(
            [
                "For keeping food cold",
                "For sleeping",
                "For watching movies",
                "For brushing teeth",
            ],
            payload["exercises"][0]["answers"],
        )

    def test_text_matching_keys_are_not_replaced(self):
        payload = normalize_exercise_data_for_web(
            {
                "exercises": [
                    {
                        "type": "matching",
                        "questions": self.questions,
                        "answers": [
                            "For keeping food cold",
                            "For sleeping",
                            "For watching movies",
                            "For brushing teeth",
                        ],
                    }
                ]
            }
        )

        self.assertEqual(
            [
                "For keeping food cold",
                "For sleeping",
                "For watching movies",
                "For brushing teeth",
            ],
            payload["exercises"][0]["answers"],
        )

    def test_worksheet_matching_pairs_keep_their_explicit_answers(self):
        payload = worksheet_to_exercises(
            {
                "worksheet_type": "matching",
                "title": "Home vocabulary",
                "matching_pairs": [
                    {"left": "Refrigerator", "right": "For keeping food cold"},
                    {"left": "Bed", "right": "For sleeping"},
                ],
            }
        )

        self.assertEqual(
            ["For keeping food cold", "For sleeping"],
            payload["exercises"][0]["answers"],
        )


if __name__ == "__main__":
    unittest.main()
