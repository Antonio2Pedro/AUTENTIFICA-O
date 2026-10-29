import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import Document, DocumentType, User, Verification, VerificationResult


class TestConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = ""
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    OCR_MAX_PAGES = 3


class ReanalyzeRouteTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        TestConfig.UPLOAD_FOLDER = self.temp_dir.name
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            user = User.query.filter_by(email="admin@example.com").first()
            document_type = DocumentType.query.filter_by(name="Certificado").first()
            document = Document(
                original_filename="documento.pdf",
                stored_filename="documento.pdf",
                file_size=4,
                uploaded_by=user,
                document_type=document_type,
            )
            db.session.add(document)
            db.session.flush()
            verification = Verification(
                document=document,
                user=user,
                ocr_text="texto antigo",
                extracted_fields={"holder_name": ""},
                validation_summary={},
                visual_summary={},
            )
            db.session.add(verification)
            db.session.flush()
            db.session.add(
                VerificationResult(
                    verification=verification,
                    risk_score=70,
                    risk_level="Alto risco",
                    ai_decision="versao anterior",
                    reasons=[],
                    recommendations=[],
                )
            )
            db.session.commit()
            self.verification_id = verification.id
            self.document_path = Path(self.temp_dir.name) / document.stored_filename
            self.document_path.write_bytes(b"%PDF")
            self.user_id = user.id

        with self.client.session_transaction() as browser_session:
            browser_session["_user_id"] = str(self.user_id)
            browser_session["_fresh"] = True

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reanalyze_updates_saved_extraction_and_risk(self):
        analysis = {
            "ocr": {"text": "texto atualizado", "warnings": []},
            "fields": {"holder_name": "Joao Antonio", "document_number": "CERT-2025-00152"},
            "validation": {"matches": ["Nome coincide."], "inconsistencies": []},
            "visual": {"signature": {}},
            "risk": {
                "risk_score": 10,
                "risk_level": "Baixo risco",
                "ai_decision": "motor atualizado",
                "reasons": [],
                "recommendations": ["Aceitavel"],
            },
        }

        with patch("app.routes.documents.process_document", return_value=analysis):
            response = self.client.post(
                f"/documents/{self.verification_id}/reanalyze", follow_redirects=True
            )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            verification = db.session.get(Verification, self.verification_id)
            self.assertEqual(verification.ocr_text, "texto atualizado")
            self.assertEqual(verification.extracted_fields["holder_name"], "Joao Antonio")
            self.assertEqual(verification.result.risk_score, 10)
            self.assertEqual(verification.result.ai_decision, "motor atualizado")


if __name__ == "__main__":
    unittest.main()
