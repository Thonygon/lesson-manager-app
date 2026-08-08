import logging
import unittest

from helpers.quick_exam_builder import (
    attach_exam_language_metadata,
    infer_exam_language,
    normalize_exam_output,
)


for logger_name in (
    "streamlit",
    "streamlit.runtime",
    "streamlit.runtime.caching.cache_data_api",
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.runtime.state.session_state_proxy",
):
    logging.getLogger(logger_name).setLevel(logging.ERROR)


class QuickExamLanguageMetadataTests(unittest.TestCase):
    def test_normalize_exam_output_preserves_language_metadata(self):
        exam_data, answer_key = normalize_exam_output(
            {
                "subject": "Spanish",
                "plan_language": "es",
                "student_material_language": "es",
                "title": "Comprensión lectora",
                "instructions": "Lee el texto y responde las preguntas.",
                "sections": [
                    {
                        "type": "reading_comprehension",
                        "title": "Parte 1",
                        "instructions": "Elige la respuesta correcta.",
                        "questions": ["¿Dónde vive Ana?"],
                        "answers": ["En Madrid."],
                    }
                ],
            }
        )
        self.assertEqual("es", exam_data.get("plan_language"))
        self.assertEqual("es", exam_data.get("student_material_language"))
        self.assertEqual("es", answer_key.get("plan_language"))
        self.assertEqual("es", answer_key.get("student_material_language"))

    def test_attach_exam_language_metadata_repairs_legacy_spanish_exam(self):
        repaired_exam, plan_language, student_material_language = attach_exam_language_metadata(
            {
                "title": "Examen de español: Información personal",
                "instructions": "Lee el texto y responde las preguntas.",
                "sections": [
                    {
                        "type": "reading_comprehension",
                        "title": "Parte 1",
                        "instructions": "Elige la respuesta correcta.",
                        "questions": ["¿Cómo se llama el estudiante?"],
                    }
                ],
            },
            subject="Spanish",
        )
        self.assertEqual("es", plan_language)
        self.assertEqual("es", student_material_language)
        self.assertEqual("es", repaired_exam.get("plan_language"))
        self.assertEqual("es", repaired_exam.get("student_material_language"))

    def test_attach_exam_language_metadata_uses_content_for_non_language_subject(self):
        repaired_exam, plan_language, student_material_language = attach_exam_language_metadata(
            {
                "title": "Prueba de ciencias",
                "instructions": "Lee el texto y responde las preguntas.",
                "sections": [
                    {
                        "type": "short_answer",
                        "title": "Parte 1",
                        "instructions": "Escribe una respuesta corta.",
                        "questions": ["¿Qué necesitan las plantas para crecer?"],
                    }
                ],
            },
            subject="Science",
        )
        self.assertEqual("es", plan_language)
        self.assertEqual("es", student_material_language)
        self.assertEqual("es", repaired_exam.get("student_material_language"))

    def test_infer_exam_language_detects_turkish_subject_content(self):
        detected = infer_exam_language(
            {
                "title": "Türkçe sınavı",
                "instructions": "Metni oku ve doğru cevabı seç.",
                "sections": [
                    {
                        "title": "Bölüm 1",
                        "instructions": "Soruları cevapla.",
                        "questions": ["Öğrenci nerede yaşıyor?"],
                    }
                ],
            },
            subject="Science",
        )
        self.assertEqual("tr", detected)


if __name__ == "__main__":
    unittest.main()
