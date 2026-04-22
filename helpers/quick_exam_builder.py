from __future__ import annotations

# CLASSIO — Quick Exam Builder (AI generation)
# ============================================================
import json
import re
from collections import OrderedDict

from core.i18n import t
from translations import I18N
from helpers.answer_key_utils import clean_answer_key_item, split_answer_key_items
from helpers.generation_guidance import (
    build_expert_panel_prompt_blurb,
    build_generation_profile_guidance,
    infer_subject_family,
)
from helpers.visual_support import enrich_exam_with_visuals


AI_EXAM_DAILY_LIMIT = 3
AI_EXAM_COOLDOWN_SECONDS = 10

EXAM_LENGTHS = ["short", "medium", "long"]

_LENGTH_SPEC = {
    "short":  {"sections": 3, "questions_min": 4, "questions_max": 5},
    "medium": {"sections": 4, "questions_min": 5, "questions_max": 7},
    "long":   {"sections": 5, "questions_min": 6, "questions_max": 10},
}

# ── Exercise catalog ─────────────────────────────────────────────────
CORE_EXERCISE_TYPES = [
    "multiple_choice",
    "true_false",
    "matching",
    "fill_in_blank",
    "short_answer",
]

LANGUAGE_EXERCISE_TYPES = [
    "reading_comprehension",
    "vocabulary",
    "sentence_transformation",
    "error_correction",
    "writing_prompt",
]

MATH_EXERCISE_TYPES = [
    "problem_solving",
    "equation_solving",
    "show_your_work",
    "table_interpretation",
    "word_problems",
]

SCIENCE_EXERCISE_TYPES = [
    "data_analysis",
    "classification",
    "process_explanation",
    "hypothesis_and_conclusion",
    "diagram_questions",
]

MUSIC_EXERCISE_TYPES = [
    "theory_questions",
    "symbol_identification",
    "rhythm_counting",
    "terminology",
    "composer_period_matching",
]

SUBJECT_GROUPS = {
    "english": "language",
    "spanish": "language",
    "turkish": "language",
    "mathematics": "math",
    "math": "math",
    "science": "science",
    "music": "music",
    "study_skills": "general",
    "other": "other",
}

EXERCISE_GROUPS = OrderedDict({
    "core": CORE_EXERCISE_TYPES,
    "language": LANGUAGE_EXERCISE_TYPES,
    "math": MATH_EXERCISE_TYPES,
    "science": SCIENCE_EXERCISE_TYPES,
    "music": MUSIC_EXERCISE_TYPES,
})

GROUP_RECOMMENDED_GROUPS = {
    "language": ["core", "language"],
    "math": ["core", "math"],
    "science": ["core", "science"],
    "music": ["core", "music"],
    "general": ["core"],
    "other": list(EXERCISE_GROUPS.keys()),
}

EXERCISE_TYPE_GROUP = {
    exercise_type: group
    for group, items in EXERCISE_GROUPS.items()
    for exercise_type in items
}

EXAM_EXERCISE_TYPES = list(OrderedDict.fromkeys(
    CORE_EXERCISE_TYPES
    + LANGUAGE_EXERCISE_TYPES
    + MATH_EXERCISE_TYPES
    + SCIENCE_EXERCISE_TYPES
    + MUSIC_EXERCISE_TYPES
).keys())


def _lp():
    import helpers.lesson_planner as lp
    return lp


def get_plan_language() -> str:
    return _lp().get_plan_language()


def get_student_material_language(subject: str) -> str:
    return _lp().get_student_material_language(subject)


def _clean_str(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ensure_list(value) -> list:
    if isinstance(value, list):
        return value
    return []


def _dedupe_keep_order(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for v in values:
        key = str(v or "").strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _strip_leading_numbering(value) -> str:
    text = _clean_str(value)
    return re.sub(
        r"^\s*(?:\(?\d+\)?[.)-]|\(?[A-Za-z]\)?[.)-])\s+",
        "",
        text,
    ).strip()


def _sentence_case_fragment(value) -> str:
    text = _clean_str(value)
    if not text:
        return ""
    if any(ch.isupper() for ch in text):
        return text
    chars = list(text)
    for idx, ch in enumerate(chars):
        if ch.isalpha():
            chars[idx] = ch.upper()
            return "".join(chars)
    return text


def _clean_question_dict(q: dict) -> dict:
    cleaned = dict(q or {})
    if isinstance(cleaned.get("left"), dict) and len(cleaned["left"]) == 1 and not cleaned.get("right"):
        only_key, only_val = next(iter(cleaned["left"].items()))
        cleaned["left"] = only_key
        cleaned["right"] = only_val
    elif isinstance(cleaned.get("right"), dict) and len(cleaned["right"]) == 1:
        only_key, only_val = next(iter(cleaned["right"].items()))
        if not cleaned.get("left"):
            cleaned["left"] = only_key
        cleaned["right"] = only_val

    for key in ("text", "stem", "original", "prompt", "left", "right", "task", "word"):
        if isinstance(cleaned.get(key), str):
            cleaned[key] = _strip_leading_numbering(cleaned[key])
    for key in ("left", "right", "word"):
        if isinstance(cleaned.get(key), str):
            cleaned[key] = _sentence_case_fragment(cleaned[key])
    return cleaned


def _clean_answer_value(value):
    if isinstance(value, str):
        return clean_answer_key_item(value)
    if isinstance(value, dict):
        return _clean_question_dict(value)
    return value


def _subject_key(subject: str) -> str:
    return _clean_str(subject).lower().replace("&", "and")


def get_subject_group(subject: str) -> str:
    key = _subject_key(subject)
    mapped = SUBJECT_GROUPS.get(key)
    if mapped:
        return mapped
    family = infer_subject_family(subject)
    if family == "study_skills":
        return "general"
    return family or "other"


def _normalize_sentence_for_quality(value) -> str:
    text = _clean_str(value)
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
    )
    text = re.sub(r"\s+([,;:.!?])", r"\1", text)
    text = re.sub(r"[.!?]+$", "", text)
    return text.casefold().strip()


def _sanitize_language_text(value, lang_code: str, *, subject_group: str) -> str:
    text = _clean_str(value)
    if not text or subject_group != "language":
        return text

    if str(lang_code or "").strip().upper() not in {"EN", "ES", "TR"}:
        return text

    text = re.sub(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]+", "", text)
    text = re.sub(r"\s+([,;:.!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
    

def _sanitize_question_value(question, lang_code: str, *, subject_group: str):
    if isinstance(question, str):
        return _sanitize_language_text(question, lang_code, subject_group=subject_group)
    if not isinstance(question, dict):
        return question

    cleaned = dict(question)
    for key in ("text", "stem", "original", "prompt", "left", "right", "task", "word"):
        if key in cleaned:
            cleaned[key] = _sanitize_language_text(cleaned.get(key, ""), lang_code, subject_group=subject_group)
    if isinstance(cleaned.get("options"), list):
        cleaned["options"] = [
            _sanitize_language_text(opt, lang_code, subject_group=subject_group)
            for opt in cleaned.get("options", [])
            if _sanitize_language_text(opt, lang_code, subject_group=subject_group)
        ]
    return cleaned


def _sanitize_exam_section(section: dict, ak_section: dict, *, student_lang: str, plan_lang: str, subject_group: str) -> tuple[dict, dict]:
    section = dict(section or {})
    ak_section = dict(ak_section or {})

    for key in ("title", "instructions", "source_text"):
        section[key] = _sanitize_language_text(section.get(key, ""), student_lang, subject_group=subject_group)

    section["questions"] = [
        _sanitize_question_value(question, student_lang, subject_group=subject_group)
        for question in section.get("questions", [])
    ]
    ak_section["answers"] = [
        _sanitize_language_text(clean_answer_key_item(answer), plan_lang, subject_group=subject_group)
        if isinstance(answer, str)
        else _sanitize_question_value(answer, plan_lang, subject_group=subject_group)
        for answer in ak_section.get("answers", [])
    ]

    if section.get("type") == "error_correction":
        kept_questions = []
        kept_answers = []
        for question, answer in zip(section.get("questions", []), ak_section.get("answers", [])):
            question_text = question.get("text", "") if isinstance(question, dict) else str(question or "")
            answer_text = answer.get("text", "") if isinstance(answer, dict) else str(answer or "")
            if not _clean_str(question_text) or not _clean_str(answer_text):
                continue
            if _normalize_sentence_for_quality(question_text) == _normalize_sentence_for_quality(answer_text):
                continue
            kept_questions.append(question)
            kept_answers.append(answer)
        section["questions"] = kept_questions
        ak_section["answers"] = kept_answers

    return section, ak_section


def _exam_quality_issues(exam_data: dict, answer_key: dict) -> list[str]:
    issues: list[str] = []
    sections = exam_data.get("sections") or []
    ak_sections = (answer_key or {}).get("sections") or []

    for idx, section in enumerate(sections):
        sec_type = section.get("type", "")
        questions = section.get("questions") or []
        ak_section = ak_sections[idx] if idx < len(ak_sections) else {}
        answers = ak_section.get("answers") or []

        if sec_type == "reading_comprehension":
            if not _clean_str(section.get("source_text", "")):
                issues.append(f"section {idx + 1} reading_comprehension needs source_text")
            if questions:
                nonempty_answers = sum(bool(_clean_str(answer)) for answer in answers)
                if nonempty_answers < len(questions):
                    issues.append(f"section {idx + 1} reading_comprehension needs one usable answer per question")

        if sec_type == "error_correction" and len(questions) < 3:
            issues.append(f"section {idx + 1} error_correction needs at least 3 valid items")

    return issues


def _exam_profile_guidance(payload: dict) -> str:
    subject_group = get_subject_group(payload.get("subject", ""))
    learner_stage = _clean_str(payload.get("learner_stage", "")).lower()
    level_or_band = _clean_str(payload.get("level_or_band", ""))

    lines = [
        "- Student-facing text must stay in the requested student_material_language unless the task explicitly teaches translation.",
        "- Do not mix scripts or inject stray characters from unrelated languages.",
        "- Answers must be plain teacher text per item, not serialized Python or JSON list strings.",
    ]

    shared_guidance = build_generation_profile_guidance(
        payload.get("subject", ""),
        learner_stage,
        level_or_band,
        product="exam",
    )
    if shared_guidance:
        lines.extend(shared_guidance.splitlines())

    if subject_group == "language" and learner_stage == "lower_secondary":
        lines.extend([
            "- Prefer short, coherent contexts such as school life, routines, friends, hobbies, sports, technology, feelings, and weekend plans.",
            "- For reading_comprehension, use a coherent passage with level-appropriate questions and short, directly checkable answers.",
            "- For error_correction, every prompt sentence must contain exactly one real error and the corrected answer must not be identical to the prompt.",
        ])

    return "\n".join(lines)


def get_group_label(group: str) -> str:
    key = f"quick_exam_group_{group}"
    translated = t(key)
    return translated if translated != key else group.replace("_", " ").title()


def get_visible_exercise_groups(subject: str, show_all: bool = False) -> OrderedDict[str, list[str]]:
    subject_group = get_subject_group(subject)
    if show_all or subject_group == "other":
        group_keys = list(EXERCISE_GROUPS.keys())
    else:
        group_keys = GROUP_RECOMMENDED_GROUPS.get(subject_group, ["core"])
    return OrderedDict((group, EXERCISE_GROUPS[group]) for group in group_keys if group in EXERCISE_GROUPS)


def get_recommended_exercise_types(subject: str) -> list[str]:
    groups = GROUP_RECOMMENDED_GROUPS.get(get_subject_group(subject), ["core"])
    exercise_types = []
    for group in groups:
        exercise_types.extend(EXERCISE_GROUPS.get(group, []))
    return _dedupe_keep_order(exercise_types)


def get_all_exercise_types_for_subject(subject: str) -> list[str]:
    group = get_subject_group(subject)
    if group == "other":
        return EXAM_EXERCISE_TYPES[:]
    return EXAM_EXERCISE_TYPES[:]


def get_default_selected_exercise_types(subject: str) -> list[str]:
    group = get_subject_group(subject)
    if group == "language":
        preferred = ["multiple_choice", "reading_comprehension", "writing_prompt"]
    elif group == "math":
        preferred = ["problem_solving", "equation_solving", "show_your_work"]
    elif group == "science":
        preferred = ["data_analysis", "classification", "process_explanation"]
    elif group == "music":
        preferred = ["theory_questions", "symbol_identification", "terminology"]
    else:
        preferred = ["multiple_choice", "short_answer", "problem_solving"]

    recommended = get_recommended_exercise_types(subject)
    return [x for x in preferred if x in recommended][:3] or recommended[:3] or CORE_EXERCISE_TYPES[:3]


def _exercise_title(exercise_type: str) -> str:
    translated = t(exercise_type)
    if translated != exercise_type:
        return translated
    return exercise_type.replace("_", " ").title()


def _exercise_help_text(exercise_type: str) -> str:
    key = f"quick_exam_help_{exercise_type}"
    translated = t(key)
    return translated if translated != key else ""


def _exercise_multiselect_label(exercise_type: str) -> str:
    return _exercise_title(exercise_type)


def _recommended_hint_text(subject: str) -> str:
    group = get_subject_group(subject)
    key = f"quick_exam_hint_{group}"
    translated = t(key)
    if translated != key:
        return translated
    fallback = t("quick_exam_hint_general")
    return fallback if fallback != "quick_exam_hint_general" else ""


_EXAM_INSTRUCTION_FALLBACKS = {
    "multiple_choice": "Read each question and circle the letter of the best answer.",
    "true_false": "Read the text and decide whether each statement is true or false.",
    "matching": "Match each item in Column A with the correct item in Column B. Write the correct letter next to each number.",
    "fill_in_blank": "Complete each sentence or prompt with the correct word, number, or phrase.",
    "short_answer": "Answer each question in one or two complete sentences.",
    "reading_comprehension": "Read the passage carefully and answer the questions using evidence from the text.",
    "vocabulary": "Complete each vocabulary task using the correct word or meaning.",
    "sentence_transformation": "Rewrite each sentence as instructed while keeping the original meaning.",
    "error_correction": "Each sentence has one mistake. Find that one mistake and rewrite the full corrected sentence.",
    "writing_prompt": "Write a clear, well-developed response to the prompt.",
    "problem_solving": "Solve each problem and show the steps you used when needed.",
    "equation_solving": "Solve each equation and write your final answer clearly.",
    "show_your_work": "Solve each task and show all your work clearly.",
    "table_interpretation": "Study the table and answer the questions that follow.",
    "word_problems": "Read each word problem carefully and solve it step by step.",
    "data_analysis": "Study the data carefully and answer the questions using evidence from the data.",
    "classification": "Classify each item correctly and justify your choice when needed.",
    "process_explanation": "Explain each process clearly using correct scientific language.",
    "hypothesis_and_conclusion": "Use the information provided to form a hypothesis or draw a conclusion.",
    "diagram_questions": "Study the diagram information carefully and answer the questions.",
    "theory_questions": "Answer each theory question clearly and accurately.",
    "symbol_identification": "Identify each symbol correctly.",
    "rhythm_counting": "Count the rhythm carefully and write the correct value or pattern.",
    "terminology": "Use the correct term for each item.",
    "composer_period_matching": "Match each composer or work with the correct period.",
}

_EXAM_INSTRUCTION_MISMATCHES = {
    "multiple_choice": ("line provided", "given line", "write the answer", "write your answer", "type the answer", "complete each sentence", "escribe la respuesta", "escribe tu respuesta", "completa cada frase", "completa cada oración", "completa cada oracion", "verdadero o falso", "columna a", "columna b", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "true_false": ("choose the best answer", "column a", "column b", "write the correct letter", "fill in the blank", "choose or circle", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "columna a", "columna b", "escribe la letra correcta", "completa cada frase", "doğru seçeneği", "dogru secenegi", "sütun a", "sutun a", "sütun b", "sutun b"),
    "matching": ("choose the best answer", "true or false", "complete each sentence", "circle the letter", "elige la opción", "elige la opcion", "verdadero o falso", "completa cada frase", "completa cada oración", "completa cada oracion", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis"),
    "fill_in_blank": ("choose the best answer", "true or false", "column a", "column b", "circle the letter", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "short_answer": ("choose the best answer", "true or false", "column a", "column b", "circle the letter", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "reading_comprehension": ("choose the best answer", "true or false", "column a", "column b", "circle the letter", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "rodea la letra", "circula la letra", "círcula la letra", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "vocabulary": ("true or false", "column a", "column b", "verdadero o falso", "columna a", "columna b", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "sentence_transformation": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "error_correction": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "writing_prompt": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "problem_solving": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "equation_solving": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "show_your_work": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "table_interpretation": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "word_problems": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "data_analysis": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "classification": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "process_explanation": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "hypothesis_and_conclusion": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "diagram_questions": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "theory_questions": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "symbol_identification": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "rhythm_counting": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "terminology": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "composer_period_matching": ("choose the best answer", "true or false", "complete each sentence", "circle the letter", "elige la opción", "elige la opcion", "verdadero o falso", "completa cada frase", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis"),
}


def _default_instruction_for_exam_type(exercise_type: str) -> str:
    key = f"instruction_{exercise_type}"
    translated = t(key)
    if translated != key:
        return translated
    return _EXAM_INSTRUCTION_FALLBACKS.get(exercise_type, "")


def _exam_instruction_needs_reset(exercise_type: str, text: str) -> bool:
    text = _clean_str(text)
    if not text:
        return True
    lowered = text.casefold()
    return any(fragment in lowered for fragment in _EXAM_INSTRUCTION_MISMATCHES.get(exercise_type, ()))


def _build_exercise_catalog_markdown(subject: str, show_all: bool) -> str:
    group = get_subject_group(subject)
    recommended = set(get_recommended_exercise_types(subject))
    lines = []
    visible_groups = get_visible_exercise_groups(subject, show_all=show_all)

    if show_all or group == "other":
        for grp_key, items in visible_groups.items():
            lines.append(f"**{get_group_label(grp_key)}**")
            for et in items:
                marker = "⭐ " if et in recommended else ""
                label = _exercise_title(et)
                help_text = _exercise_help_text(et)
                line = f"- {marker}{label}"
                if help_text:
                    line += f" — {help_text}"
                lines.append(line)
    else:
        lines.append(f"**{t('quick_exam_recommended_for_subject')}**")
        for grp_key, items in visible_groups.items():
            lines.append(f"*{get_group_label(grp_key)}*")
            for et in items:
                label = _exercise_title(et)
                help_text = _exercise_help_text(et)
                line = f"- {label}"
                if help_text:
                    line += f" — {help_text}"
                lines.append(line)

    return "\n".join(lines)


def normalize_exam_output(raw: dict) -> tuple[dict, dict]:
    raw = dict(raw or {})
    student_lang = _clean_str(raw.get("student_material_language", ""))
    plan_lang = _clean_str(raw.get("plan_language", ""))
    subject_group = get_subject_group(raw.get("subject", ""))

    exam_data = {
        "title": _clean_str(raw.get("title", "")),
        "instructions": _clean_str(raw.get("instructions", "")),
        "sections": [],
    }

    answer_key = {"sections": []}

    for sec in _ensure_list(raw.get("sections")):
        if not isinstance(sec, dict):
            continue

        section = {
            "type": _clean_str(sec.get("type", "")),
            "title": _clean_str(sec.get("title", "")),
            "instructions": _clean_str(sec.get("instructions", "")),
            "source_text": _clean_str(sec.get("source_text", "")),
            "questions": [],
        }

        ak_section = {
            "title": section["title"],
            "answers": [],
        }

        for q in _ensure_list(sec.get("questions")):
            if isinstance(q, dict):
                cleaned_q = _clean_question_dict(q)
                if cleaned_q:
                    section["questions"].append(cleaned_q)
            elif isinstance(q, str) and q.strip():
                cleaned_text = _strip_leading_numbering(q)
                if cleaned_text:
                    section["questions"].append({"text": cleaned_text})

        for a in _ensure_list(sec.get("answers")):
            if isinstance(a, str) and a.strip():
                cleaned_answer = _strip_leading_numbering(a)
                if cleaned_answer:
                    ak_section["answers"].append(cleaned_answer)
            elif isinstance(a, dict):
                ak_section["answers"].append(_clean_answer_value(a))

        if len(ak_section["answers"]) == 1 and len(section["questions"]) > 1:
            expanded_answers = split_answer_key_items(
                ak_section["answers"][0],
                expected_count=len(section["questions"]),
            )
            if sum(bool(_clean_str(answer)) for answer in expanded_answers) > 1:
                ak_section["answers"] = expanded_answers

        if _exam_instruction_needs_reset(section["type"], section["instructions"]):
            section["instructions"] = _default_instruction_for_exam_type(section["type"])

        section, ak_section = _sanitize_exam_section(
            section,
            ak_section,
            student_lang=student_lang,
            plan_lang=plan_lang,
            subject_group=subject_group,
        )

        if section["questions"]:
            exam_data["sections"].append(section)
            answer_key["sections"].append(ak_section)

    exam_data["instructions"] = _sanitize_language_text(
        exam_data.get("instructions", ""),
        student_lang,
        subject_group=subject_group,
    )
    return exam_data, answer_key


def _section_type_rules(exercise_type: str, subject_group: str = "") -> str:
    rules = {
        "multiple_choice": (
            "Each question must have a 'stem', 'options' (list of 4 strings), "
            "and 'answer' (the correct option text)."
        ),
        "true_false": (
            "Provide a short source text in the section 'source_text' field only if it genuinely improves the task. "
            "Each question is a statement string. "
            "Include 'answers' with True/False for each item. "
            "Statements must be professionally punctuated and grammatically complete. "
            "For lower-primary image-friendly topics, you may base the statements on one simple observable scene and leave source_text empty."
        ),
        "matching": (
            "Each question is an object with 'left' and 'right'. "
            "Shuffle the right side. Provide the correct mapping in 'answers'. "
            "Use clean, publication-ready text fragments for both sides, with correct capitalization and no raw dictionary formatting. "
            "For lower-primary learners, prefer concrete and visually observable items when pedagogically suitable."
        ),
        "fill_in_blank": (
            "Each question is a sentence or prompt with a blank indicated by '______'. "
            "For math or science, blanks may be used for formula terms, values, labels, or keywords. "
            "Provide 'answers' with the correct word, symbol, number, or phrase."
        ),
        "short_answer": (
            "Each question is a text string requiring a short written answer. "
            "Provide suggested answers in 'answers'."
        ),
        "reading_comprehension": (
            "Include a 'source_text' field with a reading passage or source text. "
            "Each question is a text string about the passage. "
            "Provide answers in 'answers'. "
            "For lower-primary learners, prefer scene-based passages with concrete details that can be illustrated."
        ),
        "vocabulary": (
            "Each question tests word knowledge, terminology, definitions, synonyms, or context use. "
            "For non-language subjects, adapt this to subject terminology. "
            "Each question is an object with 'word' and 'task'. "
            "Provide answers in 'answers'. "
            "For lower-primary learners, prefer concrete, image-friendly vocabulary when appropriate."
        ),
        "sentence_transformation": (
            "Each question is an object with 'original' sentence and 'prompt' "
            "(instruction for how to transform). This is mainly appropriate for language subjects."
        ),
        "error_correction": (
            "Each question is a full sentence containing EXACTLY ONE error. "
            "For non-language subjects, only use this if error correction makes genuine pedagogical sense. "
            "The error may be grammatical, numerical, conceptual, or subject-specific depending on the subject. "
            "Students must rewrite the full sentence correctly. "
            "Provide the full corrected sentence in 'answers'."
        ),
        "writing_prompt": (
            "Each question is a writing prompt string. "
            "Answers should be brief evaluation criteria, a model point outline, or expected content points."
        ),
        "problem_solving": (
            "Each question is a clear problem-solving task. "
            "Provide worked or model answers in 'answers'."
        ),
        "equation_solving": (
            "Each question asks students to solve an equation or algebraic statement. "
            "Provide the correct solution steps or final answers in 'answers'."
        ),
        "show_your_work": (
            "Each question requires a final answer plus visible reasoning or method. "
            "Provide concise model working in 'answers'."
        ),
        "table_interpretation": (
            "Include a small data table inside the question text when needed. "
            "Questions should ask students to read, compare, calculate, or infer from tabulated data."
        ),
        "word_problems": (
            "Each question should be a realistic word problem with clear quantities and a solvable task. "
            "Provide accurate model answers in 'answers'."
        ),
        "data_analysis": (
            "Each question should ask students to interpret evidence, compare data, or identify trends. "
            "Provide concise evidence-based answers in 'answers'."
        ),
        "classification": (
            "Each question asks students to group, sort, or identify categories using scientific reasoning. "
            "Provide the correct classification in 'answers'."
        ),
        "process_explanation": (
            "Each question asks students to explain a process, sequence, or mechanism. "
            "Provide brief model explanations in 'answers'."
        ),
        "hypothesis_and_conclusion": (
            "Questions should ask students to predict outcomes, form hypotheses, or draw conclusions from evidence. "
            "Provide sound model answers in 'answers'."
        ),
        "diagram_questions": (
            "Use text-friendly diagram descriptions, labels, or parts when real images are not available. "
            "Provide the correct identifications or explanations in 'answers'."
        ),
        "theory_questions": (
            "Each question should assess music theory knowledge such as notation, intervals, chords, scales, or form. "
            "Provide accurate model answers in 'answers'."
        ),
        "symbol_identification": (
            "Each question should ask students to identify a music symbol, sign, or notation mark. "
            "Provide the correct identification in 'answers'."
        ),
        "rhythm_counting": (
            "Each question should ask students to count beats, identify meter, or interpret rhythmic values. "
            "Provide the correct counts or explanations in 'answers'."
        ),
        "terminology": (
            "Each question should assess subject-specific terminology and meaning. "
            "Provide concise correct answers in 'answers'."
        ),
        "composer_period_matching": (
            "Each question should ask students to match composers, styles, or works with the correct period. "
            "Provide the correct matches in 'answers'."
        ),
    }
    if subject_group == "math" and exercise_type == "reading_comprehension":
        return (
            "Include a concise math-related source text only when it supports problem solving, data interpretation, "
            "or a word-problem context. Each question is a text string about that source. Provide answers in 'answers'."
        )
    if subject_group == "music" and exercise_type == "vocabulary":
        return (
            "Use this for music terminology, notation words, symbols, form names, or theory language. "
            "Each question is an object with 'word' and 'task'. Provide answers in 'answers'."
        )
    return rules.get(exercise_type, "")


def _subject_group_guidance(subject_group: str) -> str:
    guidance = {
        "language": (
            "- Prioritise communicative language use, grammar accuracy, vocabulary control, and reading/writing coherence.\n"
            "- It is appropriate to use reading passages, editing tasks, sentence transformation, and writing prompts.\n"
            "- Keep the level aligned with the chosen CEFR or learner stage."
        ),
        "math": (
            "- Prioritise accuracy, reasoning, procedural fluency, and problem solving.\n"
            "- Avoid language-heavy tasks unless they support mathematical thinking.\n"
            "- Use concise wording, clear numerical prompts, and age-appropriate cognitive demand."
        ),
        "science": (
            "- Prioritise concept understanding, classification, observation, explanation, and evidence-based reasoning.\n"
            "- Reading or terminology tasks are allowed when they clearly support science learning.\n"
            "- Keep explanations precise and factually correct."
        ),
        "music": (
            "- Prioritise music theory, symbols, terminology, pattern recognition, and short explanation.\n"
            "- Keep tasks text-friendly unless notation is essential.\n"
            "- Avoid overly abstract prompts that depend on audio the app cannot provide."
        ),
        "general": (
            "- Prioritise clarity, broad accessibility, and sound instructional alignment.\n"
            "- Use exercise types only when they are a natural fit for the topic."
        ),
        "other": (
            "- The subject may be a custom or less common discipline.\n"
            "- Use only the selected exercise types that genuinely fit the topic and teaching context.\n"
            "- If one selected exercise type is a weak fit, adapt it sensibly rather than forcing a poor task."
        ),
    }
    return guidance.get(subject_group, guidance["general"])


def _group_alignment_rules(subject_group: str) -> str:
    rules = {
        "language": (
            "- The product model for language subjects is Core + Language-focused.\n"
            "- Use Core sections to check foundational comprehension and response accuracy.\n"
            "- Use Language-focused sections to assess reading, vocabulary control, grammar/form, editing, or writing.\n"
            "- Prefer authentic language use over decontextualised drill unless the selected type explicitly targets form."
        ),
        "math": (
            "- The product model for math subjects is Core + Math-focused.\n"
            "- Use Core sections only when they genuinely help measure mathematical understanding efficiently.\n"
            "- Use Math-focused sections to foreground reasoning, procedure, accuracy, modelling, and interpretation.\n"
            "- Avoid turning the exam into a language-heavy literacy task unless the topic explicitly requires word-problem comprehension."
        ),
        "science": (
            "- The product model for science subjects is Core + Science-focused.\n"
            "- Use Core sections for efficient checks of knowledge and short constructed response.\n"
            "- Use Science-focused sections to foreground evidence, classification, process understanding, data interpretation, and conclusion-making.\n"
            "- Keep the scientific framing authentic: observations, variables, processes, explanations, and evidence should feel discipline-appropriate."
        ),
        "music": (
            "- The product model for music subjects is Core + Music-focused.\n"
            "- Use Core sections for efficient checks of broad understanding.\n"
            "- Use Music-focused sections to foreground notation, terminology, symbols, rhythm, theory, and stylistic/historical recognition.\n"
            "- Keep the assessment text-friendly and realistic for a no-audio environment."
        ),
        "general": (
            "- The product model for general subjects is Core-first.\n"
            "- Keep the exam broadly usable, efficient to deliver, and aligned to the selected topic."
        ),
        "other": (
            "- The product model for custom subjects is flexible across all groups.\n"
            "- Choose only the exercise types that make real instructional sense for the discipline and topic.\n"
            "- If the selected set spans multiple groups, make the exam feel coherent rather than random."
        ),
    }
    return rules.get(subject_group, rules["general"])


def _selected_exercise_blueprint(exercise_types: list[str]) -> str:
    lines = []
    for idx, exercise_type in enumerate(exercise_types, 1):
        group = EXERCISE_TYPE_GROUP.get(exercise_type, "core")
        lines.append(
            f"- Section {idx}: {exercise_type} | group={group} | label={_exercise_title(exercise_type)}"
        )
    return "\n".join(lines)


def _section_sequence_guidance(subject_group: str) -> str:
    starts = {
        "language": "Start with accessible recognition/comprehension before moving into controlled production and extended output.",
        "math": "Start with accessible fluency or recognition before moving into procedural reasoning and multi-step problem solving.",
        "science": "Start with accessible knowledge checks before moving into explanation, evidence use, and interpretation.",
        "music": "Start with accessible recognition tasks before moving into deeper theory, terminology, and interpretation.",
        "general": "Start with accessible tasks before moving into more cognitively demanding sections.",
        "other": "Sequence sections from lower to higher cognitive demand so the paper feels intentionally designed.",
    }
    return (
        f"- {starts.get(subject_group, starts['general'])}\n"
        "- Vary the response demand across sections so the paper does not feel repetitive.\n"
        "- Make each section earn its place in the assessment by measuring a distinct but relevant skill."
    )


def _shared_text_section_types() -> set[str]:
    return {"reading_comprehension", "true_false"}


def _passage_alignment_guidance(exercise_types: list[str], subject_group: str) -> str:
    selected = exercise_types or []
    shared_text_types = [et for et in selected if et in _shared_text_section_types()]
    has_reading = "reading_comprehension" in selected
    has_true_false = "true_false" in selected

    lines = [
        "- Any section that uses a passage or source text must be tightly aligned to that text.",
        "- Questions must be answerable from textual evidence, not from random outside knowledge.",
        "- Higher-level inference is allowed only when the inference is strongly grounded in the text.",
        "- Distractors in text-based multiple choice must be plausible but still resolvable from the text.",
        "- The answer key must reflect what the text supports directly or reasonably implies.",
    ]

    if has_reading and has_true_false:
        lines.extend([
            "- Because both reading_comprehension and true_false are selected, prefer ONE coherent shared passage unless there is a strong pedagogical reason not to.",
            "- If a shared passage is used, both sections must use the same facts, ideas, and evidence base.",
            "- Do not generate unrelated passages or disconnected question sets for those two sections.",
        ])
    elif shared_text_types:
        lines.extend([
            f"- The selected text-based section(s) {', '.join(shared_text_types)} should use a purposeful passage that clearly supports the task.",
            "- Do not create a passage that is decorative or loosely related to the questions.",
        ])

    if subject_group == "language":
        lines.append("- For language subjects, keep comprehension, vocabulary, and inference anchored in the actual wording, meaning, tone, and details of the passage.")
    elif subject_group in {"science", "math"}:
        lines.append("- For science or math, any text-based section should support reasoning with content evidence, data, or scenario details rather than generic reading trivia.")

    return "\n".join(lines)


def _exam_quality_guardrails() -> str:
    return (
        "- Do NOT number the questions or answers inside the JSON. The app adds numbering automatically.\n"
        "- Do NOT use markdown or bullet symbols inside question text unless the task truly needs them.\n"
        "- Make the exam coherent around the given topic and learner profile.\n"
        "- Keep instructions concise, explicit, and student-friendly.\n"
        "- Use professional, publication-ready capitalization, punctuation, grammar, and layout-friendly wording.\n"
        "- Matching terms, labels, and short prompts should look polished and academically acceptable on the printed page.\n"
        "- Avoid repeating the same task pattern with only superficial wording changes.\n"
        "- Ensure answers are complete, correct, and directly match the questions.\n"
        "- Answers must be plain text per item, not serialized Python lists or quoted arrays.\n"
        "- Only include 'source_text' when a passage or source materially improves that section.\n"
        "- Do not force language-only exercises into non-language subjects unless pedagogically justified."
    )


def _build_exam_prompts(payload: dict) -> tuple[str, str]:
    length_key = payload.get("exam_length", "medium")
    spec = _LENGTH_SPEC.get(length_key, _LENGTH_SPEC["medium"])
    exercise_types = payload.get("exercise_types", [])
    subject_group = payload.get("subject_group", "general")
    n_sections = min(spec["sections"], len(exercise_types)) if exercise_types else spec["sections"]

    type_details = []
    for et in exercise_types[:n_sections]:
        rule = _section_type_rules(et, subject_group=subject_group)
        type_details.append(f"- {et}: {rule}" if rule else f"- {et}")

    system_prompt = (
        f"{build_expert_panel_prompt_blurb('exam')} "
        "You are a world-class assessment and evaluation specialist with a PhD in Education, deep expertise in instructional design, "
        "strong assessment literacy, and classroom exam-writing experience across school subjects. "
        "Your task is to create a premium, classroom-ready exam paper that a professional teacher could use immediately. "
        "Think like an expert in validity, alignment, cognitive demand, item quality, learner accessibility, and efficient evidence collection. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "Use the requested plan_language for teacher-facing sections (answers). "
        "Use the requested student_material_language for student-facing sections "
        "(instructions, questions, source_text). "
        "Be pedagogically accurate, age-appropriate, and internally consistent."
    )

    user_prompt = f'''
Create a complete exam paper as JSON.

Input:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Exam structure:
- {n_sections} sections
- {spec["questions_min"]}-{spec["questions_max"]} questions per section
- Exercise types to include (in order):
{chr(10).join(type_details)}

Subject-group guidance:
{_subject_group_guidance(subject_group)}

Product-model alignment:
{_group_alignment_rules(subject_group)}

Passage and evidence alignment:
{_passage_alignment_guidance(exercise_types[:n_sections], subject_group)}

Selected exercise blueprint:
{_selected_exercise_blueprint(exercise_types[:n_sections])}

Section-specific rules:
{chr(10).join(type_details)}

Quality guardrails:
{_exam_quality_guardrails()}

Design principles:
- Use clear, age-appropriate language for the target learner_stage and level.
- Make the exam progressively harder from section to section.
- Sequence the paper like an expert assessor, not a random worksheet generator.
- Ensure every selected exercise type is used in a way that fits its group and the subject's product model.
- Make every section instruction match the actual response mode exactly.
- Do not tell students to write on a line if the section uses options, matching letters, or another built-in response format.
- Examples:
  - multiple_choice: tell students to choose or circle the correct option/letter
  - matching: tell students to match Column A with Column B and write the correct letter
  - true_false: tell students to decide whether each statement is true or false
  - fill_in_blank: tell students to complete each blank with the correct word, number, or phrase
- Design for efficiency: each section should gather meaningful evidence of learning with minimal fluff.
- Balance validity, reliability, clarity, and engagement.
- Prefer high-quality task design over decorative variety.
- Each section must have a clear title (e.g. "Part 1: Multiple Choice").
- Keep content factually accurate and pedagogically sound.
- Each section includes both questions AND answers.
- If the subject is custom or interdisciplinary, adapt intelligently to the topic rather than forcing a narrow template.

Profile quality guidance:
{_exam_profile_guidance(payload)}

Section sequencing guidance:
{_section_sequence_guidance(subject_group)}

Required JSON structure:
{{
  "title": "string",
  "instructions": "General exam instructions",
  "sections": [
    {{
      "type": "exercise_type",
      "title": "Part N: Section Title",
      "instructions": "Section-specific instructions",
      "source_text": "optional reading passage or source text",
      "questions": [
      ],
      "answers": [
      ]
    }}
  ]
}}

Provide ALL sections and ALL answers.
'''
    return system_prompt, user_prompt


def generate_ai_exam(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    topic: str,
    exam_title: str,
    exam_length: str,
    exercise_types: list[str],
    instructions: str,
    plan_language: str,
    student_material_language: str,
) -> tuple[dict, dict]:
    subject_group = get_subject_group(subject)

    payload = {
        "subject": subject,
        "subject_group": subject_group,
        "topic": topic,
        "exam_title": exam_title,
        "learner_stage": learner_stage,
        "level_or_band": level_or_band,
        "exam_length": exam_length,
        "exercise_types": _dedupe_keep_order(exercise_types),
        "instructions": instructions,
        "plan_language": plan_language,
        "student_material_language": student_material_language,
    }

    system_prompt, user_prompt = _build_exam_prompts(payload)
    provider_order = _lp().get_ai_provider_order()

    errors = []
    for p in provider_order:
        try:
            if p == "gemini":
                raw = _lp()._generate_with_gemini(system_prompt, user_prompt)
            elif p == "openrouter":
                raw = _lp()._generate_with_openrouter(system_prompt, user_prompt)
            else:
                raw = _lp()._generate_with_openai(system_prompt, user_prompt)

            parsed = _lp()._extract_json_object_from_text(raw)
            exam_data, answer_key = normalize_exam_output(parsed)
            exam_data["title"] = exam_data["title"] or exam_title or "Exam"
            exam_data["instructions"] = exam_data["instructions"] or instructions
            quality_issues = _exam_quality_issues(exam_data, answer_key)
            if quality_issues:
                raise ValueError("; ".join(quality_issues))
            exam_data = enrich_exam_with_visuals(
                exam_data,
                subject=subject,
                learner_stage=learner_stage,
                topic=topic,
            )
            return exam_data, answer_key
        except Exception as e:
            errors.append(f"{p}: {e}")

    raise RuntimeError(" | ".join(errors))


def generate_exam_with_limit(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    topic: str,
    exam_title: str,
    exam_length: str,
    exercise_types: list[str],
    instructions: str = "",
) -> tuple[dict, dict, str | None]:
    from helpers.quick_exam_storage import get_ai_exam_usage_status, log_exam_ai_usage

    usage = get_ai_exam_usage_status()

    if usage["used_today"] >= AI_EXAM_DAILY_LIMIT:
        lang = get_plan_language()
        msg = (
            t("ai_limit_reached")
            if "ai_limit_reached" in I18N.get(lang, {})
            else "AI daily limit reached."
        )
        return {}, {}, msg

    if not usage["cooldown_ok"]:
        return {}, {}, f"{t('ai_cooldown_active')} ({usage['seconds_left']}s)"

    try:
        log_exam_ai_usage("requested", {"subject": subject, "topic": topic})

        exam_data, answer_key = generate_ai_exam(
            subject=subject,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
            topic=topic,
            exam_title=exam_title,
            exam_length=exam_length,
            exercise_types=exercise_types,
            instructions=instructions,
            plan_language=get_plan_language(),
            student_material_language=get_student_material_language(subject),
        )

        log_exam_ai_usage("success", {"subject": subject, "topic": topic})
        return exam_data, answer_key, None

    except Exception as e:
        log_exam_ai_usage("failed", {"subject": subject, "topic": topic, "error": str(e)})
        return {}, {}, t("ai_unavailable_fallback")


def reset_exam_builder_state():
    import streamlit as st
    for key in [
        "exam_result", "exam_answer_key", "exam_kept",
        "exam_warning", "quick_exam_subject", "quick_exam_topic",
        "quick_exam_title", "quick_exam_instructions",
        "exam_show_more_types", "exam_available_types_cache",
        "exam_recommended_types_cache", "exam_selected_subject_group",
    ]:
        st.session_state.pop(key, None)


def render_quick_exam_builder_expander() -> None:
    import streamlit as st
    from helpers.quick_exam_storage import get_ai_exam_usage_status

    with st.expander(
        f"🧪 {t('quick_exam_builder') if t('quick_exam_builder') != 'quick_exam_builder' else 'Quick Exam Builder'}",
        expanded=False,
    ):
        st.caption(
            t("quick_exam_builder_caption")
            if t("quick_exam_builder_caption") != "quick_exam_builder_caption"
            else "Generate a full multi-section exam in seconds"
        )

        usage = get_ai_exam_usage_status()
        st.caption(
            t(
                "ai_plans_left_today",
                remaining=usage["remaining_today"],
                limit=AI_EXAM_DAILY_LIMIT,
            )
        )

        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            format_func=_lp().subject_label,
            key="quick_exam_subject",
        )

        other_subject_name = ""
        if subject == "other":
            other_subject_name = st.text_input(
                t("other_subject_label"), key="exam_other_subject"
            ).strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=_lp()._stage_label,
            key="exam_stage",
        )

        default_level = _lp().recommend_default_level(subject, learner_stage)
        level_options = _lp().get_level_options(subject)
        if st.session_state.get("exam_level") not in level_options:
            st.session_state["exam_level"] = default_level

        level_or_band = st.selectbox(
            t("level_or_band"),
            level_options,
            format_func=_lp()._level_label,
            key="exam_level",
        )

        topic = st.text_input(t("topic_label"), key="quick_exam_topic")
        exam_title = st.text_input(
            t("exam_title") if t("exam_title") != "exam_title" else "Exam title",
            key="quick_exam_title",
        )

        effective_subject = other_subject_name if subject == "other" and other_subject_name else subject
        subject_group = get_subject_group(subject)
        recommended_types = get_recommended_exercise_types(subject)
        all_types = get_all_exercise_types_for_subject(subject)

        st.session_state["exam_available_types_cache"] = all_types
        st.session_state["exam_recommended_types_cache"] = recommended_types
        st.session_state["exam_selected_subject_group"] = subject_group

        st.markdown(f"**{t('exam_settings') if t('exam_settings') != 'exam_settings' else 'Exam Settings'}**")

        c1, c2 = st.columns(2)
        with c1:
            exam_length = st.selectbox(
                t("exam_length") if t("exam_length") != "exam_length" else "Exam length",
                EXAM_LENGTHS,
                format_func=lambda x: t(f"{x}_exam") if t(f"{x}_exam") != f"{x}_exam" else x.capitalize(),
                key="exam_length_select",
            )
        with c2:
            show_all_default = subject_group == "other"
            show_all = st.checkbox(
                t("quick_exam_show_more_options") if subject_group != "other" else t("quick_exam_all_groups_for_other"),
                value=show_all_default,
                key="exam_show_more_types",
                disabled=(subject_group == "other"),
                help=(
                    t("quick_exam_show_more_options_help")
                    if subject_group != "other"
                    else t("quick_exam_all_groups_for_other_help")
                ),
            )

            available_types = all_types if (show_all or subject_group == "other") else recommended_types
            available_types = _dedupe_keep_order(available_types)

            current_selected = st.session_state.get("exam_exercise_types")
            if not isinstance(current_selected, list) or not current_selected:
                st.session_state["exam_exercise_types"] = get_default_selected_exercise_types(subject)
            else:
                still_valid = [x for x in current_selected if x in available_types]
                if not still_valid:
                    still_valid = get_default_selected_exercise_types(subject)
                st.session_state["exam_exercise_types"] = still_valid

            exercise_types = st.multiselect(
                t("exercise_types") if t("exercise_types") != "exercise_types" else "Exercise types",
                available_types,
                format_func=_exercise_multiselect_label,
                key="exam_exercise_types",
                help=t("quick_exam_exercise_types_help"),
            )
            st.info(_recommended_hint_text(subject))
            with st.expander(t("quick_exam_exercise_guide"), expanded=False):
                st.markdown(_build_exercise_catalog_markdown(subject, show_all), unsafe_allow_html=False)

        instructions = st.text_area(
            t("instructions") if t("instructions") != "instructions" else "Instructions",
            key="quick_exam_instructions",
            height=110,
            placeholder=t("quick_exam_instructions_placeholder"),
        )

        if st.button(
            t("generate_exam") if t("generate_exam") != "generate_exam" else "Generate Exam",
            key="btn_gen_exam",
            use_container_width=True,
        ):
            if not topic.strip():
                st.error(t("enter_topic"))
            elif subject == "other" and not other_subject_name:
                st.error(t("enter_subject_name"))
            elif not exercise_types:
                st.error(
                    t("select_exercise_types")
                    if t("select_exercise_types") != "select_exercise_types"
                    else "Please select at least one exercise type."
                )
            else:
                selected_types = _dedupe_keep_order(exercise_types)
                length_spec = _LENGTH_SPEC.get(exam_length, _LENGTH_SPEC["medium"])
                max_recommended_sections = length_spec["sections"]
                if len(selected_types) > max_recommended_sections:
                    selected_types = selected_types[:max_recommended_sections]

                with st.spinner(t("generating")):
                    exam_data, answer_key, warning = generate_exam_with_limit(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        topic=topic,
                        exam_title=exam_title or t("quick_exam_default_title", subject=effective_subject),
                        exam_length=exam_length,
                        exercise_types=selected_types,
                        instructions=instructions,
                    )

                if warning and not exam_data:
                    st.warning(warning)
                elif not exam_data or not exam_data.get("sections"):
                    st.error(
                        t("exam_generation_failed")
                        if t("exam_generation_failed") != "exam_generation_failed"
                        else "Exam generation failed. Please try again."
                    )
                else:
                    exam_data = enrich_exam_with_visuals(
                        exam_data,
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        topic=topic,
                    )
                    st.session_state["exam_result"] = exam_data
                    st.session_state["exam_answer_key"] = answer_key
                    st.session_state["exam_kept"] = False
                    st.session_state["exam_warning"] = warning

                    from helpers.quick_exam_storage import save_exam_record
                    _saved_id = save_exam_record(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        topic=topic,
                        exam_length=exam_length,
                        exercise_types=selected_types,
                        exam_data=exam_data,
                        answer_key=answer_key,
                    )
                    if _saved_id:
                        st.session_state["exam_record_id"] = _saved_id

        result = st.session_state.get("exam_result")
        ak = st.session_state.get("exam_answer_key")
        if result and ak:
            from helpers.quick_exam_storage import render_exam_result
            render_exam_result(
                result,
                ak,
                allow_assign=True,
                resource_record_id=st.session_state.get("exam_record_id"),
                subject=effective_subject,
                topic=topic,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
            )
