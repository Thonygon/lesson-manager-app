import streamlit as st
import json, os, re
from core.i18n import t
from translations import I18N

# 07.6) QUICK WORKSHEET MAKER – AI-only builder
# =========================

AI_WORKSHEET_DAILY_LIMIT = 3
AI_WORKSHEET_COOLDOWN_SECONDS = 10

WORKSHEET_TYPES = [
    "fill_in_the_blanks",
    "multiple_choice",
    "matching",
    "short_answer",
    "true_false",
    "reading_comprehension",
    "error_correction",
    "word_search_vocab",
]

# Re-use subject/stage/level constants from lesson planner
def _lp():
    import helpers.lesson_planner as lp
    return lp


def get_plan_language() -> str:
    return _lp().get_plan_language()


def get_student_material_language(subject: str) -> str:
    return _lp().get_student_material_language(subject)


# ── Normalise AI output ──────────────────────────────────────────────
def normalize_worksheet_output(raw: dict) -> dict:
    out = dict(raw or {})
    str_keys = [
        "title", "subject", "topic", "learner_stage", "level_or_band",
        "worksheet_type", "instructions", "answer_key",
        "plan_language", "student_material_language", "reading_passage",
    ]
    for k in str_keys:
        if k not in out or out[k] is None:
            out[k] = ""
        out[k] = str(out[k]).strip()

    list_keys = ["questions", "vocabulary_bank", "teacher_notes"]
    for k in list_keys:
        if not isinstance(out.get(k), list):
            out[k] = [] if out.get(k) in (None, "") else [str(out.get(k))]

    if out.get("worksheet_type") != "reading_comprehension":
        out["reading_passage"] = ""

    out["title"] = re.sub(r"\s+", " ", str(out.get("title") or "")).strip()
    out["topic"] = re.sub(r"\s+", " ", str(out.get("topic") or "")).strip()

    if out["title"]:
        out["title"] = out["title"][0].upper() + out["title"][1:]
    if out["topic"]:
        out["topic"] = out["topic"][0].upper() + out["topic"][1:]
        
    return out

# ── AI prompt (Ed.D. pedagogy-driven) ────────────────────────────────
def _build_worksheet_prompts(payload: dict) -> tuple[str, str]:
    system_prompt = (
        "You are an expert curriculum designer holding a Doctorate in Education (Ed.D.) "
        "with specialisation in differentiated instruction, formative assessment, and "
        "evidence-based resource design. "
        "Your task is to create a high-quality, classroom-ready worksheet. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "All list fields must be arrays of strings. "
        "Use the requested plan_language for teacher-facing sections (instructions, answer_key, teacher_notes). "
        "Use the requested student_material_language for the questions, reading_passage, and vocabulary_bank."
    )

    user_prompt = f"""
Create one complete, topic-based teaching worksheet as JSON.

Input:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Design principles (Ed.D. methodology):
- Scaffold questions from lower-order to higher-order thinking (Bloom's taxonomy).
- Use clear, age-appropriate language for the target learner_stage and level.
- Include 12-15 questions/items appropriate to the worksheet_type.
- For vocabulary-heavy subjects, include a vocabulary_bank list only when it is genuinely useful.
- Include a reading_passage only for reading_comprehension worksheets.
- For reading_comprehension worksheets, questions must be directly tied to the passage.
- For all other worksheet types, do not create a reading passage.
- Provide concise student-facing instructions in the student_material_language.
- answer_key must contain the correct answers for every question, numbered to match.
- teacher_notes should include 2-3 practical tips for differentiation or extension.
- Keep content factually accurate and pedagogically current.
- Do not invent sections that are not needed for the requested worksheet_type.

Required JSON structure:
{{
  "title": "string",
  "subject": "string",
  "topic": "string",
  "learner_stage": "string",
  "level_or_band": "string",
  "worksheet_type": "string",
  "plan_language": "string",
  "student_material_language": "string",
  "instructions": "string (student-facing)",
  "reading_passage": "string",
  "questions": ["string", ...],
  "vocabulary_bank": ["string", ...],
  "answer_key": "string",
  "teacher_notes": ["string", ...]
}}

Important validation rules:
- reading_passage must be "" unless worksheet_type == "reading_comprehension".
- vocabulary_bank should only be included when it is genuinely useful; otherwise return [].
- Do not invent sections that are not needed for the requested worksheet_type.
"""
    return system_prompt, user_prompt

def generate_ai_worksheet(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    worksheet_type: str,
    topic: str,
    plan_language: str,
    student_material_language: str,
) -> dict:
    payload = {
        "subject": subject,
        "topic": topic,
        "learner_stage": learner_stage,
        "level_or_band": level_or_band,
        "worksheet_type": worksheet_type,
        "plan_language": plan_language,
        "student_material_language": student_material_language,
    }

    system_prompt, user_prompt = _build_worksheet_prompts(payload)
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
            return normalize_worksheet_output(parsed)
        except Exception as e:
            errors.append(f"{p}: {e}")

    raise RuntimeError(" | ".join(errors))


def generate_worksheet_with_limit(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    worksheet_type: str,
    topic: str,
) -> tuple[dict, str | None]:
    """Returns (worksheet_dict, warning_message_or_None)."""
    from helpers.worksheet_storage import get_ai_worksheet_usage_status, log_ai_usage

    usage = get_ai_worksheet_usage_status()

    if usage["used_today"] >= AI_WORKSHEET_DAILY_LIMIT:
        lang = get_plan_language()
        msg = t("ai_limit_reached") if "ai_limit_reached" in I18N.get(lang, {}) else "AI daily limit reached."
        return {}, msg

    if not usage["cooldown_ok"]:
        return {}, f"AI cooldown active. Please wait {usage['seconds_left']} seconds."

    try:
        log_ai_usage(
            request_kind="quick_worksheet_ai",
            status="requested",
            meta={"subject": subject, "topic": topic, "worksheet_type": worksheet_type},
        )

        ws = generate_ai_worksheet(
            subject=subject,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
            worksheet_type=worksheet_type,
            topic=topic,
            plan_language=get_plan_language(),
            student_material_language=get_student_material_language(subject),
        )
        ws = normalize_worksheet_output(ws)

        log_ai_usage(
            request_kind="quick_worksheet_ai",
            status="success",
            meta={"subject": subject, "topic": topic, "worksheet_type": worksheet_type},
        )
        return ws, None

    except Exception as e:
        log_ai_usage(
            request_kind="quick_worksheet_ai",
            status="failed",
            meta={"subject": subject, "topic": topic, "error": str(e)},
        )
        return {}, f"{t('ai_unavailable_fallback')} ({e})"


def reset_worksheet_maker_state() -> None:
    for k in [
        "worksheet_result", "worksheet_kept", "worksheet_warning",
        "ws_subject", "ws_stage", "ws_level", "ws_type", "ws_topic",
    ]:
        st.session_state.pop(k, None)

# =========================
