import unittest

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


if __name__ == "__main__":
    unittest.main()
