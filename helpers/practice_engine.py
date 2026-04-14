# CLASSIO — Smart Practice Engine
# ============================================================
# Converts worksheets / exams into a unified exercise schema,
# renders interactive Streamlit widgets, checks answers,
# tracks XP / streaks / ranks, and persists to Supabase.
#
# ============================================================
from __future__ import annotations

import re
import json
import ast
import html
import unicodedata
import streamlit as st
import pandas as pd
from datetime import datetime as _dt, timezone
from typing import Optional

from core.i18n import t
from core.state import get_current_user_id, with_owner
from core.database import get_sb, load_table, clear_app_caches
from helpers.answer_key_utils import clean_answer_key_item, split_answer_key_items
from helpers.visual_support import enrich_worksheet_with_visuals, enrich_exam_with_visuals, render_streamlit_visual_support


# ════════════════════════════════════════════════════════════════
#  GAMIFICATION CONSTANTS
# ════════════════════════════════════════════════════════════════
XP_PER_CORRECT     = 5
XP_PER_ATTEMPT     = 1
XP_PERFECT_BONUS   = 15
XP_STREAK_BONUS    = 2       # per consecutive correct beyond 2

RANKS = [
    (0,     "newcomer",    "🌱"),
    (200,   "learner",     "📖"),
    (1000,  "rising_star", "⭐"),
    (3000,  "achiever",    "🏅"),
    (8000,  "expert",      "🏆"),
    (16000, "master",      "👑"),
    (30000, "legend",      "🔥"),
]


def get_rank(total_xp: int) -> tuple[str, str, int, int]:
    """Return (rank_key, emoji, xp_into_rank, xp_span_of_rank).
    xp_span_of_rank == 0 means max rank reached.
    """
    for i in range(len(RANKS) - 1, -1, -1):
        threshold, key, emoji = RANKS[i]
        if total_xp >= threshold:
            if i < len(RANKS) - 1:
                nxt = RANKS[i + 1][0]
                return key, emoji, total_xp - threshold, nxt - threshold
            return key, emoji, total_xp - threshold, 0
    return RANKS[0][1], RANKS[0][2], 0, RANKS[0][0]


def calculate_session_xp(correct: int, total: int, best_streak: int) -> int:
    """Calculate XP earned for a single practice session."""
    xp = correct * XP_PER_CORRECT + total * XP_PER_ATTEMPT
    if correct == total and total > 0:
        xp += XP_PERFECT_BONUS
    if best_streak > 2:
        xp += (best_streak - 2) * XP_STREAK_BONUS
    return xp


# ════════════════════════════════════════════════════════════════
#  A. UNIFIED EXERCISE SCHEMA
# ════════════════════════════════════════════════════════════════
#
# {
#   "title": str,
#   "instructions": str,
#   "source_type": "worksheet" | "exam",
#   "source_id": int | None,
#   "exercises": [
#     {
#       "type": "multiple_choice" | "true_false" | "fill_in_blank" | ...
#       "title": str,
#       "instructions": str,
#       "source_text": str,          # optional reading passage
#       "questions": [ ... ],        # shape depends on type
#       "answers":   [ ... ],        # one per question
#     }
#   ]
# }
# ════════════════════════════════════════════════════════════════

SUPPORTED_PRACTICE_TYPES = {
    "multiple_choice", "true_false", "fill_in_blank", "fill_in_the_blanks",
    "short_answer", "matching", "reading_comprehension", "error_correction",
    "vocabulary", "sentence_transformation", "writing_prompt",
    "problem_solving", "equation_solving", "show_your_work",
    "table_interpretation", "word_problems",
    "data_analysis", "classification", "process_explanation",
    "hypothesis_and_conclusion", "diagram_questions",
    "theory_questions", "symbol_identification", "rhythm_counting",
    "terminology", "composer_period_matching", "word_search_vocab",
}

# Backward-compatible alias used by the student practice page.
PHASE1_TYPES = SUPPORTED_PRACTICE_TYPES


# ── B. Converters ────────────────────────────────────────────────

def worksheet_to_exercises(ws: dict, *, row_id: int | None = None) -> dict:
    """Convert a saved worksheet dict into the unified exercise schema."""
    ws = enrich_worksheet_with_visuals(
        ws,
        subject=ws.get("subject", ""),
        learner_stage=ws.get("learner_stage", ""),
        topic=ws.get("topic", ""),
    )
    ws_type = str(ws.get("worksheet_type") or "").strip()
    title = str(ws.get("title") or "").strip()
    instructions = str(ws.get("instructions") or "").strip()
    visual_support = (ws.get("visual_supports") or [None])[0]

    exercises: list[dict] = []

    if ws_type == "multiple_choice":
        items = ws.get("multiple_choice_items") or []
        questions = []
        answers = []
        for item in items:
            if isinstance(item, dict):
                stem = str(item.get("stem") or item.get("question") or "").strip()
                options = item.get("options") or []
                answer = str(item.get("answer") or "").strip()
                if stem and options:
                    questions.append({"stem": stem, "options": options})
                    answers.append(answer)
        if questions:
            exercises.append({
                "type": "multiple_choice",
                "title": title,
                "instructions": instructions,
                "visual_support": visual_support,
                "questions": questions,
                "answers": answers,
            })

    elif ws_type == "true_false":
        stmts = ws.get("true_false_statements") or ws.get("questions") or []
        source_text = str(ws.get("source_text") or ws.get("text") or "").strip()
        questions = []
        for s in stmts:
            txt = s if isinstance(s, str) else str(s.get("text", s) if isinstance(s, dict) else s)
            if txt.strip():
                questions.append({"text": txt.strip()})
        # parse answer key
        raw_ak = ws.get("answer_key") or ""
        answers = _parse_flat_answer_key(raw_ak, len(questions))
        if questions:
            exercises.append({
                "type": "true_false",
                "title": title,
                "instructions": instructions,
                "source_text": source_text,
                "visual_support": visual_support,
                "questions": questions,
                "answers": answers,
            })

    elif ws_type == "fill_in_the_blanks":
        qs = ws.get("questions") or []
        questions = []
        for q in qs:
            txt = q if isinstance(q, str) else str(q.get("text", q) if isinstance(q, dict) else q)
            if txt.strip():
                questions.append({"text": txt.strip()})
        raw_ak = ws.get("answer_key") or ""
        answers = _parse_flat_answer_key(raw_ak, len(questions))
        if questions:
            exercises.append({
                "type": "fill_in_blank",
                "title": title,
                "instructions": instructions,
                "visual_support": visual_support,
                "questions": questions,
                "answers": answers,
            })

    elif ws_type == "short_answer":
        qs = ws.get("questions") or []
        questions = []
        for q in qs:
            txt = q if isinstance(q, str) else str(q.get("text", q) if isinstance(q, dict) else q)
            if txt.strip():
                questions.append({"text": txt.strip()})
        raw_ak = ws.get("answer_key") or ""
        answers = _parse_flat_answer_key(raw_ak, len(questions))
        if questions:
            exercises.append({
                "type": "short_answer",
                "title": title,
                "instructions": instructions,
                "visual_support": visual_support,
                "questions": questions,
                "answers": answers,
            })

    elif ws_type == "matching":
        pairs = ws.get("matching_pairs") or []
        if not pairs:
            left = ws.get("left_items") or []
            right = ws.get("right_items") or []
            pairs = [{"left": l, "right": r} for l, r in zip(left, right) if l and r]
        if pairs:
            questions = []
            answers = []
            for p in pairs:
                l = _strip_leading_number(str(p.get("left", "")))
                r = _strip_leading_number(str(p.get("right", "")))
                if l:
                    questions.append({"left": l, "right": r})
                    answers.append(r)
            if questions:
                exercises.append({
                    "type": "matching",
                    "title": title,
                    "instructions": instructions,
                    "visual_support": visual_support,
                    "questions": questions,
                    "answers": answers,
                })

    elif ws_type == "reading_comprehension":
        passage = str(ws.get("reading_passage") or ws.get("source_text") or ws.get("text") or "").strip()
        qs = ws.get("questions") or []
        questions = []
        for q in qs:
            txt = q if isinstance(q, str) else str(q.get("text", q) if isinstance(q, dict) else q)
            if txt.strip():
                questions.append({"text": txt.strip()})
        raw_ak = ws.get("answer_key") or ""
        answers = _parse_flat_answer_key(raw_ak, len(questions))
        if questions:
            exercises.append({
                "type": "reading_comprehension",
                "title": title,
                "instructions": instructions,
                "source_text": passage,
                "visual_support": visual_support,
                "questions": questions,
                "answers": answers,
            })

    elif ws_type == "error_correction":
        qs = ws.get("questions") or []
        questions = []
        for q in qs:
            txt = q if isinstance(q, str) else str(q.get("text", q) if isinstance(q, dict) else q)
            if txt.strip():
                questions.append({"text": txt.strip()})
        raw_ak = ws.get("answer_key") or ""
        answers = _parse_flat_answer_key(raw_ak, len(questions))
        # Strip trailing parenthetical explanations like "(don't → doesn't)"
        answers = [re.sub(r"\s*\(.*?\)\s*$", "", a).strip() for a in answers]
        if questions:
            exercises.append({
                "type": "error_correction",
                "title": title,
                "instructions": instructions,
                "visual_support": visual_support,
                "questions": questions,
                "answers": answers,
            })

    elif ws_type == "word_search_vocab":
        try:
            from helpers.worksheet_storage import _generate_wordsearch_grid, _normalize_wordsearch_words
        except Exception:
            _generate_wordsearch_grid = None
            _normalize_wordsearch_words = None

        words = ws.get("vocabulary_bank") or []
        normalized_words = _normalize_wordsearch_words(words) if _normalize_wordsearch_words else [str(w).strip().upper() for w in words if str(w).strip()]
        if normalized_words and _generate_wordsearch_grid:
            seed = "|".join(normalized_words)
            grid, placed_words, placements = _generate_wordsearch_grid(normalized_words, seed=seed)
            if grid and placed_words:
                exercises.append({
                    "type": "word_search_vocab",
                    "title": title,
                    "instructions": instructions,
                    "visual_support": visual_support,
                    "questions": [{
                        "grid": grid,
                        "words": placed_words,
                        "placements": placements or [],
                    }],
                    "answers": [placed_words],
                })

    else:
        # Unsupported worksheet types produce no exercises
        pass

    return {
        "title": title,
        "instructions": instructions,
        "source_type": "worksheet",
        "source_id": row_id,
        "exercises": exercises,
    }


def exam_to_exercises(exam_data: dict, answer_key: dict, *, row_id: int | None = None) -> dict:
    """Convert a saved exam dict + answer_key into the unified exercise schema."""
    exam_data = enrich_exam_with_visuals(
        exam_data,
        subject=exam_data.get("subject", ""),
        learner_stage=exam_data.get("learner_stage", ""),
        topic=exam_data.get("topic", ""),
    )
    exercises: list[dict] = []

    sections = exam_data.get("sections") or []
    ak_sections = (answer_key or {}).get("sections") or []

    for idx, sec in enumerate(sections):
        sec_type = str(sec.get("type") or "").strip()
        if sec_type not in SUPPORTED_PRACTICE_TYPES:
            continue
        if sec_type == "fill_in_the_blanks":
            sec_type = "fill_in_blank"
        ak = ak_sections[idx] if idx < len(ak_sections) else {}
        ex = {
            "type": sec_type,
            "title": str(sec.get("title") or "").strip(),
            "instructions": str(sec.get("instructions") or "").strip(),
            "questions": sec.get("questions") or [],
            "answers": ak.get("answers") or [],
        }
        ex["answers"] = _recover_exam_section_answers(sec_type, ex["questions"], ex["answers"])
        if sec_type == "true_false":
            recovered_answers = []
            raw_questions = sec.get("questions") or []
            raw_answers = list(ex.get("answers") or [])
            for q_idx, raw_question in enumerate(raw_questions):
                answer_value = raw_answers[q_idx] if q_idx < len(raw_answers) else ""
                if _canonical_true_false(_comparison_answer_text(answer_value)):
                    recovered_answers.append(answer_value)
                    continue

                if isinstance(raw_question, dict):
                    fallback_answer = (
                        raw_question.get("answer")
                        or raw_question.get("correct_answer")
                        or raw_question.get("correct")
                        or raw_question.get("value")
                    )
                    if _canonical_true_false(_comparison_answer_text(fallback_answer)):
                        recovered_answers.append(fallback_answer)
                        continue

                recovered_answers.append(answer_value)
            ex["answers"] = recovered_answers
        if sec.get("visual_support"):
            ex["visual_support"] = sec.get("visual_support")
        if sec_type == "matching":
            ex["answers"] = [
                _matching_answer_from_question(
                    ex["questions"][ans_idx] if ans_idx < len(ex["questions"]) else {},
                    answer,
                )
                for ans_idx, answer in enumerate(ex["answers"])
            ]
        elif sec_type == "vocabulary":
            vocab_questions = []
            raw_questions = sec.get("questions") or []
            raw_answers = ak.get("answers") or []
            answer_pool = []
            for ans in raw_answers:
                answer_text = _display_answer_text(ans).strip()
                if answer_text and answer_text not in answer_pool:
                    answer_pool.append(answer_text)

            for q_idx, raw_question in enumerate(raw_questions):
                q_data = raw_question if isinstance(raw_question, dict) else {"text": raw_question}
                correct_raw = raw_answers[q_idx] if q_idx < len(raw_answers) else ""
                correct_text = _display_answer_text(correct_raw).strip()
                options = [correct_text] if correct_text else []

                for candidate in answer_pool:
                    if candidate and candidate != correct_text and candidate not in options:
                        options.append(candidate)
                    if len(options) >= 4:
                        break

                # Fallback distractors if the section does not have enough unique answers.
                if len(options) < 4:
                    prompt_seed = _strip_leading_number(_question_prompt_text("vocabulary", q_data))
                    fallback_candidates = [
                        _sentence_case_fragment(prompt_seed),
                        f"{_sentence_case_fragment(prompt_seed)}?",
                        f"{_sentence_case_fragment(prompt_seed)}.",
                        f"{_sentence_case_fragment(prompt_seed)}!",
                    ]
                    for candidate in fallback_candidates:
                        if candidate and candidate != correct_text and candidate not in options:
                            options.append(candidate)
                        if len(options) >= 4:
                            break

                vocab_question = dict(q_data)
                vocab_question["options"] = options[:4]
                vocab_questions.append(vocab_question)

            ex["questions"] = vocab_questions
            ex["answers"] = [_display_answer_text(ans).strip() for ans in raw_answers]
        if sec.get("source_text"):
            ex["source_text"] = str(sec["source_text"]).strip()
        exercises.append(ex)

    return {
        "title": str(exam_data.get("title") or "").strip(),
        "instructions": str(exam_data.get("instructions") or "").strip(),
        "source_type": "exam",
        "source_id": row_id,
        "exercises": exercises,
    }


def normalize_exercise_data_for_web(exercise_data: dict) -> dict:
    """Upgrade legacy exercise snapshots to the current web-friendly schema."""
    data = dict(exercise_data or {})
    exercises = []

    for exercise in data.get("exercises") or []:
        ex = dict(exercise or {})
        ex_type = str(ex.get("type") or "").strip()

        if ex_type == "matching":
            raw_questions = ex.get("questions") or []
            raw_answers = ex.get("answers") or []
            ex["answers"] = [
                _matching_answer_from_question(
                    raw_questions[ans_idx] if ans_idx < len(raw_questions) else {},
                    answer,
                )
                for ans_idx, answer in enumerate(raw_answers)
            ]

        if ex_type == "vocabulary":
            raw_questions = ex.get("questions") or []
            raw_answers = ex.get("answers") or []
            answer_pool = []
            for ans in raw_answers:
                answer_text = _display_answer_text(ans).strip()
                if answer_text and answer_text not in answer_pool:
                    answer_pool.append(answer_text)

            normalized_questions = []
            for q_idx, raw_question in enumerate(raw_questions):
                q_data = raw_question if isinstance(raw_question, dict) else {"text": raw_question}
                if q_data.get("options"):
                    normalized_questions.append(q_data)
                    continue

                correct_raw = raw_answers[q_idx] if q_idx < len(raw_answers) else ""
                correct_text = _display_answer_text(correct_raw).strip()
                options = [correct_text] if correct_text else []

                for candidate in answer_pool:
                    if candidate and candidate != correct_text and candidate not in options:
                        options.append(candidate)
                    if len(options) >= 4:
                        break

                prompt_seed = _strip_leading_number(_question_prompt_text("vocabulary", q_data))
                fallback_candidates = [
                    _sentence_case_fragment(prompt_seed),
                    f"{_sentence_case_fragment(prompt_seed)}?",
                    f"{_sentence_case_fragment(prompt_seed)}.",
                    f"{_sentence_case_fragment(prompt_seed)}!",
                ]
                for candidate in fallback_candidates:
                    if candidate and candidate != correct_text and candidate not in options:
                        options.append(candidate)
                    if len(options) >= 4:
                        break

                normalized_question = dict(q_data)
                normalized_question["options"] = options[:4]
                normalized_questions.append(normalized_question)

            ex["questions"] = normalized_questions
            ex["answers"] = [_display_answer_text(ans).strip() for ans in raw_answers]

        exercises.append(ex)

    data["exercises"] = exercises
    return data


# ── helpers ──────────────────────────────────────────────────────────

def _recover_exam_section_answers(sec_type: str, questions: list, raw_answers: list) -> list:
    recovered = list(raw_answers or [])
    for q_idx, question in enumerate(questions or []):
        existing = recovered[q_idx] if q_idx < len(recovered) else ""
        if _comparison_answer_text(existing).strip():
            continue
        fallback = ""
        if isinstance(question, dict):
            fallback = (
                question.get("answer")
                or question.get("correct_answer")
                or question.get("correct")
                or question.get("value")
                or question.get("correct_option")
                or ""
            )
        if q_idx < len(recovered):
            recovered[q_idx] = fallback
        else:
            recovered.append(fallback)
    return recovered


def _matching_answer_from_question(question, fallback) -> str:
    fallback_text = _comparison_answer_text(fallback)
    question = _parse_legacy_pair_value(question)
    if isinstance(question, dict):
        right_text = _matching_choice_value(question)
        if right_text:
            if not fallback_text:
                return right_text
            if re.fullmatch(r"[A-Za-z]", str(fallback_text).strip()):
                return right_text
    return fallback_text


def _matching_choices_from_questions(questions: list) -> list[str]:
    choices: list[str] = []
    for question in questions or []:
        choice = _matching_choice_value(question)
        if choice and choice not in choices:
            choices.append(choice)
    return choices


def _matching_options_need_refresh(options: list) -> bool:
    cleaned = [str(opt or "").strip() for opt in options or [] if str(opt or "").strip()]
    if not cleaned:
        return True
    return all(re.fullmatch(r"[A-Za-z]", item) for item in cleaned)


def _localized_true_false_display(value) -> str:
    canonical = _canonical_true_false(_comparison_answer_text(value))
    if canonical == "true":
        return t("quick_exam_true_label")
    if canonical == "false":
        return t("quick_exam_false_label")
    return _display_answer_text(value)

def _parse_flat_answer_key(raw, n: int) -> list[str]:
    """Parse a worksheet answer_key (string or list) into a list of n answers."""
    return split_answer_key_items(raw, expected_count=n)


def _fold_text(value) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_answer(s: str) -> str:
    """Normalize an answer for comparison across multilingual open-text inputs."""
    text = (
        str(s or "")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
    )
    text = _fold_text(text).lower()
    text = re.sub(r"[^\w\s'/-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_error_correction_answer(s: str) -> str:
    """Normalize a rewritten correction while keeping the wording strict."""
    text = _fold_text(str(s or "").strip()).lower()
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
    )
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,;:.!?])", r"\1", text)
    text = re.sub(r"[.!?]+$", "", text).strip()
    return text


def _answer_words(s: str) -> set[str]:
    """Extract meaningful words from a normalized answer, dropping stop words."""
    _STOP = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "it", "its", "to", "of", "in", "on", "at", "for", "and", "or", "but",
        "by", "as", "with", "from", "that", "this", "also", "very", "than",
        "not", "no", "do", "does", "did", "has", "have", "had", "will",
        "can", "could", "would", "should", "may", "might",
    }
    words = set(re.findall(r"[a-z0-9]+", _normalize_answer(s)))
    return words - _STOP


def _strip_leading_number(text: str) -> str:
    """Remove leading numbering like '1. ', '2) ', '3- ', 'A. ', 'B) ' from text."""
    return re.sub(r"^[A-Za-z0-9]+[\.\)\-]\s*", "", text.strip())


def _parse_legacy_pair_value(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = ast.literal_eval(stripped)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
    return value


def _extract_legacy_pair_side(value, *, prefer: str = "value") -> str:
    value = _parse_legacy_pair_value(value)
    if isinstance(value, dict):
        if prefer in value:
            return _sentence_case_fragment(value.get(prefer, ""))
        if len(value) == 1:
            only_key, only_val = next(iter(value.items()))
            return _sentence_case_fragment(only_val if prefer == "value" else only_key)
        fallback = value.get("text", value.get("answer", str(value)))
        return _sentence_case_fragment(fallback)
    return _sentence_case_fragment(value)


def _matching_choice_value(question) -> str:
    question = _parse_legacy_pair_value(question)
    if isinstance(question, dict):
        right = question.get("right", "")
        extracted = _extract_legacy_pair_side(right, prefer="value")
        if extracted:
            return extracted
    return ""


def _display_answer_text(value) -> str:
    value = _parse_legacy_pair_value(value)
    if isinstance(value, dict):
        if "left" in value and "right" in value:
            return f"{_extract_legacy_pair_side(value.get('left', ''), prefer='key')} -> {_extract_legacy_pair_side(value.get('right', ''), prefer='value')}"
        if "word" in value and "answer" in value:
            return f"{_sentence_case_fragment(value.get('word', ''))}: {_strip_leading_number(str(value.get('answer', '')))}"
        if "original" in value and "answer" in value:
            return f"{_strip_leading_number(str(value.get('original', '')))} -> {_strip_leading_number(str(value.get('answer', '')))}"
        if len(value) == 1:
            only_key, only_val = next(iter(value.items()))
            return f"{_sentence_case_fragment(only_key)}: {_strip_leading_number(str(only_val))}"
        return clean_answer_key_item(value.get("answer", value.get("text", str(value))))
    return clean_answer_key_item(value)


def _comparison_answer_text(value) -> str:
    value = _parse_legacy_pair_value(value)
    if isinstance(value, dict):
        if "right" in value:
            return clean_answer_key_item(_extract_legacy_pair_side(value.get("right", ""), prefer="value"))
        if "answer" in value:
            return clean_answer_key_item(value.get("answer", ""))
        if "text" in value:
            return clean_answer_key_item(value.get("text", ""))
        if len(value) == 1:
            _only_key, only_val = next(iter(value.items()))
            return clean_answer_key_item(only_val)
    return clean_answer_key_item(value)


def _sentence_case_fragment(value) -> str:
    value = _parse_legacy_pair_value(value)
    if isinstance(value, dict) and len(value) == 1:
        only_key, _only_val = next(iter(value.items()))
        text = _strip_leading_number(str(only_key or ""))
    else:
        text = _strip_leading_number(str(value or ""))
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


def _display_choice_text(value) -> str:
    if not value:
        return ""
    value = _parse_legacy_pair_value(value)
    if isinstance(value, dict):
        if len(value) == 1:
            only_key, only_val = next(iter(value.items()))
            return f"{_sentence_case_fragment(only_key)}: {_strip_leading_number(str(only_val))}"
        return _display_answer_text(value)
    return _sentence_case_fragment(value)


def _strip_vocab_answer_leak(prompt: str, correct=None, options: list | None = None) -> str:
    text = _strip_leading_number(str(prompt or "")).strip()
    if not text:
        return ""

    leading, sep, remainder = text.partition(":")
    if not sep:
        return text

    lead_norm = _normalize_answer(leading)
    candidate_pool = []

    if correct is not None:
        correct_text = _display_answer_text(correct).strip()
        if correct_text:
            candidate_pool.append(correct_text)

    for option in options or []:
        option_text = _display_choice_text(option).strip()
        if option_text:
            candidate_pool.append(option_text)

    for candidate in candidate_pool:
        if _normalize_answer(candidate) == lead_norm:
            cleaned = remainder.strip()
            return cleaned or text

    return text


def _question_prompt_text(ex_type: str, question) -> str:
    question = _parse_legacy_pair_value(question)
    if isinstance(question, dict):
        if ex_type == "multiple_choice":
            return str(question.get("stem", question.get("text", "")))
        if ex_type == "matching":
            left = question.get("left", question.get("text", ""))
            return _extract_legacy_pair_side(left, prefer="key")
        if ex_type == "vocabulary":
            word = _sentence_case_fragment(question.get("word", ""))
            task = _strip_leading_number(str(question.get("task", "")))
            text = _strip_leading_number(str(question.get("text", "")))
            if word and task:
                return f"{word}: {task}"
            if task:
                return task
            if text:
                return text
            return word
        if ex_type == "sentence_transformation":
            original = _strip_leading_number(str(question.get("original", "")))
            prompt = _strip_leading_number(str(question.get("prompt", "")))
            return f"{original} ({prompt})" if prompt else original
        return str(question.get("text", question))
    return str(question)


def _is_long_response_type(ex_type: str) -> bool:
    return ex_type in {
        "short_answer", "reading_comprehension", "writing_prompt",
        "problem_solving", "show_your_work", "table_interpretation",
        "word_problems", "data_analysis", "classification",
        "process_explanation", "hypothesis_and_conclusion",
        "diagram_questions", "theory_questions", "symbol_identification",
        "rhythm_counting", "terminology", "composer_period_matching",
    }


def _is_short_text_type(ex_type: str) -> bool:
    return ex_type in {
        "fill_in_blank", "fill_in_the_blanks", "error_correction",
        "vocabulary", "sentence_transformation", "equation_solving",
    }


def _canonical_true_false(value: str) -> str:
    text = _normalize_answer(value)
    truthy = {
        _normalize_answer(t("quick_exam_true_label")),
        "true", "t", "yes", "dogru", "doğru", "verdadero",
    }
    falsy = {
        _normalize_answer(t("quick_exam_false_label")),
        "false", "f", "no", "yanlis", "yanlış", "falso",
    }
    if text in truthy:
        return "true"
    if text in falsy:
        return "false"
    return text


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", str(text or "")))


def _sentence_count(text: str) -> int:
    parts = [p.strip() for p in re.split(r"[.!?]+", str(text or "")) if p.strip()]
    return len(parts)


def _writing_prompt_feedback(student: str, correct) -> dict:
    expected = _comparison_answer_text(correct)
    expected_display = _display_answer_text(correct)
    student_norm = _normalize_answer(student)
    expected_norm = _normalize_answer(expected)

    if not student_norm:
        return {
            "is_correct": False,
            "score": 0.0,
            "expected": expected_display,
            "feedback_lines": [t("writing_feedback_missing_response")],
        }

    expected_words = _answer_words(expected_norm)
    student_words = _answer_words(student_norm)
    overlap_ratio = (len(expected_words & student_words) / len(expected_words)) if expected_words else 0.0
    words = _word_count(student)
    sentences = _sentence_count(student)

    content_score = 0.0
    if overlap_ratio >= 0.75:
        content_score = 0.6
    elif overlap_ratio >= 0.5:
        content_score = 0.45
    elif overlap_ratio >= 0.3:
        content_score = 0.3
    elif overlap_ratio > 0:
        content_score = 0.15

    development_score = 0.0
    if words >= 45 or sentences >= 3:
        development_score = 0.25
    elif words >= 25 or sentences >= 2:
        development_score = 0.15
    elif words >= 10:
        development_score = 0.05

    structure_score = 0.0
    if sentences >= 3:
        structure_score = 0.15
    elif sentences >= 2:
        structure_score = 0.1
    elif words >= 12:
        structure_score = 0.05

    score = round(min(1.0, content_score + development_score + structure_score), 2)
    is_correct = score >= 0.6

    if overlap_ratio >= 0.6:
        content_msg = t("writing_feedback_content_strong")
    elif overlap_ratio >= 0.3:
        content_msg = t("writing_feedback_content_partial")
    else:
        content_msg = t("writing_feedback_content_missing")

    if words >= 25:
        length_msg = t("writing_feedback_length_good")
    elif words >= 10:
        length_msg = t("writing_feedback_length_ok")
    else:
        length_msg = t("writing_feedback_length_short")

    if sentences >= 2:
        structure_msg = t("writing_feedback_structure_good")
    else:
        structure_msg = t("writing_feedback_structure_needs")

    return {
        "is_correct": is_correct,
        "score": score,
        "expected": expected_display,
        "feedback_lines": [content_msg, length_msg, structure_msg],
    }


def _normalize_wordsearch_words(value) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                value = parsed
        except Exception:
            value = [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, list):
        return []
    return [
        re.sub(r"\s+", "", str(word or "")).upper()
        for word in value
        if re.sub(r"\s+", "", str(word or "")).strip()
    ]


def _wordsearch_feedback(student: str, correct) -> dict:
    expected_words = _normalize_wordsearch_words(correct)
    found_words = _normalize_wordsearch_words(student)
    if not expected_words:
        return {
            "is_correct": False,
            "score": 0.0,
            "expected": "",
            "feedback_lines": [],
            "correct_count": 0,
            "total_count": 0,
        }

    expected_set = set(expected_words)
    found_set = set(found_words)
    correct_count = len(expected_set & found_set)
    total_count = len(expected_set)
    score = round(correct_count / total_count, 2) if total_count else 0.0
    missing = [word for word in expected_words if word not in found_set]

    return {
        "is_correct": correct_count == total_count,
        "score": score,
        "expected": ", ".join(expected_words),
        "feedback_lines": [
            t("word_search_feedback_progress", found=correct_count, total=total_count)
        ] + ([t("word_search_feedback_missing", words=", ".join(missing[:6]))] if missing else []),
        "correct_count": correct_count,
        "total_count": total_count,
    }


def _evaluate_answer(ex_type: str, student: str, correct) -> dict:
    if ex_type == "writing_prompt":
        return _writing_prompt_feedback(student, correct)
    if ex_type == "word_search_vocab":
        return _wordsearch_feedback(student, correct)

    is_correct = _check_answer(ex_type, student, correct)
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "expected": _display_answer_text(correct),
        "feedback_lines": [],
    }


def _clear_practice_widget_state(session_key: str) -> None:
    prefix = f"{session_key}_"
    for key in list(st.session_state.keys()):
        if key.startswith(prefix):
            st.session_state.pop(key, None)


# ════════════════════════════════════════════════════════════════
#  C. INTERACTIVE STREAMLIT RENDERER
# ════════════════════════════════════════════════════════════════

def render_practice_session(exercise_data: dict, session_key: str = "practice") -> None:
    """Render a complete interactive practice session.

    Returns a result dict on submission, None otherwise.
    Tracks streaks during grading for gamification.
    """
    exercises = exercise_data.get("exercises") or []
    if not exercises:
        st.info(t("no_exercises_available"))
        return None

    title = exercise_data.get("title") or t("smart_practice")
    instructions = exercise_data.get("instructions") or ""
    st.markdown(f"### {title}")

    if instructions:
        st.caption(instructions)

    # Session-state keys
    answers_key   = f"_practice_answers_{session_key}"
    submitted_key = f"_practice_submitted_{session_key}"

    if answers_key not in st.session_state:
        st.session_state[answers_key] = {}
    if submitted_key not in st.session_state:
        st.session_state[submitted_key] = False

    resume_answers = st.session_state.pop("_practice_resume_answers", None)
    if isinstance(resume_answers, dict):
        st.session_state[answers_key] = dict(resume_answers)
        for key, value in resume_answers.items():
            st.session_state[key] = value

    is_submitted    = st.session_state[submitted_key]
    student_answers = st.session_state[answers_key]

    total_q    = 0
    correct_q  = 0
    cur_streak = 0
    best_streak = 0

    for ex_idx, exercise in enumerate(exercises):
        ex_type    = exercise.get("type", "")
        ex_title   = exercise.get("title", "")
        ex_instr   = exercise.get("instructions", "")
        source_txt = exercise.get("source_text", "")
        questions  = exercise.get("questions") or []
        correct_answers = exercise.get("answers") or []

        # Skip duplicate title/instructions when single exercise matches outer
        if ex_title and not (len(exercises) == 1 and ex_title == title):
            st.markdown(f"#### {ex_title}")
        if ex_instr and not (len(exercises) == 1 and ex_instr == instructions):
            st.caption(ex_instr)
        render_streamlit_visual_support(exercise.get("visual_support"))
        if source_txt:
            with st.expander("📖 " + t("reading_passage"), expanded=True):
                st.write(source_txt)

        # For matching: build a shuffled list of right-side options (stable per session)
        extra = {}
        if ex_type == "matching":
            shuffle_key = f"_matching_shuffle_{session_key}_{ex_idx}"
            if (
                shuffle_key not in st.session_state
                or _matching_options_need_refresh(st.session_state.get(shuffle_key) or [])
            ):
                import random as _rnd
                opts = _matching_choices_from_questions(questions)
                if not opts:
                    opts = list(correct_answers)
                _rnd.shuffle(opts)
                st.session_state[shuffle_key] = opts
            extra["shuffled_options"] = st.session_state[shuffle_key]

        if ex_type == "word_search_vocab":
            q_key = f"{session_key}_{ex_idx}_0"
            correct = correct_answers[0] if correct_answers else []
            evaluation = None
            student_ans = _render_single_question(
                ex_type, questions[0] if questions else {}, correct, q_key, 0, is_submitted, extra=extra,
            )
            student_answers[q_key] = student_ans

            if is_submitted:
                evaluation = _evaluate_answer(ex_type, student_ans, correct)
                found_count = int(evaluation.get("correct_count", 0))
                total_count = int(evaluation.get("total_count", len(_normalize_wordsearch_words(correct))))
                total_q += total_count
                correct_q += found_count
                if found_count:
                    cur_streak += found_count
                    best_streak = max(best_streak, cur_streak)
                else:
                    cur_streak = 0

                if evaluation["is_correct"]:
                    st.success(f"✓ {t('word_search_completed')}")
                else:
                    st.warning(
                        f"{t('word_search_keep_searching')} ({round(evaluation['score'] * 100)}%)"
                    )

                for line in evaluation.get("feedback_lines", []):
                    st.caption(line)

            st.divider()
            continue

        for q_idx, question in enumerate(questions):
            q_key   = f"{session_key}_{ex_idx}_{q_idx}"
            correct = correct_answers[q_idx] if q_idx < len(correct_answers) else ""
            total_q += 1

            student_ans = _render_single_question(
                ex_type, question, correct, q_key, q_idx, is_submitted,
                extra=extra,
            )
            student_answers[q_key] = student_ans

            if is_submitted:
                evaluation = _evaluate_answer(ex_type, student_ans, correct)
                if ex_type == "true_false" and not _canonical_true_false(_comparison_answer_text(correct)):
                    cur_streak = 0
                    st.warning(t("true_false_feedback_missing_answer_key"))
                elif evaluation["is_correct"]:
                    correct_q  += 1
                    cur_streak += 1
                    best_streak = max(best_streak, cur_streak)
                    if ex_type == "writing_prompt":
                        st.success(
                            f"✓ {t('writing_feedback_pass')} ({round(evaluation['score'] * 100)}%)"
                        )
                    else:
                        st.success(f"✓ {t('correct')}")
                else:
                    cur_streak = 0
                    if ex_type == "writing_prompt":
                        st.warning(
                            f"{t('writing_feedback_revise')} ({round(evaluation['score'] * 100)}%)"
                        )
                    else:
                        st.error(f"✗ {t('incorrect')} — {evaluation['expected']}")

                if ex_type == "writing_prompt":
                    for line in evaluation.get("feedback_lines", []):
                        st.caption(line)
                    with st.expander(t("writing_feedback_model_points"), expanded=False):
                        st.write(evaluation["expected"])

        st.divider()

    # ── Submit / Results ─────────────────────────────────────────
    if not is_submitted:
        # Check if all questions are answered
        all_answered = True
        for ex_idx, exercise in enumerate(exercises):
            questions = exercise.get("questions") or []
            for q_idx in range(len(questions)):
                q_key = f"{session_key}_{ex_idx}_{q_idx}"
                ans = str(student_answers.get(q_key, "")).strip()
                if not ans:
                    all_answered = False
                    break
            if not all_answered:
                break

        total_questions_for_session = sum(len(ex.get("questions") or []) for ex in exercises)
        can_save_later = (
            str(exercise_data.get("source_type") or "") == "exam"
            and total_questions_for_session >= 8
        )

        action_cols = st.columns(2 if can_save_later else 1)
        with action_cols[0]:
            if st.button(
                f"✅ {t('check_answers')}",
                key=f"{session_key}_submit",
                use_container_width=True,
                type="primary",
            ):
                if not all_answered:
                    st.warning(t("answer_all_questions"))
                else:
                    st.session_state[submitted_key] = True
                    st.session_state[answers_key]   = student_answers
                    st.rerun()

        if can_save_later:
            with action_cols[1]:
                if st.button(
                    f"💾 {t('save_continue_later')}",
                    key=f"{session_key}_save_later",
                    use_container_width=True,
                ):
                    st.session_state[f"_practice_save_requested_{session_key}"] = True
                    st.session_state[answers_key] = student_answers
                    st.rerun()

        save_requested_key = f"_practice_save_requested_{session_key}"
        if st.session_state.pop(save_requested_key, False):
            draft_session_id = save_practice_draft(
                exercise_data,
                student_answers,
                meta=st.session_state.get("practice_meta") or {},
                session_key=session_key,
                session_id=st.session_state.get("_practice_resume_session_id"),
            )
            if draft_session_id:
                st.session_state["_practice_resume_session_id"] = draft_session_id
                st.session_state["practice_exercise_data"] = None
                st.session_state["practice_meta"] = None
                st.success(t("practice_saved_continue_later"))
                st.rerun()
            st.error(t("practice_save_failed"))
    else:
        pct = round(correct_q / total_q * 100) if total_q else 0
        xp  = calculate_session_xp(correct_q, total_q, best_streak)

        _render_score_card(correct_q, total_q, pct, xp, best_streak)

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                f"🔄 {t('try_again')}",
                key=f"{session_key}_retry",
                use_container_width=True,
            ):
                _clear_practice_widget_state(session_key)
                st.session_state.pop(answers_key, None)
                st.session_state.pop(submitted_key, None)
                st.session_state.pop(f"_practice_saved_{session_key}", None)
                st.session_state.pop("_practice_resume_session_id", None)
                st.session_state.pop("_practice_resume_answers", None)
                st.rerun()
        with col2:
            if st.button(
                f"✅ {t('finish')}",
                key=f"{session_key}_finish",
                use_container_width=True,
            ):
                _clear_practice_widget_state(session_key)
                st.session_state.pop(answers_key, None)
                st.session_state.pop(submitted_key, None)
                st.session_state.pop(f"_practice_saved_{session_key}", None)
                st.session_state.pop("practice_exercise_data", None)
                st.session_state.pop("practice_meta", None)
                st.session_state.pop("_practice_resume_session_id", None)
                st.session_state.pop("_practice_resume_answers", None)
                st.rerun()

        return {
            "total":       total_q,
            "correct":     correct_q,
            "score_pct":   pct,
            "best_streak": best_streak,
            "xp_earned":   xp,
            "answers":     student_answers,
        }

    return None


def _render_single_question(
    ex_type: str, question, correct, q_key: str, q_idx: int, is_submitted: bool,
    *, extra: dict | None = None,
) -> str:
    """Render one question and return the student's answer string."""
    prompt_text = _strip_leading_number(_question_prompt_text(ex_type, question))
    if ex_type == "vocabulary":
        prompt_text = _strip_vocab_answer_leak(
            prompt_text,
            correct=correct,
            options=(question.get("options") if isinstance(question, dict) else None),
        )

    if ex_type == "multiple_choice":
        stem = question.get("stem", "") if isinstance(question, dict) else str(question)
        options = question.get("options", []) if isinstance(question, dict) else []
        st.markdown(f"**{q_idx + 1}. {_strip_leading_number(stem)}**")
        choice = st.radio(
            "select",
            options=options,
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )
        return str(choice) if choice else ""

    elif ex_type == "true_false":
        st.markdown(f"**{q_idx + 1}. {prompt_text}**")
        choice = st.radio(
            "select",
            options=["true", "false"],
            index=None,
            format_func=lambda x: t("quick_exam_true_label") if x == "true" else t("quick_exam_false_label"),
            key=q_key,
            label_visibility="collapsed",
            horizontal=True,
            disabled=is_submitted,
        )
        return str(choice) if choice else ""

    elif ex_type == "matching":
        shuffled_options = (extra or {}).get("shuffled_options") or []
        st.markdown(f"**{q_idx + 1}. {_sentence_case_fragment(prompt_text)}**")
        choice = st.selectbox(
            "match",
            options=[""] + shuffled_options,
            format_func=_display_choice_text,
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )
        return str(choice) if choice else ""

    elif ex_type == "vocabulary" and isinstance(question, dict) and question.get("options"):
        st.markdown(f"**{q_idx + 1}. {prompt_text}**")
        choice = st.selectbox(
            "vocabulary",
            options=[""] + list(question.get("options") or []),
            format_func=_display_choice_text,
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )
        return str(choice) if choice else ""

    elif ex_type == "word_search_vocab":
        return _render_wordsearch_question(question, q_key, is_submitted)

    elif _is_long_response_type(ex_type):
        st.markdown(f"**{q_idx + 1}. {prompt_text}**")
        return st.text_area(
            "answer",
            key=q_key,
            height=120 if ex_type in ("writing_prompt", "show_your_work", "problem_solving") else 80,
            label_visibility="collapsed",
            disabled=is_submitted,
        )

    elif ex_type == "error_correction":
        st.markdown(f"**{q_idx + 1}. {t('correct_the_sentence_one_error')}:**")
        st.caption(f"✏️ *{prompt_text}*")
        return st.text_input(
            "corrected",
            key=q_key,
            placeholder=prompt_text,
            label_visibility="collapsed",
            disabled=is_submitted,
        )

    elif _is_short_text_type(ex_type):
        st.markdown(f"**{q_idx + 1}. {prompt_text}**")
        return st.text_input(
            "answer",
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )

    else:
        display = re.sub(r"_+", "______", prompt_text)
        st.markdown(f"**{q_idx + 1}. {display}**")
        return st.text_input(
            "answer",
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )


def _wordsearch_line_coords(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    sr, sc = start
    er, ec = end
    dr = er - sr
    dc = ec - sc
    step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
    step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
    if dr != 0 and dc != 0 and abs(dr) != abs(dc):
        return []
    if dr == 0 and dc == 0:
        return [(sr, sc)]
    length = max(abs(dr), abs(dc)) + 1
    return [(sr + idx * step_r, sc + idx * step_c) for idx in range(length)]


def _wordsearch_label_for_coord(coord: tuple[int, int]) -> str:
    row, col = coord
    return f"{chr(65 + col)}{row + 1}"


def _render_wordsearch_visual_grid(
    grid: list[list[str]],
    *,
    found_cells: set[tuple[int, int]],
    selected_cells: set[tuple[int, int]] | None = None,
) -> None:
    selected_cells = selected_cells or set()
    if not grid:
        st.warning(t("word_search_grid_failed"))
        return

    col_count = len(grid[0]) if grid else 0
    header_cells = "".join(
        f"<th>{html.escape(chr(65 + idx))}</th>"
        for idx in range(col_count)
    )

    body_rows = []
    for row_idx, row in enumerate(grid):
        cells = [f"<th>{row_idx + 1}</th>"]
        for col_idx, ch in enumerate(row):
            coord = (row_idx, col_idx)
            classes = []
            if coord in found_cells:
                classes.append("ws-found")
            elif coord in selected_cells:
                classes.append("ws-selected")
            class_attr = f" class='{' '.join(classes)}'" if classes else ""
            cells.append(f"<td{class_attr}>{html.escape(str(ch or ''))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <style>
        .ws-wordsearch-board-wrap {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 0.75rem 0 1rem 0;
            padding-bottom: 0.25rem;
        }}
        .ws-wordsearch-board {{
            border-collapse: separate;
            border-spacing: 6px;
            width: max-content;
            min-width: 100%;
            margin: 0 auto;
        }}
        .ws-wordsearch-board th,
        .ws-wordsearch-board td {{
            width: 2.55rem;
            min-width: 2.55rem;
            height: 2.55rem;
            text-align: center;
            vertical-align: middle;
            border-radius: 0.9rem;
            border: 1px solid rgba(203,213,225,.9);
            background: var(--panel, #fff);
            box-shadow: 0 1px 4px rgba(15,23,42,.06);
            font-weight: 800;
            font-size: 1rem;
            color: var(--text, #0f172a);
            font-family: "DejaVu Sans", "Noto Sans", "Arial Unicode MS", Arial, sans-serif;
        }}
        .ws-wordsearch-board th {{
            background: transparent;
            border: none;
            box-shadow: none;
            color: var(--muted, #64748b);
            font-size: 0.78rem;
            width: 1.7rem;
            min-width: 1.7rem;
            height: 1.7rem;
        }}
        .ws-wordsearch-board td.ws-found {{
            background: linear-gradient(135deg, rgba(16,185,129,.20), rgba(45,212,191,.16));
            border: 2px solid rgba(5,150,105,.85);
            color: #065f46;
        }}
        .ws-wordsearch-board td.ws-selected {{
            background: linear-gradient(135deg, rgba(59,130,246,.16), rgba(99,102,241,.14));
            border: 2px solid rgba(37,99,235,.75);
            color: var(--text, #0f172a);
        }}
        @media (max-width: 640px) {{
            .ws-wordsearch-board {{
                margin-left: 0;
                margin-right: 0;
            }}
            .ws-wordsearch-board th,
            .ws-wordsearch-board td {{
                width: 2.2rem;
                min-width: 2.2rem;
                height: 2.2rem;
                border-radius: 0.8rem;
                font-size: 0.95rem;
            }}
            .ws-wordsearch-board th {{
                width: 1.45rem;
                min-width: 1.45rem;
                height: 1.45rem;
                font-size: 0.74rem;
            }}
        }}
        </style>
        <div class="ws-wordsearch-board-wrap">
          <table class="ws-wordsearch-board">
            <thead>
              <tr><th></th>{header_cells}</tr>
            </thead>
            <tbody>
              {''.join(body_rows)}
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_wordsearch_question(question, q_key: str, is_submitted: bool) -> str:
    question = question or {}
    grid = question.get("grid") or []
    words = _normalize_wordsearch_words(question.get("words") or [])
    placements = question.get("placements") or []

    st.markdown(f"**{t('word_search_task_title')}**")
    st.caption(t("word_search_task_help"))

    if not grid or not words:
        st.warning(t("word_search_grid_failed"))
        return ""

    lookup: dict[tuple[tuple[int, int], ...], str] = {}
    for item in placements:
        coords = tuple(tuple(coord) for coord in item.get("coords") or [])
        word = re.sub(r"\s+", "", str(item.get("word") or "")).upper()
        if coords and word:
            lookup[coords] = word
            lookup[tuple(reversed(coords))] = word

    found_key = f"{q_key}__found"
    start_key = f"{q_key}__start"
    end_key = f"{q_key}__end"
    msg_key = f"{q_key}__msg"
    reset_key = f"{q_key}__reset_selection"

    if found_key not in st.session_state:
        st.session_state[found_key] = []
    if st.session_state.get(reset_key):
        st.session_state[start_key] = ""
        st.session_state[end_key] = ""
        st.session_state[reset_key] = False
    if start_key not in st.session_state:
        st.session_state[start_key] = ""
    if end_key not in st.session_state:
        st.session_state[end_key] = ""

    found_words = _normalize_wordsearch_words(st.session_state.get(found_key, []))
    start_label = str(st.session_state.get(start_key) or "")
    end_label = str(st.session_state.get(end_key) or "")

    found_cells = set()
    for coords, word in lookup.items():
        if word in found_words:
            found_cells.update(coords)

    status_msg = str(st.session_state.get(msg_key) or "").strip()
    if status_msg:
        st.caption(status_msg)
        st.session_state[msg_key] = ""

    found_count = len(set(found_words) & set(words))
    st.progress(found_count / len(words) if words else 0.0)
    st.caption(t("word_search_feedback_progress", found=found_count, total=len(words)))

    chips = []
    found_set = set(found_words)
    for word in words:
        done = word in found_set
        bg = "rgba(16,185,129,.18)" if done else "rgba(148,163,184,.14)"
        fg = "#047857" if done else "var(--text)"
        mark = "✓ " if done else ""
        chips.append(
            f"<span style='display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;"
            f"background:{bg};color:{fg};font-size:0.8rem;font-weight:800;border:1px solid rgba(148,163,184,.24);"
            f"margin:0 8px 8px 0;'>{mark}{word}</span>"
        )
    st.markdown("".join(chips), unsafe_allow_html=True)

    label_to_coord = {
        _wordsearch_label_for_coord((r, c)): (r, c)
        for r in range(len(grid))
        for c in range(len(grid[r]))
    }
    coord_options = [""] + list(label_to_coord.keys())

    selected_cells = set()
    if start_label in label_to_coord:
        selected_cells.add(label_to_coord[start_label])
    if start_label in label_to_coord and end_label in label_to_coord:
        selected_cells.update(_wordsearch_line_coords(label_to_coord[start_label], label_to_coord[end_label]))

    _render_wordsearch_visual_grid(
        grid,
        found_cells=found_cells,
        selected_cells=selected_cells,
    )

    picker_col1, picker_col2 = st.columns(2)
    with picker_col1:
        st.selectbox(
            t("word_search_start_cell"),
            options=coord_options,
            key=start_key,
            disabled=is_submitted,
        )
    with picker_col2:
        st.selectbox(
            t("word_search_end_cell"),
            options=coord_options,
            key=end_key,
            disabled=is_submitted,
        )

    action_col1, action_col2 = st.columns([3, 1])
    with action_col1:
        if start_label and end_label:
            st.caption(t("word_search_selected_range", start=start_label, end=end_label))
        elif start_label:
            st.caption(t("word_search_selected_cell", cell=start_label))
        else:
            st.caption(t("word_search_select_first_cell"))
    with action_col2:
        if st.button(
            t("word_search_clear_selection"),
            key=f"{q_key}_clear_selection",
            use_container_width=True,
            disabled=is_submitted or (not start_label and not end_label),
        ):
            st.session_state[reset_key] = True
            st.rerun()

    if (
        st.button(
            t("word_search_check_selection"),
            key=f"{q_key}_check_selection",
            use_container_width=True,
            disabled=is_submitted or not start_label or not end_label,
        )
        and not is_submitted
    ):
        start = label_to_coord.get(start_label)
        end = label_to_coord.get(end_label)
        coords = tuple(_wordsearch_line_coords(start, end)) if start and end else ()
        matched_word = lookup.get(coords, "")
        if matched_word and matched_word not in found_set:
            st.session_state[found_key] = sorted(found_set | {matched_word})
            st.session_state[msg_key] = t("word_search_found_word", word=matched_word)
        elif matched_word:
            st.session_state[msg_key] = t("word_search_word_already_found", word=matched_word)
        else:
            st.session_state[msg_key] = t("word_search_try_again")
        st.session_state[reset_key] = True
        st.rerun()

    return json.dumps(found_words)


# ════════════════════════════════════════════════════════════════
#  D. ANSWER CHECKING
# ════════════════════════════════════════════════════════════════

def _check_answer(ex_type: str, student: str, correct) -> bool:
    """Compare student answer to correct answer. Returns True if correct."""
    s = _normalize_answer(student)
    if not s:
        return False

    if ex_type == "true_false":
        s = _canonical_true_false(student)
        c = _canonical_true_false(_comparison_answer_text(correct))
    else:
        c = _normalize_answer(_comparison_answer_text(correct))

    if not c:
        return False

    if ex_type in ("multiple_choice", "true_false", "matching"):
        return s == c

    if ex_type == "error_correction":
        student_exact = _normalize_error_correction_answer(student)
        correct_exact = _normalize_error_correction_answer(_comparison_answer_text(correct))
        if not correct_exact:
            return False
        return student_exact == correct_exact

    # Flexible text comparison for fill-in, matching, vocabulary, etc.
    if s == c:
        return True

    # Check if student answer is contained in correct (handles extra words)
    if c in s or s in c:
        return True

    # Word-overlap scoring for short_answer / reading_comprehension / open types
    # Accept if ≥55% of the key words from the correct answer appear in the
    # student response. This handles paraphrasing, quoting from a passage, etc.
    c_words = _answer_words(c)
    if c_words:
        s_words = _answer_words(s)
        overlap = len(c_words & s_words)
        if overlap / len(c_words) >= 0.55:
            return True

    return False


# ════════════════════════════════════════════════════════════════
#  E. SCORE CARD
# ════════════════════════════════════════════════════════════════

def _render_score_card(correct: int, total: int, pct: int,
                       xp_earned: int = 0, best_streak: int = 0) -> None:
    """Show a gamified score summary card with XP + streak info."""
    if pct >= 80:
        color = "#10B981"
        emoji = "🌟"
        msg = t("excellent_score")
    elif pct >= 60:
        color = "#F59E0B"
        emoji = "👍"
        msg = t("good_score")
    else:
        color = "#EF4444"
        emoji = "💪"
        msg = t("keep_practicing")

    streak_html = ""
    if best_streak >= 2:
        streak_html = f'<div style="font-size:0.85rem;color:var(--muted);margin-top:6px;">🔥 {t("best_streak")}: <strong>{best_streak}</strong></div>'

    xp_html = ""
    if xp_earned > 0:
        xp_html = f'<div style="display:inline-block;background:linear-gradient(135deg,#8B5CF6,#6D28D9);color:#fff;font-weight:800;font-size:0.9rem;padding:6px 16px;border-radius:20px;margin-top:10px;">+{xp_earned} XP</div>'

    perfect_html = ""
    if pct == 100 and total > 0:
        perfect_html = f'<div style="font-size:0.78rem;color:#10B981;font-weight:700;margin-top:6px;">🎯 {t("perfect_score_bonus")}</div>'

    st.markdown(
        f"""<div style="
background: linear-gradient(135deg, {color}15, {color}08);
border: 2px solid {color};
border-radius: 16px;
padding: 24px;
text-align: center;
margin: 16px 0;
animation: fadeIn 0.4s ease-out;
">
<div style="font-size: 2.5rem;">{emoji}</div>
<div style="font-size: 1.8rem; font-weight: 800; color: {color}; margin: 8px 0;">{pct}%</div>
<div style="font-size: 1rem; font-weight: 600; color: var(--text);">{msg}</div>
<div style="font-size: 0.85rem; color: var(--muted); margin-top: 4px;">{correct}/{total} {t("questions_correct")}</div>
{streak_html}
{perfect_html}
{xp_html}
</div>
<style>
@keyframes fadeIn {{
from {{ opacity: 0; transform: translateY(12px); }}
to   {{ opacity: 1; transform: translateY(0); }}
}}
</style>""",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════
#  F. SUPABASE PERSISTENCE
# ════════════════════════════════════════════════════════════════

def save_practice_session(
    exercise_data: dict,
    total: int,
    correct: int,
    score_pct: float,
    xp_earned: int = 0,
    best_streak: int = 0,
    status: str = "completed",
    meta: dict | None = None,
) -> int | None:
    """Save a completed practice session. Returns session id or None."""
    meta = meta or {}
    uid = get_current_user_id()
    if not uid:
        return None
    try:
        now = _dt.now(timezone.utc).isoformat()
        payload = {
            "user_id": uid,
            "owner_id": uid,
            "source_type": str(exercise_data.get("source_type") or "custom"),
            "source_id": exercise_data.get("source_id"),
            "title": str(exercise_data.get("title") or ""),
            "subject": str(meta.get("subject") or ""),
            "topic": str(meta.get("topic") or ""),
            "learner_stage": str(meta.get("learner_stage") or ""),
            "level": str(meta.get("level") or ""),
            "exercise_data": exercise_data,
            "total_questions": total,
            "correct_count": correct,
            "score_pct": round(score_pct, 1),
            "xp_earned": xp_earned,
            "best_streak": best_streak,
            "status": status,
            "started_at": now,
            "completed_at": now if status == "completed" else None,
            "created_at": now,
        }
        res = get_sb().table("practice_sessions").insert(payload).execute()
        clear_app_caches()
        rows = res.data or []
        return rows[0]["id"] if rows else None
    except Exception as e:
        # Retry without columns that may not exist yet
        err_str = str(e)
        retry_payload = dict(payload)
        if "owner_id" in err_str:
            retry_payload.pop("owner_id", None)
        if "best_streak" in err_str or "xp_earned" in err_str:
            retry_payload.pop("xp_earned", None)
            retry_payload.pop("best_streak", None)
        if retry_payload != payload:
            try:
                res = get_sb().table("practice_sessions").insert(retry_payload).execute()
                clear_app_caches()
                rows = res.data or []
                return rows[0]["id"] if rows else None
            except Exception as e2:
                st.warning(f"Could not save practice session: {e2}")
                return None
        st.warning(f"Could not save practice session: {e}")
        return None


def save_practice_answers(
    session_id: int,
    exercise_data: dict,
    student_answers: dict,
    session_key: str = "practice",
    *,
    replace_existing: bool = False,
) -> None:
    """Save individual answers for a session."""
    uid = get_current_user_id()
    if not uid or not session_id:
        return

    exercises = exercise_data.get("exercises") or []
    rows = []

    for ex_idx, exercise in enumerate(exercises):
        correct_answers = exercise.get("answers") or []
        questions = exercise.get("questions") or []
        ex_type = exercise.get("type", "")

        for q_idx in range(len(questions)):
            q_key = f"{session_key}_{ex_idx}_{q_idx}"
            student_ans = str(student_answers.get(q_key, ""))
            correct_ans = correct_answers[q_idx] if q_idx < len(correct_answers) else ""
            correct_str = _display_answer_text(correct_ans)
            is_correct = _evaluate_answer(ex_type, student_ans, correct_ans)["is_correct"]

            rows.append({
                "session_id": session_id,
                "user_id": uid,
                "exercise_idx": ex_idx,
                "question_idx": q_idx,
                "exercise_type": ex_type,
                "student_answer": student_ans,
                "correct_answer": correct_str,
                "is_correct": is_correct,
                "answered_at": _dt.now(timezone.utc).isoformat(),
            })

    if rows:
        try:
            if replace_existing:
                get_sb().table("practice_answers").delete().eq("session_id", session_id).eq("user_id", uid).execute()
            get_sb().table("practice_answers").insert(rows).execute()
        except Exception as e:
            if "owner_id" in str(e):
                for r in rows:
                    r.pop("owner_id", None)
                try:
                    if replace_existing:
                        get_sb().table("practice_answers").delete().eq("session_id", session_id).eq("user_id", uid).execute()
                    get_sb().table("practice_answers").insert(rows).execute()
                except Exception:
                    pass
            # else silently skip


def save_practice_draft(
    exercise_data: dict,
    student_answers: dict,
    *,
    meta: dict | None = None,
    session_key: str = "practice",
    session_id: int | None = None,
) -> int | None:
    uid = get_current_user_id()
    if not uid:
        return None

    meta = meta or {}
    total_questions = 0
    for exercise in exercise_data.get("exercises") or []:
        total_questions += len(exercise.get("questions") or [])

    now = _dt.now(timezone.utc).isoformat()
    payload = {
        "user_id": uid,
        "owner_id": uid,
        "source_type": str(exercise_data.get("source_type") or "custom"),
        "source_id": exercise_data.get("source_id"),
        "title": str(exercise_data.get("title") or ""),
        "subject": str(meta.get("subject") or ""),
        "topic": str(meta.get("topic") or ""),
        "learner_stage": str(meta.get("learner_stage") or ""),
        "level": str(meta.get("level") or ""),
        "exercise_data": exercise_data,
        "total_questions": total_questions,
        "correct_count": 0,
        "score_pct": 0,
        "xp_earned": 0,
        "best_streak": 0,
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "created_at": now,
    }

    try:
        if session_id:
            update_payload = dict(payload)
            update_payload.pop("user_id", None)
            update_payload.pop("owner_id", None)
            update_payload.pop("created_at", None)
            get_sb().table("practice_sessions").update(update_payload).eq("id", session_id).eq("user_id", uid).execute()
            saved_session_id = session_id
        else:
            try:
                res = get_sb().table("practice_sessions").insert(payload).execute()
            except Exception as e:
                retry_payload = dict(payload)
                if "owner_id" in str(e):
                    retry_payload.pop("owner_id", None)
                res = get_sb().table("practice_sessions").insert(retry_payload).execute()
            rows = res.data or []
            saved_session_id = rows[0]["id"] if rows else None

        if saved_session_id:
            save_practice_answers(
                saved_session_id,
                exercise_data,
                student_answers,
                session_key=session_key,
                replace_existing=True,
            )
            clear_app_caches()
        return saved_session_id
    except Exception:
        return None


def update_practice_progress(
    exercise_data: dict,
    student_answers: dict,
    meta: dict | None = None,
    session_key: str = "practice",
    xp_earned: int = 0,
    best_streak: int = 0,
) -> None:
    """Upsert progress aggregates per subject/topic/type, including XP."""
    uid = get_current_user_id()
    if not uid:
        return

    meta = meta or {}
    subject = str(meta.get("subject") or "")
    topic   = str(meta.get("topic") or "")
    level   = str(meta.get("level") or "")

    # Aggregate by exercise type
    type_stats: dict[str, dict] = {}
    exercises = exercise_data.get("exercises") or []

    for ex_idx, exercise in enumerate(exercises):
        ex_type = exercise.get("type", "unknown")
        correct_answers = exercise.get("answers") or []
        questions = exercise.get("questions") or []

        if ex_type not in type_stats:
            type_stats[ex_type] = {"attempted": 0, "correct": 0}

        for q_idx in range(len(questions)):
            q_key = f"{session_key}_{ex_idx}_{q_idx}"
            student_ans = str(student_answers.get(q_key, ""))
            correct_ans = correct_answers[q_idx] if q_idx < len(correct_answers) else ""
            is_right = _evaluate_answer(ex_type, student_ans, correct_ans)["is_correct"]

            type_stats[ex_type]["attempted"] += 1
            if is_right:
                type_stats[ex_type]["correct"] += 1

    # Distribute XP proportionally across types
    total_correct = sum(s["correct"] for s in type_stats.values())
    sb = get_sb()

    for ex_type, stats in type_stats.items():
        type_xp = 0
        if xp_earned and total_correct:
            type_xp = round(xp_earned * stats["correct"] / total_correct)
        elif xp_earned and not total_correct:
            type_xp = round(xp_earned / len(type_stats))

        try:
            existing = (
                sb.table("practice_progress")
                .select("*")
                .eq("user_id", uid)
                .eq("subject", subject)
                .eq("topic", topic)
                .eq("exercise_type", ex_type)
                .eq("level", level)
                .execute()
            )
            rows = existing.data or []

            now = _dt.now(timezone.utc).isoformat()
            if rows:
                row = rows[0]
                new_attempted = row["total_attempted"] + stats["attempted"]
                new_correct   = row["total_correct"]   + stats["correct"]
                new_pct = round(new_correct / new_attempted * 100, 1) if new_attempted else 0
                update_data = {
                    "total_attempted": new_attempted,
                    "total_correct":   new_correct,
                    "accuracy_pct":    new_pct,
                    "last_practiced":  now,
                }
                # Include gamification fields only if the column exists
                if "total_xp" in row:
                    update_data["total_xp"] = (row.get("total_xp") or 0) + type_xp
                if "best_streak" in row:
                    update_data["best_streak"] = max(row.get("best_streak") or 0, best_streak)
                sb.table("practice_progress").update(update_data).eq("id", row["id"]).execute()
            else:
                pct = round(stats["correct"] / stats["attempted"] * 100, 1) if stats["attempted"] else 0
                insert_data = {
                    "user_id":         uid,
                    "owner_id":        uid,
                    "subject":         subject,
                    "topic":           topic,
                    "exercise_type":   ex_type,
                    "level":           level,
                    "total_attempted": stats["attempted"],
                    "total_correct":   stats["correct"],
                    "accuracy_pct":    pct,
                    "total_xp":        type_xp,
                    "best_streak":     best_streak,
                    "last_practiced":  now,
                    "created_at":      now,
                }
                try:
                    sb.table("practice_progress").insert(insert_data).execute()
                except Exception as ins_err:
                    # Retry without columns that may not exist
                    err_str = str(ins_err)
                    if "owner_id" in err_str:
                        insert_data.pop("owner_id", None)
                    if "total_xp" in err_str or "best_streak" in err_str:
                        insert_data.pop("total_xp", None)
                        insert_data.pop("best_streak", None)
                    try:
                        sb.table("practice_progress").insert(insert_data).execute()
                    except Exception:
                        pass
        except Exception:
            pass

    clear_app_caches()


def load_practice_history(limit: int = 50) -> pd.DataFrame:
    """Load the current user's recent practice sessions."""
    try:
        df = load_table("practice_sessions")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if "status" in df.columns:
            df = df[df["status"].fillna("completed").astype(str) == "completed"].copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            df = df.sort_values("created_at", ascending=False)
        return df.head(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def load_in_progress_practice_session(source_type: str, source_id: int | None) -> dict:
    uid = get_current_user_id()
    if not uid or source_id is None:
        return {}
    try:
        res = (
            get_sb()
            .table("practice_sessions")
            .select("*")
            .eq("user_id", uid)
            .eq("source_type", str(source_type or ""))
            .eq("source_id", source_id)
            .eq("status", "in_progress")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def load_practice_draft_answers(session_id: int) -> dict[str, str]:
    uid = get_current_user_id()
    if not uid or not session_id:
        return {}
    try:
        res = (
            get_sb()
            .table("practice_answers")
            .select("exercise_idx, question_idx, student_answer")
            .eq("session_id", session_id)
            .eq("user_id", uid)
            .execute()
        )
        rows = res.data or []
        return {
            f"sp_{int(row.get('exercise_idx') or 0)}_{int(row.get('question_idx') or 0)}": str(row.get("student_answer") or "")
            for row in rows
        }
    except Exception:
        return {}


def get_completed_source_ids() -> dict[str, set]:
    """Return sets of source_ids the user has already practised, keyed by source_type."""
    history = load_practice_history(limit=500)
    result: dict[str, set] = {"worksheet": set(), "exam": set()}
    if history.empty:
        return result
    for _, row in history.iterrows():
        src_type = str(row.get("source_type") or "").strip()
        src_id = row.get("source_id")
        if src_type in result and src_id is not None:
            result[src_type].add(src_id)
    return result


def update_practice_session(
    session_id: int,
    exercise_data: dict,
    total: int,
    correct: int,
    score_pct: float,
    xp_earned: int = 0,
    best_streak: int = 0,
) -> bool:
    """Update an existing practice session with new results. Returns True on success."""
    uid = get_current_user_id()
    if not uid or not session_id:
        return False
    try:
        now = _dt.now(timezone.utc).isoformat()
        payload = {
            "total_questions": total,
            "correct_count": correct,
            "score_pct": round(score_pct, 1),
            "xp_earned": xp_earned,
            "best_streak": best_streak,
            "status": "completed",
            "completed_at": now,
        }
        get_sb().table("practice_sessions").update(payload).eq("id", session_id).eq("user_id", uid).execute()
        clear_app_caches()
        return True
    except Exception:
        return False


def load_practice_progress() -> pd.DataFrame:
    """Load the current user's practice progress aggregates."""
    try:
        df = load_table("practice_progress")
        if df is None or df.empty:
            return pd.DataFrame()
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def get_total_xp() -> int:
    """Sum total XP across all practice_progress rows for the current user."""
    df = load_practice_progress()
    if df.empty or "total_xp" not in df.columns:
        return 0
    return int(df["total_xp"].sum())


def get_global_best_streak() -> int:
    """Best streak ever achieved across all progress rows."""
    df = load_practice_progress()
    if df.empty or "best_streak" not in df.columns:
        return 0
    return int(df["best_streak"].max())
