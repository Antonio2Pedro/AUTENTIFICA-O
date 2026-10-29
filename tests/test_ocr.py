import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image

from app.services import ocr


class OCRTest(unittest.TestCase):
    def test_configure_tesseract_finds_windows_install_path(self):
        executable = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        with (
            patch.dict(os.environ, {"TESSERACT_CMD": ""}),
            patch("app.services.ocr.shutil.which", return_value=None),
            patch(
                "app.services.ocr.Path.is_file",
                autospec=True,
                side_effect=lambda path: str(path) == executable,
            ),
            patch("pytesseract.pytesseract.tesseract_cmd", "tesseract"),
        ):
            pytesseract, error = ocr._configure_tesseract()
            detected_path = pytesseract.pytesseract.tesseract_cmd

        self.assertIsNotNone(pytesseract)
        self.assertIsNone(error)
        self.assertEqual(detected_path, executable)

    def test_configure_tesseract_accepts_quoted_environment_path(self):
        executable = r"C:\Custom Tesseract\tesseract.exe"

        with (
            patch.dict(os.environ, {"TESSERACT_CMD": f'"{executable}"'}),
            patch("app.services.ocr.shutil.which", return_value=None),
            patch(
                "app.services.ocr.Path.is_file",
                autospec=True,
                side_effect=lambda path: str(path) == executable,
            ),
            patch("pytesseract.pytesseract.tesseract_cmd", "tesseract"),
        ):
            pytesseract, error = ocr._configure_tesseract()
            detected_path = pytesseract.pytesseract.tesseract_cmd

        self.assertIsNotNone(pytesseract)
        self.assertIsNone(error)
        self.assertEqual(detected_path, executable)

    def test_extracts_text_from_scanned_pdf_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scanned.pdf"
            image = Image.new("RGB", (200, 100), "white")
            image_bytes = BytesIO()
            image.save(image_bytes, format="PNG")

            document = pymupdf.open()
            page = document.new_page()
            page.insert_image(page.rect, stream=image_bytes.getvalue())
            document.save(path)
            document.close()

            expected = ocr.OCRResult("Texto reconhecido", 92.0, "tesseract")
            with patch("app.services.ocr._ocr_image", return_value=expected):
                result = ocr.extract_pdf_text(path, max_pages=3)

        self.assertEqual(result.text, "Texto reconhecido")
        self.assertEqual(result.engine, "pymupdf+tesseract")
