from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import os
import shutil

from PIL import Image, ImageFilter, ImageOps


TESSERACT_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


@dataclass
class OCRResult:
    text: str
    confidence: float
    engine: str
    warnings: list[str] = field(default_factory=list)


def preprocess_image(image: Image.Image) -> Image.Image:
    """Improve contrast and size before OCR without changing the original file."""
    grayscale = ImageOps.autocontrast(image.convert("L"))
    if max(grayscale.size) < 1800:
        grayscale = grayscale.resize(
            (grayscale.width * 2, grayscale.height * 2), Image.Resampling.LANCZOS
        )
    return grayscale.filter(ImageFilter.MedianFilter(size=3))


def _configure_tesseract():
    try:
        import pytesseract
    except ImportError:
        return None, "Biblioteca pytesseract nao instalada."

    configured_path = os.environ.get("TESSERACT_CMD", "").strip().strip("\"'")
    candidates = [configured_path, shutil.which("tesseract"), *TESSERACT_WINDOWS_PATHS]
    executable = next((path for path in candidates if path and Path(path).is_file()), None)
    if not executable:
        return None, "Tesseract nao foi encontrado. Defina TESSERACT_CMD ou instale-o."

    pytesseract.pytesseract.tesseract_cmd = executable
    return pytesseract, None


def extract_text(file_path: str, max_pdf_pages: int = 3) -> OCRResult:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_pdf_text(path, max_pdf_pages)
    if suffix in {".png", ".jpg", ".jpeg"}:
        return extract_image_text(path)
    return OCRResult("", 0.0, "unsupported", ["Formato nao suportado pelo OCR."])


def extract_pdf_text(path: Path, max_pages: int) -> OCRResult:
    warnings = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        embedded_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if len(embedded_text) >= 40:
            return OCRResult(embedded_text, 90.0, "pypdf-text-layer")
        if embedded_text:
            warnings.append("A camada de texto do PDF e curta; foi aplicado OCR por imagem.")
    except Exception as exc:
        warnings.append(f"Nao foi possivel ler a camada de texto do PDF: {exc}")
        embedded_text = ""

    try:
        import pymupdf
    except ImportError:
        return OCRResult(
            embedded_text,
            0.0,
            "pdf-no-renderer",
            warnings + ["PyMuPDF nao esta instalado para converter o PDF em imagem."],
        )

    try:
        document = pymupdf.open(str(path))
        total_pages = len(document)
        pages_to_process = min(len(document), max_pages)
        page_results = []
        confidences = []
        for page_index in range(pages_to_process):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            image = Image.open(BytesIO(pixmap.tobytes("png")))
            page_ocr = _ocr_image(image)
            page_results.append(page_ocr.text)
            if page_ocr.confidence:
                confidences.append(page_ocr.confidence)
            warnings.extend(page_ocr.warnings)
        document.close()

        text = "\n".join(item for item in page_results if item).strip() or embedded_text
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        if total_pages > max_pages:
            warnings.append(f"OCR limitado as primeiras {max_pages} paginas do PDF.")
        if not text:
            warnings.append("OCR nao conseguiu extrair texto do PDF digitalizado.")
        return OCRResult(text, confidence, "pymupdf+tesseract", list(dict.fromkeys(warnings)))
    except Exception as exc:
        return OCRResult(embedded_text, 0.0, "pdf-ocr-error", warnings + [f"Falha no OCR do PDF: {exc}"])


def extract_image_text(path: Path) -> OCRResult:
    try:
        image = Image.open(path)
        return _ocr_image(image)
    except Exception as exc:
        return OCRResult("", 0.0, "image-error", [f"Falha ao abrir imagem: {exc}"])


def _ocr_image(image: Image.Image) -> OCRResult:
    pytesseract, configuration_error = _configure_tesseract()
    if configuration_error:
        return OCRResult("", 0.0, "tesseract-unavailable", [configuration_error])

    try:
        from pytesseract import Output

        processed = preprocess_image(image)
        options = "--oem 3 --psm 6"
        try:
            text = pytesseract.image_to_string(processed, lang="por+eng", config=options).strip()
            data = pytesseract.image_to_data(
                processed, lang="por+eng", config=options, output_type=Output.DICT
            )
        except Exception:
            text = pytesseract.image_to_string(processed, lang="eng", config=options).strip()
            data = pytesseract.image_to_data(
                processed, lang="eng", config=options, output_type=Output.DICT
            )

        confidence_values = []
        for raw_value in data.get("conf", []):
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if value >= 0:
                confidence_values.append(value)

        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        warnings = [] if text else ["OCR nao conseguiu extrair texto da imagem."]
        return OCRResult(text, confidence, "tesseract", warnings)
    except Exception as exc:
        return OCRResult("", 0.0, "tesseract-error", [f"Falha no OCR: {exc}"])
