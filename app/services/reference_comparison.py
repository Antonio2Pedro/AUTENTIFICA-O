import re
import unicodedata
from difflib import SequenceMatcher


def normalize_template_text(text, fields=None):
    value = (text or "").lower()
    for field_value in (fields or {}).values():
        cleaned = (field_value or "").strip().lower()
        if len(cleaned) >= 3:
            value = value.replace(cleaned, " <campo> ")

    value = re.sub(r"\b(?:cert|decl|dip)[\w.-]*\b", " <numero> ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " <data> ", value)
    value = re.sub(r"\b\d{4,}\b", " <numero> ", value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9<>]+", " ", value)
    return " ".join(value.split())


def _text_similarity(candidate_text, reference_text):
    if not candidate_text or not reference_text:
        return None
    candidate_tokens = set(candidate_text.split())
    reference_tokens = set(reference_text.split())
    union = candidate_tokens | reference_tokens
    token_score = len(candidate_tokens & reference_tokens) / len(union) if union else 0
    sequence_score = SequenceMatcher(None, candidate_text, reference_text).ratio()
    return round((token_score * 0.65 + sequence_score * 0.35) * 100, 1)


def _visual_similarity(candidate_signature, reference_signature):
    if not candidate_signature or not reference_signature:
        return None

    weights = {"aspect_ratio": 0.55, "brightness": 0.2, "contrast": 0.15, "sharpness": 0.1}
    limits = {"aspect_ratio": 0.7, "brightness": 120, "contrast": 70, "sharpness": 80}
    score = 0
    available_weight = 0
    for key, weight in weights.items():
        candidate = candidate_signature.get(key)
        reference = reference_signature.get(key)
        if candidate is None or reference is None:
            continue
        difference = abs(float(candidate) - float(reference))
        score += max(0, 1 - difference / limits[key]) * weight
        available_weight += weight
    return round(score / available_weight * 100, 1) if available_weight else None


def compare_with_reference(candidate_text, candidate_fields, candidate_visual, reference):
    if not reference:
        return None

    normalized_candidate = normalize_template_text(candidate_text, candidate_fields)
    text_score = _text_similarity(normalized_candidate, reference.normalized_text or "")
    visual_score = _visual_similarity(
        (candidate_visual or {}).get("signature", {}), reference.visual_signature or {}
    )

    differences = []
    if text_score is None:
        differences.append(
            "Semelhanca textual nao calculada: o documento ou o modelo original nao tem texto suficiente."
        )
    elif text_score < 45:
        differences.append("Estrutura textual pouco semelhante ao documento original de referencia.")
    elif text_score < 70:
        differences.append("Estrutura textual parcialmente semelhante ao modelo original.")

    if visual_score is None:
        differences.append(
            "Semelhanca visual nao calculada: faltam caracteristicas visuais no documento ou no modelo original."
        )
    elif visual_score < 45:
        differences.append("Caracteristicas visuais diferem de forma relevante do modelo original.")

    structure_match = (
        None
        if text_score is None or visual_score is None
        else text_score >= 45 and visual_score >= 45
    )
    return {
        "reference_id": reference.id,
        "reference_label": reference.label,
        "institution": reference.institution.name,
        "document_type": reference.document_type.name,
        "text_similarity": text_score,
        "visual_similarity": visual_score,
        "structure_match": structure_match,
        "differences": differences,
    }
