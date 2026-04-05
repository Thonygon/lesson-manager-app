# CLASSIO — Quick Exam Builder (AI generation)
# ============================================================
import json, re
from core.i18n import t
from translations import I18N


AI_EXAM_DAILY_LIMIT = 3
AI_EXAM_COOLDOWN_SECONDS = 10

EXAM_EXERCISE_TYPES = [
    "multiple_choice",
    "true_false",
    "matching",
    "fill_in_blank",
    "short_answer",
    "reading_comprehension",
    "vocabulary",
    "sentence_transformation",
    "error_correction",
    "writing_prompt",
]

EXAM_LENGTHS = ["short", "medium", "long"]

_LENGTH_SPEC = {
    "short":  {"sections": 3, "questions_min": 4, "questions_max": 5},
    "medium": {"sections": 4, "questions_min": 5, "questions_max": 7},
    "long":   {"sections": 5, "questions_min": 6, "questions_max": 10},
}


def _lp():
    import helpers.lesson_planner as lp
    return lp


def get_plan_language() -> str:
    return _lp().get_plan_language()


def get_student_material_language(subject: str) -> str:
    return _lp().get_student_material_language(subject)


# ── Helpers ──────────────────────────────────────────────────────────
def _clean_str(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ensure_list(value) -> list:
    if isinstance(value, list):
        return value
    return []


# ── Normalise exam output ────────────────────────────────────────────
def normalize_exam_output(raw: dict) -> tuple[dict, dict]:
    """Return (exam_data, answer_key) from raw AI JSON."""
    raw = dict(raw or {})

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
            "questions": [],
        }

        ak_section = {
            "title": section["title"],
            "answers": [],
        }

        for q in _ensure_list(sec.get("questions")):
            if isinstance(q, dict):
                section["questions"].append(q)
            elif isinstance(q, str) and q.strip():
                section["questions"].append({"text": q.strip()})

        for a in _ensure_list(sec.get("answers")):
            if isinstance(a, str) and a.strip():
                ak_section["answers"].append(a.strip())
            elif isinstance(a, dict):
                ak_section["answers"].append(a)

        if section["questions"]:
            exam_data["sections"].append(section)
            answer_key["sections"].append(ak_section)

    return exam_data, answer_key


# ── AI prompt construction ───────────────────────────────────────────
def _section_type_rules(exercise_type: str) -> str:
    rules = {
        "multiple_choice": (
            "Each question must have a 'stem', 'options' (list of 4 strings), "
            "and 'answer' (the correct option text)."
        ),
        "true_false": (
            "Provide a short source text in the section 'source_text' field. "
            "Each question is a statement string. "
            "Include 'answers' with True/False for each item."
        ),
        "matching": (
            "Each question is an object with 'left' and 'right'. "
            "Shuffle the right side. Provide the correct mapping in 'answers'."
        ),
        "fill_in_blank": (
            "Each question is a sentence with a blank indicated by '______'. "
            "Provide 'answers' with the correct word/phrase."
        ),
        "short_answer": (
            "Each question is a text string requiring a short written answer. "
            "Provide suggested answers in 'answers'."
        ),
        "reading_comprehension": (
            "Include a 'source_text' field with a reading passage. "
            "Each question is a text string about the passage. "
            "Provide answers in 'answers'."
        ),
        "vocabulary": (
            "Each question tests word knowledge: definitions, synonyms, or context use. "
            "Each question is an object with 'word' and 'task'. "
            "Provide answers in 'answers'."
        ),
        "sentence_transformation": (
            "Each question is an object with 'original' sentence and 'prompt' "
            "(instruction for how to transform). Provide 'answers' with the transformed sentence."
        ),
        "error_correction": (
            "Each question is a sentence containing ONE error. "
            "Provide the corrected sentence in 'answers'."
        ),
        "writing_prompt": (
            "Each question is a writing prompt string. "
            "Answers should be brief evaluation criteria or model points."
        ),
    }
    return rules.get(exercise_type, "")


def _build_exam_prompts(payload: dict) -> tuple[str, str]:
    length_key = payload.get("exam_length", "medium")
    spec = _LENGTH_SPEC.get(length_key, _LENGTH_SPEC["medium"])
    exercise_types = payload.get("exercise_types", [])
    n_sections = min(spec["sections"], len(exercise_types)) if exercise_types else spec["sections"]

    type_details = []
    for et in exercise_types[:n_sections]:
        rule = _section_type_rules(et)
        type_details.append(f"- {et}: {rule}" if rule else f"- {et}")

    system_prompt = (
        "You are an expert curriculum designer with a Doctorate in Education. "
        "Your task is to create a high-quality, classroom-ready exam paper. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "Use the requested plan_language for teacher-facing sections (answers). "
        "Use the requested student_material_language for student-facing sections "
        "(instructions, questions, source_text)."
    )

    user_prompt = f"""
Create a complete exam paper as JSON.

Input:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Exam structure:
- {n_sections} sections
- {spec["questions_min"]}-{spec["questions_max"]} questions per section
- Exercise types to include (in order):
{chr(10).join(type_details)}

Section-specific rules:
{chr(10).join(type_details)}

Design principles:
- Use clear, age-appropriate language for the target learner_stage and level.
- Make the exam progressively harder from section to section.
- Each section must have a clear title (e.g. "Part 1: Multiple Choice").
- Keep content factually accurate and pedagogically sound.
- Exam must be coherent around the given topic.
- Each section includes both questions AND answers.

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
        // format depends on type — see rules above
      ],
      "answers": [
        // correct answers for this section
      ]
    }}
  ]
}}

Provide ALL sections and ALL answers.
"""
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
    payload = {
        "subject": subject,
        "topic": topic,
        "exam_title": exam_title,
        "learner_stage": learner_stage,
        "level_or_band": level_or_band,
        "exam_length": exam_length,
        "exercise_types": exercise_types,
        "instructions": instructions,
        "plan_language": plan_language,
        "student_material_language": student_material_language,
    }

    system_prompt, user_prompt = _build_exam_prompts(payload)
    provider = _lp().get_ai_provider()

    if provider == "gemini":
        provider_order = ["gemini", "openrouter"]
    else:
        provider_order = ["openrouter", "gemini"]

    errors = []
    for p in provider_order:
        try:
            if p == "gemini":
                raw = _lp()._generate_with_gemini(system_prompt, user_prompt)
            else:
                raw = _lp()._generate_with_openrouter(system_prompt, user_prompt)

            parsed = _lp()._extract_json_object_from_text(raw)
            exam_data, answer_key = normalize_exam_output(parsed)
            exam_data["title"] = exam_data["title"] or exam_title or "Exam"
            exam_data["instructions"] = exam_data["instructions"] or instructions
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
    """Return (exam_data, answer_key, warning_or_none)."""
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
        return {}, {}, f"AI cooldown active. Please wait {usage['seconds_left']} seconds."

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
        return {}, {}, str(e)


def reset_exam_builder_state():
    import streamlit as st
    for key in [
        "exam_result", "exam_answer_key", "exam_kept",
        "exam_warning", "quick_exam_subject", "quick_exam_topic",
        "quick_exam_title", "quick_exam_instructions",
    ]:
        st.session_state.pop(key, None)
