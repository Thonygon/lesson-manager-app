import unittest
from unittest.mock import patch

from helpers import practice_engine
from helpers.practice_engine import _question_prompt_text, _strip_vocab_answer_leak


class PracticeEngineVocabularyTests(unittest.TestCase):
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
