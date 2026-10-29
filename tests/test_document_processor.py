import unittest
from types import SimpleNamespace

from app.services.document_processor import (
    extract_fields,
    extract_issue_date,
    validate_fields,
)
from app.services.reference_comparison import compare_with_reference
from app.services.risk_engine import values_match


class DocumentProcessorTest(unittest.TestCase):
    def test_extracts_fields_from_common_portuguese_label_variants(self):
        text = (
            "Nome completo do aluno: Joao Antonio\n"
            "N.º do certificado: CERT-2025-00152\n"
            "Curso: Engenharia Informatica\n"
            "Instituicao de ensino: Universidade X\n"
        )

        fields = extract_fields(text)

        self.assertEqual(fields["holder_name"], "Joao Antonio")
        self.assertEqual(fields["document_number"], "CERT-2025-00152")
        self.assertEqual(fields["course"], "Engenharia Informatica")
        self.assertEqual(fields["institution"], "Universidade X")

    def test_extracts_name_from_certificate_prose(self):
        fields = extract_fields(
            "Certifica-se que Kiala Paulo, filho de Manuel e Maria, "
            "concluiu o curso na Universidade X."
        )

        self.assertEqual(fields["holder_name"], "Kiala Paulo")

    def test_extracts_name_course_and_identity_number_from_scanned_certificate_ocr(self):
        text = (
            "A UNIVERSIDADE KIMPA VITA, certifica em face do arquivo respectivo, "
            "que Ant\ufffdnio Kiangebeni\nPedro Makanguilu, natural de Damba, "
            "portador do Bilhete de Identidade niimero 007317014UE046, "
            "concluiu a Licenciatura em Engenharia\nInformatica, tendo obtido notas."
        )

        fields = extract_fields(text)

        self.assertIn("Kiangebeni Pedro Makanguilu", fields["holder_name"])
        self.assertEqual(fields["holder_id_number"], "007317014UE046")
        self.assertEqual(fields["course"], "Engenharia Informatica")
        self.assertEqual(fields["institution"], "UNIVERSIDADE KIMPA VITA")
        self.assertEqual(fields["document_number"], "")

    def test_extracts_process_and_course_from_secondary_school_certificate(self):
        fields = extract_fields(
            "Director do Liceu da Damba, Uige Certifica que: Kiala Paulo, "
            "portador do B.I. n\ufffd 009524422UE047, sob processo n\ufffd 2750, "
            "na opeao de Ciencias Humanas."
        )

        self.assertEqual(fields["institution"], "Liceu da Damba")
        self.assertEqual(fields["process_number"], "2750")
        self.assertEqual(fields["holder_id_number"], "009524422UE047")
        self.assertEqual(fields["course"], "Ciencias Humanas")
        self.assertEqual(fields["document_number"], "")

    def test_issue_date_is_not_the_birth_date(self):
        text = (
            "nascido aos 25 de Junho de 2001, natural de Damba. "
            "O certificado foi emitido pela Universidade aos 03 de Fevereiro de 2026."
        )

        self.assertEqual(extract_issue_date(text), "03 de Fevereiro de 2026")

    def test_birth_date_is_not_used_when_no_issue_date_is_present(self):
        self.assertEqual(
            extract_issue_date("O titular, nascido aos 25 de Junho de 2001, natural de Damba."),
            "",
        )

    def test_notarial_copy_date_does_not_replace_certificate_issue_date(self):
        text = (
            "Certificado emitido aos 08 de Janeiro de 2018. "
            "Conferi a presente fotocopia em 2026-07-07."
        )

        self.assertEqual(extract_issue_date(text), "08 de Janeiro de 2018")

    def test_reference_fields_are_compared_even_without_official_number(self):
        fields = {
            "holder_name": "Antnio Kiangebeni Pedro Makanguilu",
            "document_number": "",
            "course": "Engenharia Informatica",
            "institution": "Universidade Kimpa Vita",
            "issue_date": "15/07/2025",
        }
        reference = SimpleNamespace(
            extracted_fields={
                "holder_name": "António Kiangebeni Pedro Makanguilu",
                "course": "Engenharia Informatica",
                "institution": "Universidade Kimpa Vita",
                "issue_date": "15/07/2024",
            }
        )

        validation = validate_fields(fields, reference=reference)

        self.assertFalse(validation["record_found"])
        self.assertTrue(any("Nome coincide com o modelo original" in item for item in validation["matches"]))
        self.assertTrue(any("Curso coincide com o modelo original" in item for item in validation["matches"]))
        self.assertTrue(any("Instituicao coincide com o modelo original" in item for item in validation["matches"]))
        self.assertTrue(
            any("Data extraido nao coincide com o modelo original" in item
                for item in validation["inconsistencies"])
        )

    def test_values_match_handles_accents_without_partial_word_false_positives(self):
        self.assertTrue(values_match("Antnio Kiangebeni", "António Kiangebeni"))
        self.assertFalse(values_match("Ana", "Banana"))

    def test_missing_reference_data_is_reported_as_not_calculated(self):
        reference = SimpleNamespace(
            id=1,
            label="Modelo sem OCR",
            institution=SimpleNamespace(name="Universidade X"),
            document_type=SimpleNamespace(name="Certificado"),
            normalized_text="",
            visual_signature={},
        )

        comparison = compare_with_reference("texto do documento", {}, {}, reference)

        self.assertIsNone(comparison["text_similarity"])
        self.assertIsNone(comparison["visual_similarity"])
        self.assertIsNone(comparison["structure_match"])
        self.assertEqual(len(comparison["differences"]), 2)

    def test_computes_text_visual_and_structure_when_data_is_available(self):
        signature = {
            "aspect_ratio": 1.4,
            "brightness": 200,
            "contrast": 55,
            "sharpness": 30,
        }
        reference = SimpleNamespace(
            id=1,
            label="Modelo",
            institution=SimpleNamespace(name="Universidade X"),
            document_type=SimpleNamespace(name="Certificado"),
            normalized_text="certificado emitido universidade x curso engenharia informatica",
            visual_signature=signature,
        )

        comparison = compare_with_reference(
            "certificado emitido universidade x curso engenharia informatica",
            {},
            {"signature": signature},
            reference,
        )

        self.assertIsNotNone(comparison["text_similarity"])
        self.assertEqual(comparison["visual_similarity"], 100.0)
        self.assertTrue(comparison["structure_match"])


if __name__ == "__main__":
    unittest.main()
