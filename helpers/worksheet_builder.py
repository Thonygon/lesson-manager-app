from __future__ import annotations

# CLASSIO — Worksheet Builder
# ============================================================
import streamlit as st
import json, os, re
from core.i18n import t
from translations import I18N
from helpers.answer_key_utils import normalize_answer_key_text, split_answer_key_items
from helpers.generation_guidance import (
    build_expert_panel_prompt_blurb,
    build_generation_profile_guidance,
    infer_subject_family,
)
from helpers.visual_support import enrich_worksheet_with_visuals

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


def _subject_key(subject: str) -> str:
    return _clean_str(subject).lower().replace("&", "and")


def _subject_group(subject: str) -> str:
    family = infer_subject_family(subject)
    if family == "study_skills":
        return "general"
    return family or "general"


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


def _worksheet_answer_key_expected_count(ws: dict) -> int | None:
    ws_type = ws.get("worksheet_type", "")
    if ws_type == "multiple_choice":
        return len(ws.get("multiple_choice_items") or [])
    if ws_type == "matching":
        return len(ws.get("matching_pairs") or ws.get("left_items") or [])
    if ws_type == "true_false":
        return len(ws.get("true_false_statements") or ws.get("questions") or [])
    if ws_type in {"fill_in_the_blanks", "short_answer", "reading_comprehension", "error_correction"}:
        return len(ws.get("questions") or [])
    return None


def _sanitize_student_material_fields(ws: dict) -> dict:
    out = dict(ws or {})
    subject_group = _subject_group(out.get("subject", ""))
    lang_code = out.get("student_material_language", "")

    for key in ("instructions", "reading_passage", "source_text", "text", "title", "topic"):
        out[key] = _sanitize_language_text(out.get(key, ""), lang_code, subject_group=subject_group)

    out["questions"] = [
        _sanitize_language_text(item, lang_code, subject_group=subject_group)
        for item in out.get("questions", [])
        if _sanitize_language_text(item, lang_code, subject_group=subject_group)
    ]
    out["true_false_statements"] = [
        _sanitize_language_text(item, lang_code, subject_group=subject_group)
        for item in out.get("true_false_statements", [])
        if _sanitize_language_text(item, lang_code, subject_group=subject_group)
    ]
    out["vocabulary_bank"] = [
        _sanitize_language_text(item, lang_code, subject_group=subject_group)
        for item in out.get("vocabulary_bank", [])
        if _sanitize_language_text(item, lang_code, subject_group=subject_group)
    ]

    sanitized_pairs = []
    for pair in out.get("matching_pairs", []):
        if not isinstance(pair, dict):
            continue
        left = _sanitize_language_text(pair.get("left", ""), lang_code, subject_group=subject_group)
        right = _sanitize_language_text(pair.get("right", ""), lang_code, subject_group=subject_group)
        if left and right:
            sanitized_pairs.append({"left": left, "right": right})
    out["matching_pairs"] = sanitized_pairs

    sanitized_mc = []
    for item in out.get("multiple_choice_items", []):
        if not isinstance(item, dict):
            continue
        stem = _sanitize_language_text(item.get("stem", ""), lang_code, subject_group=subject_group)
        options = [
            _sanitize_language_text(opt, lang_code, subject_group=subject_group)
            for opt in item.get("options", [])
            if _sanitize_language_text(opt, lang_code, subject_group=subject_group)
        ]
        answer = _sanitize_language_text(item.get("answer", ""), lang_code, subject_group=subject_group)
        if stem and len(options) >= 3:
            sanitized_mc.append({"stem": stem, "options": options[:4], "answer": answer})
    out["multiple_choice_items"] = sanitized_mc

    return out


def _repair_worksheet_answer_key(ws: dict) -> dict:
    out = dict(ws or {})
    expected_count = _worksheet_answer_key_expected_count(out)
    out["answer_key"] = normalize_answer_key_text(out.get("answer_key"), expected_count=expected_count)
    return out


def _prune_error_correction_items(ws: dict) -> dict:
    out = dict(ws or {})
    if out.get("worksheet_type") != "error_correction":
        return out

    questions = list(out.get("questions") or [])
    answers = split_answer_key_items(out.get("answer_key"), expected_count=len(questions))
    kept_questions = []
    kept_answers = []

    for question, answer in zip(questions, answers):
        if not _clean_str(question) or not _clean_str(answer):
            continue
        if _normalize_sentence_for_quality(question) == _normalize_sentence_for_quality(answer):
            continue
        kept_questions.append(question)
        kept_answers.append(answer)

    out["questions"] = kept_questions
    out["answer_key"] = "\n".join(kept_answers)
    return out


def _worksheet_quality_issues(ws: dict) -> list[str]:
    ws_type = ws.get("worksheet_type", "")
    issues: list[str] = []
    expected_count = _worksheet_answer_key_expected_count(ws)
    answers = split_answer_key_items(ws.get("answer_key"), expected_count=expected_count) if expected_count else []

    if ws_type == "reading_comprehension":
        if not _clean_str(ws.get("reading_passage", "")):
            issues.append("reading_comprehension requires a reading_passage")
        if expected_count:
            nonempty_answers = sum(bool(_clean_str(answer)) for answer in answers)
            if nonempty_answers < expected_count:
                issues.append("reading_comprehension requires one usable answer per question")

    if ws_type == "error_correction":
        if len(ws.get("questions") or []) < 3:
            issues.append("error_correction needs at least 3 valid incorrect sentences")

    return issues


def _worksheet_profile_guidance(payload: dict) -> str:
    subject_group = _subject_group(payload.get("subject", ""))
    learner_stage = _clean_str(payload.get("learner_stage", "")).lower()
    level_or_band = _clean_str(payload.get("level_or_band", ""))

    lines = [
        "- Student-facing text must stay in the requested student_material_language unless the task explicitly teaches translation.",
        "- Do not mix scripts or inject stray characters from unrelated languages.",
        "- The answer_key must be plain teacher text with one answer per item, never a Python list or quoted array.",
    ]

    shared_guidance = build_generation_profile_guidance(
        payload.get("subject", ""),
        learner_stage,
        level_or_band,
        product="worksheet",
    )
    if shared_guidance:
        lines.extend(shared_guidance.splitlines())

    if subject_group == "language" and learner_stage == "lower_secondary":
        lines.extend([
            "- Prefer short, coherent topics such as school life, hobbies, sports, friends, family, routines, technology, feelings, and weekend plans.",
            "- For reading_comprehension, write one coherent passage with enough concrete detail for the selected level, and keep the answers short and directly checkable.",
            "- For error_correction, every sentence must contain exactly one real error and the corrected answer must not be identical to the prompt sentence.",
        ])

    return "\n".join(lines)


def _ensure_list_of_strings(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_str(x) for x in value if _clean_str(x)]
    s = _clean_str(value)
    return [s] if s else []


def _ensure_matching_pairs(value) -> list[dict]:
    out = []
    if not isinstance(value, list):
        return out

    for item in value:
        if not isinstance(item, dict):
            continue
        left = _clean_str(item.get("left"))
        right = _clean_str(item.get("right"))
        if left and right:
            out.append({"left": left, "right": right})
    return out


def _ensure_multiple_choice_items(value) -> list[dict]:
    out = []
    if not isinstance(value, list):
        return out

    for item in value:
        if not isinstance(item, dict):
            continue

        stem = _strip_mc_stem_prefix(item.get("stem"))
        options = item.get("options") or []

        if not isinstance(options, list):
            options = [_clean_str(options)] if _clean_str(options) else []

        cleaned_options = []
        for opt in options:
            cleaned = _strip_mc_option_prefix(opt)
            if cleaned:
                cleaned_options.append(cleaned)

        answer = _strip_mc_option_prefix(item.get("answer"))

        if stem and len(cleaned_options) >= 3:
            out.append({
                "stem": stem,
                "options": cleaned_options[:4],
                "answer": answer,
            })

    return out


def _normalize_answer_key(value) -> str:
    return normalize_answer_key_text(value)

_MC_OPTION_PREFIX_RE = re.compile(r"^\s*(?:[A-Da-d]|[1-9])[\)\.\-:]\s*")
_MC_STEM_PREFIX_RE = re.compile(r"^\s*\d+[\)\.\-:]\s*")

def _strip_mc_option_prefix(text: str) -> str:
    return _MC_OPTION_PREFIX_RE.sub("", _clean_str(text))

def _strip_mc_stem_prefix(text: str) -> str:
    return _MC_STEM_PREFIX_RE.sub("", _clean_str(text))


_WORKSHEET_INSTRUCTION_FALLBACKS = {
    "fill_in_the_blanks": "Complete each sentence or prompt with the correct word, number, or phrase.",
    "multiple_choice": "Read each question and circle the letter of the best answer.",
    "matching": "Match each item in Column A with the correct item in Column B. Write the correct letter next to each number.",
    "short_answer": "Answer each question in one or two complete sentences.",
    "true_false": "Read the text and decide whether each statement is true or false.",
    "reading_comprehension": "Read the passage carefully and answer the questions using evidence from the text.",
    "error_correction": "Each sentence has one mistake. Find that one mistake and rewrite the full corrected sentence.",
    "word_search_vocab": "Find and circle the hidden words in the grid.",
}

_WORKSHEET_INSTRUCTION_MISMATCHES = {
    "fill_in_the_blanks": ("choose the best answer", "true or false", "column a", "column b", "circle the letter", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "multiple_choice": ("line provided", "given line", "write the answer", "write your answer", "type the answer", "complete each sentence", "escribe la respuesta", "escribe tu respuesta", "completa cada frase", "completa cada oración", "completa cada oracion", "verdadero o falso", "columna a", "columna b", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "matching": ("choose the best answer", "true or false", "complete each sentence", "circle the letter", "elige la opción", "elige la opcion", "verdadero o falso", "completa cada frase", "completa cada oración", "completa cada oracion", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis"),
    "short_answer": ("choose the best answer", "true or false", "column a", "column b", "circle the letter", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "true_false": ("choose the best answer", "column a", "column b", "write the correct letter", "fill in the blank", "choose or circle", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "columna a", "columna b", "escribe la letra correcta", "completa cada frase", "doğru seçeneği", "dogru secenegi", "sütun a", "sutun a", "sütun b", "sutun b"),
    "reading_comprehension": ("choose the best answer", "true or false", "column a", "column b", "circle the letter", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "rodea la letra", "circula la letra", "círcula la letra", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "error_correction": ("choose the best answer", "true or false", "column a", "column b", "elige la opción", "elige la opcion", "opción correcta", "opcion correcta", "verdadero o falso", "columna a", "columna b", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
    "word_search_vocab": ("choose the best answer", "true or false", "column a", "column b", "write your answer", "elige la opción", "elige la opcion", "verdadero o falso", "columna a", "columna b", "escribe tu respuesta", "doğru seçeneği", "dogru secenegi", "doğru yanlış", "dogru yanlis", "sütun a", "sutun a", "sütun b", "sutun b"),
}


def _default_instruction_for_worksheet_type(ws_type: str) -> str:
    key = f"instruction_{ws_type}"
    translated = t(key)
    if translated != key:
        return translated
    return _WORKSHEET_INSTRUCTION_FALLBACKS.get(ws_type, "")


def _worksheet_instruction_needs_reset(ws_type: str, text: str) -> bool:
    text = _clean_str(text)
    if not text:
        return True
    lowered = text.casefold()
    return any(fragment in lowered for fragment in _WORKSHEET_INSTRUCTION_MISMATCHES.get(ws_type, ()))

# ── Normalise AI output ──────────────────────────────────────────────
def normalize_worksheet_output(raw: dict) -> dict:
    out = dict(raw or {})

    str_keys = [
        "title",
        "subject",
        "topic",
        "learner_stage",
        "level_or_band",
        "worksheet_type",
        "instructions",
        "answer_key",
        "plan_language",
        "student_material_language",
        "reading_passage",
        "source_text",
        "text",
    ]
    for k in str_keys:
        out[k] = _clean_str(out.get(k, ""))

    out["questions"] = _ensure_list_of_strings(out.get("questions"))
    out["vocabulary_bank"] = _ensure_list_of_strings(out.get("vocabulary_bank"))
    out["teacher_notes"] = _ensure_list_of_strings(out.get("teacher_notes"))

    out["true_false_statements"] = _ensure_list_of_strings(out.get("true_false_statements"))
    out["left_items"] = _ensure_list_of_strings(out.get("left_items"))
    out["right_items"] = _ensure_list_of_strings(out.get("right_items"))
    out["matching_pairs"] = _ensure_matching_pairs(out.get("matching_pairs"))
    out["multiple_choice_items"] = _ensure_multiple_choice_items(out.get("multiple_choice_items"))
    out["answer_key"] = _normalize_answer_key(out.get("answer_key"))

    if out["title"]:
        out["title"] = out["title"][0].upper() + out["title"][1:]
    if out["topic"]:
        out["topic"] = out["topic"][0].upper() + out["topic"][1:]

    ws_type = out.get("worksheet_type", "")

    if ws_type != "reading_comprehension":
        out["reading_passage"] = ""

    if ws_type != "true_false":
        out["source_text"] = ""
        out["true_false_statements"] = []

    if ws_type != "matching":
        out["matching_pairs"] = []
        out["left_items"] = []
        out["right_items"] = []

    if ws_type != "multiple_choice":
        out["multiple_choice_items"] = []

    if ws_type == "word_search_vocab":
        cleaned_vocab = []
        seen = set()
        for w in out.get("vocabulary_bank", []):
            s = _clean_str(w)
            if not s:
                continue
            key = s.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned_vocab.append(s)

        out["vocabulary_bank"] = cleaned_vocab
        out["questions"] = []
        out["answer_key"] = ""
        out["teacher_notes"] = out.get("teacher_notes", [])

        if _worksheet_instruction_needs_reset(ws_type, out.get("instructions", "")):
            out["instructions"] = _default_instruction_for_worksheet_type(ws_type)

    elif ws_type == "matching":
        if not out["matching_pairs"] and out["left_items"] and out["right_items"]:
            pairs = []
            for left, right in zip(out["left_items"], out["right_items"]):
                left = _clean_str(left)
                right = _clean_str(right)
                if left and right:
                    pairs.append({"left": left, "right": right})
            out["matching_pairs"] = pairs

        out["questions"] = []
        out["reading_passage"] = ""
        out["source_text"] = ""
        out["true_false_statements"] = []
        out["multiple_choice_items"] = []

        if _worksheet_instruction_needs_reset(ws_type, out.get("instructions", "")):
            out["instructions"] = _default_instruction_for_worksheet_type(ws_type)

    elif ws_type == "true_false":
        out["reading_passage"] = ""
        out["matching_pairs"] = []
        out["left_items"] = []
        out["right_items"] = []
        out["questions"] = []
        out["multiple_choice_items"] = []

        if not out["source_text"] and out["text"]:
            out["source_text"] = out["text"]

        if _worksheet_instruction_needs_reset(ws_type, out.get("instructions", "")):
            out["instructions"] = _default_instruction_for_worksheet_type(ws_type)

    elif ws_type == "multiple_choice":
        out["reading_passage"] = ""
        out["matching_pairs"] = []
        out["left_items"] = []
        out["right_items"] = []
        out["source_text"] = ""
        out["true_false_statements"] = []
        out["questions"] = []

        if _worksheet_instruction_needs_reset(ws_type, out.get("instructions", "")):
            out["instructions"] = _default_instruction_for_worksheet_type(ws_type)

    else:
        out["matching_pairs"] = []
        out["left_items"] = []
        out["right_items"] = []
        out["source_text"] = ""
        out["true_false_statements"] = []
        out["multiple_choice_items"] = []
        if _worksheet_instruction_needs_reset(ws_type, out.get("instructions", "")):
            out["instructions"] = _default_instruction_for_worksheet_type(ws_type)

    out = _sanitize_student_material_fields(out)
    out = _repair_worksheet_answer_key(out)
    out = _prune_error_correction_items(out)
    out = _repair_worksheet_answer_key(out)

    return enrich_worksheet_with_visuals(
        out,
        subject=out.get("subject", ""),
        learner_stage=out.get("learner_stage", ""),
        topic=out.get("topic", ""),
    )


# ── AI prompt ────────────────────────────────────────────────────────
def _worksheet_type_rules(worksheet_type: str) -> str:
    rules = {
        "fill_in_the_blanks": """
Worksheet-specific rules for fill_in_the_blanks:
- Include a useful vocabulary_bank.
- Create sentence-completion items with blanks.
- Do not turn this into matching.
- Do not create a source text unless absolutely needed.
- Put the student tasks in "questions".
""",
        "multiple_choice": """
Worksheet-specific rules for multiple_choice:
- Multiple choice is a response format, not always a reading comprehension task.
- Choose the most suitable type of multiple choice based on subject, learner_stage, level, and topic.
- Possible modes include:
  - vocabulary in context,
  - concept understanding,
  - grammar/language use in context,
  - mini-scenario comprehension,
  - short factual/concept checks.
- Do NOT automatically create a full reading passage.
- Only use very short context when helpful.
- Return the items in "multiple_choice_items" as:
  [{"stem":"...", "options":["...", "...", "...", "..."], "answer":"..."}]
- Create 6-10 items depending on learner_stage and level.
- Each item must have 3 or 4 options.
- Options should be plausible and pedagogically meaningful.
- Leave "questions" empty for multiple_choice.
- Leave "reading_passage", "source_text", "true_false_statements", and "matching_pairs" empty.
- The answer_key must list the correct answer for each numbered item.
- In "options", return only the plain option text.
- Do NOT prefix options with A), B), C), D) or numbers.
- Do NOT prefix the stem with 1., 2., 3. or similar.
- The renderer will add numbering and option letters.
""",
        "matching": """
Worksheet-specific rules for matching:
- This must be a real matching task, not sentence completion.
- Do NOT create fill-in-the-blank sentences.
- Create 6-10 clear pairs depending on learner_stage and level.
- Return the pairs in "matching_pairs" as:
  [{"left":"...", "right":"..."}, ...]
- The left side and right side must be short and matchable.
- For lower stages/levels, prefer vocabulary, meanings, labels, short descriptions.
- For higher stages/levels, you may use concept-definition, phrase-meaning, sentence half-completion, term-explanation, cause-effect, character-description, event-consequence.
- Leave "questions" empty for matching.
- Leave "reading_passage" and "source_text" empty.
- The answer_key must show the correct pairs clearly.
- Use polished, publication-ready capitalization and wording for both sides.
- Do NOT prefix left_items or right_items with letters or numbers.
- Do NOT return A., B., C. or 1., 2., 3. inside the item text.
- The renderer will add numbering and lettering.
- If learner_stage is early_primary, lower_primary, primary_lower, or pre_primary, prefer concrete and visually observable items when pedagogically suitable.
""",
        "true_false": """
Worksheet-specific rules for true_false:
- This must be based on a source text.
- Do NOT create isolated standalone sentences without context.
- Create one short source text in "source_text".
- Create 6-10 statements in "true_false_statements".
- The statements must be checked against the source text.
- False statements must be false because of meaning/facts/details, NOT because of grammar mistakes.
- Leave "questions" empty for true_false.
- Leave "reading_passage" empty.
- The answer_key must clearly mark each item as True or False.
- Do NOT prefix statements with numbers or letters.
- Do NOT return 1., 2., 3. or A., B., C. inside the statement text.
- The renderer will add numbering.
- For lower-primary image-friendly topics, you may instead base the statements on one simple observable classroom-safe scene and leave source_text empty.
""",
        "reading_comprehension": """
Worksheet-specific rules for reading_comprehension:
- Create a reading passage in "reading_passage".
- Create comprehension questions in "questions".
- Do not use "source_text" or "true_false_statements" unless worksheet_type is true_false.
- For lower-primary learners, prefer concrete, scene-based passages with visible actions, objects, and settings that can be illustrated.
""",
        "word_search_vocab": """
Worksheet-specific rules for word_search_vocab:
- Create a clean vocabulary_bank only.
- Do not create questions.
- Do not create a reading passage or source text.
- Do not create matching pairs.
- For lower-primary learners, prefer concrete vocabulary that can be represented clearly with pictures.
""",
        "short_answer": """
Worksheet-specific rules for short_answer:
- Put the items in "questions".
- Questions should require short written answers.
- Do NOT prefix statements with numbers or letters.
- Do NOT return 1., 2., 3. or A., B., C. inside the statement text.
- The renderer will add numbering.
""",
        "error_correction": """
Worksheet-specific rules for error_correction:
- Put the items in "questions".
- The task should focus on correcting mistakes.
- Every sentence must contain EXACTLY ONE mistake.
- The mistake can be grammatical, numerical, conceptual, or subject-specific depending on the subject.
- Students must rewrite the whole sentence correctly, not just identify the wrong part.
- The answer key must contain the full corrected sentence.
- Do not confuse this with true_false.
- Do NOT prefix statements with numbers or letters.
- Do NOT return 1., 2., 3. or A., B., C. inside the statement text.
- The renderer will add numbering.
""",
    }
    return rules.get(worksheet_type, "")




def _worksheet_page_plan(worksheet_type: str, learner_stage: str, level_or_band: str) -> dict:
    learner_stage = str(learner_stage or "").strip().lower()
    level_or_band = str(level_or_band or "").strip().upper()

    one_page_stages = {
        "lower_primary",
        "primary_lower",
        "early_primary",
        "pre_primary",
    }

    upper_primary_like = {
        "upper_primary",
        "primary_upper",
    }

    target_pages = 2
    if learner_stage in one_page_stages:
        target_pages = 1
    elif learner_stage in upper_primary_like and level_or_band == "A1":
        target_pages = 1

    if worksheet_type == "multiple_choice":
        item_range = "5-6" if target_pages == 1 else "8-10"
    elif worksheet_type == "true_false":
        item_range = "5-6" if target_pages == 1 else "7-9"
    elif worksheet_type == "matching":
        item_range = "5-6" if target_pages == 1 else "7-8"
    elif worksheet_type == "short_answer":
        item_range = "4-5" if target_pages == 1 else "6-8"
    elif worksheet_type == "reading_comprehension":
        item_range = "4-5" if target_pages == 1 else "5-7"
    elif worksheet_type == "error_correction":
        item_range = "5-6" if target_pages == 1 else "6-8"
    else:
        item_range = "5-6" if target_pages == 1 else "6-8"

    return {
        "target_pages": target_pages,
        "item_range": item_range,
    }


def _build_worksheet_prompts(payload: dict) -> tuple[str, str]:
    worksheet_type = payload.get("worksheet_type", "")
    learner_stage = payload.get("learner_stage", "")
    level_or_band = payload.get("level_or_band", "")
    page_plan = _worksheet_page_plan(worksheet_type, learner_stage, level_or_band)

    system_prompt = (
        f"{build_expert_panel_prompt_blurb('worksheet')} "
        "You are an expert curriculum designer holding a Doctorate in Education (Ed.D.) "
        "with specialisation in differentiated instruction, formative assessment, and "
        "evidence-based resource design. "
        "Your task is to create a high-quality, classroom-ready worksheet. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "Use the requested plan_language for teacher-facing sections (answer_key, teacher_notes). "
        "Use the requested student_material_language for student-facing sections "
        "(instructions, questions, reading_passage, source_text, true_false_statements, vocabulary_bank, matching_pairs values, multiple_choice_items)."
    )

    type_rules = _worksheet_type_rules(worksheet_type)

    user_prompt = f"""
Create one complete, topic-based teaching worksheet as JSON.

Input:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Design principles:
- Use clear, age-appropriate language for the target learner_stage and level.
- Keep the worksheet pedagogically coherent and clearly aligned to the worksheet_type.
- Use publication-ready capitalization, punctuation, grammar, and clean academic formatting.
- Make the student instructions match the actual response mode exactly.
- Do not tell students to write on a line if the task uses options, matching letters, or a grid.
- Examples:
  - multiple_choice: tell students to choose or circle the correct option/letter
  - matching: tell students to match Column A with Column B and write the correct letter
  - true_false: tell students to decide whether each statement is true or false
  - word_search_vocab: tell students to find and circle the hidden words in the grid
- Include a vocabulary_bank only when it is genuinely useful.
- teacher_notes should include 2-3 practical tips for differentiation or extension.
- Keep content factually accurate and pedagogically sound.
- Do not invent unnecessary sections.
- Follow this Classio worksheet layout target:
  - target_pages: {page_plan["target_pages"]}
  - target_item_range: {page_plan["item_range"]}
- Create enough content to fill the target number of pages well, but do not overfill.
- Avoid outputs that would leave the final page half empty.
- Prefer fewer, better-distributed items over too many short items.
- For short_answer and reading_comprehension, create questions that reasonably allow student writing space below each item.

Profile quality guidance:
{_worksheet_profile_guidance(payload)}

{type_rules}

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
  "instructions": "string",
  "reading_passage": "string",
  "source_text": "string",
  "questions": ["string", ...],
  "true_false_statements": ["string", ...],
  "vocabulary_bank": ["string", ...],
  "matching_pairs": [
    {{"left": "string", "right": "string"}}
  ],
  "multiple_choice_items": [
    {{"stem": "string", "options": ["string", "string", "string", "string"], "answer": "string"}}
  ],
  "left_items": ["string", ...],
  "right_items": ["string", ...],
  "answer_key": "string or list of numbered answers",
  "teacher_notes": ["string", ...]
}}

Global validation rules:
- Only reading_comprehension may use "reading_passage".
- Only true_false may use "source_text" and "true_false_statements".
- Only matching may use "matching_pairs", "left_items", or "right_items".
- Only multiple_choice may use "multiple_choice_items".
- matching must not be sentence completion.
- true_false must include a source text.
- fill_in_the_blanks must remain a sentence-completion task.
- word_search_vocab should mainly use vocabulary_bank.
- If a section is not needed for the worksheet_type, return an empty string "" or [].
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
            normalized = normalize_worksheet_output(parsed)
            quality_issues = _worksheet_quality_issues(normalized)
            if quality_issues:
                raise ValueError("; ".join(quality_issues))
            return normalized
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
        return {}, t("ai_unavailable_fallback")


def reset_worksheet_maker_state() -> None:
    for k in [
        "worksheet_result", "worksheet_kept", "worksheet_warning",
        "ws_subject", "ws_stage", "ws_level", "ws_type", "ws_topic",
    ]:
        st.session_state.pop(k, None)
