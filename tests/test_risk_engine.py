import unittest

from app.services.risk_engine import calculate_risk


class OCRStub:
    text = "Certificado academico com conteudo suficiente para validacao inicial."
    confidence = 90


class RiskEngineTest(unittest.TestCase):
    def test_low_risk_when_record_matches(self):
        result = calculate_risk(
            fields={"document_number": "CERT-2025-00152"},
            validation={
                "record_found": True,
                "official_status": "Valido",
                "matches": ["Numero coincide."],
                "inconsistencies": [],
                "missing_fields": [],
            },
            visual={"flags": []},
            ocr_result=OCRStub(),
        )

        self.assertEqual(result["risk_level"], "Baixo risco")
        self.assertLessEqual(result["risk_score"], 30)

    def test_high_risk_when_record_is_missing_and_fields_are_absent(self):
        result = calculate_risk(
            fields={},
            validation={
                "record_found": False,
                "official_status": None,
                "matches": [],
                "inconsistencies": ["Registro oficial inexistente."],
                "missing_fields": ["Nome", "Numero", "Instituicao", "Data"],
            },
            visual={"flags": ["Contraste baixo pode prejudicar OCR."]},
            ocr_result=OCRStub(),
        )

        self.assertIn(result["risk_level"], {"Medio risco", "Alto risco"})
        self.assertGreaterEqual(result["risk_score"], 55)


if __name__ == "__main__":
    unittest.main()

