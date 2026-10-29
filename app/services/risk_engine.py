import re
import unicodedata
from difflib import SequenceMatcher


def normalize(value):
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value).replace("\ufffd", ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())


def values_match(extracted, official, fuzzy=True):
    left = normalize(extracted)
    right = normalize(official)
    if not left or not right:
        return False
    if left == right:
        return True
    if not fuzzy:
        return False
    if min(len(left), len(right)) >= 4 and (
        re.search(rf"\b{re.escape(left)}\b", right)
        or re.search(rf"\b{re.escape(right)}\b", left)
    ):
        return True
    return min(len(left), len(right)) >= 8 and SequenceMatcher(None, left, right).ratio() >= 0.88


def calculate_risk(fields, validation, visual, ocr_result, reference_comparison=None):
    score = 0
    reasons = []
    recommendations = []

    missing_fields = validation.get("missing_fields", [])
    inconsistencies = validation.get("inconsistencies", [])

    if not (ocr_result.text or "").strip():
        score += 35
        reasons.append("OCR nao extraiu texto suficiente do documento.")
        recommendations.append("Solicitar nova digitalizacao ou verificacao manual.")
    elif len(ocr_result.text.strip()) < 80:
        score += 20
        reasons.append("Texto extraido e curto para uma verificacao confiavel.")

    if ocr_result.confidence and ocr_result.confidence < 55:
        score += 15
        reasons.append("Confianca media do OCR abaixo do ideal.")
    elif ocr_result.confidence == 0:
        score += 10
        reasons.append("Nao foi possivel calcular confianca do OCR.")

    if missing_fields:
        score += min(25, len(missing_fields) * 6)
        reasons.append("Campos obrigatorios ausentes: " + ", ".join(missing_fields))

    if not validation.get("record_found"):
        score += 30
        reasons.append("Numero do documento nao encontrado nos registros oficiais.")

    if inconsistencies:
        score += min(35, len(inconsistencies) * 12)
        reasons.extend(inconsistencies)

    visual_flags = visual.get("flags", [])
    if visual_flags:
        score += min(20, len(visual_flags) * 7)
        reasons.extend(visual_flags)

    if reference_comparison:
        text_similarity = reference_comparison.get("text_similarity")
        visual_similarity = reference_comparison.get("visual_similarity")
        reference_label = reference_comparison.get("reference_label", "modelo original")

        if text_similarity is not None and text_similarity < 45:
            score += 20
            reasons.append(
                f"Estrutura textual pouco semelhante ao modelo original '{reference_label}'."
            )
        elif text_similarity is not None and text_similarity < 70:
            score += 8
            reasons.append(
                f"Estrutura textual parcialmente semelhante ao modelo original '{reference_label}'."
            )

        if visual_similarity is not None and visual_similarity < 45:
            score += 15
            reasons.append(
                f"Caracteristicas visuais diferem do modelo original '{reference_label}'."
            )

    if validation.get("official_status") and validation["official_status"] != "Valido":
        score += 25
        reasons.append(f"Registro oficial com estado: {validation['official_status']}.")

    score = max(0, min(100, score))

    if not (ocr_result.text or "").strip():
        level = "Verificacao manual necessaria"
    elif score <= 30:
        level = "Baixo risco"
    elif score <= 60:
        level = "Medio risco"
    else:
        level = "Alto risco"

    if not recommendations:
        if level == "Baixo risco":
            recommendations.append("Documento aparentemente consistente com os dados disponiveis.")
        elif level == "Medio risco":
            recommendations.append("Rever inconsistencias antes de aceitar o documento.")
        else:
            recommendations.append("Encaminhar para verificacao manual e confirmar na fonte oficial.")

    if not reasons:
        reasons.append("Dados extraidos coincidem com os registros oficiais analisados.")

    return {
        "risk_score": score,
        "risk_level": level,
        "ai_decision": "Motor explicavel de risco v1",
        "reasons": reasons,
        "recommendations": recommendations,
    }
