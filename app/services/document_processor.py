import re
from pathlib import Path
import unicodedata

from ..models import OfficialRecord
from .image_analysis import analyze_visual_quality
from .ocr import extract_text
from .reference_comparison import compare_with_reference, normalize_template_text
from .risk_engine import calculate_risk, values_match


FIELD_PATTERNS = {
    "holder_name": [
        r"(?:nome(?:\s+completo)?(?:\s+(?:do|da)\s+(?:titular|aluno|formando|benefici[aá]rio))?|titular|aluno|formando|benefici[aá]rio)\s*[:\-]\s*([^\n\r]+)",
        r"(?:certifica(?:-se)?\s+que|conferido\s+a|emitido\s+em\s+nome\s+de)\s*[:\-]?\s*([A-Z][A-Za-zÀ-ÿ'’\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ'’\-]+){1,3})(?=\s*(?:[,;.]|\b(?:filho|filha|nascido|nascida|concluiu|frequentou|portador|portadora)\b|$))",
        r"\bque\s+([A-Z][A-Za-zÀ-ÿ'’\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ'’\-]+){1,3})(?=\s*,?\s+(?:filho|filha|nascido|nascida|concluiu|frequentou|portador|portadora)\b)",
        r"\bque\s+([^\n,.;]+(?:\n[^\n,.;]+)?)\s*,?\s*(?=(?:natural\s+de|filho|filha|nascido|nascida|portador|portadora)\b)",
    ],
    "document_number": [
        r"\b(?:n[uú]mero|n(?:\.\s*)?[º°o]?|c[oó]digo|registo|registro)\s*(?:(?:do|de)\s+)?(?:documento|certificado|diploma|registo|registro)?\s*[:#\-]\s*([A-Z0-9][A-Z0-9\-/.]+)",
        r"(?:documento|certificado|diploma)\s*(?:n(?:\.\s*)?[º°o]?\s*)?[:#\-]\s*([A-Z0-9][A-Z0-9\-/.]+)",
        r"\b(?:n[uú�]mero|ni[ií]?mero|num(?:ero)?)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/.]{2,})",
        r"\b((?:CERT|DECL|DIP)[\-_]?\d{4}[\-_]?\d{3,8})\b",
    ],
    "process_number": [
        r"\bprocesso\s*(?:n[uú�]mero|ni[ií]?mero|n\s*[º°o�.]?)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/.]{1,})",
    ],
    "holder_id_number": [
        r"\b(?:bilhete\s+de\s+identidade|b\.?\s*i\.?)\s*(?:n[uú�]mero|ni[ií]?mero|n\s*[º°o�.]?)?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/.]{5,})",
        r"\b(?:passaporte|documento\s+de\s+identifica[cç][aã]o)\s*(?:n[uú�]mero|n\s*[º°o�.]?)?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/.]{5,})",
    ],
    "course": [
        r"(?:curso|programa|formacao|forma[cç][aã]o)\s*(?:de|em)?\s*[:\-]\s*([^\n\r]+)",
        r"(?:licenciatura|bacharelato|t[eé]cnico)\s+(?:em|de)\s+([^\n,.;]+(?:\s*\n\s*[^\n,.;]+)?)",
        r"\bop(?:ç|c|e)(?:ã|a)?o\s+(?:de|em)\s+([^\n,.;]+)",
    ],
    "institution": [
        r"(?:institui[cç][aã]o(?:\s+(?:de\s+ensino|emissora))?|universidade|escola|entidade\s+emissora)\s*[:\-]\s*([^\n\r]+)",
        r"(?:director|reitor|respons[aá]vel)\s+(?:do|da)\s+((?:liceu|universidade|instituto|escola)\s+[^,\n]+)",
        r"\b((?:universidade|instituto|escola)\s+[A-Z][A-Za-zÀ-ÿ ]{1,60})\b",
    ],
}

DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}"
    r"|\d{1,2}\s+de\s+[A-Za-zÀ-ÿ�]+\s+de\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)

FIELD_LABELS = {
    "holder_name": "Nome",
    "document_number": "Numero",
    "process_number": "Numero de processo",
    "holder_id_number": "Numero de identificacao",
    "course": "Curso",
    "institution": "Instituicao",
    "issue_date": "Data",
}


def clean_value(value):
    value = (value or "").replace("\ufffd", "")
    return re.sub(r"\s+", " ", value).strip(" .:-\t")


def extract_issue_date(text):
    normalized_text = unicodedata.normalize("NFKD", text or "")
    normalized_text = normalized_text.encode("ascii", "ignore").decode("ascii").lower()
    notarial_markers = (
        "ministerio da justica",
        "cartorio notarial",
        "fotocopia que achei",
        "conferi a presente fotocopia",
    )
    notarial_start = min(
        (position for marker in notarial_markers if (position := normalized_text.find(marker)) >= 0),
        default=len(text or ""),
    )
    document_text = (text or "")[:notarial_start]
    candidates = []
    for match in DATE_PATTERN.finditer(document_text):
        context = document_text[max(0, match.start() - 80) : match.start()]
        normalized_context = unicodedata.normalize("NFKD", context)
        normalized_context = normalized_context.encode("ascii", "ignore").decode("ascii")
        if re.search(r"\bnascid[oa]\b", normalized_context, re.IGNORECASE):
            continue
        candidates.append(clean_value(match.group()))
    return candidates[-1] if candidates else ""


def _date_key(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    normalized = " ".join(normalized.split())

    match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", normalized)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    match = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", normalized)
    if match:
        day, month, year = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    match = re.fullmatch(r"(\d{1,2}) de ([a-z]+) de (\d{4})", normalized)
    if match:
        day, month_name, year = match.groups()
        months = {
            "janeiro": 1,
            "fevereiro": 2,
            "marco": 3,
            "abril": 4,
            "maio": 5,
            "junho": 6,
            "julho": 7,
            "agosto": 8,
            "setembro": 9,
            "outubro": 10,
            "novembro": 11,
            "dezembro": 12,
        }
        month = months.get(month_name)
        if month:
            return f"{int(year):04d}-{month:02d}-{int(day):02d}"
    return ""


def extract_fields(text):
    fields = {}
    for key, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text or "", re.IGNORECASE):
                if key == "document_number":
                    context = (text or "")[max(0, match.start() - 50) : match.start()]
                    if re.search(
                        r"(?:bilhete\s+de\s+identidade|b\.?\s*i\.?)"
                        r"(?:\s+(?:n[uú�]mero|ni[ií]?mero|n\s*[º°o�.]?))?\s*$",
                        context,
                        re.IGNORECASE,
                    ):
                        continue
                fields[key] = clean_value(match.group(1))
                break
            if key in fields:
                break
        fields.setdefault(key, "")
    fields["issue_date"] = extract_issue_date(text)
    return fields


def _compare_fields(fields, expected_fields, source, include_document_number=False):
    comparisons = [
        ("holder_name", "Nome"),
        ("course", "Curso"),
        ("institution", "Instituicao"),
        ("issue_date", "Data"),
    ]
    if include_document_number:
        comparisons.insert(0, ("document_number", "Numero"))

    matches = []
    inconsistencies = []
    for key, label in comparisons:
        extracted = fields.get(key)
        expected = expected_fields.get(key)
        if not extracted or not expected:
            continue
        is_match = (
            _date_key(extracted) == _date_key(expected)
            if key == "issue_date" and _date_key(extracted) and _date_key(expected)
            else values_match(
                extracted,
                expected,
                fuzzy=key not in {"document_number", "issue_date"},
            )
        )
        if is_match:
            matches.append(f"{label} coincide com {source}.")
        else:
            inconsistencies.append(f"{label} extraido nao coincide com {source}.")
    return matches, inconsistencies


def validate_fields(fields, reference=None):
    missing = [
        label
        for key, label in FIELD_LABELS.items()
        if key in {"holder_name", "document_number", "institution", "issue_date"}
        and not fields.get(key)
    ]
    validation = {
        "record_found": False,
        "official_status": None,
        "matches": [],
        "inconsistencies": [],
        "missing_fields": missing,
        "official_record": None,
    }

    document_number = (fields.get("document_number") or "").upper()
    record = (
        OfficialRecord.query.filter_by(document_number=document_number).first()
        if document_number
        else None
    )
    if record:
        validation["record_found"] = True
        validation["official_status"] = record.status
        official_fields = {
            "document_number": record.document_number,
            "holder_name": record.holder_name,
            "course": record.course,
            "institution": record.institution.name,
            "issue_date": record.issue_date,
        }
        validation["official_record"] = {
            **official_fields,
            "status": record.status,
        }
        matches, inconsistencies = _compare_fields(
            fields,
            official_fields,
            "o registro oficial",
            include_document_number=True,
        )
        validation["matches"].extend(matches)
        validation["inconsistencies"].extend(inconsistencies)
        if record.status != "Valido":
            validation["inconsistencies"].append(
                "Registro oficial nao esta marcado como valido."
            )
    elif document_number:
        validation["inconsistencies"].append(
            "Registro oficial inexistente para o numero extraido."
        )
    else:
        validation["inconsistencies"].append(
            "Numero do documento nao identificado; verificacao oficial por numero indisponivel."
        )

    if reference:
        reference_fields = reference.extracted_fields or {}
        matches, inconsistencies = _compare_fields(
            fields, reference_fields, "o modelo original"
        )
        validation["matches"].extend(matches)
        validation["inconsistencies"].extend(inconsistencies)

    return validation


def build_reference_profile(file_path):
    ocr_result = extract_text(file_path)
    fields = extract_fields(ocr_result.text)
    visual = analyze_visual_quality(file_path)
    return {
        "ocr": {
            "text": ocr_result.text,
            "confidence": round(ocr_result.confidence or 0, 2),
            "engine": ocr_result.engine,
            "warnings": ocr_result.warnings,
        },
        "fields": fields,
        "visual": visual,
        "normalized_text": normalize_template_text(ocr_result.text, fields),
    }


def refresh_reference_profile(reference, upload_folder):
    reference_path = Path(upload_folder) / reference.stored_filename
    if not reference_path.is_file():
        raise FileNotFoundError(
            f"O ficheiro do modelo original '{reference.original_filename}' nao foi encontrado."
        )

    profile = build_reference_profile(str(reference_path))
    reference.normalized_text = profile["normalized_text"]
    reference.extracted_fields = profile["fields"]
    reference.visual_signature = profile["visual"].get("signature", {})
    return profile


def process_document(file_path, reference=None):
    profile = build_reference_profile(file_path)
    validation = validate_fields(profile["fields"], reference=reference)
    reference_comparison = compare_with_reference(
        profile["ocr"]["text"], profile["fields"], profile["visual"], reference
    )
    validation["reference_comparison"] = reference_comparison
    risk = calculate_risk(
        profile["fields"], validation, profile["visual"], _OCRAdapter(profile["ocr"]), reference_comparison
    )

    return {
        "ocr": profile["ocr"],
        "fields": profile["fields"],
        "validation": validation,
        "visual": profile["visual"],
        "reference": reference_comparison,
        "risk": risk,
    }


class _OCRAdapter:
    def __init__(self, data):
        self.text = data["text"]
        self.confidence = data["confidence"]
