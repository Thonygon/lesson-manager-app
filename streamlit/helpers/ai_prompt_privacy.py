"""Only approved educational signals may leave Classio for an AI provider."""

from __future__ import annotations

import re
from typing import Any


def _valid_turkish_identity_number(value: str) -> bool:
    if not re.fullmatch(r"[1-9]\d{10}", value):
        return False
    digits = [int(char) for char in value]
    odd = sum(digits[index] for index in (0, 2, 4, 6, 8))
    even = sum(digits[index] for index in (1, 3, 5, 7))
    return digits[9] == (odd * 7 - even) % 10 and digits[10] == sum(digits[:10]) % 10


def _redact_labeled_identity(match: re.Match[str]) -> str:
    delimiter, token = match.group(1, 2)
    return "[identity number removed]" if delimiter in (":", "#") or any(char.isdigit() for char in token) else match.group(0)


def _safe_pedagogical_text(value: Any, known_name_tokens: set[str]) -> str:
    if not isinstance(value, str) or any(char in value for char in "\r\n\t"):
        return ""
    text = " ".join(value.strip().split())
    if not text or len(text) > 80 or len(text.split()) > 12:
        return ""
    if not all(char.isalnum() or char.isspace() or char in "-_()/&+,.:'%" for char in text):
        return ""
    if re.search(r"\b(?:https?|www|phone|telephone|mobile|whatsapp|address|email)\b|\d{3,}", text, re.I):
        return ""
    words = {word.casefold() for word in re.findall(r"[^\W\d_]+", text)}
    if words & known_name_tokens:
        return ""
    return text


def redact_direct_identifiers(value: str) -> str:
    """Remove recognizable contact, address and labeled learner identifiers at the provider boundary."""
    text = str(value or "")
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email removed]", text, flags=re.I)
    text = re.sub(r"\b(?:https?://)?(?:www\.)?wa\.me/\+?\d{7,15}\b", "[contact removed]", text, flags=re.I)
    text = re.sub(r"\b(?:phone|tel(?:ephone|éfono|efon)?|mobile|móvil|contacto|whatsapp|gsm)\s*[:#-]?\s*\+?\d[\d\s().-]{6,}\d\b", "[contact removed]", text, flags=re.I)
    text = re.sub(r"(?<!\w)\+\d[\d\s().-]{7,}\d\b", "[contact removed]", text)
    text = re.sub(r"\b(?:address|dirección|domicilio|ikamet adresi|adres)\s*:\s*[^\n.;}]{5,120}", "[address removed]", text, flags=re.I)
    text = re.sub(r"\b(?:calle|avenida|avda\.?|carrera|street|st\.|avenue|ave\.|road|rd\.|sokak|cadde)\s+[^\n.;}]{3,85}\d+[^\n.;}]{0,25}", "[address removed]", text, flags=re.I)
    text = re.sub(r"([\"']?(?:student_name|learner_name|student_full_name|student_email|student_phone|student_address)[\"']?\s*[:=]\s*)[\"']?[^,\"'\n}]+[\"']?", r'\1"[student identifier removed]"', text, flags=re.I)
    text = re.sub(r"\b(?:student name|nombre del alumno|nombre de la alumna|nombre del estudiante|öğrenci adı)\s*:\s*[^\n.;}]{2,100}", "[student name removed]", text, flags=re.I)
    text = re.sub(r"\b(?:tckn|t\.c\.\s*kimlik(?:\s*(?:no|numarası))?|dni|nie|nif|passport|pasaporte|pasaport|ssn|social security number)\s*([:#-]?)\s*([A-Z0-9-]{6,25})\b", _redact_labeled_identity, text, flags=re.I)
    text = re.sub(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b", "[bank account removed]", text, flags=re.I)
    return re.sub(r"(?<!\d)\d{11}(?!\d)", lambda match: "[identity number removed]" if _valid_turkish_identity_number(match.group()) else match.group(), text)


def _safe_pedagogical_list(value: Any, known_name_tokens: set[str], limit: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    items: list[str] = []
    for raw in value[:limit]:
        cleaned = _safe_pedagogical_text(raw, known_name_tokens)
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def minimize_student_profile_for_ai(profile: dict[str, Any] | None) -> dict[str, Any]:
    source = profile or {}
    if not source:
        return {}
    result: dict[str, Any] = {}
    # A stable learner reference is unnecessary for a one-off pedagogical
    # prompt and would let a provider link separate requests over time.
    known_name_tokens = {
        word.casefold()
        for word in re.findall(r"[^\W\d_]{3,}", str(source.get("student_name") or ""))
    }
    for key in ("learner_stage", "level_or_band", "native_language", "subject_focus"):
        value = source.get(key)
        if isinstance(value, str) and value.isascii() and value.replace("_", "").replace("-", "").isalnum() and len(value) <= 40:
            result[key] = value
    for key in ("completed_assignments", "recent_average_score_pct"):
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 10000:
            result[key] = value
    for key, limit in (("weak_topics", 3), ("strong_topics", 2), ("weak_formats", 3), ("active_assignment_topics", 5)):
        items = _safe_pedagogical_list(source.get(key), known_name_tokens, limit)
        if items:
            result[key] = items
    program = source.get("program_context")
    if isinstance(program, dict):
        safe_program: dict[str, Any] = {}
        for key in (
            "current_program_title", "current_unit_title", "current_topic_title",
            "topic_summary", "lesson_purpose", "resource_strategy", "assessment_strategy",
            "exam_family", "exam_display_name",
        ):
            cleaned = _safe_pedagogical_text(program.get(key), known_name_tokens)
            if cleaned:
                safe_program[key] = cleaned
        for key, limit in (
            ("active_program_subjects", 3), ("next_topics", 4),
            ("suggested_worksheet_types", 4), ("suggested_exam_types", 4),
            ("topic_learning_objectives", 4), ("topic_success_criteria", 4),
            ("exam_focus_areas", 4),
        ):
            items = _safe_pedagogical_list(program.get(key), known_name_tokens, limit)
            if items:
                safe_program[key] = items
        if safe_program:
            result["program_context"] = safe_program
    return result
