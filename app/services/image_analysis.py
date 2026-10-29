from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


def _load_preview_image(path: Path):
    if path.suffix.lower() != ".pdf":
        return Image.open(path)

    import pymupdf

    document = pymupdf.open(str(path))
    if not len(document):
        document.close()
        raise ValueError("PDF sem paginas")
    pixmap = document.load_page(0).get_pixmap(
        matrix=pymupdf.Matrix(1.5, 1.5), alpha=False
    )
    document.close()
    return Image.open(BytesIO(pixmap.tobytes("png")))


def analyze_visual_quality(file_path: str) -> dict:
    path = Path(file_path)
    result = {
        "file_size_kb": round(path.stat().st_size / 1024, 2),
        "format": path.suffix.replace(".", "").upper(),
        "width": None,
        "height": None,
        "contrast": None,
        "sharpness": None,
        "signature": {},
        "flags": [],
    }

    try:
        image = _load_preview_image(path)
        gray = image.convert("L")
        width, height = image.size
        contrast = ImageStat.Stat(gray).stddev[0]
        brightness = ImageStat.Stat(gray).mean[0]
        sharpness = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).stddev[0]

        result.update(
            {
                "width": width,
                "height": height,
                "contrast": round(contrast, 2),
                "sharpness": round(sharpness, 2),
                "signature": {
                    "aspect_ratio": round(width / height, 4) if height else 0,
                    "brightness": round(brightness, 2),
                    "contrast": round(contrast, 2),
                    "sharpness": round(sharpness, 2),
                },
            }
        )

        if min(width, height) < 700:
            result["flags"].append("Resolucao baixa para leitura confiavel.")
        if contrast < 25:
            result["flags"].append("Contraste baixo pode prejudicar OCR.")
        if sharpness < 8:
            result["flags"].append("Imagem possivelmente desfocada.")
    except Exception as exc:
        result["flags"].append(f"Nao foi possivel analisar a aparencia do documento: {exc}")

    return result
