import unittest

from helpers.practice_engine import worksheet_to_exercises
from helpers.structured_text import build_text_asset, text_asset_to_markdown
from helpers.worksheet_builder import normalize_worksheet_output
from helpers.quick_exam_builder import normalize_exam_output


class StructuredResourceTextTests(unittest.TestCase):
    def test_inline_dialogue_is_inferred_from_flattened_reading_passage(self):
        text = (
            "María se encuentra con la Sra. López en la oficina. "
            "— Sra. López: Buenos días, María. Gracias por venir. "
            "¿Podría contarme un poco sobre su experiencia? "
            "María: Sí, claro. Tengo tres años trabajando en marketing digital. "
            "— Sra. López: Excelente. ¿Ha liderado campañas?"
        )

        asset = build_text_asset(text)

        self.assertEqual("dialogue", asset["text_kind"])
        self.assertTrue(any(block["type"] == "paragraph" for block in asset["blocks"]))
        self.assertGreaterEqual(len([block for block in asset["blocks"] if block["type"] == "turn"]), 2)

    def test_flattened_spanish_email_is_inferred_as_structured_email(self):
        text = (
            "De: Laura Martínez Para: equipo@empresa.com Asunto: Solicitud de reunión "
            "Estimados colegas, Les escribo para confirmar la reunión del jueves. "
            "Atentamente, Laura Martínez"
        )

        asset = build_text_asset(text)

        self.assertEqual("email", asset["text_kind"])
        self.assertEqual(["from", "to", "subject"], [block["type"] for block in asset["blocks"][:3]])
        self.assertTrue(any(block["type"] == "greeting" for block in asset["blocks"]))
        self.assertTrue(any(block["type"] == "signoff" for block in asset["blocks"]))

    def test_worksheet_normalization_preserves_multiline_source_text(self):
        raw = {
            "title": "Correo formal",
            "subject": "Spanish",
            "topic": "Comunicación profesional",
            "learner_stage": "adult_stage",
            "level_or_band": "B2",
            "worksheet_type": "true_false",
            "plan_language": "ES",
            "student_material_language": "ES",
            "instructions": "Lee el correo y decide si las afirmaciones son verdaderas o falsas.",
            "source_text": "De: Laura\nPara: Equipo\nAsunto: Reunión\n\nEstimados colegas,\nNos vemos el jueves.\n\nAtentamente,\nLaura",
            "true_false_statements": ["La reunión será el jueves."],
            "answer_key": "1. Verdadero",
        }

        ws = normalize_worksheet_output(raw, include_visuals=False)

        self.assertIn("\n", ws["source_text"])
        self.assertEqual("email", ws["text_kind"])
        self.assertGreaterEqual(len(ws["text_blocks"]), 5)

    def test_title_line_is_kept_separate_from_passage_body(self):
        asset = build_text_asset(
            "La entrevista profesional\nMaría llegó temprano a la oficina y saludó al entrevistador."
        )

        rendered = text_asset_to_markdown(asset["raw_text"])
        self.assertEqual("La entrevista profesional", asset["title"])
        self.assertIn("#### La entrevista profesional", rendered)
        self.assertIn("María llegó temprano", rendered)

    def test_practice_schema_carries_structured_text_metadata(self):
        ws = normalize_worksheet_output(
            {
                "title": "Correo formal",
                "subject": "Spanish",
                "topic": "Comunicación profesional",
                "learner_stage": "adult_stage",
                "level_or_band": "B2",
                "worksheet_type": "reading_comprehension",
                "plan_language": "ES",
                "student_material_language": "ES",
                "instructions": "Lee y responde.",
                "reading_passage": "Asunto: Informe semanal\n\nEstimado Carlos,\nAdjunto el informe.\n\nSaludos,\nAna",
                "questions": ["¿Qué adjunta Ana?"],
                "answer_key": "1. El informe semanal.",
            },
            include_visuals=False,
        )

        practice = worksheet_to_exercises(ws, row_id=10)
        exercise = practice["exercises"][0]

        self.assertEqual("email", exercise["text_kind"])
        self.assertTrue(exercise["text_blocks"])
        self.assertIn("**Asunto/Subject:**", text_asset_to_markdown(exercise["source_text"], blocks=exercise["text_blocks"]))

    def test_exam_normalization_preserves_section_source_formatting(self):
        exam, _answer_key = normalize_exam_output(
            {
                "title": "Comprensión",
                "subject": "Spanish",
                "plan_language": "ES",
                "student_material_language": "ES",
                "sections": [
                    {
                        "type": "reading_comprehension",
                        "title": "Parte 1",
                        "instructions": "Lee el correo.",
                        "source_text": "De: Ana\nPara: Carlos\nAsunto: Viaje\n\nHola Carlos,\nLlegaré mañana.",
                        "questions": [{"text": "¿Quién escribe?"}],
                        "answers": ["Ana"],
                    }
                ],
            }
        )

        section = exam["sections"][0]
        self.assertIn("\n", section["source_text"])
        self.assertEqual("email", section["text_kind"])
        self.assertTrue(section["text_blocks"])

    def test_normalization_rebuilds_text_blocks_from_edited_text(self):
        raw = {
            "title": "Entrevista",
            "subject": "Spanish",
            "topic": "Entrevistas",
            "learner_stage": "adult_stage",
            "level_or_band": "B2",
            "worksheet_type": "reading_comprehension",
            "plan_language": "ES",
            "student_material_language": "ES",
            "instructions": "Lee y responde.",
            "reading_passage": "Ana: Hola.\nLuis: Buenos días.",
            "text_kind": "article",
            "text_blocks": [{"type": "paragraph", "text": "Texto viejo"}],
            "questions": ["¿Quién saluda primero?"],
            "answer_key": "1. Ana.",
        }

        ws = normalize_worksheet_output(raw, include_visuals=False)

        self.assertEqual("dialogue", ws["text_kind"])
        self.assertTrue(all(block.get("text") != "Texto viejo" for block in ws["text_blocks"]))


if __name__ == "__main__":
    unittest.main()
