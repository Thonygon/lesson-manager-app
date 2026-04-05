# CLASSIO — Smart Practice Engine  (Phase 1)
# ============================================================
# Converts worksheets / exams into a unified exercise schema,
# renders interactive Streamlit widgets, checks answers,
# tracks XP / streaks / ranks, and persists to Supabase.
#
# Phase 1 exercise types: multiple_choice, true_false, fill_in_blank
# ============================================================
from __future__ import annotations

import re
import json
import streamlit as st
import pandas as pd
from datetime import datetime as _dt, timezone
from typing import Optional

from core.i18n import t
from core.state import get_current_user_id, with_owner
from core.database import get_sb, load_table, clear_app_caches


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
#  A. UNIFIED EXERCISE SCHEMA  (Phase 1)
# ════════════════════════════════════════════════════════════════
#
# {
#   "title": str,
#   "instructions": str,
#   "source_type": "worksheet" | "exam",
#   "source_id": int | None,
#   "exercises": [
#     {
#       "type": "multiple_choice" | "true_false" | "fill_in_blank",
#       "title": str,
#       "instructions": str,
#       "source_text": str,          # optional reading passage
#       "questions": [ ... ],        # shape depends on type
#       "answers":   [ ... ],        # one per question
#     }
#   ]
# }
# ════════════════════════════════════════════════════════════════

PHASE1_TYPES = {
    "multiple_choice", "true_false", "fill_in_blank", "fill_in_the_blanks",
    "short_answer", "matching", "reading_comprehension", "error_correction",
}


# ── B. Converters ────────────────────────────────────────────────

def worksheet_to_exercises(ws: dict, *, row_id: int | None = None) -> dict:
    """Convert a saved worksheet dict into the unified exercise schema."""
    ws_type = str(ws.get("worksheet_type") or "").strip()
    title = str(ws.get("title") or "").strip()
    instructions = str(ws.get("instructions") or "").strip()

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
                "questions": questions,
                "answers": answers,
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
    exercises: list[dict] = []

    sections = exam_data.get("sections") or []
    ak_sections = (answer_key or {}).get("sections") or []

    for idx, sec in enumerate(sections):
        sec_type = str(sec.get("type") or "").strip()
        # Phase 1: skip non-supported section types
        if sec_type not in PHASE1_TYPES:
            continue
        # Normalise fill_in_the_blanks → fill_in_blank
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


# ── helpers ──────────────────────────────────────────────────────────

def _parse_flat_answer_key(raw, n: int) -> list[str]:
    """Parse a worksheet answer_key (string or list) into a list of n answers."""
    if isinstance(raw, list):
        return [str(a).strip() for a in raw][:n]
    if not raw:
        return [""] * n
    text = str(raw).strip()

    # Strategy 1: split by newlines first
    lines = re.split(r"\n+", text)
    answers: list[str] = []

    if len(lines) >= n:
        # Multi-line format: "1. True\n2. False\n…"
        for ln in lines:
            cleaned = re.sub(r"^[A-Za-z0-9]+[\.)\-]\s*", "", ln).strip()
            if cleaned:
                answers.append(cleaned)
    else:
        # Single-line format: "1. True 2. False 3. True …"
        # Split on number prefixes like "2." "3)" etc.
        parts = re.split(r"(?:^|\s+)(?=\d+[\.)\-]\s)", text)
        for p in parts:
            cleaned = re.sub(r"^[A-Za-z0-9]+[\.)\-]\s*", "", p).strip()
            if cleaned:
                answers.append(cleaned)

    # pad to n
    while len(answers) < n:
        answers.append("")
    return answers[:n]


def _normalize_answer(s: str) -> str:
    """Normalize an answer for comparison: lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _strip_leading_number(text: str) -> str:
    """Remove leading numbering like '1. ', '2) ', '3- ', 'A. ', 'B) ' from text."""
    return re.sub(r"^[A-Za-z0-9]+[\.\)\-]\s*", "", text.strip())


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
        if source_txt:
            with st.expander("📖 " + t("reading_passage"), expanded=True):
                st.write(source_txt)

        # For matching: build a shuffled list of right-side options (stable per session)
        extra = {}
        if ex_type == "matching":
            shuffle_key = f"_matching_shuffle_{session_key}_{ex_idx}"
            if shuffle_key not in st.session_state:
                import random as _rnd
                opts = list(correct_answers)
                _rnd.shuffle(opts)
                st.session_state[shuffle_key] = opts
            extra["shuffled_options"] = st.session_state[shuffle_key]

        for q_idx, question in enumerate(questions):
            q_key   = f"{session_key}_{ex_idx}_{q_idx}"
            correct = correct_answers[q_idx] if q_idx < len(correct_answers) else ""
            total_q += 1

            student_ans = _render_single_question(
                ex_type, question, correct, q_key, q_idx, is_submitted,
                extra=extra,
            )
            student_answers[q_key] = student_ans

            if is_submitted and correct:
                is_right = _check_answer(ex_type, student_ans, correct)
                if is_right:
                    correct_q  += 1
                    cur_streak += 1
                    best_streak = max(best_streak, cur_streak)
                    st.success(f"✓ {t('correct')}")
                else:
                    cur_streak = 0
                    expected = correct if isinstance(correct, str) else str(correct)
                    st.error(f"✗ {t('incorrect')} — {expected}")

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
                st.session_state.pop(answers_key, None)
                st.session_state.pop(submitted_key, None)
                st.session_state.pop(f"_practice_saved_{session_key}", None)
                st.rerun()
        with col2:
            if st.button(
                f"✅ {t('finish')}",
                key=f"{session_key}_finish",
                use_container_width=True,
            ):
                st.session_state.pop(answers_key, None)
                st.session_state.pop(submitted_key, None)
                st.session_state.pop(f"_practice_saved_{session_key}", None)
                st.session_state.pop("practice_exercise_data", None)
                st.session_state.pop("practice_meta", None)
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
        text = question.get("text", str(question)) if isinstance(question, dict) else str(question)
        st.markdown(f"**{q_idx + 1}. {_strip_leading_number(text)}**")
        choice = st.radio(
            "select",
            options=["True", "False"],
            key=q_key,
            label_visibility="collapsed",
            horizontal=True,
            disabled=is_submitted,
        )
        return str(choice) if choice else ""

    elif ex_type == "matching":
        left = question.get("left", "") if isinstance(question, dict) else str(question)
        shuffled_options = (extra or {}).get("shuffled_options") or []
        st.markdown(f"**{q_idx + 1}. {_strip_leading_number(left)}**")
        choice = st.selectbox(
            "match",
            options=[""] + shuffled_options,
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )
        return str(choice) if choice else ""

    elif ex_type == "short_answer":
        text = question.get("text", str(question)) if isinstance(question, dict) else str(question)
        st.markdown(f"**{q_idx + 1}. {_strip_leading_number(text)}**")
        return st.text_area(
            "answer",
            key=q_key,
            height=80,
            label_visibility="collapsed",
            disabled=is_submitted,
        )

    elif ex_type == "reading_comprehension":
        text = question.get("text", str(question)) if isinstance(question, dict) else str(question)
        st.markdown(f"**{q_idx + 1}. {_strip_leading_number(text)}**")
        return st.text_area(
            "answer",
            key=q_key,
            height=80,
            label_visibility="collapsed",
            disabled=is_submitted,
        )

    elif ex_type == "error_correction":
        text = question.get("text", str(question)) if isinstance(question, dict) else str(question)
        st.markdown(f"**{q_idx + 1}. {t('correct_the_sentence')}:**")
        st.caption(f"✏️ *{_strip_leading_number(text)}*")
        return st.text_input(
            "corrected",
            key=q_key,
            placeholder=_strip_leading_number(text),
            label_visibility="collapsed",
            disabled=is_submitted,
        )

    else:
        # fill_in_blank / fill_in_the_blanks
        text = question.get("text", str(question)) if isinstance(question, dict) else str(question)
        display = re.sub(r"_+", "______", _strip_leading_number(text))
        st.markdown(f"**{q_idx + 1}. {display}**")
        return st.text_input(
            "answer",
            key=q_key,
            label_visibility="collapsed",
            disabled=is_submitted,
        )


# ════════════════════════════════════════════════════════════════
#  D. ANSWER CHECKING
# ════════════════════════════════════════════════════════════════

def _check_answer(ex_type: str, student: str, correct) -> bool:
    """Compare student answer to correct answer. Returns True if correct."""
    s = _normalize_answer(student)
    if not s:
        return False

    if isinstance(correct, dict):
        c = _normalize_answer(correct.get("answer", correct.get("text", str(correct))))
    else:
        c = _normalize_answer(str(correct))

    if not c:
        return False

    # Exact types
    if ex_type in ("multiple_choice", "true_false", "matching"):
        return s == c

    # Flexible text comparison for fill-in, matching, vocabulary, etc.
    if s == c:
        return True

    # Check if student answer is contained in correct (handles extra words)
    if c in s or s in c:
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
            correct_str = correct_ans if isinstance(correct_ans, str) else str(correct_ans)
            is_correct = _check_answer(ex_type, student_ans, correct_ans)

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
            get_sb().table("practice_answers").insert(rows).execute()
        except Exception as e:
            if "owner_id" in str(e):
                for r in rows:
                    r.pop("owner_id", None)
                try:
                    get_sb().table("practice_answers").insert(rows).execute()
                except Exception:
                    pass
            # else silently skip


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
            is_right = _check_answer(ex_type, student_ans, correct_ans)

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
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            df = df.sort_values("created_at", ascending=False)
        return df.head(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


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
