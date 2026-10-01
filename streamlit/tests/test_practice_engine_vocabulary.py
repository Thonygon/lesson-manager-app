import unittest
from unittest.mock import patch

from helpers import practice_engine
from helpers.practice_engine import _question_prompt_text, _strip_vocab_answer_leak


class PracticeEngineVocabularyTests(unittest.TestCase):
    def test_exam_vocabulary_preserves_authored_three_options_and_answer_order(self):
        payload = practice_engine.exam_to_exercises(
            {
                "title": "Vocabulary quiz",
                "sections": [
                    {
                        "type": "vocabulary",
                        "questions": [
                            {
                                "word": "Happy",
                                "task": "Choose the correct synonym.",
                                "options": ["Sad", "Glad", "Angry"],
                            }
                        ],
                    }
                ],
            },
            {"sections": [{"answers": ["B"]}]},
            row_id=7,
        )

        question = payload["exercises"][0]["questions"][0]
        self.assertEqual(["Sad", "Glad", "Angry"], question["options"])
        self.assertEqual(["Glad"], payload["exercises"][0]["answers"])

    def test_exam_vocabulary_parses_inline_choices_without_adding_fourth_option(self):
        payload = practice_engine.exam_to_exercises(
            {
                "title": "Vocabulary quiz",
                "sections": [
                    {
                        "type": "vocabulary",
                        "questions": [
                            {
                                "word": "Tiny",
                                "task": "Choose the best synonym. A) Huge B) Small C) Loud",
                            }
                        ],
                    }
                ],
            },
            {"sections": [{"answers": ["B"]}]},
            row_id=8,
        )

        question = payload["exercises"][0]["questions"][0]
        self.assertEqual("Choose the best synonym.", question["task"])
        self.assertEqual(["Huge", "Small", "Loud"], question["options"])
        self.assertEqual(["Small"], payload["exercises"][0]["answers"])

    def test_exam_vocabulary_maps_d_answer_to_all_are_incorrect_option(self):
        payload = practice_engine.exam_to_exercises(
            {
                "title": "Daily Routines: Simple present tense",
                "sections": [
                    {
                        "type": "vocabulary",
                        "questions": [
                            {
                                "word": "Do",
                                "task": (
                                    "Which one is correct?\n"
                                    "A) She dos the laundry on Mondays.\n"
                                    "B) She do the laundry on Mondays.\n"
                                    "C) She doing the laundry on Mondays.\n"
                                    "D) All are incorrect."
                                ),
                            }
                        ],
                    }
                ],
            },
            {"sections": [{"answers": ["D"]}]},
            row_id=9,
        )

        question = payload["exercises"][0]["questions"][0]
        self.assertEqual(
            [
                "She dos the laundry on Mondays.",
                "She do the laundry on Mondays.",
                "She doing the laundry on Mondays.",
                "All are incorrect.",
            ],
            question["options"],
        )
        self.assertEqual(["All are incorrect."], payload["exercises"][0]["answers"])

    def test_normalize_legacy_vocabulary_keeps_existing_three_choices_and_maps_label_answer(self):
        normalized = practice_engine.normalize_exercise_data_for_web(
            {
                "exercises": [
                    {
                        "type": "vocabulary",
                        "questions": [
                            {
                                "text": "Pick the antonym. A) early B) late C) noisy",
                            }
                        ],
                        "answers": ["B"],
                    }
                ]
            }
        )

        question = normalized["exercises"][0]["questions"][0]
        self.assertEqual("Pick the antonym.", question["text"])
        self.assertEqual(["Early", "Late", "Noisy"], question["options"])
        self.assertEqual(["Late"], normalized["exercises"][0]["answers"])

    def test_labeled_choice_text_preserves_alpha_labels_for_student_ui(self):
        self.assertEqual("A) First answer", practice_engine._labeled_choice_text("First answer", 0))
        self.assertEqual("D) All are incorrect.", practice_engine._labeled_choice_text("All are incorrect.", 3))

    def test_preserves_word_when_it_is_not_the_answer(self):
        prompt = _question_prompt_text(
            "vocabulary",
            {"word": "Antes", "task": "Escribe un sinonimo."},
        )
        visible = _strip_vocab_answer_leak(
            prompt,
            correct="Previo",
            options=["Previo", "Despues", "Lento", "Dificil"],
        )
        self.assertEqual(visible, "Antes: Escribe un sinonimo.")

    def test_hides_word_when_it_would_leak_the_answer(self):
        prompt = _question_prompt_text(
            "vocabulary",
            {"word": "Moderno", "task": "It is something new."},
        )
        visible = _strip_vocab_answer_leak(
            prompt,
            correct="Moderno",
            options=["Antiguo", "Clasico", "Moderno", "Lento"],
        )
        self.assertEqual(visible, "It is something new.")

    def test_worksheet_conversion_preserves_vocabulary_bank_for_fill_in_blank(self):
        payload = practice_engine.worksheet_to_exercises(
            {
                "worksheet_type": "fill_in_the_blanks",
                "title": "Daily routine",
                "questions": ["I ___ breakfast at 7."],
                "answer_key": "eat",
                "vocabulary_bank": ["eat", "drink", "sleep"],
            }
        )

        self.assertEqual(["eat", "drink", "sleep"], payload["exercises"][0]["vocabulary_bank"])

    def test_render_practice_vocabulary_bank_shows_words_to_students(self):
        with (
            patch.object(practice_engine.st, "markdown") as markdown,
            patch.object(practice_engine.st, "write") as write,
        ):
            practice_engine._render_practice_vocabulary_bank([" eat ", "", "drink"])

        markdown.assert_called_once()
        write.assert_called_once_with("eat, drink")


if __name__ == "__main__":
    unittest.main()
